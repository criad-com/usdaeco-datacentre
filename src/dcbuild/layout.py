"""The resolver: Spec -> Plan.

Turns design intent into a fully-resolved build plan. Everything geometric or
topological that both builders must agree on is decided HERE, once:

  * wall solver — derives every wall segment from the room schedule,
    deduplicating party walls, classifying external/fire/internal, and cutting
    door openings
  * generation — racks, rack rows, PDUs, busways, data trays, TCS manifolds,
    per-rack feed edges, MMR/comms racks, security devices
  * routing — orthogonal (Manhattan) 3D polylines for pipe mains + branches,
    power cabling, and data containment spines, at fixed layer elevations

Deterministic by construction: same spec in, same plan out.
"""
from __future__ import annotations

from collections import defaultdict
import math

from . import ids, footprint
from .model import FIRE_TYPES, Spec
from .plan import (CameraP, ColumnP, DoorP, EdgeP, EquipP, GridLineP, OpeningP, Plan,
                   RackP, RouteP, RowP, RunP, SlabP, SpaceP, StoreyP, SystemP,
                   WallP)

EPS = 1e-6
DELTA = 0.01  # probe offset for the wall solver's side tests

# Footprint (w, d, h) per equipment class; w runs along local X before `rot`.
EQUIP_SIZES: dict[str, tuple[float, float, float]] = {
    "utility_intake": (1.2, 0.8, 1.5),
    "rmu":            (2.0, 1.4, 2.0),
    "transformer":    (2.6, 2.0, 2.3),
    "generator":      (5.5, 2.2, 2.6),
    "fuel_tank":      (3.0, 1.5, 1.8),
    "msb":            (4.0, 1.0, 2.2),
    "ups":            (0.9, 0.9, 2.0),
    "battery":        (2.6, 0.8, 2.0),
    "uob":            (3.0, 1.0, 2.2),
    "pdu":            (0.9, 0.9, 2.0),
    "mcc":            (2.4, 0.8, 2.2),
    "hdb":            (0.8, 0.3, 1.2),
    "dry_cooler":     (3.6, 2.2, 2.5),
    "pump":           (1.2, 0.6, 0.9),
    "buffer_tank":    (1.6, 1.6, 2.6),
    "dosing":         (1.2, 0.8, 1.6),
    "heat_exchanger": (1.5, 0.8, 1.5),
    "chiller":        (3.0, 1.4, 2.0),
    "cdu":            (1.2, 1.0, 2.0),
    "crah":           (2.4, 0.9, 2.4),
    "ahu":            (3.0, 1.6, 2.1),
    "carrier_rack":   (0.6, 1.2, 2.2),
    "ava":            (0.16, 0.16, 0.28),
    "iris":           (0.10, 0.06, 0.16),
}

CYLINDER_CLASSES = {"buffer_tank"}

# Overhead service layers (z, metres above FFL) not already fixed in the spec.
CABLE_TRAY_Z = 5.4       # LV power cabling layer (above pipe layers)
BURIED_Z = -0.5          # external HV/LV cable burial depth
SURFACE_Z = 0.3          # fuel lines on the yard


# ============================================================== wall solver
def _point_space(spaces, px, py):
    for s in spaces:
        if footprint.contains(footprint.vertices(s), px, py):
            return s
    return None


def _solve_storey_walls(spec: Spec, storey_id: str, sid: str):
    """All wall segments for one storey: [(axis, c, a0, a1, left, right)] where
    for axis 'v' the wall is x=c spanning y a0..a1 (left = smaller-x side);
    for axis 'h' the wall is y=c spanning x a0..a1 (left = smaller-y side)."""
    spaces = [s for s in spec.spaces.spaces if s.storey == storey_id and s.type != "void"]
    walls = []
    for axis in ("v", "h"):
        if axis == "v":
            lines = sorted({round(v, 6) for s in spaces for v, _ in footprint.vertices(s)})
            cuts = sorted({round(v, 6) for s in spaces for _, v in footprint.vertices(s)})
        else:
            lines = sorted({round(v, 6) for s in spaces for _, v in footprint.vertices(s)})
            cuts = sorted({round(v, 6) for s in spaces for v, _ in footprint.vertices(s)})
        for c in lines:
            pending = None  # (a0, a1, left, right) being merged
            for a0, a1 in zip(cuts, cuts[1:]):
                mid = (a0 + a1) / 2.0
                if axis == "v":
                    lo = _point_space(spaces, c - DELTA, mid)
                    hi = _point_space(spaces, c + DELTA, mid)
                else:
                    lo = _point_space(spaces, mid, c - DELTA)
                    hi = _point_space(spaces, mid, c + DELTA)
                key = (lo.id if lo else None, hi.id if hi else None)
                if key[0] == key[1]:  # same space (or both outside): no wall
                    seg = None
                else:
                    seg = (a0, a1, lo, hi)
                if seg and pending and abs(pending[1] - a0) < EPS \
                        and (pending[2].id if pending[2] else None) == key[0] \
                        and (pending[3].id if pending[3] else None) == key[1]:
                    pending = (pending[0], a1, pending[2], pending[3])
                else:
                    if pending:
                        walls.append((axis, c, *pending))
                    pending = seg
            if pending:
                walls.append((axis, c, *pending))
    return walls


def _block_of(spec: Spec, space) -> str:
    r = space.rect
    storey = next(s for s in spec.facility.storeys if s.id == space.storey)
    for name in storey.blocks:
        block = spec.facility.building.blocks[name]
        if block.x - EPS <= r.x and r.x + r.w <= block.x + block.w + EPS \
                and block.y - EPS <= r.y and r.y + r.d <= block.y + block.d + EPS:
            return name
    raise ValueError(f"space {space.id} not inside any building block")


def _roof(spec, block):
    return {"elevation": spec.facility.roof.elevation, "thickness": spec.facility.roof.thickness,
            **(spec.facility.roof.model_extra or {}).get(block, {})}


def _wall_height(spec: Spec, storey, left, right) -> float:
    elev = next(s.elevation for s in spec.facility.storeys if s.id == storey)

    def envelope_height(space):
        block = _block_of(spec, space)
        levels = [s.elevation for s in spec.facility.storeys
                  if block in s.blocks and s.elevation > elev + EPS]
        return min([*levels, _roof(spec, block)["elevation"]]) - elev

    if left and right:
        if _block_of(spec, left) != _block_of(spec, right):
            return max(envelope_height(left), envelope_height(right))
        return max(left.height, right.height)
    return envelope_height(left or right)


