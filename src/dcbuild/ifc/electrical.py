"""ELECTRICAL discipline: the 2N power distribution, as a connected port graph.

Two fully-independent trains (side A warm red, side B blue) from utility intake
to every rack:

    UTIL -> RMU -> TX -> MSB -> UPS (x4, + battery strings) -> UOB -> PDU
         -> row busway -> tap junction -> drop cord -> rack (hand-off to `it`)

Authored here:
  * every plan equipment with discipline == "power", per the conventions class
    mapping, typed (one shared type per spec class), boxed, contained in its
    space (EXT -> site), rated via DC_<Class>Rating typed psets;
  * every RouteP kind == "cable" as a Run polyline (LV / HV / DC cable segments
    with JUNCTION fittings at bends — cables have no BEND enum; the fuel-line
    edges, which the resolver also emits as kind "cable", follow the binding
    class map instead: IfcPipeSegment/RIGIDSEGMENT + BEND, SystemType FUEL);
  * every RunP kind == "busway" as a comb: BUSBARSEGMENT spans between a
    JUNCTION tap fitting per rack, each with a drop cord down to rack top; the
    feed end ties to a nozzle port on its PDU.

Cross-module hand-off (conventions): every drop-cord BOTTOM port is registered
in ``b.ports`` as ``{rack_id}.pwr.{a|b}``, FlowDirection SOURCE — the `it`
module authors the rack's SINK intake and connects. Mechanical loads (mech_feeds
cables to `clg.*` equipment owned by `cooling`) get their cable end registered
as ``{load_id}.pwr`` instead of a nozzle we must not author.

Note: IfcElectricApparentPowerMeasure does not exist in IFC4X3_ADD2, so kVA
ratings use IfcPowerMeasure (values converted to SI: VA / W / J / m3).
"""
from __future__ import annotations

from .geom import X_RUN, X_RUN_NEG, Z_UP, at, rot_z
from .run import Run

RACK_TOP = 2.3        # drop-cord bottom z — the rack hand-off point
FUEL_DIA = 0.08       # fuel line bore (m)
CABLE_TRAY = (0.12, 0.06)

SIDE_RGB = {"A": (0.75, 0.22, 0.17), "B": (0.17, 0.35, 0.75)}
SIDE_MATERIAL = {"A": "Power Train A", "B": "Power Train B"}

# spec class -> (occurrence class, type class, predefined, type name, ObjectType)
CLASS_MAP = {
    "utility_intake": ("IfcBuildingElementProxy", "IfcBuildingElementProxyType",
                       "USERDEFINED", "Utility Intake", "UtilityIntake"),
    "rmu":         ("IfcElectricDistributionBoard", "IfcElectricDistributionBoardType",
                    "SWITCHBOARD", "Ring Main Unit 11kV", None),
    "msb":         ("IfcElectricDistributionBoard", "IfcElectricDistributionBoardType",
                    "SWITCHBOARD", "Main LV Switchboard", None),
    "uob":         ("IfcElectricDistributionBoard", "IfcElectricDistributionBoardType",
                    "SWITCHBOARD", "UPS Output Board", None),
    "pdu":         ("IfcElectricDistributionBoard", "IfcElectricDistributionBoardType",
                    "DISTRIBUTIONBOARD", "Power Distribution Unit", None),
    "hdb":         ("IfcElectricDistributionBoard", "IfcElectricDistributionBoardType",
                    "DISTRIBUTIONBOARD", "House Distribution Board", None),
    "mcc":         ("IfcElectricDistributionBoard", "IfcElectricDistributionBoardType",
                    "MOTORCONTROLCENTRE", "Motor Control Centre", None),
    "transformer": ("IfcTransformer", "IfcTransformerType",
                    "CURRENT", "Cast Resin Transformer 11kV/400V", None),
    "generator":   ("IfcElectricGenerator", "IfcElectricGeneratorType",
                    "STANDALONE", "Standby Diesel Generator", None),
    "ups":         ("IfcElectricFlowStorageDevice", "IfcElectricFlowStorageDeviceType",
                    "UPS", "UPS Module", None),
    "battery":     ("IfcElectricFlowStorageDevice", "IfcElectricFlowStorageDeviceType",
                    "BATTERY", "Battery String", None),
    "fuel_tank":   ("IfcTank", "IfcTankType", "STORAGE", "Diesel Fuel Tank", None),
}

