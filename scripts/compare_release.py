#!/usr/bin/env python3
"""Offline release comparison using two generators and one tested family set.

Requires built sibling plugins and a clean baseline checkout. Outputs and raw
hashes are retained; only IFC creation and USD study receipt timestamps may
differ. No source checkout is built or modified by this command.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = dict(core="usdAeco", buildup="usdAecoBuildUp", wall="usdAecoWall",
                 pipe="usdAecoPipe", cctv="usdAecoCctv", sync="usdAecoSync")


def git(source, *args):
    return subprocess.check_output(["git", *args], cwd=source, text=True).strip()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def comparable(path):
    data = path.read_bytes()
    if path.suffix == ".ifc":
        # The same field excluded by check.py's independent STEP comparison.
        data, count = re.subn(rb"(FILE_NAME\('[^']*',)'[^']*'", rb"\1'<timestamp>'", data)
        if count != 1:
            raise ValueError("Expected one IFC FILE_NAME timestamp: "+path.name)
    elif path.suffix == ".usda":
        data = re.sub(rb'(string "aeco:cctv:time" = )"[^"\n]*"', rb'\1"<timestamp>"', data)
    return data


def build(args):
    os.environ["AECO_FAMILY_ROOT"] = str(args.family_root)
    os.environ["AECO_DATACENTRE_SOURCE"] = str(args.generator)
    # Explicit source roots avoid ambient overrides selecting another release.
    for name in (*LIBRARIES, "toolchain"):
        os.environ["AECO_"+name.upper()+"_SOURCE"] = str(args.family_root/("usdaeco-"+name))
    sys.path[:0] = [str(args.generator/"src"), str(args.family_root/"usdaeco-scenarios")]
    from family import activate
    activate(args.pluginset)
    definition = importlib.util.spec_from_file_location(
        "release_datacentre", args.family_root/"usdaeco-scenarios/scenarios/datacentre.py")
    dc = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(dc)
    from dcbuild import graph, layout, spec
    from dcbuild.qa.design import door_optics
    from dcbuild.qa.manifest import manifest

    stats = dc.prepare(args.out)
    # Measurements are printed, not included in deterministic QA documents.
    print("INFO timings", json.dumps(stats.pop("seconds")), flush=True)
    stage, config = dc.author_schedule(args.out)
    reports = dc.run_schedule(stage, args.out, "embree")
    dc.save_composed(stage, args.out)
    plan = layout.resolve(spec.load(args.generator/"spec"))
    failures = graph.run_all(plan)
    if failures:
        raise ValueError(str(failures))
    for name, report in reports.items():
        expected = len(config[name][0])
        if (len(report["results"]) != expected or report["exclusionsCovered"]
                or any(not row["fixedCoverage"] for row in report["results"].values())):
            raise ValueError("Coverage failed: "+name)
    if stats["cctv"]["sensors"] != 45 or stats["derive"]["sensors"] != 45:
        raise ValueError("Expected 45 imported and derived sensors")
    qa = args.out/"qa"
    write_json(qa/"build.json", dc.portable(stats, args.out))
    write_json(qa/"manifest.json", manifest(plan))
    write_json(qa/"optics.json", dict(critical=door_optics(plan), external=door_optics(plan, external=True)))
    write_json(qa/"studies.json", dc.stable_reports(reports))
    # Core's semantics and geometry are subordinate layers. Their root stage
    # supplies fallbackPrimTypes; validate each composed entry point here.
    stages = sorted(p for p in args.out.rglob("*.usda") if not p.name.endswith(".semantics.usda"))
    print(f"== stage: vanilla composition ({len(stages)} stages)", flush=True)
    print("PASS vanilla prim census", dc.vanilla(stages), flush=True)


def compare(args):
    if args.out.exists():
        raise ValueError("Use a new output directory to retain previous evidence")
    print("== stage: audit comparison inputs", flush=True)
    baseline = git(args.baseline, "rev-parse", "HEAD")
    if baseline != git(ROOT, "rev-parse", "v0.3.3^{commit}"):
        raise ValueError("Baseline must be the v0.3.3 release commit")
    if git(args.baseline, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Baseline must be clean")
    pins = json.loads((ROOT/"dependencies.json").read_text())
    family_pins = json.loads((args.family_root/"usdaeco-scenarios/dependencies.json").read_text())["repositories"]
    sources = {}
    for name in (*LIBRARIES, "toolchain", "scenarios"):
        source = args.family_root/("usdaeco-"+name)
        expected = family_pins.get(name)
        revision = git(source, "rev-parse", "HEAD")
        if expected and revision != expected["revision"]:
            raise ValueError("Family source revision drift: "+name)
        if git(source, "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Modified family source: "+name)
        library = LIBRARIES.get(name)
        pin = next((p for p in pins["repos"].values() if p["library"] == library),
                   pins.get("observations", {}).get(library))
        if pin and (revision != pin["revision"] or pin["ref"] != expected["base_tag"]):
            raise ValueError("Tested input pin drift: "+name)
        sources[name] = dict(revision=revision, ref=expected["base_tag"] if expected else git(source, "describe", "--exact-match", "--tags"))
        if name in LIBRARIES:
            lib = LIBRARIES[name]
            manifest = json.loads((source/"schemas"/lib/"library.json").read_text())
            descriptor = (source/"plugins"/lib/"resources/plugInfo.json").read_text()
            plugin = json.loads("\n".join(line for line in descriptor.splitlines() if not line.lstrip().startswith("#")))
            metadata = next(p["Info"]["aeco"] for p in plugin["Plugins"] if p["Name"] == lib)
            if metadata != {k: manifest[k] for k in ("version", "tier", "requires")}:
                raise ValueError("Plugin metadata drift: "+name)
    args.out.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    env.pop("PXR_PLUGINPATH_NAME", None)
    pluginset = args.out/"pluginset"
    subprocess.run([sys.executable, str(args.family_root/"usdaeco-toolchain/tools/pluginset.py"), str(pluginset),
                    *[str(args.family_root/("usdaeco-"+n)/"plugins"/lib/"resources") for n, lib in LIBRARIES.items()]],
                   env=env, check=True)
    for label, generator in (("baseline", args.baseline), ("candidate", ROOT)):
        print("== stage: independent "+label+" build", flush=True)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--generator", str(generator),
                        "--family-root", str(args.family_root), "--pluginset", str(pluginset),
                        "--out", str(args.out/label)], env=env, check=True)
    return summarize(args.out, sources, baseline, pins)


def summarize(directory, sources, baseline, pins):
    print("== stage: compare retained output bytes", flush=True)
    def inventory(directory):
        return {p.relative_to(directory).as_posix(): p for p in directory.rglob("*")
                if p.suffix in (".ifc", ".usd", ".usda", ".usdc", ".json")}
    a, b = [inventory(directory/label) for label in ("baseline", "candidate")]
    if set(a) != set(b) or not a:
        raise ValueError("Output inventory differs or is empty")
    rows = []
    for name in sorted(a):
        left, right = a[name].read_bytes(), b[name].read_bytes()
        ca, cb = comparable(a[name]), comparable(b[name])
        rows.append(dict(path=name, bytesBaseline=len(left), bytesCandidate=len(right),
                         sha256Baseline=sha(left), sha256Candidate=sha(right),
                         comparableSha256Baseline=sha(ca), comparableSha256Candidate=sha(cb),
                         byteIdentical=left == right, stampOnly=left != right and ca == cb, passed=ca == cb))
    result = dict(baseline=dict(ref="v0.3.3", revision=baseline),
                  candidate=dict(version="0.3.4", revision=git(ROOT, "rev-parse", "HEAD")),
                  testedInputs=pins, sources=sources, outputs=rows,
                  scriptSha256=sha(Path(__file__).read_bytes()),
                  countBySuffix=dict(Counter(Path(name).suffix for name in a)),
                  total=len(rows), byteIdentical=sum(r["byteIdentical"] for r in rows),
                  stampOnly=sum(r["stampOnly"] for r in rows), failed=sum(not r["passed"] for r in rows),
                  excludedFields=["IFC FILE_NAME creation timestamp", "USD customLayerData aeco:cctv:time receipt timestamp"],
                  releaseStampsExcluded=[], nativeRevit="NOT RUN",
                  scope="Both generators use the same current family inputs. QA contains semantic data; timings are INFO in the run log.")
    write_json(directory/"comparison.json", result)
    print(f"{result['byteIdentical']} byte-identical, {result['stampOnly']} timestamp-only", flush=True)
    print(f"{result['total']} checks, {result['failed']} failed", flush=True)
    return int(bool(result["failed"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--family-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--generator", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--pluginset", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    if args.worker:
        build(args)
        return 0
    if args.baseline is None:
        parser.error("--baseline is required")
    return compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