def _wall_kind(spec: Spec, left, right) -> str:
    if left is None or right is None:
        return "external"
    if left and right and _block_of(spec, left) != _block_of(spec, right):
        return "fire"
    if (left and left.type in FIRE_TYPES) or (right and right.type in FIRE_TYPES):
        return "fire"
    return "internal"


def _validate_spaces(spec: Spec) -> None:
    """Every cell belongs to exactly one room, inside a declared storey block."""
    by_storey = defaultdict(list)
    for space in spec.spaces.spaces:
        if space.type == "void":
            continue
        _block_of(spec, space)
        by_storey[space.storey].append(space)
    for storey in spec.facility.storeys:
        group = by_storey[storey.id]
        xs = sorted({x for s in group for x, _ in footprint.vertices(s)})
        ys = sorted({y for s in group for _, y in footprint.vertices(s)})
        for x0, x1 in zip(xs, xs[1:]):
            for y0, y1 in zip(ys, ys[1:]):
                hits = [s.id for s in group if footprint.contains(footprint.vertices(s), (x0+x1)/2, (y0+y1)/2)]
                if len(hits) > 1:
                    raise ValueError(f"spaces overlap on {storey.id}: {hits}")
        for block in storey.blocks:
            want = storey.expected_areas[block]
            got = sum(footprint.area(footprint.vertices(s)) for s in group if _block_of(spec, s) == block)
            rect = spec.facility.building.blocks[block]
            if abs(want - rect.w*rect.d) > 1e-3 or abs(got-want) > 1e-3:
                raise ValueError(f"{storey.id}/{block}: space areas {got} != block area {want}")


# ============================================================== helpers
def _manhattan(p1, p2, z) -> list[tuple[float, float, float]]:
    """Orthogonal route p1 -> p2 at layer z (X leg first, then Y)."""
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    pts = [(x1, y1, z)]
    if abs(x2 - x1) > EPS:
        pts.append((x2, y1, z))
    if abs(y2 - y1) > EPS:
        pts.append((x2, y2, z))
    if len(pts) == 1:
        pts.append((x2, y2, z))
    return pts


def _nearest_on_polyline(pts, px, py):
    """Nearest point on an axis-aligned polyline (2D projection)."""
    best, best_d = None, None
    for (x1, y1, _z1), (x2, y2, _z2) in zip(pts, pts[1:]):
        if abs(x1 - x2) < EPS:  # vertical in plan
            qx, qy = x1, min(max(py, min(y1, y2)), max(y1, y2))
        else:
            qx, qy = min(max(px, min(x1, x2)), max(x1, x2)), y1
        d = abs(qx - px) + abs(qy - py)
        if best_d is None or d < best_d:
            best, best_d = (qx, qy), d
    return best, best_d