# plan rating key -> (property name, measure type, to-SI conversion)
RATING_PROPS = {
    "rating_kva": ("RatedApparentPower", "IfcPowerMeasure", lambda v: float(v) * 1e3),
    "rating_kw":  ("RatedPower", "IfcPowerMeasure", lambda v: float(v) * 1e3),
    "rating_kwh": ("StoredEnergy", "IfcEnergyMeasure", lambda v: float(v) * 3.6e6),
    "voltage":    ("Voltage", "IfcLabel", str),
    "volume_l":   ("Volume", "IfcVolumeMeasure", lambda v: float(v) / 1e3),
    "fuel":       ("FuelType", "IfcLabel", str),
}

KIND_LABEL = {"hv_cable": "HV Cable", "lv_cable": "LV Cable",
              "dc_cable": "DC Cable", "fuel_line": "Fuel Line"}


def _camel(cls: str) -> str:
    return "".join(p.capitalize() for p in cls.split("_"))


class _Run(Run):
    """Run that also stamps DC_Identity on every member it authors (the base
    class only keys them). Keys are re-derived from the deterministic counters."""

    def __init__(self, b, system, base, *, side=None, **kw):
        super().__init__(b, system, base, **kw)
        self._side = side

    def seg(self, *args, **kw):
        out = super().seg(*args, **kw)
        self.b.identify(out[0], f"{self.base}.seg{self._n['seg']:03d}", Side=self._side)
        return out

    def fitting(self, *args, **kw):
        el = super().fitting(*args, **kw)
        self.b.identify(el, f"{self.base}.fit{self._n['fit']:03d}", Side=self._side)
        return el

    def dropper(self, *args, **kw):
        out = super().dropper(*args, **kw)
        self.b.identify(out[0], f"{self.base}.drop{self._n['drop']:03d}", Side=self._side)
        return out


# ---------------------------------------------------------------- equipment
def _equipment(b, plan):
    """All power-discipline equipment. Returns {spec_id: (element, EquipP)}."""
    els: dict[str, tuple] = {}
    by_side: dict[str, list] = {"A": [], "B": []}
    for e in plan.equipment:
        if e.discipline != "power":
            continue
        occ_class, type_class, predef, type_name, object_type = CLASS_MAP[e.cls]
        etype = b.typed(type_class, predef, type_name, key=f"type.pwr.{e.cls}")
        el = b.entity(occ_class, predefined=predef, name=e.name, key=e.id)
        if object_type:
            el.ObjectType = object_type
            etype.ElementType = object_type
        b.assign_type([el], etype)
        w, d, h = e.size
        m = rot_z(e.rot, e.pos) if e.rot else at(Z_UP, e.pos)
        b.box(el, w, d, h, m, structure=b.container_for(e.space))
        b.identify(el, e.id, Side=e.side)
        items = [(name, measure, conv(e.rating[k]))
                 for k, (name, measure, conv) in RATING_PROPS.items() if k in e.rating]
        if items:
            b.properties(el, f"DC_{_camel(e.cls)}Rating", items)
        by_side[e.side or "A"].append(el)
        els[e.id] = (el, e)
    for side, group in by_side.items():
        # utility-intake proxies are not IfcDistributionElements — the system
        # API (correctly) refuses them as members; they still carry ports.
        b.assign_system([el for el in group if el.is_a("IfcDistributionElement")],
                        b.system(f"sys.pwr.{side.lower()}"))
        _paint(b, group, side)
    return els


def _paint(b, elements, side):
    b.assign_material(elements, b.material(SIDE_MATERIAL[side], "electrical",
                                           rgb=SIDE_RGB[side]))
    for el in elements:
        b.style_product(el, SIDE_MATERIAL[side])


