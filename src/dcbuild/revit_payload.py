"""Validated, unit-explicit payload for the native camera authoring phase."""
import copy
import json
import math
from types import SimpleNamespace

from . import ids
from .camera_contract import occurrence_payload, type_payload


FAMILIES = {
    "dome_5mp": "Surveillance-Camera-AXIS_P3277-LV-metric.rfa",
    "bullet_4mp_outdoor": "Surveillance-Camera-AXIS_P3277-LV-metric.rfa",
    "ptz_4k": "Surveillance-Camera-AXIS_Q6088-E-metric.rfa",
}

STATUS_CATEGORIES = [
    "OST_Walls", "OST_Doors", "OST_Floors", "OST_StructuralColumns",
    "OST_ElectricalEquipment", "OST_MechanicalEquipment", "OST_SpecialityEquipment",
    "OST_GenericModel", "OST_SecurityDevices", "OST_Rooms", "OST_CableTray",
    "OST_CableTrayFitting", "OST_PipeCurves", "OST_PipeFitting", "OST_Levels",
]


def prepare(plan):
    """Enrich a copy; canonical generator plan and its identity digest stay stable."""
    plan = copy.deepcopy(plan)
    spaces = {s["id"]: s for s in plan["spaces"]}
    levels = {s["id"] for s in plan["storeys"]}
    catalog = plan["security"]["camera_types"]
    for name, cfg in catalog.items():
        density = cfg.get("target_density")
        if (type(density) not in (int, float) or not math.isfinite(density)
                or density <= 0 or density != int(density)):
            raise ValueError(f"{name}: native type target density must be a positive integer")
    identities = {}
    for group in ("storeys", "grid_lines", "spaces", "walls", "doors", "columns", "slabs",
                  "equipment", "racks", "runs", "routes", "cameras"):
        for row in plan[group]:
            if row["id"] in identities:
                raise ValueError(f"Duplicate plan identity: {row['id']}")
            identities[row["id"]] = ids.guid(row["id"])
    for c in plan["cameras"]:
        label = c["id"]
        if c["global_id"] != identities[label]:
            raise ValueError(f"{label}: contract GUID differs")
        if c["type"] not in FAMILIES or c["type"] not in catalog:
            raise ValueError(f"{label}: unsupported family type")
        space = spaces[c["space"]]
        level = space["storey"]
        if space.get("external") and level not in levels:
            level = min(plan["storeys"], key=lambda s: s["elevation"])["id"]
        if level not in levels:
            raise ValueError(f"{label}: missing native level")
        cfg = catalog[c["type"]]
        numbers = [*c["pos"], c["device_rotation"], c["pan"], c["tilt"], c["roll"],
                   c["focal_length"], c["range"], c["target_density"]]
        if len(c["pos"]) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in numbers):
            raise ValueError(f"{label}: nonfinite or malformed camera pose")
        if c["roll"] not in (0, 90) or c["target_density"] != int(c["target_density"]):
            raise ValueError(f"{label}: family cannot represent roll or fractional density")
        if not cfg["focal_range"][0] <= c["focal_length"] <= cfg["focal_range"][1] or c["range"] <= 0 or c["target_density"] < 0:
            raise ValueError(f"{label}: driver outside envelope")
        if len(c["presets"]) > 4 or any(n not in c["presets"] for n in c["tour"]):
            raise ValueError(f"{label}: unsupported presets or invalid tour")
        for name, preset in c["presets"].items():
            for key in ("pan", "tilt", "focalLength", "dwell"):
                if not math.isfinite(preset[key]):
                    raise ValueError(f"{label}/{name}: nonfinite {key}")
            if not cfg["focal_range"][0] <= preset["focalLength"] <= cfg["focal_range"][1]:
                raise ValueError(f"{label}/{name}: focal length outside envelope")
        # Home first: numbered head 1 also supplies the PTZ's active pose.
        order = sorted(c["presets"], key=lambda n: (not c["presets"][n].get("home", False), n))
        c.update(level=level, family=FAMILIES[c["type"]], preset_order=order,
                 native_target_density=c["target_density"] if c["target_density"] > 0 else cfg["target_density"],
                 contract={k: v if isinstance(v, str) else json.dumps(v, sort_keys=True, allow_nan=False)
                           for k, v in occurrence_payload(SimpleNamespace(**c)).items()},
                 type_contract={k: v if isinstance(v, str) else json.dumps(v, sort_keys=True, allow_nan=False)
                                for k, v in type_payload(c["type"], cfg).items()})
    plan["revit_identities"] = identities
    plan["revit_status"] = {"value": "NEW", "categories": STATUS_CATEGORIES.copy()}
    return plan
