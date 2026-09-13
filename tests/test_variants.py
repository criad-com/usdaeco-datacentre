"""Variant input contracts, including malformed inheritance and merge inputs."""
from copy import deepcopy
import dataclasses
from pathlib import Path

import pytest

from dcbuild import layout, spec


def test_base_plan_unchanged():
    from dcbuild.qa.manifest import manifest
    import json
    plan = layout.resolve(spec.load(variant="base"))
    assert manifest(plan) == json.loads(Path("manifests/demo-datacentre-01.json").read_text())


def test_overlay_records_merge_without_mutating_inputs():
    base = {"records": [{"id": "a", "nested": {"x": 1, "y": 2}}, {"id": "b"}], "list": [1]}
    saved = deepcopy(base)
    result = spec.merge(base, {"records": [{"id": "a", "nested": {"x": 3}}, {"id": "c"}], "list": [2]})
    assert result == {"records": [{"id": "a", "nested": {"x": 3, "y": 2}}, {"id": "b"}, {"id": "c"}], "list": [2]}
    assert base == saved


@pytest.mark.parametrize("bad", ["../base", "missing", "Base", "a/b"])
def test_invalid_variant_rejected(bad):
    with pytest.raises(ValueError):
        spec.load(variant=bad)


def test_duplicate_overlay_ids_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        spec.merge([{"id": "a"}], [{"id": "b"}, {"id": "b"}])


def test_inheritance_and_cycle(tmp_path):
    import shutil
    shutil.copytree(spec.spec_dir(), tmp_path/"spec")
    directory = tmp_path/"spec"
    (directory/"variants/first.yaml").write_text('''security:
  door_cameras: {height: 2.5}
''')
    (directory/"variants/second.yaml").write_text('''extends: first
security:
  door_cameras: {range: 9}
''')
    resolved = spec.load(directory, "second")
    assert (resolved.security.door_cameras.height, resolved.security.door_cameras.range) == (2.5, 9)
    (directory/"variants/first.yaml").write_text('extends: second\n')
    with pytest.raises(ValueError, match="cycle"):
        spec.load(directory, "second")


def test_floors_room_copy_and_local_edit():
    source = spec.load(variant="floors")
    plan = layout.resolve(source)
    assert len(plan.storeys) == 3
    original = {s.id for s in plan.spaces if s.storey == "lvl.l1"}
    repeated = {s.id.removesuffix(".2") for s in plan.spaces if s.storey == "lvl.l2"}
    assert original == repeated and len(original) == 6
    assert plan.space("sp.wc.2").w == plan.space("sp.wc").w
    assert plan.space("sp.kitchen.2").w == plan.space("sp.kitchen").w
    assert plan.meta["expected"]["drift"]["walls_moved"] == 1
    assert plan.meta["expected"]["drift"]["doors_extra"] == 1
    assert next(d for d in plan.doors if d.id == "door.office.2b").width == .9


def test_floors_slabs_and_roof_are_per_block():
    plan = layout.resolve(spec.load(variant="floors"))
    assert [(s.id, s.top_elevation) for s in plan.slabs if s.kind == "upper"] == [
        ("slab.l1.office", 4), ("slab.l2.office", 7)]
    roofs = {s.id: s.top_elevation-s.thickness for s in plan.slabs if s.kind == "roof"}
    assert roofs == {"slab.roof.main": 7, "slab.roof.office": 10}
    assert max(c.height for c in plan.columns) == 10


def test_floors_circulation_and_determinism():
    from dcbuild import graph
    plan = layout.resolve(spec.load(variant="floors"))
    assert not graph.run_all(plan)
    assert dataclasses.asdict(plan) == dataclasses.asdict(layout.resolve(spec.load(variant="floors")))


def test_floor_area_and_block_membership_rejected():
    source = spec.load(variant="floors")
    source.facility.storeys[-1].expected_areas["office"] = 200
    with pytest.raises(ValueError, match="areas"):
        layout.resolve(source)
    source = spec.load(variant="floors")
    source.facility.storeys[-1].blocks = ["main"]
    with pytest.raises(ValueError, match="not inside"):
        layout.resolve(source)


def test_floor_ifc_prototype_stair_and_space_geometry(tmp_path):
    from dcbuild import ids
    from dcbuild.ifc import architecture, spatial
    from dcbuild.ifc.builder import Builder
    import ifcopenshell.util.element as element
    import ifcopenshell.util.placement as placement
    plan = layout.resolve(spec.load(variant="floors"))
    b = Builder(plan)
    spatial.build(b, plan)
    architecture.build(b, plan)
    assert element.get_psets(b.storeys['lvl.l2'])['DC_Typical']['Prototype'] == 'lvl.l1'
    assert len(b.file.by_type('IfcStair')) == 3
    assert element.get_container(b.file.by_guid(ids.guid('slab.l1.office'))) == b.storeys['lvl.l1']
    meeting = b.spaces['sp.meeting.1.2']
    assert element.get_psets(meeting)['Qto_SpaceBaseQuantities']['GrossFloorArea'] == 36
    assert placement.get_local_placement(meeting.ObjectPlacement)[2,3] == 7


@pytest.mark.parametrize('variant,counts', [
    ('base',(2,33,92,41,45,0)), ('floors',(3,39,111,47,47,0)),
    ('pod',(2,35,92,41,45,23)), ('clash',(2,35,92,41,45,26)),
    ('iris',(2,33,92,41,45,0))])
def test_variant_resolved_counts(variant,counts):
    p=layout.resolve(spec.load(variant=variant))
    assert (len(p.storeys),len(p.spaces),len(p.walls),len(p.doors),len(p.cameras),len(p.meta.get('fitout',[])))==counts


def test_floors_ground_interface_stops_at_main_roof():
    source=spec.load(variant='floors');p=layout.resolve(source)
    rooms={s.id:s for s in source.spaces.spaces}
    interfaces=[w for w in p.walls if w.left and w.right and
                layout._block_of(source,rooms[w.left])!=layout._block_of(source,rooms[w.right])]
    assert interfaces
    assert all(w.storey=='lvl.l0' and w.height==7 for w in interfaces)


def test_full_union_preserves_rooms_fixtures_and_design():
    from dcbuild import graph
    plan = layout.resolve(spec.load(variant="full"))
    assert not graph.run_all(plan)
    assert (len(plan.storeys), len(plan.spaces), len(plan.walls), len(plan.doors),
            len(plan.columns), len(plan.cameras)) == (3, 41, 111, 47, 80, 47)
    assert sum(s.storey == "lvl.l2" for s in plan.spaces) == 6
    assert sum(s.type == "void" for s in plan.spaces) == 2
    assert len(plan.meta["fitout"]) == 26
    assert plan.meta["expected"]["reader_summary"] == {"pass": 10, "fail": 1}
    assert len(plan.meta["expected"]["clash"]) == 3


def test_multiple_parents_check_cycles(tmp_path):
    import shutil
    shutil.copytree(spec.spec_dir(), tmp_path / "spec")
    directory = tmp_path / "spec"
    (directory / "variants/iris.yaml").write_text("extends: [base, full]\n")
    with pytest.raises(ValueError, match="cycle"):
        spec.load(directory, "full")
