"""IFC validation gate (G1). STRICT and BLOCKING — non-zero exit on any failure.

Every check returns a list of failure strings; empty = pass (style of graph.py).

  schema        ifcopenshell.validate with express rules, per file: any
                schema/express error = FAIL
  ports         (demo-datacentre-01.ifc) every IfcRelConnectsPorts joins two existing,
                placed ports of the same SystemType; every IfcDistributionPort
                nests in exactly one element
  guids         (demo-datacentre-01.ifc) no GlobalId collisions across ALL rooted entities
                (deterministic keys collide if two modules reuse a key)
  orphans       (demo-datacentre-01.ifc) every IfcProduct (except annotations / grids /
                ports / openings) is contained or aggregated somewhere
  plan          (demo-datacentre-01.ifc) the file matches the resolved plan: rack / wall /
                door / column counts, every equipment id present by DC guid,
                all systems present as IfcDistributionSystem
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.validate

from .. import ids, layout, spec as spec_mod
from .cameras import approaches_and_yards, cameras, statuses

COMBINED = "demo-datacentre-01.ifc"
DETAIL_CAP = 25
# products legitimately outside the containment tree
ORPHAN_EXEMPT = ("IfcAnnotation", "IfcGrid", "IfcPort", "IfcOpeningElement")


def _ref(e) -> str:
    return f"{e.is_a()}:{getattr(e, 'GlobalId', '?')}({getattr(e, 'Name', None) or '-'})"


# ------------------------------------------------------------------ checks
def schema(path: Path) -> list[str]:
    fails = []
    logger = ifcopenshell.validate.json_logger()
    try:
        ifcopenshell.validate.validate(str(path), logger, express_rules=True)
    except ModuleNotFoundError as exc:
        # ifcopenshell's express rule_executor imports _pytest for assertion
        # rewriting. No silent skip: rerun attribute-level checks and FAIL.
        fails.append(f"schema: express rules NOT run ({exc}) — "
                     f"install pytest or run via scripts/check_all.sh")
        logger = ifcopenshell.validate.json_logger()
        ifcopenshell.validate.validate(str(path), logger, express_rules=False)
    for s in logger.statements:
        if str(s.get("level", "error")).lower() not in ("error", "critical"):
            continue
        where = s.get("attribute") or (str(s["instance"])[:60] if s.get("instance") else "")
        fails.append(f"schema: {s['message']}" + (f" [{where}]" if where else ""))
    return fails


def ports(f: ifcopenshell.file) -> list[str]:
    fails = []
    for rel in f.by_type("IfcRelConnectsPorts"):
        p1, p2 = rel.RelatingPort, rel.RelatedPort
        if p1 is None or p2 is None:
            fails.append(f"ports: connection {rel.GlobalId} missing a port")
            continue
        for p in (p1, p2):
            if p.ObjectPlacement is None:
                fails.append(f"ports: {_ref(p)} in a connection but unplaced")
        if p1.SystemType != p2.SystemType:
            fails.append(f"ports: SystemType mismatch {p1.SystemType} <-> {p2.SystemType} "
                         f"({_ref(p1)} <-> {_ref(p2)})")
    for port in f.by_type("IfcDistributionPort"):
        n = len(port.Nests or ())
        if n != 1:
            fails.append(f"ports: {_ref(port)} nests in {n} elements (want exactly 1)")
    return fails


def guids(f: ifcopenshell.file) -> list[str]:
    seen = defaultdict(list)
    for e in f.by_type("IfcRoot"):
        seen[e.GlobalId].append(e)
    return [f"guid: {g} used by {len(es)} entities "
            f"({', '.join(_ref(e) for e in es[:4])})"
            for g, es in sorted(seen.items()) if len(es) > 1]


def orphans(f: ifcopenshell.file) -> list[str]:
    fails = []
    for e in f.by_type("IfcProduct"):
        if any(e.is_a(c) for c in ORPHAN_EXEMPT):
            continue
        placed = (getattr(e, "ContainedInStructure", None)
                  or getattr(e, "Decomposes", None)
                  or getattr(e, "Nests", None))
        if not placed:
            fails.append(f"orphan: {_ref(e)} neither contained nor aggregated")
    return fails


def plan_consistency(f: ifcopenshell.file, plan) -> list[str]:
    fails = []
    by_guid: dict[str, ifcopenshell.entity_instance] = {}
    for e in f.by_type("IfcRoot"):
        by_guid.setdefault(e.GlobalId, e)

    # racks: exact count of TECHNICALCABINET furniture (server racks + the
    # MMR/comms carrier racks, which are equipment in the plan), each joined
    # by DC guid
    cabinets = [e for e in f.by_type("IfcFurniture")
                if ifcopenshell.util.element.get_predefined_type(e) == "TECHNICALCABINET"]
    want_cabinets = len(plan.racks) + sum(1 for e in plan.equipment
                                          if e.cls == "carrier_rack")
    if len(cabinets) != want_cabinets:
        fails.append(f"plan: {len(cabinets)} TECHNICALCABINET IfcFurniture "
                     f"!= {want_cabinets} plan racks+carrier racks")
    missing = [r.id for r in plan.racks
               if not (e := by_guid.get(ids.guid(r.id))) or not e.is_a("IfcFurniture")]
    if missing:
        fails.append(f"plan: {len(missing)} racks missing by guid "
                     f"(e.g. {sorted(missing)[:3]})")

    for cls, want, label in (("IfcWall", len(plan.walls), "walls"),
                             ("IfcDoor", len(plan.doors), "doors"),
                             ("IfcColumn", len(plan.columns), "columns")):
        got = len(f.by_type(cls))
        if got != want:
            fails.append(f"plan: {got} {cls} != {want} plan {label}")

    miss_eq = [e.id for e in plan.equipment if ids.guid(e.id) not in by_guid]
    if miss_eq:
        fails.append(f"plan: {len(miss_eq)}/{len(plan.equipment)} equipment missing by guid "
                     f"(e.g. {sorted(miss_eq)[:3]})")

    for s in plan.systems:
        e = by_guid.get(ids.guid(s.id))
        if e is None or not e.is_a("IfcDistributionSystem"):
            fails.append(f"plan: system {s.id} missing as IfcDistributionSystem")
    return fails


# ------------------------------------------------------------------ gate
def validate_file(path: Path, plan) -> list[str]:
    fails = schema(path)
    f = ifcopenshell.open(str(path))
    fails += statuses(f, plan)
    if path.name == COMBINED:
        fails += ports(f) + guids(f) + orphans(f) + plan_consistency(f, plan)
        fails += cameras(f, plan) + approaches_and_yards(f, plan)
        from .fitout import check as fitout_check
        fails += fitout_check(f, plan)
    elif path.name == "demo-datacentre-01-security.ifc":
        fails += cameras(f, plan)
    return fails


def main(dir: Path, variant="base") -> int:
    assert dir.is_dir(), f"validate-ifc: {dir} is not a directory"
    files = sorted(p for p in dir.glob("*.ifc") if not p.name.startswith("smoke"))
    assert files, f"validate-ifc: no .ifc files in {dir}"
    required = {COMBINED, *[f"demo-datacentre-01-{d}.ifc" for d in
                ("arch", "structure", "site", "electrical", "cooling", "it", "security")]}
    plan = layout.resolve(spec_mod.load(variant=variant))
    if plan.meta.get("fitout"):
        required.add("demo-datacentre-01-fitout.ifc")
    missing = required - {p.name for p in files}
    if missing:
        print(f"G1 FAIL — missing required files: {sorted(missing)}")
        return 1

    results: dict[str, list[str]] = {}
    for path in files:
        results[path.name] = fails = validate_file(path, plan)
        if fails:
            print(f"-- {path.name}")
            for msg in fails[:DETAIL_CAP]:
                print(f"FAIL  {msg}")
            if len(fails) > DETAIL_CAP:
                print(f"      ... and {len(fails) - DETAIL_CAP} more")

    width = max(len(n) for n in results)
    print(f"\nG1 summary ({dir})")
    for name, fails in results.items():
        print(f"  {name:<{width}}  {'FAIL (' + str(len(fails)) + ')' if fails else 'PASS'}")
    total = sum(len(v) for v in results.values())
    if total:
        print(f"G1 FAIL — {total} failures in "
              f"{sum(1 for v in results.values() if v)}/{len(results)} files")
        return 1
    print(f"G1 OK — {len(results)} files clean (schema+express"
          f"{', ports, guids, orphans, plan' if COMBINED in results else ''})")
    return 0
