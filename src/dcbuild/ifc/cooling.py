"""COOLING discipline: the three hydraulic loops (FWS / TCS / CHW).

* FWS  dry coolers on the yard <-> plant room <-> CDU primaries in Hall A
       (warm-water glycol; CONDENSERWATER ports, green).
* TCS  CDU secondaries -> per-row supply/return manifolds -> rack hoses
       (direct liquid cooling of Hall A; USERDEFINED ports — "COOLING" is not
       in IfcDistributionSystemEnum in IFC4X3_ADD2 — teal).
* CHW  chillers <-> CRAHs in Hall B + office AHU + trim HX
       (CHILLEDWATER ports, light blue).

Tie-in approach, applied consistently everywhere:

* a route end that lands on the INTERIOR of a header -> one JUNCTION fitting
  splitting the header at that point (segments butt the fitting faces); the
  branch connects to an arm port on the fitting. Several branches meeting the
  header at the same point share one junction (one arm each).
* route ends that MEET at the same coordinate -> plain port-to-port connect.
* equipment sitting ON its header (CRAHs, chillers) -> JUNCTION on the header
  + a short vertical branch stub (dropper) + nozzle port on the unit. Supply
  and return headers are stacked in plan, so the supply tap is offset -0.25 m
  and the return tap +0.25 m along the header axis (stubs don't collide).
  Where that tap falls at/beyond a header end, the header terminates ON the
  fitting (a BEND when only 2 arms are used — a run never ends on an open tee).
* pumps -> nozzle off the pump TOP face via a short vertical riser + BEND
  elbow (the proven dcgen pump_nozzle pattern); supply/return risers are
  offset +-0.1 m along the branch axis so the two risers don't collide.

Every IfcRelConnectsPorts is authored SOURCE -> SINK in the flow direction:
supply flows away from the producing plant (dry coolers / chillers / CDU
secondaries / pump discharges), returns flow back toward it. The only
deliberately-open ports are the 160 TCS hose bottoms, registered in b.ports
as "{rack_id}.clg.s" / "{rack_id}.clg.r" for the IT module to consume.
"""
from __future__ import annotations

import numpy as np

from .geom import Z_UP, at, matrix, rot_z
from .run import Run

# Loop colour code (conventions.md): FWS green, TCS teal, CHW light blue.
LOOP_RGB = {"fws": (0.16, 0.55, 0.34), "tcs": (0.10, 0.55, 0.55),
            "chw": (0.35, 0.6, 0.85)}
LOOP_SYSTEM = {"fws": "sys.fws", "tcs": "sys.tcs", "chw": "sys.chw"}
# Port SystemType per loop. NB "COOLING" is NOT a valid IfcDistributionSystemEnum
# value in IFC4X3_ADD2 -> every TCS port is USERDEFINED (consistently, so
# connected pairs share SystemType); matches the sys.tcs USERDEFINED system.
LOOP_PORT_SYSTEM = {"fws": "CONDENSERWATER", "tcs": "USERDEFINED",
                    "chw": "CHILLEDWATER"}
LOOP_LABEL = {"fws": "FWS", "tcs": "TCS", "chw": "CHW"}

# spec class -> (IFC class, PredefinedType, ObjectType, shared type name)
EQUIP_IFC = {
    "dry_cooler": ("IfcCoolingTower", "USERDEFINED", "DryCooler", "Dry Cooler"),
    "chiller": ("IfcChiller", "AIRCOOLED", None, "Air-Cooled Chiller"),
    "pump": ("IfcPump", "ENDSUCTION", None, "End-Suction Pump"),
    "buffer_tank": ("IfcTank", "STORAGE", None, "Buffer Tank"),
    "dosing": ("IfcUnitaryEquipment", "USERDEFINED", "DosingSkid", "Dosing Skid"),
    "heat_exchanger": ("IfcHeatExchanger", "PLATE", None, "Plate Heat Exchanger"),
    "cdu": ("IfcUnitaryEquipment", "USERDEFINED", "CDU", "Coolant Distribution Unit"),
    "crah": ("IfcUnitaryEquipment", "AIRCONDITIONINGUNIT", None, "CRAH"),
    "ahu": ("IfcUnitaryEquipment", "AIRHANDLER", None, "AHU"),
}

# plan rating key -> (property name, measure type, SI factor)
RATING_PROPS = {
    "rating_kw": ("Rating", "IfcPowerMeasure", 1000.0),                    # kW -> W
    "flow_ls": ("NominalFlowRate", "IfcVolumetricFlowRateMeasure", 1e-3),  # l/s -> m3/s
    "volume_l": ("NominalCapacity", "IfcVolumeMeasure", 1e-3),             # l -> m3
}

STUB_OFF = 0.25    # supply/return stub offset along the header for on-header units
RISER_OFF = 0.10   # pump supply/return riser offset along the branch axis


# ---------------------------------------------------------------- geometry
_FRAMES: dict = {}


