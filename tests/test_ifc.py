from pathlib import Path
import json
import math

import ifcopenshell
import ifcopenshell.api.unit
import ifcopenshell.api.pset
import ifcopenshell.util.element as element
import ifcopenshell.util.placement as placement
import numpy as np
import pytest

from dcbuild import ids, layout, spec
from dcbuild.ifc import security, spatial
from dcbuild.ifc.builder import Builder
from dcbuild.qa import cameras as qa
from dcbuild.qa.validate_ifc import schema


@pytest.fixture(scope="module")
def fixture(tmp_path_factory):
    plan = layout.resolve(spec.load())
    b = Builder(plan)
    spatial.build(b, plan)
    security.build(b, plan)
    path = tmp_path_factory.mktemp("camera-ifc") / "security.ifc"
    b.write(path)
    return plan, path


def test_security_schema_and_contract(fixture):
    plan, path = fixture
    model = ifcopenshell.open(path)
    assert not schema(path)
    assert not qa.cameras(model, plan)
    assert not qa.statuses(model)


@pytest.mark.parametrize("length,angle", [("METERS", "radian"), ("METERS", "degree"), ("MILLIMETERS", "radian"), ("MILLIMETERS", "degree")])
def test_camera_writer_unit_combinations(length, angle):
    plan = layout.resolve(spec.load())
    b = Builder(plan)
    ifcopenshell.api.unit.assign_unit(b.file, length={"is_metric": True, "raw": length})
    if angle == "degree":
        angle_unit = ifcopenshell.api.unit.add_conversion_based_unit(b.file, name="degree")
    else:
        angle_unit = b.file.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")
    assignment = b.project.UnitsInContext
    assignment.Units = [u for u in assignment.Units if u.UnitType != "PLANEANGLEUNIT"] + [angle_unit]
    spatial.build(b, plan)
    security.build(b, plan)
    assert not qa.cameras(b.file, plan)
    model = ifcopenshell.file.from_string(b.file.to_string())
    assert not qa.cameras(model, plan)
    camera = model.by_guid(ids.guid("sec.cam.door.hall.a.s"))
    mirror = element.get_psets(camera)["Pset_AudioVisualApplianceTypeCamera"]
    assert mirror["TiltHorizontal"] == pytest.approx(-60 if angle == "degree" else -math.pi/3)
    assert mirror["Zoom"] == pytest.approx(3 if length == "MILLIMETERS" else 0.003)


@pytest.mark.parametrize("mutation,expected", [("json", "JSON"), ("angle", "TiltHorizontal"), ("type", "type"), ("system", "system"), ("frame", "placement"), ("preset", "presets")])
def test_camera_corruption_is_rejected(fixture, mutation, expected):
    plan, path = fixture
    model = ifcopenshell.open(path)
    camera = model.by_guid(ids.guid("sec.cam.lobby"))
    psets = element.get_psets(camera, should_inherit=False)
    if mutation in {"json", "angle", "preset"}:
        name = "Pset_AecoCctv" if mutation == "json" else "Pset_AudioVisualApplianceTypeCamera"
        pset = model.by_id(psets[name]["id"])
        prop = next(p for p in pset.HasProperties if p.Name == {"json": "Sensors", "angle": "TiltHorizontal", "preset": "PanTiltZoomPreset"}[mutation])
        if mutation == "json":
            prop.NominalValue = model.create_entity("IfcText", "{")
        elif mutation == "angle":
            prop.NominalValue = model.create_entity("IfcPlaneAngleMeasure", camera.id())
        else:
            prop.DefinedValues = prop.DefinedValues[:-1]
            prop.DefiningValues = prop.DefiningValues[:-1]
    elif mutation == "type":
        camera.IsTypedBy[0].RelatingType = model.by_type("IfcAlarmType")[0]
    elif mutation == "system":
        group = next(r for r in camera.HasAssignments if r.is_a("IfcRelAssignsToGroup"))
        group.RelatedObjects = [e for e in group.RelatedObjects if e != camera]
    elif mutation == "frame":
        camera.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = (0., 1., 0.)
    assert any(expected in failure for failure in qa.cameras(model, plan))


