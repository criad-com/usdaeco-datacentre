import dataclasses
import math
import uuid

import ifcopenshell.guid
import pytest

from dcbuild import graph, ids, layout, spec


@pytest.fixture
def plan():
    return layout.resolve(spec.load())


def test_resolve_is_repeatable(plan):
    assert dataclasses.asdict(plan) == dataclasses.asdict(layout.resolve(spec.load()))
    assert not graph.run_all(plan)


def test_namespace_is_neutral():
    expected = uuid.uuid5(uuid.NAMESPACE_DNS, "usdaeco-datacentre:pwr.msb.a")
    assert ifcopenshell.guid.expand(ids.guid("pwr.msb.a")) == expected.hex


@pytest.mark.parametrize("group,count", [("door", 11), ("ext", 5), ("corr", 18), ("yard", 8), ("lobby", 3)])
def test_camera_census(plan, group, count):
    assert sum(c.id.split(".")[2] == group for c in plan.cameras) == count


def test_door_camera_pose_and_reader_associations(plan):
    doors = {d.id: d for d in plan.doors}
    for entry in plan.security["iris"]:
        d = doors[entry["door"]]
        cam = next(c for c in plan.cameras if c.targets == [d.id])
        nx, ny = layout.NORMALS[d.approach_normal]
        assert cam.pos[:2] == pytest.approx((d.pos[0]+.65*nx-.45*ny, d.pos[1]+.65*ny+.45*nx))
        assert cam.pos[2] == pytest.approx(3.0)
        assert cam.pan == pytest.approx(math.degrees(math.atan2(d.pos[1]-cam.pos[1], d.pos[0]-cam.pos[0])))
        assert cam.tilt == 60 and cam.focal_length == 3 and cam.range == 12
        reader = plan.equip(entry["id"])
        assert reader.space == d.approach_space
        wall = next(w for w in plan.walls if w.id == d.wall_id)
        assert (reader.pos[0]-d.pos[0])*nx + (reader.pos[1]-d.pos[1])*ny > wall.thickness/2


def test_rules_respond_to_spec_edits():
    source = spec.load()
    original = layout.resolve(source)
    source.security.corridor_cameras.max_spacing = 12
    changed = layout.resolve(source)
    assert len(changed.cameras) > len(original.cameras)
    source.security.door_cameras.setback = 1.8
    moved = layout.resolve(source)
    old = next(c for c in changed.cameras if c.id == "sec.cam.door.hall.a.s")
    new = next(c for c in moved.cameras if c.id == old.id)
    assert old.global_id == new.global_id
    assert math.dist(old.pos, new.pos) == pytest.approx(1.15)


def test_upper_corridor_uses_storey_elevation(plan):
    camera = next(c for c in plan.cameras if c.space == "sp.ocorr.1")
    assert camera.pos[2] == pytest.approx(6.9)


def test_ptz_presets_and_tours(plan):
    cams = [c for c in plan.cameras if c.type == "ptz_4k"]
    assert len(cams) == 3
    assert sum(len(c.presets) for c in cams) == 7
    for c in cams:
        assert c.tour[0] == "Home"
        assert set(c.tour) == set(c.presets)
        assert c.presets["Home"]["home"]
        assert c.pan == c.presets["Home"]["pan"]
        assert all(0 <= p["tilt"] <= 90 for p in c.presets.values())
    assert set(cams[-1].presets) == {"Home", "MainDoor", "LobbyCorridor"}


def test_yards_and_targets(plan):
    assert len([s for s in plan.spaces if s.external]) == 3
    assert all(e.space.startswith("sp.yard.") for e in plan.equipment if e.pad)
    targets = plan.targets()
    assert (len(targets["doors"]), len(targets["regions"]), len(targets["cameras"])) == (41, 11, 45)
    assert len({x["GlobalId"] for kind in ("doors", "regions", "cameras") for x in targets[kind]}) == 97


def test_door_plane_optics(plan):
    from dcbuild.qa.design import door_optics
    evidence = door_optics(plan)
    assert len(evidence) == 11 and all(v['passed'] for v in evidence.values())
    assert max(v['maxDistance'] for v in evidence.values()) == pytest.approx(2.945657821268451)
    assert min(v['minDensity'] for v in evidence.values()) == pytest.approx(343.7419528642624)


@pytest.mark.parametrize('field,value', [('pos', (8, 16.3, 5.9)), ('tilt', 0), ('range', 1)])
def test_door_optical_regressions_refused(plan, field, value):
    from dcbuild.qa.design import door_optics
    cam = next(c for c in plan.cameras if c.id.startswith('sec.cam.door.'))
    setattr(cam, field, value)
    assert not door_optics(plan)[cam.id]['passed']


def test_corridor_spacing_and_mounts(plan):
    elevations = {s.id: s.elevation for s in plan.storeys}
    for space in plan.spaces:
        if space.type != 'corridor':
            continue
        cams = [c for c in plan.cameras if c.id.startswith('sec.cam.corr.') and c.space == space.id]
        assert len(cams) % 2 == 0
        for a,b in zip(cams, cams[1:]):
            assert math.dist(a.pos, b.pos) <= 18
            assert abs(a.pan-b.pan) == 180
        assert all(c.pos[2]-elevations[space.storey] == pytest.approx(min(3.5, space.height-.1)) for c in cams)


