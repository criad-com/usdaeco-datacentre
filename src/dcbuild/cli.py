"""dcbuild CLI.

  dcbuild plan                  resolve spec -> out/build_plan.json (+ summary)
  dcbuild check                 run design invariants on the resolved plan (G0)
  dcbuild build-ifc             author the IFC models (federated per discipline)
  dcbuild validate-ifc          schema + port-graph validation of built IFCs (G1)
  dcbuild parity <revit.ifc>    compare a Revit-exported IFC against ours (G2)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import graph, layout, spec as spec_mod


def _resolve(variant="base"):
    sp = spec_mod.load(variant=variant)
    return sp, layout.resolve(sp)


def cmd_plan(args) -> int:
    _, plan = _resolve(getattr(args, "variant", "base"))
    out = Path(args.out) if args.out else Path("out")/args.variant/"build_plan.json"
    plan.write_json(out)
    from .qa.variants import write_manifest
    write_manifest(plan, Path(args.manifest_dir))
    plan.write_targets(out.with_name("targets.json"))
    print(f"resolved: {len(plan.spaces)} spaces, {len(plan.walls)} walls, "
          f"{len(plan.doors)} doors, {len(plan.columns)} columns, "
          f"{len(plan.racks)} racks, {len(plan.equipment)} equipment, "
          f"{len(plan.runs)} runs, {len(plan.routes)} routes, "
          f"{len(plan.edges)} edges, {len(plan.cameras)} cameras / {len(plan.cameras)} heads -> {out}")
    return 0


def cmd_check(args) -> int:
    _, plan = _resolve(getattr(args, "variant", "base"))
    fails = graph.run_all(plan)
    for f in fails:
        print(f"FAIL  {f}")
    if not fails:
        print(f"G0 OK — all design invariants hold "
              f"({len(graph.ALL_CHECKS)} checks, {len(plan.racks)} racks, "
              f"{sum(r.kw for r in plan.racks):.0f} kW IT load)")
    return 1 if fails else 0


def cmd_build_ifc(args) -> int:
    from .ifc import build as ifc_build
    _, plan = _resolve(getattr(args, "variant", "base"))
    written = ifc_build.build(plan, (Path(args.out) if args.out else Path("out")/args.variant/"ifc"), disciplines=args.disciplines)
    if not args.disciplines:
        import ifcopenshell
        from .qa.variants import write_manifest
        write_manifest(plan, Path(args.manifest_dir), ifcopenshell.open(written[0]))
    for p in written:
        print(f"wrote {p}")
    return 0


def cmd_validate_ifc(args) -> int:
    from .qa import validate_ifc
    return validate_ifc.main(Path(args.dir) if args.dir else Path("out")/args.variant/"ifc", variant=args.variant)


def cmd_build_programme(args) -> int:
    from . import programme
    _, plan = _resolve(args.variant)
    out = Path(args.out) if args.out else Path("out")/args.variant/"programme"
    for path in programme.build(plan, out):
        print(f"wrote {path}")
    return 0


def cmd_parity(args) -> int:
    from .qa import parity
    _, plan = _resolve(getattr(args, "variant", "base"))
    if args.package == "arch":
        return parity.architecture(plan, Path(args.revit_ifc), Path(args.reference), args.report)
    return parity.main(plan, Path(args.revit_ifc), Path(args.dir))


def cmd_publish(args) -> int:
    from .publish import publish
    for variant in spec_mod.variants() if args.all else [args.variant or "base"]:
        publish(variant, Path(args.out))
    return 0


def cmd_partition_revit(args) -> int:
    import json
    from .revit_delivery import partition
    print(json.dumps(partition(args.source, args.reference, args.spine, args.out), sort_keys=True))
    return 0


def cmd_render(args) -> int:
    from .render import render_variant
    for variant in spec_mod.variants() if args.all else [args.variant or "base"]:
        render_variant(variant)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dcbuild")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("partition-revit", help="partition native architecture over the issued shared spine")
    p.add_argument("source")
    p.add_argument("--reference", required=True, help="independent generator architecture IFC")
    p.add_argument("--spine", default="dist/full/shared.ifc")
    p.add_argument("--out", default="out/full/revit/arch.ifc")
    p.set_defaults(fn=cmd_partition_revit)

    p = sub.add_parser("publish", help="build combined IFC and publish portable USD layers")
    selection = p.add_mutually_exclusive_group()
    selection.add_argument("--variant", choices=spec_mod.variants())
    selection.add_argument("--all", action="store_true", help="publish every named variant")
    p.add_argument("--out", default="dist", help="publication parent directory (default: dist)")
    p.set_defaults(fn=cmd_publish)

    p = sub.add_parser("render", help="render facility overviews from published USD")
    selection = p.add_mutually_exclusive_group()
    selection.add_argument("--variant", choices=spec_mod.variants())
    selection.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("plan", help="resolve spec -> build_plan.json")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("check", help="design invariants (G0)")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("build-ifc", help="author IFC models")
    p.add_argument("--out", default=None)
    p.add_argument("--disciplines", nargs="*", default=None,
                   help="subset: arch structure site electrical cooling it security")
    p.set_defaults(fn=cmd_build_ifc)

    p = sub.add_parser("validate-ifc", help="IFC validation gates (G1)")
    p.add_argument("--dir", default=None)
    p.set_defaults(fn=cmd_validate_ifc)

    p = sub.add_parser("build-programme", help="emit XER, MSPDI and activity sidecars")
    p.add_argument("--out", default=None)
    p.add_argument("--variant", default="base")
    p.set_defaults(fn=cmd_build_programme)

    p = sub.add_parser("parity", help="Revit IFC vs our IFC (G2)")
    p.add_argument("revit_ifc")
    p.add_argument("--dir", default="out/ifc")
    p.add_argument("--variant", default="base")
    p.add_argument("--package", choices=["arch"])
    p.add_argument("--reference", default="dist/full/arch.ifc")
    p.add_argument("--report", help="architecture parity JSON output (default: beside the native input)")
    p.set_defaults(fn=cmd_parity)

    for name in ("plan", "check", "build-ifc", "validate-ifc"):
        sub.choices[name].add_argument("--variant", default="base")

    for name in ("plan", "build-ifc"):
        sub.choices[name].add_argument("--manifest-dir", default="manifests")

    args = ap.parse_args(argv)
    print(f"== stage: {args.cmd}", flush=True)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
