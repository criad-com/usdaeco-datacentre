"""Physical security: AVA sounder-beacons + iris scanners.

AVA (Audible/Visual Alarm) — IFC has no combined audible+visual alarm enum,
so it is an IfcAlarm of PredefinedType USERDEFINED with ObjectType "AVA",
one per critical space, contained in that space. The iris scanner is an
access-control biometric reader -> IfcSensor/IDENTIFIERSENSOR beside its
controlled door (IFC4X3 has no access-control device class). All devices
join the building-wide ``sys.sec`` distribution system.

Positions/sizes come fully resolved from the plan (the security entries in
``plan.security`` reference EquipP records in ``plan.equipment``).
"""
from __future__ import annotations

import json
import math
import ifcopenshell.util.unit

from ..camera_contract import occurrence_payload, type_payload
from .geom import Z_UP, at, rot_z

SEC_MAT = "Security Device"
SEC_RGB = (0.45, 0.2, 0.55)


def build(b, plan) -> None:
    mat = b.material(SEC_MAT, "polymer", rgb=SEC_RGB)
    system = b.system("sys.sec")
    equip = {e.id: e for e in plan.equipment}

    ava_type = b.typed("IfcAlarmType", "AVA", "AVA Sounder Beacon",
                       key="type.sec.ava")
    iris_type = b.typed("IfcSensorType", "IDENTIFIERSENSOR", "Iris Scanner",
                        key="type.sec.iris")

    def device(ifc_class, predefined, rtype, e, **extra):
        """A typed wall/ceiling-mounted device box at its EquipP pos/rot."""
        el = b.entity(ifc_class, predefined=predefined, name=e.name, key=e.id)
        b.assign_type([el], rtype)
        if predefined == "AVA":
            # assign_type moves USERDEFINED/ObjectType onto the type; restate
            # them on the occurrence so it reads IfcAlarm/USERDEFINED "AVA"
            # directly (the class-mapping contract in docs/conventions.md).
            el.PredefinedType = "USERDEFINED"
            el.ObjectType = "AVA"
        w, d, h = e.size
        x, y, z = e.pos
        matrix = rot_z(e.rot, (x, y, z)) if e.rot else at(Z_UP, (x, y, z))
        b.box(el, w, d, h, matrix, structure=b.container_for(e.space))
        b.identify(el, e.id, System="sys.sec", **extra)
        b.style_product(el, SEC_MAT)
        mount = plan.security.get("iris_mounting", {}).get(extra.get("Door"))
        if mount:
            scale = ifcopenshell.util.unit.calculate_unit_scale(b.file, "LENGTHUNIT")
            b.properties(el, "DC_Security", [(name, "IfcLabel" if name == "Side" else "IfcLengthMeasure",
                                               value if name == "Side" else value/scale)
                                              for name, value in mount.items()])
        return el

    devices = [device("IfcAlarm", "AVA", ava_type, equip[entry["id"]])
               for entry in plan.security["ava"]]
    devices += [device("IfcSensor", "IDENTIFIERSENSOR", iris_type,
                       equip[entry["id"]], Door=entry["door"])
                for entry in plan.security["iris"]]
    devices += cameras(b, plan)

    b.assign_material(devices, mat)
    b.assign_system(devices, system)
    b.serves_building(system, "Physical security serves the building")


def _tier_a(b, owner, payload):
    b.properties(owner, "Pset_AecoCctv", [
        (key, "IfcText", value if key == "Contract" else json.dumps(value, sort_keys=True, allow_nan=False))
        for key, value in payload.items()])


def cameras(b, plan):
    types = {}
    for name, cfg in plan.security["camera_types"].items():
        typ = b.typed("IfcAudioVisualApplianceType", "CAMERA", name, key="type.sec.cam."+name)
        _tier_a(b, typ, type_payload(name, cfg))
        w, d, h = cfg["body_size"]
        # Type representation creates a mapping reused by every occurrence.
        b.assign_rep(typ, b.profile_rep(b.rect_profile(w, d), h))
        types[name] = typ

    length_scale = ifcopenshell.util.unit.calculate_unit_scale(b.file, "LENGTHUNIT")
    angle_scale = ifcopenshell.util.unit.calculate_unit_scale(b.file, "PLANEANGLEUNIT")
    result = []
    for c in plan.cameras:
        cfg = plan.security["camera_types"][c.type]
        el = b.entity("IfcAudioVisualAppliance", predefined="CAMERA", name=c.id, key=c.id)
        b.assign_type([el], types[c.type])
        el.PredefinedType = "CAMERA"
        b.contain(el, rot_z(c.device_rotation, c.pos), structure=b.container_for(c.space))
        b.identify(el, c.id, System=c.system)
        _tier_a(b, el, occurrence_payload(c))
        # PanHorizontal is a defective length template whose numeric value is degrees.
        ps = b.properties(el, "Pset_AudioVisualApplianceTypeCamera", [
            ("IsOutdoors", "IfcBoolean", cfg["outdoor"]),
            ("VideoResolutionWidth", "IfcInteger", cfg["pixels"][0]),
            ("VideoResolutionHeight", "IfcInteger", cfg["pixels"][1]),
            ("PanHorizontal", "IfcLengthMeasure", c.pan),
            ("TiltHorizontal", "IfcPlaneAngleMeasure", math.radians(-c.tilt)/angle_scale),
            ("Zoom", "IfcPositiveLengthMeasure", c.focal_length/1000/length_scale),
        ])
        video = b.file.create_entity("IfcPropertyEnumeratedValue", Name="CameraType",
                                     EnumerationValues=[b.file.create_entity("IfcLabel", "VIDEO")])
        keys, values = [], []
        for name, preset in c.presets.items():
            keys.append(b.file.create_entity("IfcIdentifier", "Sensor_0:"+name))
            values.append(b.file.create_entity("IfcText", json.dumps(
                {**preset, "tilt": -preset["tilt"]}, sort_keys=True, allow_nan=False)))
        table = b.file.create_entity("IfcPropertyTableValue", Name="PanTiltZoomPreset",
                                     DefiningValues=keys or None, DefinedValues=values or None)
        ps.HasProperties = [*ps.HasProperties, video, table]
        result.append(el)
    return result
