"""IT fit-out: server cabinets, data containment and carrier racks.

* Racks — typed IfcFurniture/TECHNICALCABINET (one shared type per rack
  footprint, own representation per occurrence — WR11: one user per rep),
  with the DC_Rack rating pset and their own service intake ports. In the
  combined build the upstream modules (electrical, cooling) have already
  registered the busway drop-cord / TCS hose ports in ``b.ports`` under
  ``{rack_id}.pwr.{a|b}`` / ``{rack_id}.clg.{s|r}``; we author the rack-side
  port and make the SOURCE -> SINK connection. Standalone, the registry is
  empty and the ports are simply not authored.
* Data trays — a comb ``Run`` per rack row (CABLETRAYSEGMENTs butting TEE
  fittings, a DROPPER onto every cabinet, BEND at the row end), collected by
  per-row spine stubs into the hall spine, which crosses the corridor into
  the serving MMR. The whole hall system is one connected port graph whose
  upstream (carrier) end is the spine's MMR entry.
* MMR / office comms carrier racks — same cabinet pattern, assigned to the
  data system they serve.
"""
from __future__ import annotations

import re

import ifcopenshell.guid
import numpy as np

from .geom import X_RUN, X_RUN_NEG, Z_UP, at, rot_z
from .run import Run
from .. import ids

RACK_MAT = "Rack Steel"
TRAY_MAT = "Data Tray Steel"
RACK_RGB = (0.15, 0.15, 0.18)
TRAY_RGB = (0.8, 0.7, 0.2)

DROP_BOTTOM = 2.25         # droppers land just above the cabinet top
CLG_PORT_Z = 2.0           # rack DLC hose intake ports: rack rear top

_MAIN = re.compile(r"rt\.it\.spine\.([a-z0-9]+)$")
_STUB = re.compile(r"rt\.it\.spine\.([a-z0-9]+)\.r(\d+)$")

# carrier-rack id prefix -> the data system those racks serve
_CARRIER_SYSTEM = {"it.mmr1": "sys.data.a", "it.mmr2": "sys.data.b",
                   "it.comms": "sys.data.off"}


def build(b, plan) -> None:
    rack_mat = b.material(RACK_MAT, "steel", rgb=RACK_RGB)
    tray_mat = b.material(TRAY_MAT, "steel", rgb=TRAY_RGB)

    _racks(b, plan, rack_mat)
    types, drop_type = _carrier_types(b, plan, tray_mat)
    feeds = _row_combs(b, plan, types, drop_type, tray_mat)
    _spine_routes(b, plan, types, drop_type, feeds, tray_mat)
    _carrier_racks(b, plan, rack_mat)

    for sys_id, label in (("sys.data.a", "Hall A data containment serves the building"),
                          ("sys.data.b", "Hall B data containment serves the building"),
                          ("sys.data.off", "Office structured cabling serves the building")):
        if sys_id in b.systems:
            b.serves_building(b.systems[sys_id], label)


# ---------------------------------------------------------------- cabinets
def _cabinet(b, type_name, type_key, name, key, size, matrix, space, mat):
    """One typed TECHNICALCABINET occurrence with its own rep (WR11)."""
    w, d, h = size
    rtype = b.typed("IfcFurnitureType", "TECHNICALCABINET", type_name, key=type_key)
    el = b.entity("IfcFurniture", name=name, key=key)
    b.assign_type([el], rtype)
    b.assign_rep(el, b.profile_rep(b.rect_profile(w, d), h))
    b.contain(el, matrix, structure=b.container_for(space))
    b.assign_material([el], mat)
    b.style_product(el, RACK_MAT)
    return el


def _racks(b, plan, mat) -> None:
    for r in plan.racks:
        w, d, h = r.size
        tag = f"{round(w * 1000)}x{round(d * 1000)}"
        row = r.row.split(".")[-1].upper()               # it.row.a1 -> A1
        x, y = r.pos
        el = _cabinet(b, f"Server Rack {tag}", f"type.it.rack.{tag}",
                      f"Server Rack {row}-{r.index:02d}", r.id, r.size,
                      at(Z_UP, (x, y, 0.0)), r.space, mat)
        b.identify(el, r.id, Hall=r.hall)
        b.properties(el, "DC_Rack", [
            ("RatedPowerkW", "IfcPowerMeasure", float(r.kw)),
            ("Cooling", "IfcLabel", r.cooling),
        ])
        _rack_service_ports(b, r, el, x, y, h)


