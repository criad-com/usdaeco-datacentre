"""Published-floor comparison by classification, inherited type and placement.

Generator ids label the findings and assert the planted fixture only after
matching. No consumer schema or consumer implementation is required.
"""
import math

from pxr import Gf, Usd, UsdGeom

TOLERANCE = 1e-6


def value(prim, name, default=None):
    got = prim.GetAttribute(name).Get()
    return default if got is None else got


def source_id(prim):
    return value(prim, "aeco:props:DC_Identity:Id", "")


def elements(container):
    return [p for p in Usd.PrimRange(container) if (apis := p.GetMetadata("apiSchemas"))
            and "AecoElementAPI" in apis.GetAppliedItems()]


def match_key(prim):
    codes = tuple((a.GetName(), a.Get()) for a in prim.GetAttributes()
                  if a.GetName().startswith("aeco:class:") and a.GetName().endswith(":code"))
    return codes, tuple(str(p) for p in prim.GetInherits().GetAllDirectInherits())


def plain(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    return [plain(v) for v in value]


def shape(prim):
    result = []
    for p in Usd.PrimRange(prim):
        if value(p, "aeco:derived:role") not in (None, "body") or p.GetTypeName() == "AecoPort":
            continue
        for attr in p.GetAttributes():
            name = attr.GetName()
            if (not attr.HasAuthoredValueOpinion() or attr.GetMetadata("aecoDerived")
                    or name.startswith(("aeco:props:", "aeco:class:", "aeco:qto:", "aeco:derived:",
                                        "primvars:", "visibility", "purpose"))
                    or name in ("aeco:id", "aeco:axis:length")
                    or p == prim and name.startswith("xformOp")):
                continue
            result.append((str(p.GetPath().MakeRelativePath(prim.GetPath())), name, plain(attr.Get())))
    return result


def close(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= TOLERANCE
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    return a == b


def compare(stage, prototype, instance, offset):
    left, right = elements(prototype), elements(instance)
    cache = UsdGeom.XformCache()
    worlds = {p: cache.GetLocalToWorldTransform(p) for p in left + right}
    shapes = {p: shape(p) for p in left + right}
    transform = Gf.Matrix4d(1).SetTranslate(Gf.Vec3d(*offset))
    pairs, changes = [], []
    for mode in ("placement", "shape", "remaining"):
        candidates = []
        for a in left:
            for b in right:
                if match_key(a) != match_key(b):
                    continue
                registered = worlds[a] * transform
                distance = max(abs(registered[i][j] - worlds[b][i][j]) for i in range(4) for j in range(4))
                same = close(shapes[a], shapes[b])
                if mode == "placement" and distance > TOLERANCE or mode == "shape" and not same:
                    continue
                candidates.append((distance, str(a.GetPath()), str(b.GetPath()), a, b, same))
        for distance, _, _, a, b, same in sorted(candidates):
            if a not in left or b not in right:
                continue
            left.remove(a)
            right.remove(b)
            pairs.append((a, b))
            if distance > TOLERANCE or not same:
                changes.append({"kind": "moved" if same else "changed", "prototype": source_id(a),
                                "instance": source_id(b), "classification": value(b, "aeco:class:ifc:code")})
    changes.extend({"kind": "missing", "prototype": source_id(a), "instance": None,
                    "classification": value(a, "aeco:class:ifc:code")} for a in left)
    changes.extend({"kind": "extra", "prototype": None, "instance": source_id(b),
                    "classification": value(b, "aeco:class:ifc:code")} for b in right)
    return pairs, sorted(changes, key=lambda row: (row["kind"], row["instance"] or row["prototype"] or ""))


def partition_lengths(container):
    lengths = []
    for prim in elements(container):
        if value(prim, "aeco:class:ifc:code") != "IfcWall.PARTITIONING":
            continue
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])
        bounds = Gf.Range3d()
        for body in Usd.PrimRange(prim):
            if body.IsA(UsdGeom.Mesh) and value(body, "aeco:derived:role") == "body":
                bounds.UnionWith(cache.ComputeRelativeBound(body, prim).ComputeAlignedRange())
        measured = bounds.GetSize()[0]
        reported = value(prim, "aeco:props:Qto_WallBaseQuantities:Length")
        if not close(measured, reported):
            raise ValueError("Partition body length differs from its IFC quantity")
        lengths.append(measured)
    return round(sum(lengths), 6)


def measure(stage, expected):
    indexed = {source_id(p): p for p in stage.Traverse() if source_id(p)}
    prototype, instance = (indexed[expected[k]] for k in ("prototype", "instance"))
    offset = expected["offset_m"]
    if not close(offset, [0, 0, value(instance, "aeco:elevation") - value(prototype, "aeco:elevation")]):
        raise ValueError("Typical offset differs from level elevations")
    pairs, changes = compare(stage, prototype, instance, offset)
    lengths = {expected[k]: partition_lengths(indexed[expected[k]]) for k in ("prototype", "instance")}
    return {"units": "metres", "matching": "classification + inherited type + placement; body comparison",
            "expected": expected, "matched_elements": len(pairs), "changes": changes,
            "partition_length_m": lengths,
            "net_partition_length_delta_m": round(lengths[expected["instance"]] - lengths[expected["prototype"]], 6)}


def verify(stage, expected):
    actual = measure(stage, expected)
    moved = next(d for d in expected["deviations"] if d["kind"] == "wallMoved")
    extra = next(d for d in expected["deviations"] if d["kind"] == "doorExtra")
    wanted = [{"kind": "changed", "prototype": moved["prototype"], "instance": moved["id"],
               "classification": "IfcWall.PARTITIONING"},
              {"kind": "extra", "prototype": None, "instance": extra["id"], "classification": "IfcDoor.DOOR"}]
    if actual["changes"] != wanted:
        raise ValueError("Typical floor differs beyond the planted wall and door: " + str(actual["changes"]))
    if not close(actual["net_partition_length_delta_m"], expected["expected_net_partition_length_delta_m"]):
        raise ValueError("Typical net partition length delta differs")
    indexed = {source_id(p): p for p in stage.Traverse() if source_id(p)}
    for key, axis in (("prototype", "axis_from"), ("id", "axis_to")):
        prim = indexed[moved[key]]
        transform = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
        length = value(prim, "aeco:props:Qto_WallBaseQuantities:Length")
        ends = [list(transform.Transform(Gf.Vec3d(x, 0, 0)))[:2] for x in (0, length)]
        if not close(ends, moved[axis]):
            raise ValueError("Published moved wall axis differs from the planted edit")
    lateral = [b - a for a, b in zip(moved["axis_from"][1], moved["axis_to"][1])] + [0]
    if not close(lateral, moved["offset_m"]):
        raise ValueError("Planted wall offset differs from its axes")
    return actual