# ============================================================== resolve
def resolve(spec: Spec) -> Plan:
    _validate_spaces(spec)
    fac = spec.facility

    storeys = [StoreyP(s.id, s.name, s.elevation) for s in fac.storeys]
    storey_elev = {s.id: s.elevation for s in fac.storeys}

    # -- grids -------------------------------------------------------------
    grid_lines: list[GridLineP] = []
    gx, gy = fac.grid.x, fac.grid.y
    y_lo, y_hi = gy.start - 2.0, gy.values[-1] + 2.0
    x_lo, x_hi = gx.start - 2.0, gx.values[-1] + 2.0
    for i, v in enumerate(gx.values, start=1):
        grid_lines.append(GridLineP(f"grid.x.{i:02d}", str(i), "x", v, y_lo, y_hi))
    for i, v in enumerate(gy.values):
        label = chr(ord("A") + i)
        grid_lines.append(GridLineP(f"grid.y.{label.lower()}", label, "y", v, x_lo, x_hi))

    # -- spaces ------------------------------------------------------------
    spaces = [SpaceP(s.id, s.name, s.type, s.storey, s.x, s.y, s.w, s.d, s.height)
              for s in spec.spaces.spaces]

    # -- walls + doors -----------------------------------------------------
    walls: list[WallP] = []
    wall_by_id: dict[str, WallP] = {}
    for storey in storey_elev:
        sid = storey.split(".")[-1]
        segs = _solve_storey_walls(spec, storey, sid)
        segs.sort(key=lambda t: (t[0], t[1], t[2]))
        for n, (axis, c, a0, a1, lo, hi) in enumerate(segs, start=1):
            kind = _wall_kind(spec, lo, hi)
            wall = WallP(
                id=f"wall.{sid}.{axis}.{n:03d}",
                storey=storey,
                kind=kind,
                p1=(c, a0) if axis == "v" else (a0, c),
                p2=(c, a1) if axis == "v" else (a1, c),
                height=_wall_height(spec, storey, lo, hi),
                thickness=fac.wall_types[kind].thickness,
                left=lo.id if lo else None,
                right=hi.id if hi else None,
            )
            walls.append(wall)
            wall_by_id[wall.id] = wall

    for edit in spec.wall_edits:
        if edit.id not in wall_by_id:
            raise ValueError(f"wall edit names missing wall {edit.id}")
        if (not all(math.isfinite(v) for p in (edit.p1, edit.p2) for v in p)
                or math.dist(edit.p1, edit.p2) < EPS
                or (abs(edit.p1[0] - edit.p2[0]) > EPS and abs(edit.p1[1] - edit.p2[1]) > EPS)):
            raise ValueError(f"wall edit {edit.id} requires a finite orthogonal axis")
        wall_by_id[edit.id].p1, wall_by_id[edit.id].p2 = edit.p1, edit.p2

    doors: list[DoorP] = []
    door_by_id: dict[str, DoorP] = {}
    space_by_id = {s.id: s for s in spec.spaces.spaces}
    for d in spec.spaces.doors:
        pair = set(d.between)
        anchor_space = next(s for s in d.between if s != "EXT")
        storey = space_by_id[anchor_space].storey
        kind_cfg = spec.spaces.door_kinds[d.kind]
        width = d.width or kind_cfg.width
        height = d.height or kind_cfg.height
        px, py = d.at
        hit = None
        for w in walls:
            if w.storey != storey:
                continue
            (x1, y1), (x2, y2) = w.p1, w.p2
            on = (abs(px - x1) < EPS and min(y1, y2) - EPS <= py <= max(y1, y2) + EPS) \
                if abs(x1 - x2) < EPS else \
                (abs(py - y1) < EPS and min(x1, x2) - EPS <= px <= max(x1, x2) + EPS)
            if not on:
                continue
            sides = {w.left or "EXT", w.right or "EXT"}
            if sides == pair:
                hit = w
                break
        if hit is None:
            raise ValueError(f"door {d.id}: no wall between {d.between} through {d.at}")
        hit.openings.append(OpeningP(d.id, d.at, width, height))
        door = DoorP(d.id, d.name or d.id, d.kind, hit.id, storey, d.at, width, height,
                     external="EXT" in pair)
        doors.append(door)
        door_by_id[d.id] = door

    # -- columns -----------------------------------------------------------
    col_pts: set[tuple[float, float]] = set()
    main, office = fac.building.blocks["main"], fac.building.blocks["office"]
    for v in gx.values:
        if main.x - EPS <= v <= main.x2 + EPS:
            col_pts.update({(v, main.y), (v, main.y2)})
        if office.x - EPS <= v <= office.x2 + EPS:
            col_pts.add((v, office.y))
    for v in gy.values:
        if main.y - EPS <= v <= main.y2 + EPS:
            col_pts.update({(main.x, v), (main.x2, v)})
        if office.y - EPS <= v <= office.y2 + EPS:
            col_pts.update({(office.x, v), (office.x2, v)})
    for yline in fac.structure.internal_lines.get("y", []):
        col_pts.update({(v, yline) for v in gx.values if main.x - EPS <= v <= main.x2 + EPS})
    for xline in fac.structure.internal_lines.get("x", []):
        col_pts.update({(xline, v) for v in gy.values if main.y - EPS <= v <= main.y2 + EPS})
    columns = [ColumnP(f"col.{i:03d}", pt, max(_roof(spec, name)["elevation"] for name, block in fac.building.blocks.items()
                       if block.contains(*pt)), fac.structure.column.size)
               for i, pt in enumerate(sorted(col_pts), start=1)]

    # -- slabs -------------------------------------------------------------
    slabs: list[SlabP] = []
    g = fac.slabs["ground"].thickness
    u = fac.slabs["upper"].thickness
    r = fac.roof.thickness
    slabs.append(SlabP("slab.ground.main", "ground", main.x, main.y, main.w, main.d, 0.0, g))
    slabs.append(SlabP("slab.ground.office", "ground", office.x, office.y, office.w, office.d, 0.0, g))
    for storey in fac.storeys[1:]:
        for block_name in storey.blocks:
            block = fac.building.blocks[block_name]
            stairs = [s for s in spec.spaces.spaces if s.storey == storey.id
                      and s.type == "stair" and _block_of(spec, s) == block_name]
            key = f"slab.{storey.id.split('.')[-1]}.{block_name}"
            if fac.split_upper_slabs and stairs:
                stair = stairs[0]
                if abs(stair.x-block.x) > EPS or abs(stair.y+stair.d-block.y2) > EPS:
                    raise ValueError("split slab requires a stair at the northwest corner")
                slabs.append(SlabP(key+".s", "upper", block.x, block.y, block.w,
                                   stair.y-block.y, storey.elevation, u))
                slabs.append(SlabP(key+".n", "upper", stair.x+stair.w, stair.y,
                                   block.x2-stair.x-stair.w, stair.d, storey.elevation, u))
            else:
                slabs.append(SlabP(key, "upper", block.x, block.y, block.w, block.d,
                                   storey.elevation, u, [(s.x, s.y, s.w, s.d) for s in stairs]))
    for name, block in fac.building.blocks.items():
        roof = _roof(spec, name)
        slabs.append(SlabP(f"slab.roof.{name}", "roof", block.x, block.y, block.w, block.d,
                           roof["elevation"] + roof["thickness"], roof["thickness"]))
    for pad in fac.external_works.pads:
        slabs.append(SlabP(pad.id, "pad", pad.x, pad.y, pad.w, pad.d, 0.0, pad.thickness))

    # -- IT: rows / racks / PDUs / busways / trays / manifolds -------------
    rows: list[RowP] = []
    racks: list[RackP] = []
    runs: list[RunP] = []
    routes: list[RouteP] = []
    edges: list[EdgeP] = [EdgeP(e.src, e.dst, e.kind, f"sys.pwr.{_side_of(spec, e.src)}")
                          for e in spec.power.edges]
    equipment: list[EquipP] = []

    it = spec.it
    cool = spec.cooling
    pw = spec.power
    tray_w, tray_h = it.containment.tray_size
    man_cfg = spec.cooling.tcs_manifolds

    for hall in it.halls:
        hs = space_by_id[hall.space]
        rt = it.rack_types[hall.rack_type]
        short = hall.id.split(".")[-1]                      # a | b
        span = (hall.racks_per_row - 1) * hall.rack_pitch
        cx = hs.x + hs.w / 2.0
        first_x = cx - span / 2.0
        rack_xs = [first_x + i * hall.rack_pitch for i in range(hall.racks_per_row)]
        x_start = rack_xs[0] - rt.width / 2.0
        x_end = rack_xs[-1] + rt.width / 2.0
        if x_start < hs.x + hall.row_x_margin - EPS or x_end > hs.x + hs.w - hall.row_x_margin + EPS:
            raise ValueError(f"{hall.id}: rack row exceeds x margins")

        for rix in range(1, hall.rows + 1):
            row_y = hall.first_row_y + (rix - 1) * hall.row_pitch
            row_id = f"it.row.{short}{rix}"
            rows.append(RowP(row_id, hall.id, hall.space, rix, row_y, x_start, x_end,
                             rack_xs, hall.cooling))
            for i, rx in enumerate(rack_xs, start=1):
                racks.append(RackP(ids.sub(f"rack.{short}.r{rix}", i), hall.id, row_id,
                                   i, (rx, row_y), (rt.width, rt.depth, rt.height),
                                   hall.rack_kw, hall.space, hall.cooling))

            # PDUs: side A west end, side B east end
            rule = pw.pdu_rules[hall.id]
            for side, px in (("A", x_start - rule.offset_from_row_end),
                             ("B", x_end + rule.offset_from_row_end)):
                pdu_id = f"pwr.pdu.{side.lower()}.{short}{rix}"
                equipment.append(EquipP(pdu_id, "pdu", f"PDU-{side}-{short.upper()}{rix}",
                                        "power", hall.space, None, (px, row_y, 0.0),
                                        EQUIP_SIZES["pdu"], 0.0, side=side,
                                        rating={"rating_kva": rule.rating_kva}))
                edges.append(EdgeP(f"pwr.uob.{side.lower()}", pdu_id, "lv_cable",
                                   f"sys.pwr.{side.lower()}"))
                uob = next(n for n in pw.nodes if n.id == f"pwr.uob.{side.lower()}")
                routes.append(RouteP(f"rt.{pdu_id}", "cable", f"sys.pwr.{side.lower()}",
                                     _feeder_route(uob.pos, (px, row_y)),
                                     from_id=uob.id, to_id=pdu_id))

                # Busway above the row, spanning from its PDU across every rack
                bw_id = f"it.bw.{side.lower()}.{short}{rix}"
                y_off = pw.busway.y_offset[side]
                bx0, bx1 = (px, x_end) if side == "A" else (x_start, px)
                runs.append(RunP(bw_id, "busway", row_id, side, row_y + y_off, pw.busway.z,
                                 bx0, bx1, rack_xs, (0.25, 0.15), "box", feed=pdu_id))
                edges.append(EdgeP(pdu_id, bw_id, "busway_feed", f"sys.pwr.{side.lower()}"))
                for i, rx in enumerate(rack_xs, start=1):
                    edges.append(EdgeP(bw_id, ids.sub(f"rack.{short}.r{rix}", i),
                                       "rack_cord", f"sys.pwr.{side.lower()}"))

            # Data tray above the row
            runs.append(RunP(f"it.tray.{short}.r{rix}", "tray", row_id, None, row_y,
                             it.containment.tray_z, x_start, x_end, rack_xs,
                             (tray_w, tray_h), "box"))

            # TCS manifolds (DLC halls only)
            if hall.cooling == "dlc":
                feed_x = x_start - 1.0
                sup_y = row_y + man_cfg["y_offset"]["supply"]
                ret_y = row_y + man_cfg["y_offset"]["return"]
                z_s, z_r = cool.elevations["tcs_supply"], cool.elevations["tcs_return"]
                runs.append(RunP(f"clg.man.{short}.r{rix}.s", "manifold_supply", row_id,
                                 None, sup_y, z_s, feed_x, x_end, rack_xs,
                                 (cool.pipe_diameters["tcs_manifold"],) * 2, "pipe"))
                runs.append(RunP(f"clg.man.{short}.r{rix}.r", "manifold_return", row_id,
                                 None, ret_y, z_r, feed_x, x_end, rack_xs,
                                 (cool.pipe_diameters["tcs_manifold"],) * 2, "pipe"))
                hall_hdr_y = cool.routing["fws"]["hall_header_y"]
                routes.append(RouteP(f"rt.clg.man.{short}.r{rix}.feed.s", "pipe", "sys.tcs.supply",
                                     [(feed_x, hall_hdr_y, z_s), (feed_x, sup_y, z_s)]))
                routes.append(RouteP(f"rt.clg.man.{short}.r{rix}.feed.r", "pipe", "sys.tcs.return",
                                     [(feed_x, ret_y, z_r), (feed_x, hall_hdr_y, z_r)]))

        # Data containment spine: rows collect to a spine, cross the corridor,
        # drop into the serving MMR.
        route = it.containment.routes[hall.id]
        tz = it.containment.tray_z
        top_row_y = hall.first_row_y + (hall.rows - 1) * hall.row_pitch
        mx, my = route.mmr_entry
        routes.append(RouteP(f"rt.it.spine.{short}", "tray", f"sys.data.{short}",
                             [(route.spine_x, top_row_y, tz),
                              (route.spine_x, route.corridor_y, tz),
                              (mx, route.corridor_y, tz),
                              (mx, my, tz)],
                             size=tuple(it.containment.spine_tray_size)))
        for rix in range(1, hall.rows + 1):
            row_y = hall.first_row_y + (rix - 1) * hall.row_pitch
            routes.append(RouteP(f"rt.it.spine.{short}.r{rix}", "tray", f"sys.data.{short}",
                                 [(route.spine_x, row_y, tz), (x_start, row_y, tz)],
                                 size=tuple(it.containment.tray_size)))

    # -- MMR + office comms racks -----------------------------------------
    for mmr in it.meet_me_rooms:
        ms = space_by_id[mmr.space]
        rt = it.rack_types[mmr.rack_type]
        for i in range(1, mmr.racks + 1):
            equipment.append(EquipP(
                ids.sub(f"it.{mmr.id.replace('.', '')}.r", i).replace(".r.", ".r"),
                "carrier_rack", f"{mmr.id.upper()} Rack {i}", "it", mmr.space, None,
                (ms.x + 0.75, ms.y + 2.0 + (i - 1) * 1.5, 0.0),
                (rt.width, rt.depth, rt.height), 90.0))
    comms = space_by_id[it.office_it["comms_space"]]
    for i in (1, 2):
        equipment.append(EquipP(f"it.comms.r{i:02d}", "carrier_rack", f"Office Comms Rack {i}",
                                "it", comms.id, None,
                                (comms.x + 0.75, comms.y + 1.5 + (i - 1) * 1.5, 0.0),
                                (0.6, 1.2, 2.2), 90.0))
    routes.append(RouteP("rt.it.office", "tray", "sys.data.off",
                         [(comms.x + 2.0, comms.y + 2.0, it.office_it["tray_z"]),
                          (comms.x + 2.0, -1.5, it.office_it["tray_z"]),
                          (16.5, -1.5, it.office_it["tray_z"])],
                         size=tuple(it.containment.tray_size)))

    # -- power + cooling equipment ----------------------------------------
    for n in pw.nodes:
        equipment.append(EquipP(n.id, n.cls, n.name, "power", n.space, n.pad, n.pos,
                                EQUIP_SIZES[n.cls], 0.0,
                                shape="cylinder" if n.cls in CYLINDER_CLASSES else "box",
                                side=n.side, rating=n.rating()))
    for n in cool.nodes:
        rot = 90.0 if n.cls == "crah" else 0.0
        equipment.append(EquipP(n.id, n.cls, n.name, "cooling", n.space, n.pad, n.pos,
                                EQUIP_SIZES[n.cls], rot,
                                shape="cylinder" if n.cls in CYLINDER_CLASSES else "box",
                                loop=n.loop, rating=n.rating()))

    # -- power cable routes (spec edges) ----------------------------------
    node_by_id = {n.id: n for n in pw.nodes}
    for e in spec.power.edges:
        a, b = node_by_id[e.src], node_by_id[e.dst]
        if e.kind == "fuel_line":
            z = SURFACE_Z
        elif a.space == "EXT" or b.space == "EXT":
            z = BURIED_Z
        else:
            z = CABLE_TRAY_Z
        routes.append(RouteP(f"rt.{e.src}--{e.dst}", "cable", f"sys.pwr.{a.side.lower()}",
                             _manhattan(a.pos, b.pos, z), from_id=e.src, to_id=e.dst))

    # -- mechanical power feeds -------------------------------------------
    cool_by_id = {n.id: n for n in cool.nodes}
    for mcc_id, loads in pw.mech_feeds.items():
        side = node_by_id[mcc_id].side.lower()
        for load in loads:
            ln = cool_by_id[load]
            z = BURIED_Z if ln.space == "EXT" else CABLE_TRAY_Z
            edges.append(EdgeP(mcc_id, load, "lv_cable", f"sys.pwr.{side}"))
            routes.append(RouteP(f"rt.{mcc_id}--{load}", "cable", f"sys.pwr.{side}",
                                 _manhattan(node_by_id[mcc_id].pos, ln.pos, z),
                                 from_id=mcc_id, to_id=load))

    # -- cooling pipe mains + branches ------------------------------------
    routes.extend(_cooling_routes(spec, cool_by_id))

    # -- security ----------------------------------------------------------
    sec = {"ava": [], "iris": []}
    for sp_id in spec.security.ava_spaces:
        s = space_by_id[sp_id]
        dev_id = f"sec.ava.{sp_id.removeprefix('sp.')}"
        pos = (s.x + s.w / 2.0, s.y + s.d / 2.0, s.height - 0.3)
        equipment.append(EquipP(dev_id, "ava", f"AVA {s.name}", "security", sp_id, None,
                                pos, EQUIP_SIZES["ava"], 0.0))
        sec["ava"].append({"id": dev_id, "space": sp_id})
    for door_id in spec.security.iris_doors:
        d = door_by_id[door_id]
        w = wall_by_id[d.wall_id]
        vertical = abs(w.p1[0] - w.p2[0]) < EPS
        mount = spec.security.iris_readers.model_dump()
        override = spec.security.iris_reader_overrides.get(door_id)
        if override:
            mount.update(override.model_dump(exclude_none=True))
        offset = mount["door_edge_offset"]
        off = (0.0, d.width / 2.0 + offset) if vertical else (d.width / 2.0 + offset, 0.0)
        dev_id = f"sec.iris.{door_id.removeprefix('door.')}"
        height = mount["height"] - (EQUIP_SIZES["iris"][2]/2 if mount["reference"] == "centre" else 0)
        pos = (d.pos[0] + off[0], d.pos[1] + off[1], storey_elev[d.storey]+height)
        equipment.append(EquipP(dev_id, "iris", f"Iris Scanner {door_id}", "security",
                                w.left or w.right, None, pos, EQUIP_SIZES["iris"],
                                0.0 if vertical else 90.0))
        sec["iris"].append({"id": dev_id, "door": door_id})
        if mount["reference"] == "centre":
            sec.setdefault("iris_mounting", {})[door_id] = {"MountingHeight": height+EQUIP_SIZES["iris"][2]/2,
                                                            "DoorEdgeOffset": offset, "Side": mount["side"]}

    # -- systems -----------------------------------------------------------
    systems = [
        SystemP("sys.pwr.a", "Power Train A", "ELECTRICAL", "A"),
        SystemP("sys.pwr.b", "Power Train B", "ELECTRICAL", "B"),
        SystemP("sys.fws", "Facility Water System", "CONDENSERWATER"),
        SystemP("sys.tcs", "Technology Cooling System (Hall A)", "COOLING"),
        SystemP("sys.chw", "Chilled Water", "CHILLEDWATER"),
        SystemP("sys.data.a", "Data Containment Hall A", "DATA"),
        SystemP("sys.data.b", "Data Containment Hall B", "DATA"),
        SystemP("sys.data.off", "Office Structured Cabling", "DATA"),
        SystemP("sys.sec", "Physical Security", "SECURITY"),
    ]

    # Yards share the pad footprints but have distinct spatial identities.
    for pad in fac.external_works.pads:
        spaces.append(SpaceP("sp.yard." + pad.id.removeprefix("pad."), pad.name,
                             "yard", "site", pad.x, pad.y, pad.w, pad.d,
                             spec.security.yard_cameras.height, external=True))
    for e in equipment:
        if e.space == "EXT" and e.pad:
            e.space = "sp.yard." + e.pad.removeprefix("pad.")
    sec["camera_types"] = {k: v.model_dump() for k, v in spec.security.camera_types.items()}
    sec["rules"] = {name: getattr(spec.security, name).model_dump() for name in
                    ("door_cameras", "external_door_cameras", "corridor_cameras", "yard_cameras",
                     "yard_fixed_cameras", "lobby_ptz", "lobby_fixed_cameras")}
    if spec.security.external_shared_approaches is not None:
        sec["rules"]["external_shared_approaches"] = spec.security.external_shared_approaches.model_dump()
    plan = Plan(
        meta={"code": fac.project.code, "name": fac.project.name,
              "description": fac.project.description, "generator": "dcbuild",
              "capacity_kw": dict(pw.capacity_kw)},
        storeys=storeys,
        roof=fac.roof.model_dump(),
        grid_lines=grid_lines,
        blocks={k: v.model_dump() for k, v in fac.building.blocks.items()},
        wall_types={k: v.model_dump() for k, v in fac.wall_types.items()},
        heights=dict(fac.heights),
        spaces=spaces,
        walls=walls,
        doors=doors,
        columns=columns,
        slabs=slabs,
        equipment=equipment,
        racks=racks,
        rows=rows,
        runs=runs,
        routes=routes,
        edges=edges,
        systems=systems,
        redundancy_groups=[rg.model_dump() for rg in cool.redundancy_groups],
        mech_feeds=dict(pw.mech_feeds),
        security=sec,
        cooling_cfg={"elevations": dict(cool.elevations),
                     "pipe_diameters": dict(cool.pipe_diameters),
                     "routing": dict(cool.routing),
                     "tcs_manifolds": dict(cool.tcs_manifolds)},
        it_cfg={"containment": spec.it.containment.model_dump(),
                "office_it": dict(spec.it.office_it)},
    )
    if spec.variant != "base":
        plan.meta.update(variant=spec.variant, expected=spec.expected,
                         storey_rules={s.id: s.model_dump() for s in fac.storeys},
                         space_geometry={s.id: {"footprint": s.footprint, "z_offset": s.z_offset, "parent": s.parent}
                                         for s in spec.spaces.spaces if s.footprint or s.z_offset or s.parent})
    if spec.publication:
        plan.meta["publication"] = spec.publication
    if spec.fitout:
        plan.meta["fitout"] = spec.fitout.model_dump(mode="json")["elements"]
    if spec.programme:
        plan.meta["programme"] = spec.programme.model_dump(mode="json")
    _resolve_cameras(plan, spec)
    return plan