def _frame(d) -> np.ndarray:
    """Run frame with local +Z along the (axis-aligned) direction `d`."""
    key = tuple(int(round(float(v))) for v in d)
    if key not in _FRAMES:
        z = np.array(key, dtype=float)
        z = z / np.linalg.norm(z)
        up = np.array([0.0, 0.0, 1.0]) if abs(z[2]) < 0.5 else np.array([1.0, 0.0, 0.0])
        x = np.cross(up, z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        _FRAMES[key] = matrix(tuple(x), tuple(y), tuple(z))
    return _FRAMES[key]


def _key_pt(p):
    return (round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[2]), 4))


def _unit2(a, b):
    """Unit 2D direction a -> b (axis-aligned)."""
    d = np.array([float(b[0]) - float(a[0]), float(b[1]) - float(a[1]), 0.0])
    return d / np.linalg.norm(d)


# ---------------------------------------------------------------- runs
class PipeRun(Run):
    """Run that DC-identifies every member it authors (Run only keys them)."""

    def __init__(self, b, sys_id, *args, **kw):
        super().__init__(b, *args, **kw)
        self.sys_id = sys_id

    def _made(self, kind):
        self.b.identify(self.members[-1], f"{self.base}.{kind}{self._n[kind]:03d}",
                        System=self.sys_id)

    def seg(self, *a, **kw):
        out = super().seg(*a, **kw)
        self._made("seg")
        return out

    def fitting(self, *a, **kw):
        out = super().fitting(*a, **kw)
        self._made("fit")
        return out

    def dropper(self, *a, **kw):
        out = super().dropper(*a, **kw)
        self._made("drop")
        return out


class Loop:
    """Shared system / material / element types for one hydraulic loop."""

    def __init__(self, b, loop):
        self.b = b
        self.loop = loop
        self.label = LOOP_LABEL[loop]
        self.sys_id = LOOP_SYSTEM[loop]
        self.system = b.system(self.sys_id)
        self.port_system = LOOP_PORT_SYSTEM[loop]
        self.mat_name = f"{self.label} Pipework"
        self.material = b.material(self.mat_name, "steel", rgb=LOOP_RGB[loop])
        self.bend = b.typed("IfcPipeFittingType", "BEND", f"{self.label} Pipe Bend")
        self.junc = b.typed("IfcPipeFittingType", "JUNCTION", f"{self.label} Pipe Junction")
        b.assign_material([self.bend, self.junc], self.material)
        self._seg_types: dict = {}
        self.runs: list[PipeRun] = []
        self.equip: list = []

    def seg_type(self, dia):
        name = f"{self.label} Pipe DN{int(round(dia * 1000))}"
        if name not in self._seg_types:
            st = self.b.typed("IfcPipeSegmentType", "RIGIDSEGMENT", name)
            self.b.assign_material([st], self.material)
            self._seg_types[name] = st
        return self._seg_types[name]

    def run(self, base, dia) -> PipeRun:
        st = self.seg_type(dia)
        r = PipeRun(self.b, self.sys_id, self.system, base,
                    system_type=self.port_system, seg_type=st,
                    seg_predef="RIGIDSEGMENT", seg_class="IfcPipeSegment",
                    fit_class="IfcPipeFitting", drop_type=st,
                    drop_predef="RIGIDSEGMENT", branch_predef="JUNCTION",
                    bend_predef="BEND", port_kind="PIPE", diameter=dia)
        self.runs.append(r)
        return r

    def commit(self, serves):
        members = [m for r in self.runs for m in r.members]
        self.b.assign_system(members + self.equip, self.system)
        self.b.serves_building(self.system, serves)
        for m in members:
            self.b.style_product(m, self.mat_name)


