"""Architecture: walls (typed per kind) + openings + doors, floor / roof
slabs, and the office stair.

Patterns ported from dc-examples/dcgen/architecture.py (ifcopenshell 0.8.5),
scaled to the resolved plan:

* every wall is authored on its **centreline** p1 -> p2 — the wall solver puts
  party walls on the shared space-boundary line, so the body must straddle it.
  ``add_wall_representation(offset=-thickness/2)`` + the same placement matrix
  ``create_2pt_wall`` derives (local X along the run) does exactly that;
* a door is an ``IfcOpeningElement`` voiding the host wall
  (``IfcRelVoidsElement``) + an ``IfcDoor`` filling it (``IfcRelFillsElement``),
  generalised from dcgen to walls running along either world axis and to
  storeys above ground;
* slabs are extruded down from ``top_elevation``; the office L01 slab carries
  the stair void in its profile (``voided_slab_rep``).
"""
from __future__ import annotations

import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import numpy as np

from .geom import Z_UP, at, matrix

EPS = 1e-9

# Neutral fabric greys (conventions.md: colour-code systems, greys for fabric).
MATERIAL_RGB = {
    "Precast Concrete Panel": (0.72, 0.72, 0.70),
    "Dense Concrete Blockwork": (0.58, 0.58, 0.56),
    "Metal Stud Partition": (0.86, 0.86, 0.84),
    "Reinforced Concrete": (0.62, 0.62, 0.60),
    "Steel Door Leaf": (0.45, 0.47, 0.50),
}

WALL_PREDEF = {"external": "SOLIDWALL", "fire": "SOLIDWALL", "internal": "PARTITIONING"}
DOOR_PREDEF = {"single": "DOOR", "double": "DOOR", "roller": "GATE"}
# add_door_representation geometry variant per door kind (0.8.5 supported set).
DOOR_OPERATION = {
    "single": "SINGLE_SWING_LEFT",
    "double": "DOUBLE_DOOR_SINGLE_SWING",
    "roller": "DOUBLE_DOOR_SLIDING",
}
SLAB_PREDEF = {"ground": "BASESLAB", "upper": "FLOOR", "roof": "ROOF"}

STAIR_WIDTH = 1.2       # flight / landing width
STAIR_WAIST = 0.3       # slab thickness of flight + landing (vertical)
STAIR_RUN = 1.5         # horizontal run of the flight
STAIR_LANDING = 1.3     # depth of the top landing


# -- shared types ------------------------------------------------------------
def _typed(b, cls, predefined, name, key, material=None, category=None):
    """Get-or-create a shared element type; material bound once, on creation."""
    new = name not in b._types
    t = b.typed(cls, predefined, name, key=key)
    if new and material:
        b.assign_material([t], b.material(material, category, rgb=MATERIAL_RGB.get(material)))
    return t


def _wall_type(b, plan, kind):
    cfg = plan.wall_types[kind]
    return _typed(
        b, "IfcWallType", WALL_PREDEF[kind],
        f"{kind.title()} Wall {int(round(cfg['thickness'] * 1000))}",
        key=f"type.wall.{kind}", material=cfg["material"], category="concrete")


def _door_type(b, d):
    return _typed(
        b, "IfcDoorType", DOOR_PREDEF[d.kind],
        f"Door {d.kind.title()} {int(round(d.width * 1000))}x{int(round(d.height * 1000))}",
        key=f"type.door.{d.kind}", material="Steel Door Leaf", category="steel")


# -- walls -------------------------------------------------------------------
def _add_wall(b, plan, w):
    cfg = plan.wall_types[w.kind]
    wall = b.entity("IfcWall", name=w.id, key=w.id)
    b.assign_type([wall], _wall_type(b, plan, w.kind))

    p1 = np.asarray(w.p1, dtype=float)
    p2 = np.asarray(w.p2, dtype=float)
    v = p2 - p1
    length = float(np.linalg.norm(v))
    v = v / length
    elev = b.storey_elev(w.storey)
    # Body centred on the p1->p2 axis (offset=-t/2), local X along the run —
    # the centreline placement create_2pt_wall's one-sided body doesn't give.
    rep = ifcopenshell.api.geometry.add_wall_representation(
        b.file, context=b.body, length=length, height=w.height,
        thickness=w.thickness, offset=-w.thickness / 2.0)
    b.assign_rep(wall, rep)
    b.contain(wall,
              matrix((v[0], v[1], 0), (-v[1], v[0], 0), (0, 0, 1),
                     (p1[0], p1[1], elev)),
              structure=b.storeys[w.storey])
    b.style_product(wall, cfg["material"])

    b.identify(wall, w.id)
    b.pset(wall, "Pset_WallCommon", {
        "IsExternal": w.kind == "external",
        "LoadBearing": w.kind != "internal",
        "FireRating": cfg["fire_rating"],
    })
    b.quantities(wall, "Qto_WallBaseQuantities", [
        ("Length", "length", length),
        ("Height", "length", w.height),
        ("Width", "length", w.thickness),
        ("GrossSideArea", "area", length * w.height),
        ("GrossVolume", "volume", length * w.height * w.thickness),
    ])
    return wall