NORMALS = {"+X": (1, 0), "-X": (-1, 0), "+Y": (0, 1), "-Y": (0, -1)}


def _resolve_cameras(plan: Plan, spec: Spec) -> None:
    """Resolve every device frame, approach, optical driver and PTZ target once."""
    security = spec.security
    spaces = {s.id: s for s in plan.spaces}
    walls = {w.id: w for w in plan.walls}
    elevations = {s.id: s.elevation for s in plan.storeys}
    yards = [s for s in plan.spaces if s.external]

    def nearest_yard(pos):
        def distance(s):
            dx = max(s.x-pos[0], 0, pos[0]-s.x-s.w)
            dy = max(s.y-pos[1], 0, pos[1]-s.y-s.d)
            return (math.hypot(dx, dy), s.id)
        return min(yards, key=distance)

    for d in plan.doors:
        w = walls[d.wall_id]
        vertical = abs(w.p1[0]-w.p2[0]) < EPS
        if d.external:
            sign = -1 if w.left is None else 1
            d.approach_space = nearest_yard(d.pos).id
        else:
            candidates = [spaces[s] for s in (w.left, w.right) if s]
            # Corridors first; prefer the technical corridor at a block link.
            approach = min(candidates, key=lambda s: (
                {"corridor": 0, "lobby": 1}.get(s.type, 2), -s.height, s.id))
            d.approach_space = approach.id
            sign = -1 if w.left == approach.id else 1
        d.approach_normal = ("+" if sign > 0 else "-") + ("X" if vertical else "Y")

    # Reader identity/association stays stable when a door moves.
    for entry in plan.security["iris"]:
        d = next(d for d in plan.doors if d.id == entry["door"])
        reader = plan.equip(entry["id"])
        reader.space = d.approach_space
        normal = NORMALS[d.approach_normal]
        mount = plan.security.get("iris_mounting", {}).get(d.id, {})
        if mount.get("Side") == "push":
            normal = tuple(-v for v in normal)
            wall = walls[d.wall_id]
            reader.space = wall.right if reader.space == wall.left else wall.left
        standoff = walls[d.wall_id].thickness / 2 + 0.04
        reader.pos = (reader.pos[0] + normal[0]*standoff,
                      reader.pos[1] + normal[1]*standoff, reader.pos[2])

    def add(key, rule, space, pos, pan, scenario, mount, targets):
        typ = security.camera_types[rule.type]
        cam = CameraP(key, ids.guid(key), rule.type, space, tuple(pos), pan,
                      rule.tilt, rule.focal_length or typ.focal_range[0], rule.range, scenario, mount, targets,
                      target_density=typ.target_density)
        plan.cameras.append(cam)
        return cam

    for d in plan.doors:
        if d.external:
            rule, prefix, mount = security.external_door_cameras, "ext", "wall"
        elif d.id in security.iris_doors:
            rule, prefix, mount = security.door_cameras, "door", "pendant"
        else:
            continue
        normal = NORMALS[d.approach_normal]
        space = spaces[d.approach_space]
        z = elevations[d.storey] + (rule.height if rule.height is not None else space.height-rule.ceiling_offset)
        pos = (d.pos[0]+normal[0]*rule.setback-normal[1]*rule.lateral_offset,
               d.pos[1]+normal[1]*rule.setback+normal[0]*rule.lateral_offset, z)
        pan = math.degrees(math.atan2(d.pos[1]-pos[1], d.pos[0]-pos[0]))
        add(f"sec.cam.{prefix}.{d.id.removeprefix('door.')}", rule, space.id, pos, pan, "door", mount, [d.id])

    support = security.external_shared_approaches
    if support is not None:
        _share_external_approaches(plan, support, elevations)

    rule = security.corridor_cameras
    for s in plan.spaces:
        if s.type != "corridor":
            continue
        compact = max(s.w, s.d) <= 1.5 * min(s.w, s.d)
        along_x = s.w >= s.d and not compact
        count = 2 * max(1, math.ceil(max(s.w, s.d)/rule.max_spacing/2))
        # Include both ends and retain the existing numbered identities.
        if max(s.w, s.d) > rule.max_spacing * (count - 1):
            count += 2
        for n in range(count):
            distance = rule.corner_inset + (max(s.w, s.d)-2*rule.corner_inset)*n/(count-1)
            pos = (s.x+(distance if along_x else s.w/2),
                   s.y+(s.d/2 if along_x else distance),
                   elevations[s.storey]+min(rule.height, s.height-rule.ceiling_offset))
            cam = add(f"sec.cam.corr.{s.id.removeprefix('sp.')}.{n+1}", rule, s.id, pos,
                (0.0 if along_x else 90.0) + (180 if n % 2 else 0), "corridor", "pendant", [s.id])
            if compact:
                cam.tilt = rule.compact_tilt
                cam.focal_length = security.camera_types[rule.type].focal_range[0]

    # Opposing fixed views supplement PTZ tours; every pad gets the same rule.
    rule = security.yard_fixed_cameras
    for s in yards:
        block = plan.blocks["main"]
        west = s.x+s.w/2 < block["x"]+block["w"]/2
        for n in range(2):
            inset = rule.corner_inset
            pos = (s.x+(s.w-inset if n else inset),
                   s.y+(s.d-inset if bool(n) != west else inset), rule.height)
            pan = math.degrees(math.atan2(s.y+s.d/2-pos[1], s.x+s.w/2-pos[0]))
            add(f"sec.cam.yard.{s.id.removeprefix('sp.yard.')}.fixed.{n+1}", rule,
                s.id, pos, pan, "plant", "pole", [s.id])

    rule = security.lobby_fixed_cameras
    for s in plan.spaces:
        if s.type != "lobby":
            continue
        for n in range(2):
            inset = rule.corner_inset
            pos = (s.x+(s.w-inset if n else inset),
                   s.y+(s.d-inset if n else inset), elevations[s.storey]+rule.height)
            pan = math.degrees(math.atan2(s.y+s.d/2-pos[1], s.x+s.w/2-pos[0]))
            add(f"sec.cam.lobby.fixed.{n+1}", rule, s.id, pos, pan, "lobby", "corner", [s.id])

    def preset(cam, name, point, home=False):
        dx, dy, dz = (point[i]-cam.pos[i] for i in range(3))
        cam.presets[name] = {"pan": math.degrees(math.atan2(dy, dx)),
                             "tilt": math.degrees(math.atan2(-dz, math.hypot(dx, dy))),
                             "focalLength": cam.focal_length, "dwell": 4.0, "home": home}
        cam.tour.append(name)
        if home:
            cam.pan, cam.tilt = cam.presets[name]["pan"], cam.presets[name]["tilt"]

    rule = security.yard_cameras
    for s in yards:
        if not s.id.startswith("sp.yard.gen."):
            continue
        side = s.id.rsplit(".", 1)[-1]
        pos = (s.x+rule.corner_inset, s.y+rule.corner_inset, rule.height)
        cam = add(f"sec.cam.yard.{side}", rule, s.id, pos, 0, "plant", "pole", [s.id])
        preset(cam, "Home", (s.x+s.w/2, s.y+s.d/2, 1.6), home=True)
        for pad in spec.facility.external_works.pads:
            if "sp.yard."+pad.id.removeprefix("pad.") == s.id:
                preset(cam, "Pad_"+pad.id.removeprefix("pad.").replace(".", "_"),
                       (pad.x+pad.w/2, pad.y+pad.d/2, pad.thickness))

    rule = security.lobby_ptz
    for s in plan.spaces:
        if s.type != "lobby":
            continue
        pos = (s.x+rule.corner_inset, s.y+s.d-rule.corner_inset,
               elevations[s.storey]+rule.height)
        cam = add("sec.cam.lobby", rule, s.id, pos, 0, "lobby", "corner", [s.id])
        preset(cam, "Home", (s.x+s.w/2, s.y+s.d/2, elevations[s.storey]+1.6), home=True)
        for d in plan.doors:
            w = walls[d.wall_id]
            if s.id not in (w.left, w.right):
                continue
            if d.external:
                name = "MainDoor"
            elif any(spaces[sid].type == "corridor" for sid in (w.left, w.right) if sid):
                name = "LobbyCorridor"
            else:
                continue
            preset(cam, name, (*d.pos, elevations[d.storey]+d.threshold_height))
            cam.targets.append(d.id)