def test_night_yard_views_are_fixed_ir_bullets(plan):
    for space in [s for s in plan.spaces if s.external]:
        fixed = [c for c in plan.cameras if c.space == space.id and '.fixed.' in c.id]
        assert len(fixed) == 2
        assert all(not plan.security['camera_types'][c.type]['motorised']
                   and plan.security['camera_types'][c.type]['ir_range'] == 40 for c in fixed)
    assert len(plan.cameras) <= 45


def test_door_clearance_and_wall_fit(plan):
    assert min(graph.door_column_clearances(plan).values()) == pytest.approx(0.35)
    for d in plan.doors:
        w = next(w for w in plan.walls if w.id == d.wall_id)
        axis = 1 if w.p1[0] == w.p2[0] else 0
        assert min(w.p1[axis], w.p2[axis]) <= d.pos[axis]-d.width/2
        assert max(w.p1[axis], w.p2[axis]) >= d.pos[axis]+d.width/2


@pytest.mark.parametrize("door_id,position", [
    ("door.hall.b.s", (42, 18)), ("door.corr.c", (36, 18)),
    ("door.elec.a", (6, 15)), ("door.plant", (36, 15)), ("door.elec.b", (66, 15)),
])
def test_original_column_collisions_are_rejected(plan, door_id, position):
    next(d for d in plan.doors if d.id == door_id).pos = position
    assert any(door_id in failure for failure in graph.door_columns(plan))


def test_missing_camera_is_rejected(plan):
    plan.cameras.pop()
    assert graph.camera_rules(plan)


def test_external_primary_door_plane_optics(plan):
    from dcbuild.qa.design import door_optics
    evidence = door_optics(plan, external=True)
    assert len(evidence) == 5 and all(v['passed'] for v in evidence.values())
    assert min(v['minDensity'] for v in evidence.values()) >= 125


def test_shared_approach_reuses_one_camera_and_preserves_every_guid(plan):
    source = spec.load()
    source.security.external_shared_approaches = None
    previous = layout.resolve(source)
    assert {c.id: c.global_id for c in previous.cameras} == {c.id: c.global_id for c in plan.cameras}
    old = {c.id: c for c in previous.cameras}
    changed = [c for c in plan.cameras if c != old[c.id]]
    assert len(changed) == 1
    camera = changed[0]
    assert camera.targets[0] == old[camera.id].targets[0]
    assert len(camera.targets) == 2 and camera.mount == 'pole'
    assert camera.pos != old[camera.id].pos
    assert camera.focal_length == plan.security['camera_types'][camera.type]['focal_range'][1]


@pytest.mark.parametrize('distance', [10, 16.99])
def test_shared_approach_requires_a_nearby_door(distance):
    source = spec.load()
    source.security.external_shared_approaches.max_neighbour_distance = distance
    plan = layout.resolve(source)
    assert not any(len(c.targets) > 1 for c in plan.cameras if c.id.startswith('sec.cam.ext.'))


@pytest.mark.parametrize('normal', ['+Y', '-X', '+X'])
def test_shared_approach_translates_and_rotates_with_facade(normal):
    source = spec.load()
    rule = source.security.external_shared_approaches
    source.security.external_shared_approaches = None
    original = layout.resolve(source)
    reference = layout.resolve(spec.load())
    shared = next(c for c in reference.cameras if c.id.startswith('sec.cam.ext.') and len(c.targets) == 2)
    nx, ny = layout.NORMALS[normal]
    # Rotate the original south-facing facade into each other cardinal frame.
    def xy(point):
        x, y = point
        return (-ny*x-nx*y+11, nx*x-ny*y-7)
    for d in original.doors:
        if d.id in shared.targets:
            d.pos = xy(d.pos)
            d.approach_normal = normal
    layout._share_external_approaches(original, rule, {s.id: s.elevation for s in original.storeys})
    camera = next(c for c in original.cameras if c.id == shared.id)
    assert camera.pos == pytest.approx((*xy(shared.pos[:2]), shared.pos[2]))
    assert camera.pan == pytest.approx(math.degrees(math.atan2(-ny, -nx)))
    assert camera.tilt == pytest.approx(shared.tilt)
    assert camera.targets == shared.targets


@pytest.mark.parametrize('mutation', ['level', 'plane', 'direction'])
def test_shared_approach_rejects_incompatible_facades(mutation):
    source = spec.load()
    rule = source.security.external_shared_approaches
    source.security.external_shared_approaches = None
    plan = layout.resolve(source)
    door = next(d for d in plan.doors if d.id == 'door.plant.ext')
    if mutation == 'level':
        door.storey = 'lvl.l1'
    elif mutation == 'plane':
        door.pos = (door.pos[0], door.pos[1]+.5)
    else:
        door.approach_normal = '+Y'
    layout._share_external_approaches(plan, rule, {s.id: s.elevation for s in plan.storeys})
    assert not any(len(c.targets) > 1 for c in plan.cameras if c.id.startswith('sec.cam.ext.'))


def test_wide_lens_cannot_meet_shared_approach_density(plan):
    from dcbuild.qa.design import door_optics
    camera = next(c for c in plan.cameras if c.id.startswith('sec.cam.ext.') and len(c.targets) == 2)
    camera.focal_length = plan.security['camera_types'][camera.type]['focal_range'][0]
    assert not door_optics(plan, external=True)[camera.id]['passed']
