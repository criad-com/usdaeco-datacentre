"""Blocking native-export parity: full joins, stable identities and camera drivers.

Camera device positions use 1 mm and driver values use 1e-6 degrees/mm/metres.
Other product geometry retains the documented 150 mm bbox fallback because
native family insertion points and generated solid origins differ.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np
import json
import math
import ifcopenshell.util.element as element

from .. import ids

TOL = 0.05          # m
COVERAGE = 1.0     # racks + equipment
LIST_CAP = 10
MARK_PROPS = ("Reference", "Mark", "Id")


# ------------------------------------------------------------------ joins
def _pset_index(f: ifcopenshell.file, prop_names) -> dict[str, list]:
    """value-of-named-property -> [products], via IfcRelDefinesByProperties."""
    index = defaultdict(list)
    for rel in f.by_type("IfcRelDefinesByProperties"):
        ps = rel.RelatingPropertyDefinition
        if ps is None or not ps.is_a("IfcPropertySet"):
            continue
        for prop in ps.HasProperties or ():
            if (prop.is_a("IfcPropertySingleValue") and prop.Name in prop_names
                    and prop.NominalValue is not None):
                for obj in rel.RelatedObjects:
                    index[str(prop.NominalValue.wrappedValue)].append(obj)
    return index


def _ours_lookup(f: ifcopenshell.file):
    by_guid = {e.GlobalId: e for e in f.by_type("IfcProduct")}
    by_specid = _pset_index(f, ("Id",))
    return lambda spec_id: (by_guid.get(ids.guid(spec_id))
                           or next(iter(by_specid.get(spec_id, [])), None))


def _revit_lookup(f: ifcopenshell.file):
    by_mark = defaultdict(list)
    for e in f.by_type("IfcProduct"):
        tag = getattr(e, "Tag", None)
        if tag:
            by_mark[str(tag)].append(e)
    for mark, objs in _pset_index(f, MARK_PROPS).items():
        by_mark[mark].extend(o for o in objs if o.is_a("IfcProduct"))

    def lookup(spec_id):
        candidates = {e.id():e for e in by_mark.get(spec_id, [])}
        if len(candidates)>1:
            raise ValueError(f"Duplicate exported Mark: {spec_id}")
        return next(iter(candidates.values()), None)

    return lookup


def _origin(e, scale) -> np.ndarray | None:
    if getattr(e, "ObjectPlacement", None) is None:
        return None
    m = ifcopenshell.util.placement.get_local_placement(e.ObjectPlacement)
    return np.array(m[:3, 3], dtype=float) * scale


_GEOM_SETTINGS = None
TOL_GEOM = 0.15  # mesh/export wobble allowance for the bbox-centre fallback


def _bbox_centre(e) -> np.ndarray | None:
    """World bbox centre from tessellated geometry (SI metres).

    Ground-truth fallback: Revit-exported DirectShapes often carry identity
    placements with world-coordinate meshes, and representation conventions
    (e.g. wall body vs placement origin) differ between authoring tools —
    geometry is what must actually coincide."""
    global _GEOM_SETTINGS
    if not getattr(e, "Representation", None):
        return None
    try:
        import ifcopenshell.geom
        if _GEOM_SETTINGS is None:
            _GEOM_SETTINGS = ifcopenshell.geom.settings()
            _GEOM_SETTINGS.set("use-world-coords", True)
        shape = ifcopenshell.geom.create_shape(_GEOM_SETTINGS, e)
        v = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        if not len(v):
            return None
        return (v.min(axis=0) + v.max(axis=0)) / 2.0
    except Exception:
        return None


def _properties(model, owner):
    """Property entities, with occurrence values overriding type values."""
    result = {}
    for obj in (element.get_type(owner), owner):
        if not obj:
            continue
        for pset, data in element.get_psets(obj, should_inherit=False).items():
            entity = model.by_id(data["id"])
            if entity.is_a("IfcPropertySet"):
                for p in entity.HasProperties:
                    result[(pset, p.Name)] = p
    return result


def camera_drivers(model, camera):
    props = _properties(model, camera)
    def value(names, pset=None):
        for name in names:
            matches = [p for (ps, n), p in props.items() if n == name and (pset is None or ps == pset)]
            for p in matches:
                v = getattr(p, "NominalValue", None)
                if v is None and p.is_a("IfcPropertyBoundedValue"):
                    v = p.SetPointValue
                if v is None:
                    continue
                raw = v.wrappedValue
                if v.is_a("IfcPlaneAngleMeasure"):
                    source = ifcopenshell.util.unit.get_property_unit(p, model)
                    if source:
                        factor = ifcopenshell.util.unit.convert_unit(1., source, model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN"))
                    else:
                        factor = ifcopenshell.util.unit.calculate_unit_scale(model, "PLANEANGLEUNIT")
                    raw = math.degrees(float(raw)*factor)
                elif name == "Zoom" and "LengthMeasure" in v.is_a():
                    raw = float(raw)*ifcopenshell.util.unit.calculate_unit_scale(model)*1000
                return raw
        return None
    psets=element.get_psets(camera, should_inherit=False)
    if "Pset_AecoCctv" in psets:
        payload=json.loads(psets["Pset_AecoCctv"]["Sensors"])
        if not payload:
            raise ValueError("Empty authoritative camera Sensors")
        driver=payload[0]["drivers"]
        return {key:driver["aeco:cctvSensor:"+field] for key,field in
                (("pan","pan"),("tilt","tilt"),("focal","focalLength"))}
    result={}
    for key,standard,aliases in (
        ("pan","PanHorizontal",("FOV Pan","FOV Camera Rotation","FOV 1 Pan","FOV 1 Camera Rotation")),
        ("tilt","TiltHorizontal",("FOV Tilt","FOV Camera Tilt","FOV 1 Tilt","FOV 1 Camera Tilt")),
        ("focal","Zoom",("FOV Desired Focal Length","FOV 1 Desired Focal Length"))):
        v=value((standard,),"Pset_AudioVisualApplianceTypeCamera")
        if v is not None and key=="tilt": v=-v
        result[key]=v if v is not None else value(aliases)
    return result


def camera_parity(model, camera, planned):
    failures=[]
    if not camera.is_a("IfcAudioVisualAppliance") or camera.PredefinedType != "CAMERA":
        failures.append("camera classification differs")
    try:
        values=camera_drivers(model,camera)
        for field,expected in (("pan",planned.pan),("tilt",planned.tilt),("focal",planned.focal_length)):
            value=values[field]
            if value is None or not math.isfinite(float(value)) or abs(float(value)-expected)>1e-6:
                failures.append(f"{field} differs: {value} vs {expected}")
    except (ValueError,KeyError,TypeError) as exc:
        failures.append("invalid camera payload: "+str(exc))
    position=_origin(camera,ifcopenshell.util.unit.calculate_unit_scale(model))
    if position is None or not np.isfinite(position).all() or np.linalg.norm(position-np.array(planned.pos))>0.001:
        failures.append("camera device position differs by more than 1 mm")
    if camera.ObjectPlacement:
        matrix=ifcopenshell.util.placement.get_local_placement(camera.ObjectPlacement)
        angle=math.degrees(math.atan2(matrix[1,0],matrix[0,0]))
        if abs((angle-planned.device_rotation+180)%360-180)>1e-6:
            failures.append("camera device rotation differs")
    return failures


# ------------------------------------------------------------------ gate
def main(plan, revit_ifc: Path, our_dir: Path) -> int:
    ours_path = our_dir / "demo-datacentre-01.ifc"
    assert ours_path.exists(), f"parity: {ours_path} missing — run build-ifc first"
    assert revit_ifc.exists(), f"parity: {revit_ifc} missing"

    ours = ifcopenshell.open(str(ours_path))
    revit = ifcopenshell.open(str(revit_ifc))
    our_scale = ifcopenshell.util.unit.calculate_unit_scale(ours)
    rev_scale = ifcopenshell.util.unit.calculate_unit_scale(revit)
    find_ours = _ours_lookup(ours)
    find_revit = _revit_lookup(revit)

    categories = [("racks", [r.id for r in plan.racks]),
                  ("equipment", [e.id for e in plan.equipment]),
                  ("doors", [d.id for d in plan.doors]),
                  ("walls", [w.id for w in plan.walls]),
                  ("columns", [c.id for c in plan.columns]),
                  ("cameras", [c.id for c in plan.cameras])]
    planned_cameras={c.id:c for c in plan.cameras}
    rows=[]

    fails: list[str] = []
    core_planned = core_both = 0     # racks + equipment coverage pool
    print(f"G2 parity: {ours_path.name} vs {revit_ifc.name}")
    for name, spec_ids in categories:
        missing_ours, missing_revit, deltas, over = [], [], [], []
        classes = Counter()
        for spec_id in spec_ids:
            try:
                o, r = find_ours(spec_id), find_revit(spec_id)
            except ValueError as exc:
                fails.append(str(exc))
                o, r = find_ours(spec_id), None
            if o is None:
                missing_ours.append(spec_id)
            if r is None:
                missing_revit.append(spec_id)
            if o is None or r is None:
                continue
            classes[r.is_a()] += 1
            if r.GlobalId != ids.guid(spec_id):
                fails.append(f"{spec_id}: exported GUID differs")
            if name == "cameras":
                fails.extend(f"{spec_id}: {failure}" for failure in camera_parity(revit,r,planned_cameras[spec_id]))
                position=_origin(r,rev_scale)
                if position is not None:
                    deltas.append(float(np.linalg.norm(position-np.array(planned_cameras[spec_id].pos))))
                continue
            po, pr = _origin(o, our_scale), _origin(r, rev_scale)
            if po is not None and pr is not None:
                d = float(np.linalg.norm(po - pr))
                if d > TOL:
                    # placement conventions differ between authoring tools;
                    # fall back to comparing actual geometry centres
                    go, gr = _bbox_centre(o), _bbox_centre(r)
                    if go is not None and gr is not None:
                        d = float(np.linalg.norm(go - gr))
                        if d > TOL_GEOM:
                            over.append((spec_id, d))
                    else:
                        over.append((spec_id, d))
                deltas.append(d)
        both = len(spec_ids) - len(set(missing_ours) | set(missing_revit))
        if name in ("racks", "equipment", "doors", "walls", "columns", "cameras"):
            core_planned += len(spec_ids)
            core_both += both
        dpos = f"{max(deltas):.3f} m" if deltas else "n/a"
        print(f"  {name:<10} planned {len(spec_ids):>4}  "
              f"ours {len(spec_ids) - len(missing_ours):>4}  "
              f"revit {len(spec_ids) - len(missing_revit):>4}  both {both:>4}  "
              f"max dpos {dpos}")
        if classes:
            print(f"             revit classes: {dict(classes)}")
        for label, miss in (("ours", missing_ours), ("revit", missing_revit)):
            if miss:
                fails.append(f"{name}: missing {len(miss)} in {label}")
                print(f"             missing in {label}: {len(miss)} "
                      f"(e.g. {sorted(miss)[:LIST_CAP]})")
        rows.append({"category":name,"planned":len(spec_ids),"joined":both,"max_position_delta_m":max(deltas) if deltas else None})
        for spec_id, d in sorted(over, key=lambda t: -t[1])[:LIST_CAP]:
            fails.append(f"parity: {name} {spec_id} position delta {d:.3f} m > {TOL} m")
        if len(over) > LIST_CAP:
            fails.append(f"parity: {name} ... and {len(over) - LIST_CAP} more over-tolerance")

    coverage = core_both / core_planned if core_planned else 0.0
    print(f"  coverage (all required products): {core_both}/{core_planned} = {coverage:.1%}")
    if coverage < COVERAGE:
        fails.append(f"parity: all required product coverage {coverage:.1%} < {COVERAGE:.0%}")

    spaces=len(revit.by_type("IfcSpace"))
    camera_count=sum(e.PredefinedType=="CAMERA" for e in revit.by_type("IfcAudioVisualAppliance"))
    door_count=len(revit.by_type("IfcDoor"))
    if spaces<30 or camera_count!=len(plan.cameras) or door_count!=len(plan.doors):
        fails.append(f"Export census differs: {camera_count} cameras, {spaces} spaces, {door_count} doors")
    result={"categories":rows,"joined":core_both,"planned":core_planned,
            "cameras":camera_count,"spaces":spaces,"doors":door_count,"failures":fails}
    revit_ifc.with_suffix(".parity.json").write_text(json.dumps(result,indent=2)+"\n")
    for msg in fails:
        print(f"FAIL  {msg}")
    if fails:
        print(f"G2 FAIL — {len(fails)} failures")
        return 1
    print(f"G2 OK — {core_both}/{core_planned} required products joined, "
          f"camera positions <= 0.001 m; other products use declared geometry tolerances")
    return 0