def _rack_service_ports(b, r, el, x, y, h) -> None:
    """Rack intake ports, connected to the upstream ports registered by
    electrical / cooling (combined build only — absent keys are skipped)."""
    for side in ("a", "b"):
        drop = b.ports.get(f"{r.id}.pwr.{side}")
        if drop is not None:                             # busway drop cord -> rack
            port = b.add_port(el, system_type=drop.SystemType or "ELECTRICAL",
                              predefined="CABLE", matrix=at(Z_UP, (x, y, h)),
                              flow="SINK", key=f"{r.id}.port.pwr.{side}")
            b.connect(drop, port, direction="SOURCE")
    if r.cooling == "dlc":
        # NOTE: IfcDistributionSystemEnum has no COOLING value in IFC4X3_ADD2
        # (conventions.md says sys.tcs -> COOLING; that keyword does not exist
        # in the schema). Mirror the upstream hose port's SystemType so the
        # connected pair always shares whatever valid value cooling chose.
        supply = b.ports.get(f"{r.id}.clg.s")
        if supply is not None:                           # TCS hose -> rack inlet
            port = b.add_port(el, system_type=supply.SystemType or "CHILLEDWATER",
                              predefined="PIPE",
                              matrix=at(Z_UP, (x, y, CLG_PORT_Z)), flow="SINK",
                              key=f"{r.id}.port.clg.s")
            b.connect(supply, port, direction="SOURCE")
        ret = b.ports.get(f"{r.id}.clg.r")
        if ret is not None:                              # rack outlet -> return hose
            port = b.add_port(el, system_type=ret.SystemType or "CHILLEDWATER",
                              predefined="PIPE",
                              matrix=at(Z_UP, (x, y, CLG_PORT_Z)), flow="SOURCE",
                              key=f"{r.id}.port.clg.r")
            b.connect(port, ret, direction="SOURCE")


