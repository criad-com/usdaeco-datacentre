"""Finite planar-face probes of the three published comparison bodies, in metres.

This fixture-specific check uses actual triangles and world transforms. Exact
distances are analytic source-sweep facts, not execution of an exact-body engine.
"""
from collections import Counter
import hashlib
import json
import math
import uuid

import numpy as np

from .. import ids

PRECISION = 1e-7  # round measured bounds outward to 0.1 micrometre


def body(stage, name):
    import ifcopenshell.guid
    from pxr import Usd, UsdGeom
    identity = str(uuid.UUID(ifcopenshell.guid.expand(ids.guid(name))))
    elements = [p for p in stage.Traverse() if p.GetAttribute("aeco:id").Get() == identity]
    if len(elements) != 1:
        raise ValueError(f"Expected one element: {name}")
    meshes = [p for p in Usd.PrimRange(elements[0]) if p.IsA(UsdGeom.Mesh)
              and p.GetAttribute("aeco:derived:role").Get() == "body"]
    if len(meshes) != 1:
        raise ValueError(f"Expected one body: {name}")
    mesh = UsdGeom.Mesh(meshes[0])
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(mesh.GetPrim())
    points = np.array([matrix.Transform(p) for p in mesh.GetPointsAttr().Get()])
    counts = list(mesh.GetFaceVertexCountsAttr().Get())
    indices = np.array(mesh.GetFaceVertexIndicesAttr().Get())
    if not counts or set(counts) != {3} or len(indices) != 3*len(counts):
        raise ValueError(f"Expected triangle body: {name}")
    faces = indices.reshape(-1, 3)
    edges = Counter(tuple(sorted((int(a), int(b)))) for f in faces for a, b in zip(f, np.roll(f, -1)))
    if set(edges.values()) != {2} or set(indices) != set(range(len(points))):
        raise ValueError(f"Expected closed manifold body: {name}")
    triangles = points[faces]
    if not np.isfinite(points).all() or np.any(np.linalg.norm(np.cross(
            triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]), axis=1) < 1e-12):
        raise ValueError(f"Invalid body triangles: {name}")
    return mesh, points, triangles


def radial_error(points, case):
    """Maximum radial deviation of serialized ring vertices AND chord interiors."""
    start, end = np.array(case["axis"], dtype=float)
    direction = end-start
    length = np.linalg.norm(direction)
    direction /= length
    axial = (points-start) @ direction
    if np.max(np.minimum(abs(axial), abs(axial-length))) > 2e-6:
        raise ValueError("Pipe points no longer form the source sweep's two end rings")
    errors, sides = [], []
    for cap in (0., length):
        ring = points[abs(axial-cap) < 2e-6] - (start + cap*direction)
        if len(ring) < 3:
            raise ValueError("Pipe ring missing")
        u = ring[0] / np.linalg.norm(ring[0])
        v = np.cross(direction, u)
        ring = ring[np.argsort(np.arctan2(ring @ v, ring @ u))]
        ends = np.roll(ring, -1, axis=0)
        edges = ends-ring
        t = np.clip(-np.sum(ring*edges, axis=1)/np.sum(edges*edges, axis=1), 0, 1)
        distances = np.r_[np.linalg.norm(ring, axis=1), np.linalg.norm(ring+t[:, None]*edges, axis=1)]
        errors.extend(abs(distances-case["od"]/2))
        sides.append(len(ring))
    if sides[0] != sides[1] or sum(sides) != len(points):
        raise ValueError("Pipe rings differ")
    return math.ceil(max(errors)/PRECISION)*PRECISION, sides[0]


def on_face(point, triangles, dimension, coordinate):
    """The projected witness must lie on a published finite triangle, not an AABB."""
    faces = triangles[np.all(abs(triangles[:, :, dimension]-coordinate) < 2e-6, axis=1)]
    p = point.copy()
    p[dimension] = coordinate
    for a, b, c in faces:
        v0, v1, v2 = b-a, c-a, p-a
        aa, bb, ab = v0@v0, v1@v1, v0@v1
        den = aa*bb-ab*ab
        u = (bb*(v2@v0)-ab*(v2@v1))/den
        v = (aa*(v2@v1)-ab*(v2@v0))/den
        if u >= -1e-8 and v >= -1e-8 and u+v <= 1+1e-8:
            return True
    return False


