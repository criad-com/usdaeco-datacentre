"""IFC camera contract, identity, placement and phase acceptance checks."""
import json
import math
from functools import lru_cache

import ifcopenshell.util.element as element
import ifcopenshell.util.placement as placement
import ifcopenshell.util.pset as pset
import ifcopenshell.util.unit as unit
import numpy as np

from .. import ids
from ..camera_contract import CONTRACT, occurrence_payload, type_payload


@lru_cache(maxsize=None)
def common_templates(schema, cls):
    return tuple(t.Name for t in pset.get_template(schema).get_applicable(cls, pset_only=True)
                 if t.Name.endswith("Common"))


def status_census(model, expected_status=None):
    covered, missing, exempt = [], [], []
    expected_status = expected_status or {}
    for product in model.by_type("IfcProduct"):
        common = common_templates(model.schema, product.is_a())
        if not common:
            exempt.append(product)
            continue
        properties = element.get_psets(product, should_inherit=False)
        wanted = expected_status.get(product.GlobalId, "NEW")
        if any(properties.get(name, {}).get("Status") in (wanted, [wanted]) for name in common):
            covered.append(product)
        else:
            missing.append(product)
    return covered, missing, exempt


def statuses(model, plan=None):
    expected = {ids.guid(e["id"]): e["status"] for e in plan.meta.get("fitout", [])} if plan else {}
    _, missing, exempt = status_census(model, expected)
    return ([f"status: {e.is_a()} {e.GlobalId} missing or incorrect occurrence Common.Status" for e in missing]
            + [f"status: unexpected class without Common Pset {e.is_a()}" for e in exempt if not e.is_a("IfcGrid")])


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _check_tier_a(owner, expected, failures):
    properties = element.get_psets(owner, should_inherit=False).get("Pset_AecoCctv", {})
    for key, want in expected.items():
        try:
            got = properties.get(key)
            if key != "Contract":
                got = json.loads(got, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if got != _canonical(want):
                failures.append(f"camera contract: {owner.Name} tier A {key} differs from plan")
        except (TypeError, ValueError) as exc:
            failures.append(f"camera contract: {owner.Name} invalid {key} JSON: {exc}")
    for rel in getattr(owner, "IsDefinedBy", ()):
        ps = getattr(rel, "RelatingPropertyDefinition", None)
        if ps and ps.Name == "Pset_AecoCctv":
            if any(not prop.NominalValue.is_a("IfcText") for prop in ps.HasProperties):
                failures.append(f"camera contract: {owner.Name} tier A requires IfcText")


def cameras(model, plan):
    failures = []
    occurrences = [e for e in model.by_type("IfcAudioVisualAppliance")
                   if e.PredefinedType == "CAMERA" or element.get_predefined_type(e) == "CAMERA"]
    types = [e for e in model.by_type("IfcAudioVisualApplianceType") if e.PredefinedType == "CAMERA"]
    if len(occurrences) != len(plan.cameras):
        failures.append(f"camera census: {len(occurrences)} != {len(plan.cameras)}")
    if len(types) != len(plan.security["camera_types"]):
        failures.append(f"camera types: {len(types)} != {len(plan.security['camera_types'])}")
    by_guid = {e.GlobalId: e for e in model.by_type("IfcRoot")}
    for name, cfg in plan.security["camera_types"].items():
        typ = by_guid.get(ids.guid("type.sec.cam."+name))
        if not typ or not typ.is_a("IfcAudioVisualApplianceType") or typ.PredefinedType != "CAMERA":
            failures.append(f"camera type: missing CAMERA {name}")
            continue
        _check_tier_a(typ, type_payload(name, cfg), failures)
        if len(typ.RepresentationMaps or ()) != 1:
            failures.append(f"camera type: {name} missing mapped body")
    length = unit.calculate_unit_scale(model, "LENGTHUNIT")
    angle = unit.calculate_unit_scale(model, "PLANEANGLEUNIT")
    if unit.get_project_unit(model, "PLANEANGLEUNIT") is None:
        failures.append("camera units: project plane-angle unit missing")
    for c in plan.cameras:
        owner = by_guid.get(c.global_id)
        if owner not in occurrences:
            failures.append(f"camera identity: missing {c.id}")
            continue
        cfg = plan.security["camera_types"][c.type]
        _check_tier_a(owner, occurrence_payload(c), failures)
        typ = element.get_type(owner)
        if not typ or typ.GlobalId != ids.guid("type.sec.cam."+c.type):
            failures.append(f"camera type: {c.id} has incorrect type")
        if owner.PredefinedType != "CAMERA":
            failures.append(f"camera entity: {c.id} must state CAMERA on occurrence")
        container = element.get_container(owner)
        if not container or container.GlobalId != ids.guid(c.space) or not container.is_a("IfcSpace"):
            failures.append(f"camera containment: {c.id} must be in {c.space}")
        if not any(getattr(r, "RelatingGroup", None) and r.RelatingGroup.GlobalId == ids.guid(c.system)
                   for r in owner.HasAssignments):
            failures.append(f"camera system: {c.id} missing {c.system}")
        transform = placement.get_local_placement(owner.ObjectPlacement)
        if not np.allclose(transform[:3, 3]*length, c.pos, atol=1e-6, rtol=0) or not np.allclose(transform[:3, :3], np.eye(3), atol=1e-6):
            failures.append(f"camera placement: {c.id} must use unrotated device frame at plan position")
        if not owner.Representation or not all(r.RepresentationType == "MappedRepresentation" for r in owner.Representation.Representations):
            failures.append(f"camera body: {c.id} must reuse its type representation")
        properties = element.get_psets(owner, should_inherit=False)
        standard = properties.get("Pset_AudioVisualApplianceTypeCamera", {})
        expected = {"CameraType": ["VIDEO"], "IsOutdoors": cfg["outdoor"],
                    "VideoResolutionWidth": cfg["pixels"][0], "VideoResolutionHeight": cfg["pixels"][1],
                    "PanHorizontal": c.pan, "TiltHorizontal": math.radians(-c.tilt)/angle,
                    "Zoom": c.focal_length/1000/length}
        for name, want in expected.items():
            got = standard.get(name)
            ok = math.isclose(got, want, abs_tol=1e-8) if isinstance(got, (int, float)) and isinstance(want, (int, float)) else got == want
            if not ok:
                failures.append(f"camera tier B: {c.id} {name}: {got} != {want}")
        prop_objects = {}
        for rel in owner.IsDefinedBy:
            ps = getattr(rel, "RelatingPropertyDefinition", None)
            if ps and ps.Name == "Pset_AudioVisualApplianceTypeCamera":
                prop_objects = {p.Name: p for p in ps.HasProperties}
        for name, nominal_type in (("PanHorizontal", "IfcLengthMeasure"), ("TiltHorizontal", "IfcPlaneAngleMeasure"),
                                   ("Zoom", "IfcPositiveLengthMeasure")):
            prop = prop_objects.get(name)
            if not prop or not prop.is_a("IfcPropertySingleValue") or not prop.NominalValue.is_a(nominal_type):
                failures.append(f"camera tier B: {c.id} {name} wrong measure type")
        table = prop_objects.get("PanTiltZoomPreset")
        if not table or not table.is_a("IfcPropertyTableValue"):
            failures.append(f"camera presets: {c.id} missing table")
        else:
            try:
                keys, values = table.DefiningValues or (), table.DefinedValues or ()
                actual = {k.wrappedValue: json.loads(v.wrappedValue) for k, v in zip(keys, values)}
                want = {"Sensor_0:"+k: {**v, "tilt": -v["tilt"]} for k, v in c.presets.items()}
                if len(keys) != len(values) or len(actual) != len(keys) or actual != want:
                    failures.append(f"camera presets: {c.id} table differs from plan")
            except (TypeError, ValueError) as exc:
                failures.append(f"camera presets: {c.id} invalid table JSON: {exc}")
    return failures


def approaches_and_yards(model, plan):
    failures = []
    roots = {e.GlobalId: e for e in model.by_type("IfcRoot")}
    for d in plan.doors:
        door = roots.get(ids.guid(d.id))
        if not door:
            failures.append(f"door approach: missing {d.id}")
            continue
        got = element.get_psets(door).get("DC_DoorApproach", {})
        for name, value in (("ApproachSpace", d.approach_space), ("ApproachNormal", d.approach_normal), ("ThresholdHeight", 1.6)):
            if got.get(name) != value:
                failures.append(f"door approach: {d.id} incorrect {name}")
    for s in plan.spaces:
        if not s.external:
            continue
        yard = roots.get(ids.guid(s.id))
        if not yard or not yard.is_a("IfcSpace"):
            failures.append(f"yard: missing space {s.id}")
            continue
        if not yard.Decomposes or not yard.Decomposes[0].RelatingObject.is_a("IfcSite"):
            failures.append(f"yard: {s.id} must aggregate under site")
        if element.get_psets(yard).get("Pset_SpaceCommon", {}).get("IsExternal") is not True or not yard.Representation:
            failures.append(f"yard: {s.id} requires exterior property and footprint geometry")
    for e in plan.equipment:
        if e.pad:
            product = roots.get(ids.guid(e.id))
            container = element.get_container(product) if product else None
            if not container or container.GlobalId != ids.guid(e.space):
                failures.append(f"yard equipment: {e.id} missing containment in {e.space}")
    return failures