# ---------------------------------------------------------------- polyline+taps
def _route(run, name, pts, bend_type, junc_type, taps=()):
    """Author an orthogonal polyline as segments + BEND elbows at direction
    changes, with a JUNCTION/BEND fitting splitting the run at every tap.

    ``taps`` = [(tag, point, predefined)]; each point must lie on the
    polyline. A tap AT the first/last waypoint makes that fitting the route
    TERMINUS (the run starts/ends on the fitting; no open end port there).
    Returns (first_port, last_port, fits) — fits[tag] = (element, point);
    first_port / last_port is None at a terminus fitting.
    """
    P = [np.asarray(p, dtype=float) for p in pts]
    P = [p for i, p in enumerate(P) if i == 0 or np.linalg.norm(p - P[i - 1]) > 1e-9]
    if len(P) < 2:
        raise ValueError(f"{name}: degenerate route")
    hf = run.fw / 2.0
    fits: dict = {}
    tap_list = [(tag, np.asarray(q, dtype=float), predef) for tag, q, predef in taps]
    used = [False] * len(tap_list)

    def endpoint_tap(pt):
        for k, (tag, q, predef) in enumerate(tap_list):
            if not used[k] and np.linalg.norm(q - pt) < 1e-6:
                used[k] = True
                return (tag, predef)
        return None

    # node list: (kind, point, meta) with kind in open|term|tap|bend
    t0 = endpoint_tap(P[0])
    nodes = [("term" if t0 else "open", P[0], t0)]
    for i in range(len(P) - 1):
        a, c = P[i], P[i + 1]
        d = c - a
        length = float(np.linalg.norm(d))
        u = d / length
        on_leg = []
        for k, (tag, q, predef) in enumerate(tap_list):
            if used[k]:
                continue
            t = float(np.dot(q - a, u))
            if 1e-6 < t < length - 1e-6 and np.linalg.norm(a + u * t - q) < 1e-6:
                used[k] = True
                on_leg.append((t, tag, q, predef))
        for _t, tag, q, predef in sorted(on_leg, key=lambda x: x[0]):
            nodes.append(("tap", q, (tag, predef)))
        if i < len(P) - 2:
            nodes.append(("bend", c, None))
    tN = endpoint_tap(P[-1])
    nodes.append(("term" if tN else "open", P[-1], tN))
    if not all(used):
        missing = [tap_list[k][0] for k in range(len(tap_list)) if not used[k]]
        raise ValueError(f"{name}: tap(s) not on the route: {missing}")

    def make_fit(idx, kind, pt, meta):
        if kind == "bend":
            el = run.fitting(f"{name} Bend {idx}", run.bend_predef, bend_type, tuple(pt))
        else:  # tap | term
            tag, predef = meta
            ftype = junc_type if predef == "JUNCTION" else bend_type
            el = run.fitting(f"{name} Tap {tag}", predef, ftype, tuple(pt))
            fits[tag] = (el, tuple(pt))
        return el

    els: list = [None] * len(nodes)
    first_port = last_port = None
    n_bend = 0
    for i in range(len(nodes) - 1):
        ka, pa, ma = nodes[i]
        kb, pb, mb = nodes[i + 1]
        d = pb - pa
        length = float(np.linalg.norm(d))
        u = d / length
        fr = _frame(u)
        if ka != "open" and els[i] is None:  # terminus at the very start
            els[i] = make_fit(i, ka, pa, ma)
        start = pa + u * hf if ka != "open" else pa
        end = pb - u * hf if kb != "open" else pb
        _seg, p_near, p_far = run.seg(
            f"{name} Seg {i + 1}", fr, tuple(start), float(np.linalg.norm(end - start)))
        if ka == "open":
            if first_port is None:
                first_port = p_near
        else:
            out_port = run.port(els[i], run.face(tuple(pa), tuple(u), +1.0), fr)
            run.connect(out_port, p_near)
        if kb != "open":
            if kb == "bend":
                n_bend += 1
            els[i + 1] = make_fit(n_bend if kb == "bend" else i + 1, kb, pb, mb)
            in_port = run.port(els[i + 1], run.face(tuple(pb), tuple(u), -1.0), fr)
            run.connect(p_far, in_port)
        else:
            last_port = p_far
    return first_port, last_port, fits