def _share_external_approaches(plan: Plan, rule, elevations) -> None:
    """A wide opening's existing bullet also watches its nearest small door.

    Only same-level, coplanar, equally outward-facing doors can share a view.
    Centre the pole between the small door's threshold and the wide opening's
    far jamb: the small door retains its close bullet, while the wide opening
    needs its whole face in this view. No new camera or identity is introduced.
    The family scene study, not this geometric selection, proves visibility.
    """
    exterior = [d for d in plan.doors if d.external]
    for door in exterior:
        if door.width < rule.min_width:
            continue
        normal = NORMALS[door.approach_normal]
        across = (-normal[1], normal[0])
        neighbours = [d for d in exterior
                      if d.width < rule.min_width and d.storey == door.storey
                      and d.approach_normal == door.approach_normal
                      and abs(sum((d.pos[i]-door.pos[i])*normal[i] for i in range(2))) < EPS
                      and EPS < math.dist(d.pos, door.pos) <= rule.max_neighbour_distance]
        if not neighbours:
            continue
        neighbour = min(neighbours, key=lambda d: (math.dist(d.pos, door.pos), d.id))
        direction = math.copysign(1, sum((door.pos[i]-neighbour.pos[i])*across[i] for i in range(2)))
        far_jamb = tuple(door.pos[i]+across[i]*direction*door.width/2 for i in range(2))
        aim = tuple((neighbour.pos[i]+far_jamb[i])/2 for i in range(2))
        camera = next(c for c in plan.cameras if c.targets == [door.id])
        camera.pos = (*[aim[i]+normal[i]*rule.setback for i in range(2)],
                      elevations[door.storey]+rule.height)
        camera.pan = math.degrees(math.atan2(-normal[1], -normal[0]))
        camera.tilt = math.degrees(math.atan2(rule.height-rule.aim_height, rule.setback))
        camera.focal_length = rule.focal_length
        camera.mount = "pole"
        camera.targets.append(neighbour.id)