# -- openings + doors --------------------------------------------------------
def _add_opening(b, w, wall_el, op, door, vertical, elev):
    """IfcOpeningElement voiding the host wall, centred on the wall line at
    ``op.at``, extruded through the wall (+0.1 m past each face)."""
    key = f"{door.id}.opening"
    opening = b.entity("IfcOpeningElement", predefined="OPENING",
                       name=f"{door.name} Opening", key=key)
    depth = w.thickness + 0.2
    b.assign_rep(opening, b.profile_rep(b.rect_profile(op.width, op.height), depth))
    cx, cy = op.at
    if vertical:      # wall runs along Y: extrude through it along +X
        m = matrix((0, 1, 0), (0, 0, 1), (1, 0, 0),
                   (cx - depth / 2.0, cy, elev + op.height / 2.0))
    else:             # wall runs along X: extrude through it along +Y
        m = matrix((1, 0, 0), (0, 0, -1), (0, 1, 0),
                   (cx, cy - depth / 2.0, elev + op.height / 2.0))
    b.place(opening, m)
    # add_feature re-parents the placement under the wall, preserving world coords
    ifcopenshell.api.feature.add_feature(b.file, feature=opening, element=wall_el)
    b.identify(opening, key)
    return opening


def _add_door(b, plan, d, w, opening, vertical, elev):
    door = b.entity("IfcDoor", predefined=DOOR_PREDEF[d.kind], name=d.name, key=d.id)
    door.OverallHeight, door.OverallWidth = d.height, d.width   # nominal leaf size
    b.assign_type([door], _door_type(b, d))
    drep = ifcopenshell.api.geometry.add_door_representation(
        b.file, context=b.body, overall_height=d.height, overall_width=d.width,
        operation_type=DOOR_OPERATION[d.kind])
    b.assign_rep(door, drep)
    cx, cy = d.pos
    if vertical:      # leaf width along world Y (90 deg CCW about Z)
        m = matrix((0, 1, 0), (-1, 0, 0), (0, 0, 1), (cx, cy - d.width / 2.0, elev))
    else:             # leaf width along world X
        m = matrix((1, 0, 0), (0, 1, 0), (0, 0, 1), (cx - d.width / 2.0, cy, elev))
    if d.id in plan.security.get("iris_mounting", {}):
        from ..layout import NORMALS
        normal = NORMALS[d.approach_normal]
        # Door geometry swings into local +Y. Preserve the threshold centre.
        across = (normal[1], -normal[0])
        m = matrix((*across, 0), (*normal, 0), (0, 0, 1),
                   (cx-across[0]*d.width/2, cy-across[1]*d.width/2, elev))
    b.contain(door, m, structure=b.storeys[d.storey])
    ifcopenshell.api.feature.add_filling(b.file, opening=opening, element=door)
    b.style_product(door, "Steel Door Leaf")

    b.identify(door, d.id)
    props = {"IsExternal": d.external}
    if w.kind == "fire":
        props["FireRating"] = plan.wall_types["fire"]["fire_rating"]
    b.pset(door, "Pset_DoorCommon", props)
    b.properties(door, "DC_DoorApproach", [
        ("ApproachSpace", "IfcIdentifier", d.approach_space),
        ("ApproachNormal", "IfcLabel", d.approach_normal),
        ("ThresholdHeight", "IfcLengthMeasure", d.threshold_height),
    ])
    return door


# -- slabs -------------------------------------------------------------------
def _slab_storey(plan, s):
    block = next(name for name in plan.blocks if name in s.id.split("."))
    rules = plan.meta.get("storey_rules", {})
    candidates = [st for st in plan.storeys if block in rules.get(st.id, {}).get("blocks", [block])
                  and st.elevation <= s.top_elevation + EPS]
    if s.kind == "roof" and not rules:
        return plan.storeys[-1].id if block == "office" else plan.storeys[0].id
    return max(candidates, key=lambda st: st.elevation).id


