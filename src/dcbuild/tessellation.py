"""Per-product circular-sweep tessellation for the published comparison fixture.

Runs before USD authoring. The exact IFC profile and placements are the source;
the requested deflection chooses the smallest polygon meeting that bound.
"""
import math

import numpy as np

from . import ids


def circular_sweep(product, policy):
    import ifcopenshell.util.placement as placement
    reps = [r for r in product.Representation.Representations
            if r.RepresentationIdentifier == "Body"]
    if len(reps) != 1 or len(reps[0].Items) != 1:
        raise ValueError("Controlled tessellation needs one circular extrusion")
    solid = reps[0].Items[0]
    if not (solid.is_a("IfcExtrudedAreaSolid") and solid.SweptArea.is_a("IfcCircleProfileDef")):
        raise ValueError("Controlled tessellation needs a circular extrusion")
    radius = solid.SweptArea.Radius
    mode, deflection = policy["mode"], policy["deflection"]
    if mode not in {"inscribed", "circumscribed"} or not 0 < deflection < radius:
        raise ValueError("Invalid circular tessellation policy")
    angle = math.acos(1 - deflection / radius if mode == "inscribed" else radius / (radius + deflection))
    sides = max(3, math.ceil(math.pi / angle))
    vertex_radius = radius if mode == "inscribed" else radius / math.cos(math.pi / sides)
    frame = placement.get_axis2placement(solid.Position)
    profile = solid.SweptArea.Position
    origin = profile.Location.Coordinates if profile else (0., 0.)
    start = (frame @ np.array([*origin, 0., 1.]))[:3]
    axis = frame[:3, :3] @ np.array(solid.ExtrudedDirection.DirectionRatios)
    axis /= np.linalg.norm(axis)
    product_frame = placement.get_local_placement(product.ObjectPlacement)
    direction = np.array(policy["vertex_direction"], dtype=float)
    u = product_frame[:3, :3].T @ direction
    if not np.isfinite(u).all() or not math.isclose(np.linalg.norm(u), 1.) or abs(u @ axis) > 1e-9:
        raise ValueError("Vertex direction must be a unit vector perpendicular to the sweep")
    v = np.cross(axis, u)
    ring = np.array([vertex_radius * (math.cos(2*math.pi*i/sides)*u +
                                     math.sin(2*math.pi*i/sides)*v) for i in range(sides)])
    points = np.concatenate((start + ring, start + axis*solid.Depth + ring))
    faces = []
    for i in range(sides):
        j = (i + 1) % sides
        faces.extend(((i, j, j+sides), (i, j+sides, i+sides)))
    for i in range(1, sides-1):
        faces.extend(((0, i+1, i), (sides, sides+i, sides+i+1)))
    return points.reshape(-1).tolist(), np.array(faces).reshape(-1).tolist()


def extract_geometry(ifc, policies):
    """Use the pinned converter for all products, then retessellate selected sweeps."""
    from usdaeco_ifc.convert.geometry import extract_geometry as extract
    geo = extract(ifc, threads=1)
    for name, policy in policies.items():
        guid = ids.guid(name)
        if guid not in geo:
            raise ValueError(f"Missing tessellation product: {name}")
        points, faces = circular_sweep(ifc.by_guid(guid), policy)
        geo[guid].update(verts=points, faces=faces)
    return geo