def hard_fingerprint(stage):
    from pxr import UsdGeom
    mesh, _, _ = body(stage, "pipe.clash.hard")
    values = dict(points=str(mesh.GetPointsAttr().Get()), counts=str(mesh.GetFaceVertexCountsAttr().Get()),
                  indices=str(mesh.GetFaceVertexIndicesAttr().Get()),
                  transform=str(UsdGeom.XformCache().GetLocalToWorldTransform(mesh.GetPrim())))
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def measure_cases(stage, cases, policies, *, stamp=False, stamp_layer=None):
    """Return measured receipts and fail if geometry, stamps or expectations drift."""
    from pxr import Sdf, Usd
    rows = []
    for case in cases:
        name = case["id"]
        mesh, points, _ = body(stage, name)
        partner, other, triangles = body(stage, case["partner"])
        band, sides = radial_error(points, case)
        # Partners are planar prisms: verify all facets are axis-aligned before
        # assigning zero chordal error (float coordinate error is checked below).
        normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        if not np.all(np.max(abs(normals), axis=1) > 1-1e-9):
            raise ValueError("Comparison partner is no longer an orthogonal planar body")
        for prim, error in ((mesh.GetPrim(), band), (partner.GetPrim(), 0.)):
            for key in ("aeco:body:tolerance", "aeco:derived:tolerance"):
                if stamp:
                    with Usd.EditContext(stage, stamp_layer(prim) if stamp_layer else stage.GetEditTarget()):
                        attr = prim.CreateAttribute(key, Sdf.ValueTypeNames.Double, custom=False)
                        attr.SetMetadata("aecoDerived", True)
                        attr.Set(error)
                value = prim.GetAttribute(key).Get()
                if value is None or not math.isfinite(value) or abs(value-error) > 1e-12:
                    raise ValueError(f"Measured deflection differs from {key}: {name}")
        policy = policies.get(name)
        if policy and band > policy["deflection"]:
            raise ValueError(f"Requested tessellation bound exceeded: {name}")
        if name.endswith("near"):
            dimension = 2
            face = other[:, dimension].max()
            exact = case["axis"][0][2]-case["od"]/2-case["tray_top"]
            if abs(face-case["tray_top"]) > 2e-6:
                raise ValueError("Published tray face differs from source")
        else:
            dimension = 1
            face = other[:, dimension].max()
            plane = case["wall_face_plane"]
            if abs(face-plane["offset"]) > 2e-6 or abs(np.ptp(other[:, 1])-plane["thickness"]) > 2e-6:
                raise ValueError("Published wall faces differ from source")
            exact = case["axis"][0][1]-case["od"]/2-plane["offset"]
        if name.endswith("hard"):
            witness = points.mean(axis=0)
            back = other[:, 1].min()
            if not (back < witness[1] < face and on_face(witness, triangles, 1, back)):
                raise ValueError("Hard crossing lacks an interior wall witness")
            distance = -min(face-witness[1], witness[1]-back)
            verdict = "hard" if distance < -band else "undecidable"
            exact_verdict, exact = "hard", None
        else:
            witness = points[np.argmin(points[:, dimension])]
            distance = float(witness[dimension]-face)
            if name.endswith("near"):
                verdict = "undecidable" if 0 < distance <= band and band >= exact else "clearance"
                exact_verdict = "clearance" if exact > 0 else "hard"
            else:
                verdict = "falsePenetration" if distance < -case["mesh"]["minimum_penetration"] and abs(distance) <= band else "touching"
                exact_verdict = "touching" if abs(exact) < 1e-9 else "clearance"
        if not on_face(witness, triangles, dimension, face):
            raise ValueError(f"Mesh witness misses finite partner face: {name}")
        if verdict != case["mesh"]["verdict"] or exact_verdict != case["exact"]["verdict"]:
            raise ValueError(f"Published verdict differs from expectation: {name}: {verdict}/{exact_verdict}")
        if exact is not None and abs(exact-case["exact"]["distance"]) > 1e-9:
            raise ValueError(f"Analytic distance differs from expectation: {name}")
        if "combined_deflection_band" in case["mesh"] and abs(band-case["mesh"]["combined_deflection_band"]) > 1e-12:
            raise ValueError(f"Published band differs from expectation: {name}: {band}")
        rows.append(dict(id=name, partner=case["partner"], axis=case["axis"], radius=case["od"]/2,
                         tessellation=policy or {"mode": "converter-default"}, sides=sides,
                         mesh=dict(verdict=verdict, signed_distance=float(distance),
                                   combined_deflection_band=band, pipe_deflection=band, partner_deflection=0.,
                                   witness=witness.tolist()),
                         exact=dict(verdict=exact_verdict, distance=exact, method="analytic source sweep")))
    return rows


def verify_clash(folder, source):
    from pxr import Usd
    stage = Usd.Stage.Open(str(folder / "dc.usda"))
    data = json.loads((folder / "dc.manifest.json").read_text())
    rows = measure_cases(stage, source.expected["clash"], source.publication["tessellation"])
    if data.get("clash") != dict(units="metres", expected=source.expected["clash"], cases=rows):
        raise ValueError("Published clash receipt differs from source or measured bodies")
    return rows