def _nozzle(b, element, key, location, system_type="ELECTRICAL", kind="CABLE", flow=None):
    """A deterministic equipment connection port at world `location`."""
    return b.add_port(element, system_type=system_type, predefined=kind,
                      matrix=at(Z_UP, location), flow=flow, key=key)


# ---------------------------------------------------------------- shared types
def _run_types(b):
    t = {
        "lv": b.typed("IfcCableSegmentType", "CABLESEGMENT",
                      "LV Power Cable", key="type.pwr.cable.lv"),
        "hv": b.typed("IfcCableSegmentType", "CABLESEGMENT",
                      "HV Power Cable 11kV", key="type.pwr.cable.hv"),
        "dc": b.typed("IfcCableSegmentType", "CABLESEGMENT",
                      "DC Battery Cable", key="type.pwr.cable.dc"),
        "junction": b.typed("IfcCableFittingType", "JUNCTION",
                            "Cable Junction", key="type.pwr.cable.junction"),
        "fuel_seg": b.typed("IfcPipeSegmentType", "RIGIDSEGMENT",
                            "Fuel Line DN80", key="type.pwr.fuel.seg"),
        "fuel_bend": b.typed("IfcPipeFittingType", "BEND",
                             "Fuel Line Bend DN80", key="type.pwr.fuel.bend"),
        "busway": b.typed("IfcCableSegmentType", "BUSBARSEGMENT",
                          "Busbar Trunking", key="type.pwr.busway"),
        "tap": b.typed("IfcCableFittingType", "JUNCTION",
                       "Busway Tap-Off Junction", key="type.pwr.busway.tap"),
        "cord": b.typed("IfcCableSegmentType", "CABLESEGMENT",
                        "Rack Power Cord", key="type.pwr.cord"),
    }
    b.properties(t["hv"], "DC_CableRating", [("Voltage", "IfcLabel", "11kV")])
    return t


# ---------------------------------------------------------------- cable routes
def _cable_routes(b, plan, els, types):
    edge_kind = {(e.src, e.dst): e.kind for e in plan.edges}
    for r in plan.routes:
        if r.kind != "cable":
            continue
        kind = edge_kind.get((r.from_id, r.to_id), "lv_cable")
        side = r.system.rsplit(".", 1)[1].upper()
        system = b.system(r.system)

        if kind == "fuel_line":  # binding class map: fuel legs are pipe, SystemType FUEL
            run = _Run(b, system, r.id, side=side, system_type="FUEL",
                       seg_type=types["fuel_seg"], seg_predef="RIGIDSEGMENT",
                       seg_class="IfcPipeSegment", fit_class="IfcPipeFitting",
                       branch_predef="JUNCTION", bend_predef="BEND",
                       port_kind="PIPE", diameter=FUEL_DIA)
            bend_type, port_st, port_kind = types["fuel_bend"], "FUEL", "PIPE"
        else:
            run = _Run(b, system, r.id, side=side, system_type="ELECTRICAL",
                       seg_type=types[{"hv_cable": "hv", "dc_cable": "dc"}.get(kind, "lv")],
                       seg_predef="CABLESEGMENT",
                       seg_class="IfcCableSegment", fit_class="IfcCableFitting",
                       branch_predef="JUNCTION", bend_predef="JUNCTION",
                       port_kind="CABLE", tray=CABLE_TRAY)
            bend_type, port_st, port_kind = types["junction"], "ELECTRICAL", "CABLE"

        def _name(eid):
            return els[eid][1].name if eid in els else eid
        label = f"{KIND_LABEL[kind]} {_name(r.from_id)}-{_name(r.to_id)}"
        first, last = run.polyline(label, r.waypoints, bend_type)

        # Tie the ends: nozzle on each referenced equipment, SOURCE = upstream.
        z0, z1 = r.waypoints[0][2], r.waypoints[-1][2]
        el_from, e_from = els[r.from_id]
        nz_from = _nozzle(b, el_from, f"{r.id}.nz.from",
                          (e_from.pos[0], e_from.pos[1], z0),
                          system_type=port_st, kind=port_kind)
        b.connect(nz_from, first, direction="SOURCE")
        if r.to_id in els:
            el_to, e_to = els[r.to_id]
            nz_to = _nozzle(b, el_to, f"{r.id}.nz.to",
                            (e_to.pos[0], e_to.pos[1], z1),
                            system_type=port_st, kind=port_kind)
            b.connect(last, nz_to, direction="SOURCE")
        else:
            # Mechanical load owned by the cooling module: register the live
            # cable end for it to consume (absent in federated files).
            last.FlowDirection = "SOURCE"
            b.ports[f"{r.to_id}.pwr"] = last

        b.assign_system(run.members, system)
        _paint(b, run.members, side)