def _carrier_racks(b, plan, mat) -> None:
    for e in plan.equipment:
        if e.cls != "carrier_rack":
            continue
        sys_id = next((s for p, s in _CARRIER_SYSTEM.items()
                       if e.id.startswith(p + ".")), None)
        w, d, h = e.size
        tag = f"{round(w * 1000)}x{round(d * 1000)}"
        x, y, z = e.pos
        matrix = rot_z(e.rot, (x, y, z)) if e.rot else at(Z_UP, (x, y, z))
        el = _cabinet(b, f"Carrier Rack {tag}", f"type.it.carrier_rack.{tag}",
                      e.name, e.id, e.size, matrix, e.space, mat)
        b.identify(el, e.id, System=sys_id)
        if sys_id:
            # ifcopenshell.api.system.assign_system rejects IfcFurniture in an
            # IfcDistributionSystem; the schema allows any object in the group,
            # so author the IfcRelAssignsToGroup directly.
            b.file.create_entity(
                "IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[el], RelatingGroup=b.system(sys_id))


# ------------------------------------------------------------- containment
def _carrier_types(b, plan, mat):
    """Shared carrier types per tray size in the plan + the one dropper type."""
    it = plan.it_cfg["containment"]
    sizes = {tuple(r.size) for r in plan.runs if r.kind == "tray"}
    sizes |= {tuple(r.size) for r in plan.routes if r.kind == "tray"}
    types = {}
    for size in sorted(sizes):
        tag = f"{round(size[0] * 1000)}x{round(size[1] * 1000)}"
        seg = b.typed("IfcCableCarrierSegmentType", "CABLETRAYSEGMENT",
                      f"Cable Tray {tag} GI", key=f"type.it.tray.{tag}")
        tee = b.typed("IfcCableCarrierFittingType", "TEE",
                      f"Cable Tray Tee {tag}", key=f"type.it.tee.{tag}")
        bend = b.typed("IfcCableCarrierFittingType", "BEND",
                       f"Cable Tray Bend {tag}", key=f"type.it.bend.{tag}")
        b.pset(seg, "Pset_CableCarrierSegmentTypeCommon",
               {"Reference": f"CT-{tag}", "Status": "NEW"})
        b.assign_material([seg, tee, bend], mat)
        types[size] = (seg, tee, bend)

    dw, dh = it["dropper_size"]
    dtag = f"{round(dw * 1000)}x{round(dh * 1000)}"
    drop = b.typed("IfcCableCarrierSegmentType", "DROPPER",
                   f"Cable Tray Dropper {dtag}", key=f"type.it.drop.{dtag}")
    b.pset(drop, "Pset_CableCarrierSegmentTypeCommon",
           {"Reference": f"CT-DROP-{dtag}", "Status": "NEW"})
    b.assign_material([drop], mat)
    return types, (drop, (dw, dh))


def _tray_run(b, base, size, types, drop_type, system):
    seg_t, _tee_t, _bend_t = types[tuple(size)]
    drop_t, drop_size = drop_type
    return Run(b, system, base, system_type="DATA", seg_type=seg_t,
               seg_predef="CABLETRAYSEGMENT", drop_type=drop_t,
               tray=tuple(size), drop=tuple(drop_size), port_kind="CABLECARRIER")


def _finish_run(b, run, sys_id, mat_name=TRAY_MAT) -> None:
    """Identity + colour + system membership for every generated member.

    The member keys are reconstructed exactly as ``Run._key`` issued them
    (per-kind counters in creation order, verified against each member's
    deterministic GlobalId), so DC_Identity always matches GlobalId.
    """
    counters = {"seg": 0, "fit": 0, "drop": 0}
    for m in run.members:
        for kind in ("seg", "fit", "drop"):
            key = f"{run.base}.{kind}{counters[kind] + 1:03d}"
            if m.GlobalId == ids.guid(key):
                counters[kind] += 1
                break
        else:
            raise AssertionError(f"{run.base}: member {m.GlobalId} has no Run key")
        b.identify(m, key, System=sys_id)
        b.style_product(m, mat_name)
    b.assign_material(run.members, b.material(mat_name))
    b.assign_system(run.members, run.system)


def _row_combs(b, plan, types, drop_type, mat):
    """One comb run per rack-row data tray. Returns {row id: comb feed port}."""
    rows = {r.id: r for r in plan.rows}
    feeds = {}
    for rp in plan.runs:
        if rp.kind != "tray":
            continue
        row = rows[rp.row]
        short = row.hall.split(".")[-1]
        sys_id = f"sys.data.{short}"
        run = _tray_run(b, rp.id, rp.size, types, drop_type, b.system(sys_id))
        feeds[rp.row] = run.comb_run(f"Data Tray {short.upper()}{row.index}",
                                     rp.y, rp.z, rp.x_start, rp.taps,
                                     types[tuple(rp.size)][1],   # TEE
                                     types[tuple(rp.size)][2],   # BEND
                                     drop_top=rp.z, drop_bottom=DROP_BOTTOM)
        _finish_run(b, run, sys_id)
    return feeds


def _spine_routes(b, plan, types, drop_type, feeds, mat) -> None:
    """Spine trays: the per-hall main spine (hall face -> corridor -> MMR),
    the per-row stubs tying each comb into it, and the office tray."""
    tray_routes = [r for r in plan.routes if r.kind == "tray"]
    mains = {}    # hall short -> (run, hall-face leg segment, start port, start xyz)

    for rp in tray_routes:                       # pass 1: mains + office
        m = _MAIN.fullmatch(rp.id)
        if m:
            run = _tray_run(b, rp.id, rp.size, types, drop_type, b.system(rp.system))
            first, last = run.polyline(f"Data Spine {m.group(1).upper()}",
                                       rp.waypoints, types[tuple(rp.size)][2])
            last.FlowDirection = "SOURCE"        # open upstream end: carrier hand-off in the MMR
            mains[m.group(1)] = (run, run.members[0], first, rp.waypoints[0])
            _finish_run(b, run, rp.system)
        elif not _STUB.fullmatch(rp.id):         # e.g. rt.it.office
            run = _tray_run(b, rp.id, rp.size, types, drop_type, b.system(rp.system))
            run.polyline(rp.id.replace("rt.it.", "").title() + " Data Tray",
                         rp.waypoints, types[tuple(rp.size)][2])
            _finish_run(b, run, rp.system)

    for rp in tray_routes:                       # pass 2: per-row stubs
        m = _STUB.fullmatch(rp.id)
        if not m:
            continue
        short, n = m.group(1), int(m.group(2))
        run = _tray_run(b, rp.id, rp.size, types, drop_type, b.system(rp.system))
        first, last = run.polyline(f"Spine Stub {short.upper()}{n}",
                                   rp.waypoints, types[tuple(rp.size)][2])
        feed = feeds.get(f"it.row.{short}{n}")
        if feed is not None:                     # stub end -> row comb feed
            run.connect(last, feed)
        main = mains.get(short)
        if main is not None:                     # tie the stub into the main spine
            mrun, mseg, mfirst, mstart = main
            j = rp.waypoints[0]                  # junction: shared coordinate on the spine
            if np.allclose(j, mstart):
                jport = mfirst                   # top row: the spine's own end port
            else:                                # branch port on the spine's hall-face leg
                d = np.asarray(rp.waypoints[1], dtype=float) - np.asarray(j, dtype=float)
                jport = mrun.port(mseg, tuple(j), X_RUN if d[0] >= 0 else X_RUN_NEG)
            mrun.connect(jport, first)
        _finish_run(b, run, rp.system)