def test_missing_product_status_fails(fixture):
    _, path = fixture
    model = ifcopenshell.open(path)
    camera = model.by_guid(ids.guid("sec.cam.lobby"))
    pset = model.by_id(element.get_psets(camera)["Pset_AudioVisualApplianceTypeCommon"]["id"])
    for p in pset.HasProperties:
        if p.Name == "Status":
            p.EnumerationValues = [model.create_entity("IfcLabel", "EXISTING")]
    assert any(camera.GlobalId in failure for failure in qa.statuses(model))


def test_empty_presets_have_an_empty_table(fixture):
    plan, path = fixture
    model = ifcopenshell.open(path)
    camera = model.by_guid(ids.guid("sec.cam.door.hall.a.s"))
    pset = model.by_id(element.get_psets(camera)["Pset_AudioVisualApplianceTypeCamera"]["id"])
    table = next(p for p in pset.HasProperties if p.Name == "PanTiltZoomPreset")
    assert not table.DefiningValues and not table.DefinedValues


def test_nested_ports_preserve_world_placements_and_creation_order():
    plan = layout.resolve(spec.load())
    b = Builder(plan)
    spatial.build(b, plan)
    device = b.entity("IfcSensor", name="Test reader", key="test.reader")
    matrix = np.eye(4)
    matrix[:3, 3] = (3, 4, 1)
    b.contain(device, matrix, structure=b.spaces["sp.corr.w"])
    ports = []
    for i in range(3):
        matrix[:3, 3] = (4+i, 4, 1)
        port = b.add_port(device, matrix=matrix, key=f"test.reader.port.{i}")
        ports.append(port)
        assert placement.get_local_placement(port.ObjectPlacement)[:3, 3] == pytest.approx((4+i,4,1))
    assert list(device.IsNestedBy[0].RelatedObjects) == ports
    assert all(len(port.Nests) == 1 for port in ports)


@pytest.mark.parametrize("length,angle", [("METERS", "radian"), ("MILLIMETERS", "degree")])
def test_native_parity_camera_units_and_missing_driver(length, angle):
    from dcbuild.qa.parity import camera_parity
    plan = layout.resolve(spec.load())
    b = Builder(plan)
    ifcopenshell.api.unit.assign_unit(b.file, length={"is_metric": True, "raw": length})
    unit = (ifcopenshell.api.unit.add_conversion_based_unit(b.file, name="degree") if angle == "degree"
            else b.file.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN"))
    b.project.UnitsInContext.Units = [u for u in b.project.UnitsInContext.Units if u.UnitType != "PLANEANGLEUNIT"]+[unit]
    spatial.build(b, plan)
    security.build(b, plan)
    planned = plan.cameras[5]
    camera = b.file.by_guid(planned.global_id)
    assert not camera_parity(b.file, camera, planned)
    a = element.get_psets(camera, should_inherit=False)['Pset_AecoCctv']['id']
    ifcopenshell.api.pset.remove_pset(b.file, product=camera, pset=b.file.by_id(a))
    assert not camera_parity(b.file, camera, planned)  # independent tier B path
    mirror = element.get_psets(camera, should_inherit=False)['Pset_AudioVisualApplianceTypeCamera']['id']
    pset = b.file.by_id(mirror)
    pset.HasProperties = [p for p in pset.HasProperties if p.Name != 'TiltHorizontal']
    assert any('tilt differs' in f for f in camera_parity(b.file, camera, planned))


def test_native_parity_duplicate_mark_fails(fixture):
    from dcbuild.qa.parity import _revit_lookup
    _, path = fixture
    model = ifcopenshell.open(path)
    cameras = model.by_type('IfcAudioVisualAppliance')
    cameras[0].Tag = cameras[1].Tag = 'duplicate.camera'
    with pytest.raises(ValueError, match='Duplicate exported Mark'):
        _revit_lookup(model)('duplicate.camera')
