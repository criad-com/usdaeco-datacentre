"""Public per-variant manifest; IFC class counts come from the actual writer."""
from collections import Counter
import dataclasses
import hashlib
import json
from pathlib import Path


def census_model(plan):
    from ..ifc.build import DISCIPLINES, _modules
    from ..ifc.builder import Builder
    from ..ifc import spatial
    b = Builder(plan)
    spatial.build(b, plan)
    for _, module in _modules(DISCIPLINES):
        module.build(b, plan)
    return b.file


def manifest(plan, model=None):
    if model is None:
        model = census_model(plan)
    fitout = plan.meta.get("fitout", [])
    programmes = plan.meta.get("programme", {}).get("programmes", [])
    counts = {key: len(getattr(plan, key)) for key in
              ("storeys", "spaces", "walls", "doors", "columns", "cameras")}
    counts.update(readers=len(plan.security["iris"]),
                  rooms=sum(not s.external and s.type != "void" for s in plan.spaces),
                  ceilings=sum(e["ifc_class"] == "IfcCovering" for e in fitout),
                  voids=sum(s.type == "void" for s in plan.spaces),
                  pods=sum(e["ifc_class"] == "IfcElementAssembly" for e in fitout),
                  temporary=sum(e.get("status") == "TEMPORARY" for e in fitout),
                  mep_by_class=dict(sorted(Counter(e.is_a() for e in model.by_type("IfcDistributionElement")).items())),
                  activities_per_programme={p["id"]: len(p["activities"]) for p in programmes},
                  fitout_by_class=dict(sorted(Counter(e["ifc_class"] for e in fitout).items())),
                  fix_counts=dict(sorted(Counter(e["fix"] for e in fitout if e.get("fix")).items())))
    return {"facility": plan.meta["code"], "variant": plan.meta.get("variant", "base"),
            "units": "metres", "up_axis": "Z", "counts": counts,
            "plan_sha256": hashlib.sha256(json.dumps(dataclasses.asdict(plan), sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "expected": plan.meta.get("expected", {})}


def write_manifest(plan, directory: Path, model=None):
    result = manifest(plan, model)
    path = directory / f"{result['facility']}.{result['variant']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return path
