"""Design invariants, proven on the resolved plan (gate G0).

The point of encoding the facility as a graph: the redundancy claims in the
brief are CHECKED, not asserted. Every check returns a list of failure strings;
empty = pass.

  power_2n          every rack has a live path to BOTH utility intakes, and the
                    A and B paths share no equipment (true 2N, node-disjoint)
  capacity          nameplate arithmetic: spec capacity == generated rack load;
                    TX/GEN/UPS/PDU/busway sized for their downstream load
  mech_n_plus_1     every cooling redundancy group survives its worst single
                    failure at design load
  mech_diversity    no cooling redundancy group is fed entirely from one power
                    side (a single MCC failure must not take out a whole group)
  circulation       every space is reachable from an external door through the
                    door graph (incl. stair links)
"""
from __future__ import annotations

from collections import defaultdict, deque
import math

from .plan import Plan



def _adjacency(plan: Plan, system: str) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for e in plan.edges:
        if e.system == system:
            adj[e.src].add(e.dst)
            adj[e.dst].add(e.src)
    return adj


def _reachable(adj: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    q = deque([start])
    while q:
        for nxt in adj[q.popleft()]:
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


# ------------------------------------------------------------------ checks
def power_2n(plan: Plan) -> list[str]:
    fails = []
    rack_ids = {r.id for r in plan.racks}
    reach = {}
    for side, util in (("a", "pwr.util.a"), ("b", "pwr.util.b")):
        adj = _adjacency(plan, f"sys.pwr.{side}")
        reach[side] = _reachable(adj, util)
        missing = rack_ids - reach[side]
        if missing:
            fails.append(f"power_2n: {len(missing)} racks unreachable from {util} "
                         f"(e.g. {sorted(missing)[:3]})")
    # Node-disjointness: the only elements allowed on both trains are the
    # dual-corded racks themselves.
    shared = (reach.get("a", set()) & reach.get("b", set())) - rack_ids
    if shared:
        fails.append(f"power_2n: A and B trains share equipment: {sorted(shared)[:5]}")
    return fails


def capacity(plan: Plan) -> list[str]:
    fails = []
    rack_kw = sum(r.kw for r in plan.racks)
    declared = plan.meta["capacity_kw"]
    if abs(rack_kw - declared["it_load"]) > 1e-6:
        fails.append(f"capacity: spec it_load {declared['it_load']} kW != "
                     f"generated rack load {rack_kw} kW")
    equip = {e.id: e for e in plan.equipment}

    # Per-row: PDU and busway sized for the row (0.9 pf).
    row_kw = defaultdict(float)
    for r in plan.racks:
        row_kw[r.row] += r.kw
    for run in plan.runs:
        if run.kind != "busway":
            continue
        pdu = equip[run.feed]
        need_kva = row_kw[run.row] / 0.9
        if pdu.rating.get("rating_kva", 0) < need_kva:
            fails.append(f"capacity: {pdu.id} {pdu.rating.get('rating_kva')} kVA "
                         f"< row demand {need_kva:.0f} kVA")

    # Per-side: UPS fleet carries the full IT load; TX/GEN carry everything.
    for side in ("A", "B"):
        ups_kw = sum(e.rating.get("rating_kw", 0) for e in plan.equipment
                     if e.cls == "ups" and e.side == side)
        if ups_kw < rack_kw:
            fails.append(f"capacity: UPS-{side} fleet {ups_kw} kW < IT load {rack_kw} kW")
        need_kva = (rack_kw / 0.95 + declared["mech_load"] + declared["house_load"]) / 0.9
        for cls in ("transformer", "generator"):
            unit = next(e for e in plan.equipment if e.cls == cls and e.side == side)
            if unit.rating.get("rating_kva", 0) < need_kva:
                fails.append(f"capacity: {unit.id} {unit.rating.get('rating_kva')} kVA "
                             f"< side demand {need_kva:.0f} kVA")
    return fails


def mech_n_plus_1(plan: Plan) -> list[str]:
    fails = []
    equip = {e.id: e for e in plan.equipment}
    for rg in plan.redundancy_groups:
        members = rg["members"]
        if len(members) - 1 < rg["duty_required"]:
            fails.append(f"mech_n_plus_1: {rg['id']} cannot survive a single failure "
                         f"({len(members)} units, {rg['duty_required']} duty)")
        ratings = [equip[m].rating.get("rating_kw") for m in members]
        if all(r is not None for r in ratings):
            # worst single failure = losing the LARGEST unit
            surviving = sum(sorted(ratings, reverse=True)[1:])
            if surviving < rg["serves_kw"] * 0.999:
                fails.append(f"mech_n_plus_1: {rg['id']} carries only {surviving} kW "
                             f"after losing its largest unit (< {rg['serves_kw']} kW load)")
    return fails


def mech_diversity(plan: Plan) -> list[str]:
    fails = []
    fed_by = {}
    for mcc, loads in plan.mech_feeds.items():
        side = "A" if mcc.endswith(".a") else "B"
        for load in loads:
            fed_by[load] = side
    for rg in plan.redundancy_groups:
        sides = {fed_by.get(m) for m in rg["members"]}
        sides.discard(None)
        if len(rg["members"]) > 1 and len(sides) < 2:
            fails.append(f"mech_diversity: {rg['id']} entirely fed from side "
                         f"{sides or '?'} — one MCC failure kills the group")
    # every powered cooling unit must actually have a feed (tanks/HX are passive)
    passive = {"buffer_tank", "heat_exchanger"}
    cooled = {e.id for e in plan.equipment
              if e.discipline == "cooling" and e.cls not in passive}
    unfed = cooled - set(fed_by)
    if unfed:
        fails.append(f"mech_diversity: cooling equipment with no power feed: {sorted(unfed)}")
    return fails


def circulation(plan: Plan) -> list[str]:
    adj: dict[str, set[str]] = defaultdict(set)
    for d in plan.doors:
        wall = next(w for w in plan.walls if w.id == d.wall_id)
        a = wall.left or "EXT"
        b = wall.right or "EXT"
        adj[a].add(b)
        adj[b].add(a)
    stairs = sorted((s for s in plan.spaces if s.type == "stair"),
                    key=lambda s: next(st.elevation for st in plan.storeys if st.id == s.storey))
    for a, b in zip(stairs, stairs[1:]):
        if (a.x, a.y, a.w, a.d) == (b.x, b.y, b.w, b.d):
            adj[a.id].add(b.id)
            adj[b.id].add(a.id)
    reached = _reachable(adj, "EXT")
    missing = {s.id for s in plan.spaces if not s.external and s.type != "void"} - reached
    return [f"circulation: unreachable from outside: {sorted(missing)}"] if missing else []


def door_column_clearances(plan: Plan) -> dict[str, float]:
    """3D distance between each opening volume and every column body."""
    walls = {w.id: w for w in plan.walls}
    elevations = {s.id: s.elevation for s in plan.storeys}
    result = {}
    for d in plan.doors:
        w = walls[d.wall_id]
        vertical = abs(w.p1[0]-w.p2[0]) < 1e-6
        half = ((w.thickness+0.2)/2, d.width/2) if vertical else (d.width/2, (w.thickness+0.2)/2)
        distances = []
        for c in plan.columns:
            dx, dy = (max(abs(d.pos[i]-c.pos[i])-half[i]-c.size/2, 0) for i in (0, 1))
            dz = max(elevations[d.storey]-c.height, 0)
            distances.append(math.sqrt(dx*dx+dy*dy+dz*dz))
        result[d.id] = min(distances, default=math.inf)
    return result


def door_columns(plan: Plan) -> list[str]:
    return [f"door_columns: {key} clearance {distance:.3f} m < 0.3 m"
            for key, distance in door_column_clearances(plan).items() if distance < 0.3-1e-6]


def camera_rules(plan: Plan) -> list[str]:
    fails = []
    rules = plan.security["rules"]
    expected = {
        "door": len(plan.security["iris"]), "ext": sum(d.external for d in plan.doors),
        "corr": sum(2 * math.ceil((max(s.w, s.d)/rules["corridor_cameras"]["max_spacing"]+1)/2)
                    for s in plan.spaces if s.type == "corridor"),
        "yard": sum(s.id.startswith("sp.yard.gen.") for s in plan.spaces)
                + 2 * sum(s.external for s in plan.spaces),
        "lobby": 3 * sum(s.type == "lobby" for s in plan.spaces),
    }
    for group, count in expected.items():
        actual = sum(c.id.split(".")[2] == group for c in plan.cameras)
        if actual != count:
            fails.append(f"camera_rules: {group}: {actual} cameras != {count}")
    seen = set()
    for c in plan.cameras:
        if c.id in seen:
            fails.append(f"camera_rules: duplicate {c.id}")
        seen.add(c.id)
        if c.type not in plan.security["camera_types"]:
            fails.append(f"camera_rules: {c.id} unknown type {c.type}")
        s = plan.space(c.space)
        if not s.external and not (s.x <= c.pos[0] <= s.x+s.w and s.y <= c.pos[1] <= s.y+s.d):
            fails.append(f"camera_rules: {c.id} outside mounting space {s.id}")
        if c.scenario != "door" and s.type == "hall":
            fails.append(f"camera_rules: {c.id} monitors a hall interior")
        if any(name not in c.presets for name in c.tour):
            fails.append(f"camera_rules: {c.id} tour references a missing preset")
    return fails


from .qa.variant_rules import CHECKS as VARIANT_CHECKS

ALL_CHECKS = [power_2n, capacity, mech_n_plus_1, mech_diversity, circulation, door_columns, camera_rules] + VARIANT_CHECKS


def run_all(plan: Plan) -> list[str]:
    fails: list[str] = []
    for check in ALL_CHECKS:
        fails.extend(check(plan))
    return fails