# ---------------------------------------------------------------- busways
def _busways(b, plan, els, types):
    rack_id = {(r.row, r.index): r.id for r in plan.racks}
    for rp in plan.runs:
        if rp.kind != "busway":
            continue
        side = rp.side
        system = b.system(f"sys.pwr.{side.lower()}")
        run = _Run(b, system, rp.id, side=side, system_type="ELECTRICAL",
                   seg_type=types["busway"], seg_predef="BUSBARSEGMENT",
                   seg_class="IfcCableSegment", fit_class="IfcCableFitting",
                   drop_type=types["cord"], drop_predef="CABLESEGMENT",
                   branch_predef="JUNCTION", bend_predef="JUNCTION",
                   port_kind="CABLE", tray=tuple(rp.size), drop=(0.05, 0.05))
        label = f"Busway {side} {rp.row.split('.')[-1].upper()}"

        # Comb along the row (mirrors Run.comb_run, but EVERY tap — including
        # the last, where the run ends with no open through-port — is a
        # JUNCTION with a drop cord whose bottom port is registered per rack).
        taps = list(enumerate(rp.taps, start=1))       # (rack index, tap x)
        x_prev = rp.x_start if side == "A" else rp.x_end   # feed end: nearest PDU
        if side == "B":
            taps.reverse()
        hf = run.fw / 2.0
        feed = prev_far = None
        n = len(taps)
        for k, (idx, rx) in enumerate(taps, start=1):
            s = 1.0 if rx >= x_prev else -1.0
            frame = X_RUN if s > 0 else X_RUN_NEG
            start_x = x_prev if prev_far is None else x_prev + s * hf
            seg, p_near, p_far = run.seg(f"{label} Seg {k}", frame,
                                         (start_x, rp.y, rp.z),
                                         abs((rx - s * hf) - start_x))
            if prev_far is None:
                feed = p_near
            else:
                run.connect(prev_far, p_near)
            fit = run.fitting(f"{label} Tap {k}", run.branch_predef, types["tap"],
                              (rx, rp.y, rp.z))
            near_arm = run.port(fit, (rx - s * hf, rp.y, rp.z), frame)
            run.connect(p_far, near_arm)
            branch_arm = run.port(fit, (rx, rp.y, rp.z))
            drp, d_top, d_bot = run.dropper(f"{label} Drop {k}", rx, rp.y, rp.z, RACK_TOP)
            run.connect(branch_arm, d_top)
            # Hand-off: this cord FEEDS the rack; `it` authors the SINK + connects.
            d_bot.FlowDirection = "SOURCE"
            b.ports[f"{rack_id[(rp.row, idx)]}.pwr.{side.lower()}"] = d_bot
            if k < n:
                prev_far = run.port(fit, (rx + s * hf, rp.y, rp.z), frame)
            x_prev = rx

        # Feed end -> nozzle on the feeding PDU.
        pdu_el, pdu_e = els[rp.feed]
        nz = _nozzle(b, pdu_el, f"{rp.id}.nz.feed",
                     (pdu_e.pos[0], pdu_e.pos[1], rp.z))
        b.connect(nz, feed, direction="SOURCE")

        b.assign_system(run.members, system)
        _paint(b, run.members, side)


# ---------------------------------------------------------------- entry point
def build(b, plan):
    els = _equipment(b, plan)
    types = _run_types(b)
    _cable_routes(b, plan, els, types)
    _busways(b, plan, els, types)
    for side in ("A", "B"):
        b.serves_building(b.system(f"sys.pwr.{side.lower()}"),
                          f"Power train {side} serves the building")