def _side_of(spec: Spec, node_id: str) -> str:
    n = next(n for n in spec.power.nodes if n.id == node_id)
    return n.side.lower()


def _feeder_route(uob_pos, pdu_xy) -> list[tuple[float, float, float]]:
    """UOB (electrical room) -> in-hall PDU at the LV cable layer, entering the
    hall on the PDU's x so the run crosses the spine corridor cleanly."""
    ux, uy = float(uob_pos[0]), float(uob_pos[1])
    px, py = float(pdu_xy[0]), float(pdu_xy[1])
    z = CABLE_TRAY_Z
    return [(ux, uy, z), (ux, 16.5, z), (px, 16.5, z), (px, py, z)]


def _cooling_routes(spec: Spec, cool_by_id) -> list[RouteP]:
    cool = spec.cooling
    e = cool.elevations
    dia = cool.pipe_diameters
    fws = cool.routing["fws"]
    chw = cool.routing["chw"]
    routes: list[RouteP] = []

    def pair(base_id, system, pts, diameter, dz=0.3):
        """Author supply + return as a stacked pair (return dz above supply)."""
        routes.append(RouteP(f"{base_id}.s", "pipe", f"{system}.supply", pts, diameter=diameter))
        routes.append(RouteP(f"{base_id}.r", "pipe", f"{system}.return",
                             [(x, y, z + dz) for x, y, z in pts], diameter=diameter))

    # FWS: dry-cooler yard header -> penetration -> plant riser -> spine
    # crossing -> Hall A CDU header.
    drcs = [n for n in cool.nodes if n.cls == "dry_cooler"]
    yard_y = fws["yard_header_y"]
    yz = e["yard_header"]
    xs = sorted(n.pos[0] for n in drcs)
    pair("rt.clg.fws.yard", "sys.fws", [(xs[0], yard_y, yz), (xs[-1], yard_y, yz)], dia["fws_main"])
    for n in drcs:
        pair(f"rt.{n.id}", "sys.fws", [(n.pos[0], yard_y, yz), (n.pos[0], n.pos[1], yz)],
             dia["fws_branch"])

    pen_x, pen_y = fws["wall_penetration"]
    riser_x, riser_y = fws["plant_riser"]
    sx = fws["spine_crossing_x"]
    hy = fws["hall_header_y"]
    hz = e["fws_header"]
    cdus = [n for n in cool.nodes if n.cls == "cdu"]
    hdr_x_end = min(n.pos[0] for n in cdus)
    main_pts = [(pen_x, yard_y, yz), (riser_x, riser_y, yz), (riser_x, riser_y, hz),
                (sx, riser_y, hz), (sx, hy, hz), (hdr_x_end, hy, hz)]
    pair("rt.clg.fws.main", "sys.fws", main_pts, dia["fws_main"])
    for n in cdus:
        pair(f"rt.{n.id}.pri", "sys.fws", [(n.pos[0], hy, hz), (n.pos[0], n.pos[1], hz)],
             dia["fws_branch"])
    # plant equipment branches off the riser leg
    for n in cool.nodes:
        if n.loop == "fws" and n.space == "sp.plant":
            (qx, qy), dist = _nearest_on_polyline(main_pts, n.pos[0], n.pos[1])
            if dist > 0.2:
                pair(f"rt.{n.id}", "sys.fws", [(qx, qy, hz), (n.pos[0], n.pos[1], hz)],
                     dia["fws_branch"])

    # TCS: CDU secondary header above the CDU row (row manifold feeds are
    # generated with the manifolds in resolve()).
    z_s, z_r = e["tcs_supply"], e["tcs_return"]
    # Header must reach the westmost row-manifold feed (x_start - 1.0) as well
    # as every CDU. Recompute the DLC hall's rack span the same way resolve() does.
    dlc = next(h for h in spec.it.halls if h.cooling == "dlc")
    hs = next(s for s in spec.spaces.spaces if s.id == dlc.space)
    rt = spec.it.rack_types[dlc.rack_type]
    span = (dlc.racks_per_row - 1) * dlc.rack_pitch
    man_feed_x = (hs.x + hs.w / 2.0 - span / 2.0) - rt.width / 2.0 - 1.0
    hdr_span = [min(min(n.pos[0] for n in cdus), man_feed_x),
                max(n.pos[0] for n in cdus)]
    routes.append(RouteP("rt.clg.tcs.hdr.s", "pipe", "sys.tcs.supply",
                         [(hdr_span[0], hy, z_s), (hdr_span[1], hy, z_s)],
                         diameter=dia["tcs_header"]))
    routes.append(RouteP("rt.clg.tcs.hdr.r", "pipe", "sys.tcs.return",
                         [(hdr_span[0], hy, z_r), (hdr_span[1], hy, z_r)],
                         diameter=dia["tcs_header"]))
    for n in cdus:
        routes.append(RouteP(f"rt.{n.id}.sec.s", "pipe", "sys.tcs.supply",
                             [(n.pos[0], hy, z_s), (n.pos[0], n.pos[1], z_s)],
                             diameter=dia["tcs_manifold"]))
        routes.append(RouteP(f"rt.{n.id}.sec.r", "pipe", "sys.tcs.return",
                             [(n.pos[0], n.pos[1], z_r), (n.pos[0], hy, z_r)],
                             diameter=dia["tcs_manifold"]))

    # CHW: chillers -> corridor centre -> Hall B, perimeter CRAH headers.
    cz = e["chw_header"]
    ex, ey = chw["hall_b_entry"]
    wx, eex = chw["west_wall_x"], chw["east_wall_x"]
    ny = chw["north_crossing_y"]
    chillers = sorted((n for n in cool.nodes if n.cls == "chiller"), key=lambda n: -n.pos[0])
    main_pts = [(chillers[0].pos[0], chillers[0].pos[1], cz),
                (chw["spine_crossing_x"], chillers[0].pos[1], cz),
                (chw["spine_crossing_x"], ey, cz), (wx, ey, cz)]
    pair("rt.clg.chw.main", "sys.chw", main_pts, dia["chw_main"])
    crah_y = sorted({n.pos[1] for n in cool.nodes if n.cls == "crah"})
    pair("rt.clg.chw.hdr.w", "sys.chw", [(wx, crah_y[0], cz), (wx, ny, cz)], dia["chw_main"])
    pair("rt.clg.chw.hdr.n", "sys.chw", [(wx, ny, cz), (eex, ny, cz)], dia["chw_main"])
    pair("rt.clg.chw.hdr.e", "sys.chw", [(eex, ny, cz), (eex, crah_y[0], cz)], dia["chw_main"])
    for n in cool.nodes:
        if n.loop != "chw" or n.cls in ("chiller", "crah"):
            continue  # chillers/CRAHs sit on their headers; module taps in place
        (qx, qy), dist = _nearest_on_polyline(main_pts, n.pos[0], n.pos[1])
        if dist > 0.2:
            pair(f"rt.{n.id}", "sys.chw", [(qx, qy, cz), (n.pos[0], n.pos[1], cz)],
                 dia["chw_branch"])
    # trim HX also taps CHW
    hx = cool_by_id.get("clg.hx.1")
    if hx is not None:
        (qx, qy), dist = _nearest_on_polyline(main_pts, hx.pos[0], hx.pos[1])
        pair("rt.clg.hx.1.chw", "sys.chw", [(qx, qy, cz), (hx.pos[0], hx.pos[1], cz)],
             dia["chw_branch"])
    return routes