# ---------------------------------------------------------------- build
def build(b, plan):
    cfg = plan.cooling_cfg
    dias = cfg["pipe_diameters"]
    hose_z = cfg["tcs_manifolds"]["hose_drop_z"]
    routes = {r.id: r for r in plan.routes if r.kind == "pipe"}
    authored: set[str] = set()

    loops = {k: Loop(b, k) for k in ("fws", "tcs", "chw")}
    fws, tcs, chw = loops["fws"], loops["tcs"], loops["chw"]
    els: dict = {}

    # ==== 1. EQUIPMENT ====================================================
    cool_equip = [e for e in plan.equipment if e.discipline == "cooling"]
    for e in cool_equip:
        cls, predef, otype, tname = EQUIP_IFC[e.cls]
        el = b.entity(cls, predefined=predef, name=e.name, key=e.id)
        etype = b.typed(f"{cls}Type", predef, tname)
        if otype and not etype.ElementType:
            etype.ElementType = otype
        b.assign_type([el], etype)
        # assign_type nulls the occurrence attributes (type inheritance);
        # re-assert them so the class mapping is explicit on the occurrence.
        el.PredefinedType = predef
        if otype:
            el.ObjectType = otype
        w, d, h = e.size
        m = rot_z(e.rot, (e.pos[0], e.pos[1], e.pos[2]))
        if e.shape == "cylinder":
            b.tube(el, w / 2.0, h, m, structure=b.container_for(e.space))
        else:
            b.box(el, w, d, h, m, structure=b.container_for(e.space))
        b.identify(el, e.id, Loop=e.loop)
        lp = loops[e.loop]
        b.assign_material([el], lp.material)
        b.style_product(el, lp.mat_name)
        lp.equip.append(el)
        if e.cls == "cdu":
            tcs.equip.append(el)  # CDUs belong to FWS (primary) AND TCS
        items = [(RATING_PROPS[k][0], RATING_PROPS[k][1], float(v) * RATING_PROPS[k][2])
                 for k, v in e.rating.items() if k in RATING_PROPS]
        if items:
            cname = "".join(p.capitalize() for p in e.cls.split("_"))
            b.properties(el, f"DC_{cname}Rating", items)
        els[e.id] = el

    eq = {e.id: e for e in cool_equip}
    drcs = sorted((e for e in cool_equip if e.cls == "dry_cooler"), key=lambda e: e.pos[0])
    cdus = sorted((e for e in cool_equip if e.cls == "cdu"), key=lambda e: e.pos[0])
    chillers = sorted((e for e in cool_equip if e.cls == "chiller"), key=lambda e: e.pos[0])

    # ---- shared wiring helpers -------------------------------------------
    def arm(header_run, fits, tag, direction, flow=None):
        """Branch arm port on a header fitting: at the fitting face along
        `direction`, local +Z pointing out along it. Returns (port, face_pt)."""
        el, pt = fits[tag]
        face = header_run.face(pt, tuple(direction), +1.0)
        return header_run.port(el, face, _frame(direction), flow=flow), face

    def branch_ends(r, e):
        """(equipment_end, header_end) of a branch RouteP."""
        w0, wn = tuple(map(float, r.waypoints[0])), tuple(map(float, r.waypoints[-1]))
        d0 = abs(w0[0] - e.pos[0]) + abs(w0[1] - e.pos[1])
        dn = abs(wn[0] - e.pos[0]) + abs(wn[1] - e.pos[1])
        return (w0, wn) if d0 <= dn else (wn, w0)

    def tie_branch(loop, rid, e, header_port, header_pt, to_equipment, dia=None):
        """A branch route between a header connection and an equipment nozzle
        at the route's equipment end. header_pt = trimmed junction-arm face
        (None -> direct port-to-port at the shared coordinate). Flow (and the
        authoring order) is header->equipment when `to_equipment`."""
        r = routes[rid]
        equip_end, hdr_end = branch_ends(r, e)
        h_pt = header_pt if header_pt is not None else hdr_end
        pts = [h_pt, equip_end] if to_equipment else [equip_end, h_pt]
        run = loop.run(r.id, dia or r.diameter)
        p1, p2 = run.polyline(r.id, pts, loop.bend)
        u = _unit2(equip_end, h_pt)  # nozzle +Z pointing along the branch, out of the unit
        noz = run.port(els[e.id], equip_end, _frame(u),
                       flow="SINK" if to_equipment else "SOURCE")
        if to_equipment:
            run.connect(header_port, p1)
            run.connect(p2, noz)
        else:
            run.connect(noz, p1)
            run.connect(p2, header_port)
        authored.add(rid)
        return run

    def stub_tap(header_run, fits, tag, e, tap_xy, z_hdr, to_equipment):
        """On-header equipment tap: vertical stub from the header fitting down
        to the unit's top face + nozzle connect (comb pattern: branch arm at
        the fitting centre, stub spans from the centre z)."""
        el_fit, pt = fits[tag]
        c_arm = header_run.port(el_fit, pt)
        top = e.pos[2] + e.size[2]
        _stub, s_top, s_bot = header_run.dropper(
            f"{e.id} {'Feed' if to_equipment else 'Riser'} Stub",
            tap_xy[0], tap_xy[1], z_hdr, top)
        noz = header_run.port(els[e.id], (tap_xy[0], tap_xy[1], top), Z_UP,
                              flow="SINK" if to_equipment else "SOURCE")
        if to_equipment:
            header_run.connect(c_arm, s_top)
            header_run.connect(s_bot, noz)
        else:
            header_run.connect(noz, s_bot)
            header_run.connect(s_top, c_arm)

    def pump_branch(loop, rid, e, header_port, header_pt, supply):
        """Pump tie (dcgen pump_nozzle pattern): nozzle port on the pump TOP
        face, short vertical riser to the branch elevation, BEND elbow, then
        the horizontal leg to the header connection. Discharge (supply side)
        risers sit +RISER_OFF toward the header, suction -RISER_OFF."""
        r = routes[rid]
        equip_end, hdr_end = branch_ends(r, e)
        h_pt = header_pt if header_pt is not None else hdr_end
        z_route = equip_end[2]
        u = _unit2(e.pos, h_pt)                      # pump -> header
        s = 1.0 if supply else -1.0
        rx = e.pos[0] + u[0] * RISER_OFF * s
        ry = e.pos[1] + u[1] * RISER_OFF * s
        top = e.pos[2] + e.size[2]
        run = loop.run(r.id, r.diameter)
        hf = run.fw / 2.0
        noz = run.port(els[e.id], (rx, ry, top), Z_UP,
                       flow="SOURCE" if supply else "SINK")
        _riser, r_bot, r_top = run.seg(f"{r.id} Riser", _frame((0, 0, 1)),
                                       (rx, ry, top), (z_route - hf) - top)
        elbow = run.fitting(f"{r.id} Elbow", "BEND", loop.bend, (rx, ry, z_route))
        e_down = run.port(elbow, (rx, ry, z_route - hf))
        arm_pt = (rx + u[0] * hf, ry + u[1] * hf, z_route)
        e_arm = run.port(elbow, arm_pt, _frame(u))
        if supply:  # pump -> header
            fr, start, end = _frame(u), np.asarray(arm_pt), np.asarray(h_pt)
        else:       # header -> pump
            fr, start, end = _frame(-u), np.asarray(h_pt), np.asarray(arm_pt)
        _leg, h1, h2 = run.seg(f"{r.id} Leg", fr, tuple(start),
                               float(np.linalg.norm(end - start)))
        if supply:
            run.connect(noz, r_bot)
            run.connect(r_top, e_down)
            run.connect(e_arm, h1)
            run.connect(h2, header_port)
        else:
            run.connect(header_port, h1)
            run.connect(h2, e_arm)
            run.connect(e_down, r_top)
            run.connect(r_bot, noz)
        authored.add(rid)

    def main_ties(branches, authored_pts):
        """Dedupe branch tie-in points on a main against its authored
        polyline. Returns (taps for _route, ties[rid] = (kind, tag/None))."""
        taps: dict = {}
        ties: dict = {}
        p0, pn = _key_pt(authored_pts[0]), _key_pt(authored_pts[-1])
        for e, rid in branches:
            _eq_end, hdr_end = branch_ends(routes[rid], e)
            k = _key_pt(hdr_end)
            if k == p0:
                ties[rid] = ("end0", None)
            elif k == pn:
                ties[rid] = ("endN", None)
            else:
                if k not in taps:
                    taps[k] = (e.id, hdr_end)
                ties[rid] = ("tap", taps[k][0])
        return [(tag, pt, "JUNCTION") for tag, pt in taps.values()], ties

    def tie_port(kind, tag, p1, p2, run, fits, rid, e):
        """Resolve one branch's header connection -> (port, face_pt|None)."""
        if kind == "end0":
            return p1, None
        if kind == "endN":
            return p2, None
        eq_end, hdr_end = branch_ends(routes[rid], e)
        return arm(run, fits, tag, _unit2(hdr_end, eq_end))

    # ==== 2a. FWS =========================================================
    # yard headers (supply z, return z+0.3), junction taps at the interior
    # dry coolers + the main offtake; the end coolers meet the header ends.
    pen_x = cfg["routing"]["fws"]["wall_penetration"][0]
    yard: dict = {}
    for sub in ("s", "r"):
        r = routes[f"rt.clg.fws.yard.{sub}"]
        run = fws.run(r.id, r.diameter)
        z, yard_y = r.waypoints[0][2], r.waypoints[0][1]
        taps = [(e.id, (e.pos[0], yard_y, z), "JUNCTION") for e in drcs[1:-1]]
        taps.append(("main", (pen_x, yard_y, z), "JUNCTION"))
        p1, p2, fits = _route(run, r.id, [tuple(w) for w in r.waypoints],
                              fws.bend, fws.junc, taps)
        yard[sub] = (run, p1, p2, fits)
        authored.add(r.id)

    for e in drcs:  # dry-cooler branches: supply sources FROM the cooler
        for sub, to_eq in (("s", False), ("r", True)):
            run, p1, p2, fits = yard[sub]
            if e is drcs[0]:
                hp, hpt = p1, None
            elif e is drcs[-1]:
                hp, hpt = p2, None
            else:
                hp, hpt = arm(run, fits, e.id, (0, -1, 0))
            tie_branch(fws, f"rt.{e.id}.{sub}", e, hp, hpt, to_eq)

    # FWS mains: supply authored plant->hall (flow order), return hall->plant.
    fws_plant = sorted((e for e in cool_equip
                        if e.loop == "fws" and e.space == "sp.plant"
                        and e.cls in ("pump", "buffer_tank", "dosing", "heat_exchanger")),
                       key=lambda e: e.id)
    yard_hf = yard["s"][0].fw / 2.0
    main_conn: dict = {}
    for sub, to_hall in (("s", True), ("r", False)):
        r = routes[f"rt.clg.fws.main.{sub}"]
        pts = [tuple(w) for w in r.waypoints]
        if not to_hall:
            pts = list(reversed(pts))
        # butt the yard-header junction (its arm faces north)
        i = 0 if to_hall else -1
        pts[i] = (pts[i][0], pts[i][1] + yard_hf, pts[i][2])
        branches = [(e, f"rt.{e.id}.{sub}") for e in fws_plant] + \
                   [(e, f"rt.{e.id}.pri.{sub}") for e in cdus]
        taps, ties = main_ties(branches, pts)
        run = fws.run(r.id, r.diameter)
        p1, p2, fits = _route(run, r.id, pts, fws.bend, fws.junc, taps)
        authored.add(r.id)
        # tie the main into the yard header
        y_run, _yp1, _yp2, y_fits = yard[sub]
        y_arm, _ = arm(y_run, y_fits, "main", (0, 1, 0))
        if to_hall:
            run.connect(y_arm, p1)
        else:
            run.connect(p2, y_arm)
        for rid, (kind, tag) in ties.items():
            main_conn[rid] = tie_port(kind, tag, p1, p2, run, fits, rid,
                                      next(e for e, rr in branches if rr == rid))

    for e in fws_plant:
        for sub in ("s", "r"):
            rid = f"rt.{e.id}.{sub}"
            hp, hpt = main_conn[rid]
            if e.cls == "pump":  # discharge -> supply main, suction <- return main
                pump_branch(fws, rid, e, hp, hpt, supply=(sub == "s"))
            else:                # passive: supply into the unit, return out of it
                tie_branch(fws, rid, e, hp, hpt, to_equipment=(sub == "s"))
    for e in cdus:               # CDU primaries consume FWS
        for sub in ("s", "r"):
            rid = f"rt.{e.id}.pri.{sub}"
            hp, hpt = main_conn[rid]
            tie_branch(fws, rid, e, hp, hpt, to_equipment=(sub == "s"))

    # ==== 2b/3. TCS: CDU secondary headers + row manifolds + rack hoses ===
    # Headers: all four row feeds AND the CDU-A1 branch meet the header's west
    # end -> that end terminates on a multi-arm JUNCTION fitting.
    hdr_conn: dict = {}
    hdr_ports: dict = {}
    for sub in ("s", "r"):
        r = routes[f"rt.clg.tcs.hdr.{sub}"]
        pts = [tuple(w) for w in r.waypoints]
        if sub == "s":
            pts = list(reversed(pts))  # supply flows east -> west (CDUs -> feeds)
        west_x, east_x = min(p[0] for p in pts), max(p[0] for p in pts)
        z = pts[0][2]
        taps = [(e.id, (e.pos[0], pts[0][1], z), "JUNCTION")
                for e in cdus if west_x + 1e-6 < e.pos[0] < east_x - 1e-6]
        taps.append(("west", (west_x, pts[0][1], z), "JUNCTION"))
        run = tcs.run(r.id, r.diameter)
        p1, p2, fits = _route(run, r.id, pts, tcs.bend, tcs.junc, taps)
        hdr_conn[sub] = (run, fits)
        hdr_ports[sub] = (p1, p2)
        authored.add(r.id)
        for e in cdus:  # CDU secondaries: source the supply, sink the return
            rid = f"rt.{e.id}.sec.{sub}"
            if abs(e.pos[0] - east_x) < 1e-6:  # meets the header's east end
                hp, hpt = (p1, None) if sub == "s" else (p2, None)
            else:
                tag = e.id if west_x + 1e-6 < e.pos[0] else "west"
                hp, hpt = arm(run, fits, tag, (0, -1, 0))
            tie_branch(tcs, rid, e, hp, hpt, to_equipment=(sub == "r"))

    # Row manifolds: comb runs with a JUNCTION + FLEXIBLESEGMENT hose at every
    # rack tap, ending on a BEND. Hose bottoms are the registered hand-off ports.
    hose_type = b.typed("IfcPipeSegmentType", "FLEXIBLESEGMENT",
                        f"TCS Rack Hose DN{int(round(dias['tcs_hose'] * 1000))}")
    b.assign_material([hose_type], tcs.material)
    racks_by_row: dict = {}
    for rk in plan.racks:
        racks_by_row.setdefault(rk.row, {})[rk.index] = rk

    def manifold(rn):
        supply = rn.kind == "manifold_supply"
        run = tcs.run(rn.id, rn.size[0])
        hf = run.fw / 2.0
        y, z = rn.y, rn.z
        row_racks = racks_by_row[rn.row]
        fr = _frame((1, 0, 0))

        def flow(a, c):  # supply flows west->east along the comb, return east->west
            run.connect(a, c) if supply else run.connect(c, a)

        feed_port = prev_far = None
        x_prev = rn.x_start
        n = len(rn.taps)
        for i, tx in enumerate(rn.taps):
            last = i == n - 1
            start_x = x_prev if prev_far is None else x_prev + hf
            _s, p_near, p_far = run.seg(f"{rn.id} Seg {i + 1}", fr,
                                        (start_x, y, z), (tx - hf) - start_x)
            if prev_far is None:
                feed_port = p_near
            else:
                flow(prev_far, p_near)
            fit = run.fitting(f"{rn.id} {'Bend' if last else 'Tap'} {i + 1}",
                              "BEND" if last else "JUNCTION",
                              tcs.bend if last else tcs.junc, (tx, y, z))
            w_arm = run.port(fit, (tx - hf, y, z), fr)
            flow(p_far, w_arm)
            rack = row_racks[i + 1]
            hose_id = f"{rn.id}.hose{i + 1:02d}"
            hose = b.entity("IfcPipeSegment", predefined="FLEXIBLESEGMENT",
                            name=f"{rack.id} {'Supply' if supply else 'Return'} Hose",
                            key=hose_id)
            b.assign_type([hose], hose_type)
            hose.PredefinedType = "FLEXIBLESEGMENT"  # assign_type nulls it
            b.tube(hose, dias["tcs_hose"] / 2.0, z - hose_z,
                   matrix((1, 0, 0), (0, -1, 0), (0, 0, -1), (tx, y, z)),
                   length=z - hose_z)
            b.identify(hose, hose_id, System=tcs.sys_id)
            run.members.append(hose)
            c_arm = run.port(fit, (tx, y, z))
            h_top = b.add_port(hose, system_type=tcs.port_system, predefined="PIPE",
                               matrix=at(Z_UP, (tx, y, z)), key=f"{hose_id}.top")
            h_bot = b.add_port(hose, system_type=tcs.port_system, predefined="PIPE",
                               matrix=at(Z_UP, (tx, y, hose_z)),
                               flow="SOURCE" if supply else "SINK",
                               key=f"{rack.id}.clg.{'s' if supply else 'r'}")
            assert h_bot is b.ports[f"{rack.id}.clg.{'s' if supply else 'r'}"]
            if supply:
                run.connect(c_arm, h_top)   # manifold -> hose -> rack
            else:
                run.connect(h_top, c_arm)   # rack -> hose -> manifold
            if not last:
                prev_far = run.port(fit, (tx + hf, y, z), fr)
            x_prev = tx
        return feed_port

    man_runs = sorted((rn for rn in plan.runs
                       if rn.kind in ("manifold_supply", "manifold_return")),
                      key=lambda rn: rn.id)
    for rn in man_runs:
        feed_port = manifold(rn)
        base, sub = rn.id.rsplit(".", 1)
        r = routes[f"rt.{base}.feed.{sub}"]
        run = tcs.run(r.id, r.diameter or dias["tcs_manifold"])
        h_run, h_fits = hdr_conn[sub]
        h_arm, h_face = arm(h_run, h_fits, "west", (0, 1, 0))
        if sub == "s":  # header -> feed -> manifold
            p1, p2 = run.polyline(r.id, [h_face, tuple(r.waypoints[1])], tcs.bend)
            run.connect(h_arm, p1)
            run.connect(p2, feed_port)
        else:           # manifold -> feed -> header
            p1, p2 = run.polyline(r.id, [tuple(r.waypoints[0]), h_face], tcs.bend)
            run.connect(feed_port, p1)
            run.connect(p2, h_arm)
        authored.add(r.id)

    # ==== 2c/4. CHW =======================================================
    # Hall B perimeter headers with a JUNCTION + stub + nozzle at each CRAH
    # (supply tap at crah_y - 0.25, return at +0.25); headers that would run
    # past their outermost tap terminate ON that fitting (a BEND).
    wx, ex = cfg["routing"]["chw"]["west_wall_x"], cfg["routing"]["chw"]["east_wall_x"]
    crahs_w = sorted((e for e in cool_equip if e.cls == "crah" and abs(e.pos[0] - wx) < 1e-6),
                     key=lambda e: e.pos[1])
    crahs_e = sorted((e for e in cool_equip if e.cls == "crah" and abs(e.pos[0] - ex) < 1e-6),
                     key=lambda e: e.pos[1])
    main_s_end = tuple(routes["rt.clg.chw.main.s"].waypoints[-1])
    main_r_end = tuple(routes["rt.clg.chw.main.r"].waypoints[-1])

    def crah_header(rid, crah_list, main_tie_pt, flip):
        """One perimeter header leg with its CRAH taps. `flip` reverses the
        given waypoints so the authored order follows the flow."""
        r = routes[rid]
        sub = rid.rsplit(".", 1)[1]
        supply = sub == "s"
        pts = [tuple(w) for w in r.waypoints]
        if flip:
            pts = list(reversed(pts))
        off = -STUB_OFF if supply else STUB_OFF
        x, z = pts[0][0], pts[0][2]
        # the header's south end is free (the north end joins hdr.n) -> it
        # always terminates ON the southernmost CRAH's tap fitting (a BEND),
        # extending (supply) or shortening (return) the given end by 0.25 m.
        si = 0 if pts[0][1] < pts[-1][1] else -1
        taps = []
        for k, e in enumerate(crah_list):
            ty = e.pos[1] + off
            if k == 0:
                pts[si] = (x, ty, z)
                taps.append((e.id, (x, ty, z), "BEND"))
            else:
                taps.append((e.id, (x, ty, z), "JUNCTION"))
        if main_tie_pt is not None:
            taps.append(("main", main_tie_pt, "JUNCTION"))
        run = chw.run(r.id, r.diameter)
        p1, p2, fits = _route(run, r.id, pts, chw.bend, chw.junc, taps)
        authored.add(r.id)
        for e in crah_list:  # CRAHs consume supply, source return
            stub_tap(run, fits, e.id, e, (x, e.pos[1] + off), z, to_equipment=supply)
        return run, p1, p2, fits

    ws_run, ws_p1, ws_p2, ws_fits = crah_header("rt.clg.chw.hdr.w.s", crahs_w, main_s_end, False)
    wr_run, wr_p1, wr_p2, wr_fits = crah_header("rt.clg.chw.hdr.w.r", crahs_w, main_r_end, False)
    es_run, es_p1, es_p2, es_fits = crah_header("rt.clg.chw.hdr.e.s", crahs_e, None, False)
    er_run, er_p1, er_p2, er_fits = crah_header("rt.clg.chw.hdr.e.r", crahs_e, None, True)
    for sub, flip, joins in (
            ("s", False, ((ws_p2, "first"), ("last", es_p1))),
            ("r", True, ((er_p2, "first"), ("last", wr_p2)))):
        r = routes[f"rt.clg.chw.hdr.n.{sub}"]
        pts = [tuple(w) for w in r.waypoints]
        if flip:
            pts = list(reversed(pts))
        run = chw.run(r.id, r.diameter)
        p1, p2 = run.polyline(r.id, pts, chw.bend)
        ends = {"first": p1, "last": p2}
        for a, c in joins:
            run.connect(ends.get(a, a), ends.get(c, c))
        authored.add(r.id)

    # CHW mains: chillers sit ON the main -> JUNCTION taps offset +-0.25 m
    # (the CH-2 tap replaces/extends the main end -> terminus BEND fitting).
    chw_plant = sorted((e for e in cool_equip if e.loop == "chw" and e.space == "sp.plant"
                        and e.cls in ("pump", "ahu")), key=lambda e: e.id)
    hx = eq.get("clg.hx.1")
    chw_hdr_hf = ws_run.fw / 2.0
    for sub, to_hall in (("s", True), ("r", False)):
        r = routes[f"rt.clg.chw.main.{sub}"]
        supply = sub == "s"
        pts = [tuple(w) for w in r.waypoints]
        if not to_hall:
            pts = list(reversed(pts))
        # butt the hall-header junction (its arm faces west)
        i = -1 if to_hall else 0
        pts[i] = (pts[i][0] - chw_hdr_hf, pts[i][1], pts[i][2])
        # chiller taps: CH at the plant end of the main -> terminus fitting
        ch_taps = []
        j = 0 if to_hall else -1
        plant_end = pts[j]
        for e in chillers:
            tx = e.pos[0] + (-STUB_OFF if supply else STUB_OFF)
            tp = (tx, e.pos[1], plant_end[2])
            if abs(e.pos[0] - plant_end[0]) < 1e-6:
                pts[j] = tp                    # shorten (supply) / extend (return)
                ch_taps.append((e.id, tp, "BEND"))
            else:
                ch_taps.append((e.id, tp, "JUNCTION"))
        branches = [(e, f"rt.{e.id}{'.chw' if e is hx else ''}.{sub}")
                    for e in chw_plant + [hx]]
        taps, ties = main_ties(branches, pts)
        run = chw.run(r.id, r.diameter)
        p1, p2, fits = _route(run, r.id, pts, chw.bend, chw.junc, taps + ch_taps)
        authored.add(r.id)
        # main <-> hall header (junction "main" on hdr.w)
        h_run, h_fits = (ws_run, ws_fits) if supply else (wr_run, wr_fits)
        h_arm, _ = arm(h_run, h_fits, "main", (-1, 0, 0))
        if to_hall:
            run.connect(p2, h_arm)
        else:
            run.connect(h_arm, p1)
        for e in chillers:  # chillers source the supply, sink the return
            stub_tap(run, fits, e.id, e,
                     (e.pos[0] + (-STUB_OFF if supply else STUB_OFF), e.pos[1]),
                     plant_end[2], to_equipment=not supply)
        for e, rid in branches:
            hp, hpt = tie_port(*ties[rid], p1, p2, run, fits, rid, e)
            if e.cls == "pump":
                pump_branch(chw, rid, e, hp, hpt, supply=supply)
            else:  # AHU + trim HX consume CHW
                tie_branch(chw, rid, e, hp, hpt, to_equipment=supply)

    # ==== 5. SYSTEMS ======================================================
    missing = {r.id for r in plan.routes if r.kind == "pipe"} - authored
    if missing:
        raise ValueError(f"cooling: unauthored pipe routes: {sorted(missing)}")
    fws.commit("Facility water serves the building")
    tcs.commit("Technology cooling serves Hall A")
    chw.commit("Chilled water serves Hall B and the office")

    # ==== 6. POWER INTAKES ================================================
    # The electrical module (built earlier in the combined model) registers
    # each mech-feed cable end as "{load_id}.pwr" (FlowDirection SOURCE).
    # Consume them: one ELECTRICAL intake port per powered unit, at the unit
    # top, connected feed -> intake. Absent in a standalone cooling build.
    for e in cool_equip:
        feed = b.ports.get(f"{e.id}.pwr")
        if feed is None:
            continue
        intake = b.add_port(els[e.id], system_type="ELECTRICAL", predefined="CABLE",
                            matrix=at(Z_UP, (e.pos[0], e.pos[1], e.size[2])),
                            flow="SINK", key=f"{e.id}.pwr.intake")
        b.connect(feed, intake)