def _add_slab(b, plan, s):
    slab = b.entity("IfcSlab", predefined=SLAB_PREDEF[s.kind], name=s.id, key=s.id)
    base = s.top_elevation - s.thickness       # top of slab at top_elevation
    if s.voids:
        outer = [(s.x, s.y), (s.x + s.w, s.y), (s.x + s.w, s.y + s.d), (s.x, s.y + s.d)]
        voids = [[(vx, vy), (vx + vw, vy), (vx + vw, vy + vd), (vx, vy + vd)]
                 for vx, vy, vw, vd in s.voids]
        if len(s.voids) == 1 and s.voids[0][0] == s.x and s.voids[0][1]+s.voids[0][3] == s.y+s.d:
            vx, vy, vw, vd = s.voids[0]
            # A notch in the outer loop; no edge-touching inner boundary.
            outline = [(s.x, s.y), (s.x+s.w, s.y), (s.x+s.w, s.y+s.d),
                       (vx+vw, vy+vd), (vx+vw, vy), (vx, vy)]
            rep = b.profile_rep(b.arbitrary_profile(outline), s.thickness)
        else:
            rep = b.voided_slab_rep(s.thickness, outer, voids)
        m = at(Z_UP, (0.0, 0.0, base))         # profile carries world XY
    else:
        rep = b.profile_rep(b.rect_profile(s.w, s.d), s.thickness)
        m = at(Z_UP, (s.x + s.w / 2.0, s.y + s.d / 2.0, base))
    b.assign_rep(slab, rep)
    typical = any(r.get("typical_of") for r in plan.meta.get("storey_rules", {}).values())
    container = b.building if typical and s.kind == "roof" else b.storeys[_slab_storey(plan, s)]
    b.contain(slab, m, structure=container)
    b.assign_material([slab], b.material("Reinforced Concrete", "concrete",
                                         rgb=MATERIAL_RGB["Reinforced Concrete"]))
    b.style_product(slab, "Reinforced Concrete")

    b.identify(slab, s.id)
    b.pset(slab, "Pset_SlabCommon", {
        "IsExternal": s.kind == "roof",
        "LoadBearing": True,
    })
    gross = s.w * s.d
    items = [
        ("Width", "length", s.thickness),
        ("GrossArea", "area", gross),
        ("GrossVolume", "volume", gross * s.thickness),
    ]
    if s.voids:
        net = gross - sum(vw * vd for _x, _y, vw, vd in s.voids)
        items += [("NetArea", "area", net), ("NetVolume", "volume", net * s.thickness)]
    b.quantities(slab, "Qto_SlabBaseQuantities", items)
    return slab


# -- stair -------------------------------------------------------------------
def _add_stair(b, plan, sp, destination, key, *, top_elevation=None):
    """One straight flight L00 -> L01 in the 3x3 m stair shaft, authored as a
    single side-profile extrusion (inclined-slab flight + level top landing in
    one closed polygon, extruded across the flight width), landing top flush
    with the L01 floor."""
    elev = b.storey_elev(sp.storey)
    rise = (b.storey_elev(destination.storey) if top_elevation is None else top_elevation) - elev

    stair = b.entity("IfcStair", predefined="STRAIGHT_RUN_STAIR",
                     name="Office Stair", key=key)
    # Side profile in (u = along run, v = up): flight underside parallel to its
    # top surface (waist measured vertically), landing bottom/top horizontal.
    run, ld, t = STAIR_RUN, STAIR_LANDING, STAIR_WAIST
    profile = b.arbitrary_profile([
        (0.0, 0.0), (run, rise - t), (run + ld, rise - t),
        (run + ld, rise), (run, rise), (0.0, t),
    ])
    b.assign_rep(stair, b.profile_rep(profile, STAIR_WIDTH))
    # u -> world +Y, v -> world +Z, extruded across world +X (the X_RUN frame),
    # flight centred in the shaft, clear of the 150 mm boundary walls.
    x0 = sp.x + (sp.w - STAIR_WIDTH) / 2.0
    y0 = sp.y + 0.1
    b.contain(stair, matrix((0, 1, 0), (0, 0, 1), (1, 0, 0), (x0, y0, elev)),
              structure=b.spaces[sp.id])
    b.assign_material([stair], b.material("Reinforced Concrete", "concrete",
                                          rgb=MATERIAL_RGB["Reinforced Concrete"]))
    b.style_product(stair, "Reinforced Concrete")

    b.identify(stair, key)
    b.pset(stair, "Pset_StairCommon", {"IsExternal": False})
    return stair


# -- module entry ------------------------------------------------------------
def build(b, plan) -> None:
    doors_by_id = {d.id: d for d in plan.doors}
    for w in plan.walls:
        wall = _add_wall(b, plan, w)
        vertical = abs(w.p1[0] - w.p2[0]) < EPS
        elev = b.storey_elev(w.storey)
        for op in w.openings:
            d = doors_by_id[op.door_id]
            opening = _add_opening(b, w, wall, op, d, vertical, elev)
            _add_door(b, plan, d, w, opening, vertical, elev)

    for s in plan.slabs:
        if s.kind == "pad":
            continue                  # site module owns the external pads
        _add_slab(b, plan, s)

    stairs = sorted((s for s in plan.spaces if s.type == "stair"), key=lambda s: b.storey_elev(s.storey))
    for i, (lower, upper) in enumerate(zip(stairs, stairs[1:]), 1):
        _add_stair(b, plan, lower, upper, f"arch.stair.{i}")
    if stairs and plan.meta.get("storey_rules", {}).get(stairs[-1].storey, {}).get("typical_of"):
        # The repeated top storey retains its ascending flight, to roof level.
        roof = next(s for s in plan.slabs if s.id == "slab.roof.office")
        _add_stair(b, plan, stairs[-1], None, f"arch.stair.{len(stairs)}",
                   top_elevation=roof.top_elevation - roof.thickness)
