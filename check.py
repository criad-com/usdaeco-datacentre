#!/usr/bin/env python3
"""Blocking generator gate using the family's N checks, M failed convention."""
import argparse
import dataclasses
import hashlib
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from dcbuild.dependencies import archive_runtime_digest, dependency_pin, dependency_source
KIT, _ = dependency_source("toolchain")
sys.path.insert(0, str(KIT / "tools"))
from usdaeco_check import Report as FamilyReport
from usdaeco_check.publication import check_publication
from usdaeco_check.structure import TERM_PATTERNS, check_structure, public_org_text

import ifcopenshell
import ifcopenshell.util.element as element

from dcbuild import graph, layout, spec
from dcbuild.qa.cameras import cameras, status_census
from dcbuild.qa.manifest import manifest
from dcbuild.qa.design import door_optics
from dcbuild.revit_payload import prepare

ROOT = Path(__file__).resolve().parent


class Report:
    def __init__(self):
        self.results = []
        self.family = FamilyReport()

    def check(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        self.results.append({"name": name, "status": status, "ok": bool(ok), "detail": detail})
        self.family.check(name, ok, detail)
        return bool(ok)

    def note(self, name, detail):
        self.results.append({"name": name, "status": "INFO", "ok": None, "detail": detail})
        print(f"INFO  {name} — {detail}", flush=True)

    def not_run(self, name, reason):
        self.results.append({"name": name, "status": "NOT RUN", "ok": None, "detail": reason})
        print(f"NOT RUN  {name} — {reason}", flush=True)

    def timing(self, name, seconds):
        detail = f"{seconds:.3f} s (measurement only)"
        self.results.append({"name": name, "status": "INFO", "ok": None,
                             "seconds": seconds, "detail": detail})
        print(f"INFO  {name} — {detail}", flush=True)

    def finish(self, path):
        failed = sum(r["status"] == "FAIL" for r in self.results)
        passed = sum(r["status"] == "PASS" for r in self.results)
        informational = sum(r["status"] == "INFO" for r in self.results)
        not_run = sum(r["status"] == "NOT RUN" for r in self.results)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"checks": self.results, "failed": failed,
                                        "passed": passed, "informational": informational,
                                        "not_run": not_run,
                                        "total": len(self.results)}, indent=2)+"\n")
        print(f"\n{passed} passed, {informational} informational", flush=True)
        if not_run:
            print(f"{not_run} not run", flush=True)
        print(f"\n{len(self.results)} checks, {failed} failed", flush=True)
        return int(bool(failed))


def normalized_ifc(path):
    # Only the FILE_NAME timestamp is permitted to differ.
    return re.sub(r"(FILE_NAME\('[^']*',)'[^']*'", r"\1'<timestamp>'", path.read_text())


def core_validation_context():
    """Require the pinned Python plugin and every declared registry callback."""
    from pxr import Plug, UsdValidation
    core, _ = dependency_source("validation_core")
    Plug.Registry().RegisterPlugins(str(core / "usdAeco"))
    Plug.Registry().RegisterPlugins(str(core / "usdAecoValidators"))
    # Import must succeed: missing PYTHONPATH is a failure, never a skipped gate.
    import usdAecoValidators
    if Path(usdAecoValidators.__file__).resolve() != core / "usdAecoValidators/__init__.py":
        raise ValueError("usdAecoValidators did not import from the pinned validation core")
    registry = UsdValidation.ValidationRegistry()
    metadata = registry.GetValidatorMetadataForKeyword("UsdAecoValidators")
    declared = json.loads((core / "usdAecoValidators/plugInfo.json").read_text())
    names = {"usdAecoValidators:" + name for name in
             declared["Plugins"][0]["Info"]["Validators"] if name != "keywords"}
    if not names or names != {m.name for m in metadata}:
        raise ValueError("Core validator registry metadata is empty or incomplete")
    validators = registry.GetOrLoadValidatorsByName(sorted(names))
    if len(validators) != len(names) or not all(validators):
        raise ValueError("Core validators failed to load")
    return UsdValidation.ValidationContext(validators), len(validators)


def term_sweep():
    # Character classes keep this checker from matching its own patterns.
    forbidden = re.compile(r"c[d]c1|cr[i]ad|fo[r]um|n[p]g|10[.]0[.]|[f]elix|neu[f]eld|"
                           r"[A-Z]:[\\]|[0-9a-f]{2}(?::[0-9a-f]{2}){5}|/(?:Us[e]rs|Vol[u]mes)/", re.I)
    shared = [re.compile(pattern, re.I) for pattern in TERM_PATTERNS]

    def matches(value):
        value = public_org_text(value)
        # Random hex identities can contain a legacy four-character term.
        # Exempt only complete, quoted UUID values; scan all other text.
        value = re.sub(r'"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"', '"<uuid>"', value, flags=re.I)
        return forbidden.search(value) or any(pattern.search(value) for pattern in shared)

    files = [p for p in ROOT.rglob("*") if p.is_file() and not p.is_symlink()
             and not any(part in {".git", ".work", "out", ".venv", "__pycache__", ".pytest_cache"} for part in p.relative_to(ROOT).parts)
             and p.name != "STEERING.md"]
    hits = []
    for p in files:
        try:
            if p.suffix == ".usdc":
                from pxr import Sdf
                content = Sdf.Layer.FindOrOpen(str(p)).ExportToString()
            elif p.suffix == ".png":
                from PIL import Image
                with Image.open(p) as im:
                    im.verify()
                    content = json.dumps(im.info, default=str)
            else:
                content = p.read_text()
            # Same narrowly scoped public attribution exception as S25.
            if p.name == "LICENSE":
                content = re.sub(r"(?m)^Copyright \(c\) 2026 Cr[i]ad$", "", content)
            if matches(content):
                hits.append(str(p.relative_to(ROOT)))
        except (UnicodeDecodeError, OSError, ValueError):
            hits.append(str(p.relative_to(ROOT))+" (unreviewed binary)")
    return hits


def recorded_revit(report):
    """Audit committed native measurements; never contact the endpoint in this gate."""
    data = json.loads((ROOT / "artifacts/revit-0.4.2.json").read_text())
    pin = dependency_pin("revit_recorded")
    sources_match = data["transport"] == {k: pin[k] for k in ("repo", "ref", "revision", "runtime_sha256")}
    sources_match &= set(data["source_sha256"]) == {
        "revit/driver.py", "revit/src/manifest.json", "src/dcbuild/revit_payload.py"}
    sources_match &= all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
                         for name, expected in data["source_sha256"].items())
    expected = {
        "update": {"created": 0, "updated": 45, "batches": 9},
        "parity": {"joined": 527, "required": 527, "failures": 0},
        "importer": {"cameras": 45, "sensors": 45},
    }
    for name, numbers in expected.items():
        row = data[name]
        if row["status"] == "NOT RUN":
            report.not_run("recorded Revit base " + name, row["reason"])
        else:
            report.check("recorded Revit base " + name,
                         sources_match and row["status"] == "PASS"
                         and all(row[k] == v for k, v in numbers.items()),
                         json.dumps(row, sort_keys=True) + "; recorded evidence, no live execution")
    for variant in ("floors", "pod", "clash", "iris"):
        report.not_run("native Revit " + variant,
                       "Base only; further native family work required, including pods and ceilings")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("out/check.json"))
    parser.add_argument("--out", type=Path, default=Path("out/check"))
    args = parser.parse_args()
    os.chdir(ROOT)
    report = Report()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def command(name, *arguments):
        print(f"== stage: {name}", flush=True)
        start = time.perf_counter()
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env)
        elapsed = time.perf_counter()-start
        report.check(name, result.returncode == 0)
        report.timing(name+" elapsed", elapsed)
        return result.returncode == 0, elapsed

    try:
        print("== stage: publication sweep", flush=True)
        publication = check_publication(ROOT)
        report.check(publication.name, publication.ok, publication.detail)
        print("== stage: pinned toolchain archive", flush=True)
        kit, pin = dependency_source("toolchain")
        archive_digest = archive_runtime_digest(kit, pin)
        report.check("toolchain pristine archive runtime digest", archive_digest == pin["runtime_sha256"],
                     pin["ref"] + ": " + archive_digest)
        print("== stage: core validator registry", flush=True)
        validation, validator_count = core_validation_context()
        report.check("core validators loaded", validator_count == 8, f"{validator_count}/8 through UsdValidation")
        a, b = args.out/"a", args.out/"b"
        ok, _ = command("resolve CLI", "-m", "dcbuild", "plan", "--out", str(a/"build_plan.json"), "--manifest-dir", str(a/"manifests"))
        command("G0 CLI", "-m", "dcbuild", "check")
        first, _ = command("IFC build CLI", "-m", "dcbuild", "build-ifc", "--out", str(a/"ifc"), "--manifest-dir", str(a/"manifests"))
        if first:
            command("G1 schema/express and semantics", "-m", "dcbuild", "validate-ifc", "--dir", str(a/"ifc"))
        plan = layout.resolve(spec.load())
        for check in graph.ALL_CHECKS:
            failures = check(plan)
            report.check("G0 "+check.__name__, not failures, "; ".join(failures))
        optics = door_optics(plan)
        report.check("door face plane optics before occlusion", len(optics) == 11 and all(v["passed"] for v in optics.values()),
                     f"{len(optics)}/11; max {max(v['maxDistance'] for v in optics.values()):.6f} m; min {min(v['minDensity'] for v in optics.values()):.6f} px/m")
        report.check("door mounts independent of clear height", all(c.pos[2] == 3.0 and c.mount == "pendant"
                     for c in plan.cameras if c.id.startswith("sec.cam.door.")), "11 at 3.0 m")
        exterior = door_optics(plan, external=True)
        report.check("external primary face plane optics before occlusion", len(exterior) == 5 and all(v["passed"] for v in exterior.values()),
                     f"{len(exterior)}/5; min {min(v['minDensity'] for v in exterior.values()):.6f} px/m; full inset face corners")
        shared = [c for c in plan.cameras if c.id.startswith("sec.cam.ext.") and len(c.targets) > 1]
        report.check("external shared approach rule census", len(shared) == 1 and len(shared[0].targets) == 2
                     and shared[0].mount == "pole", "1 existing bullet, 2 approaches; scene coverage checked by the family runner")
        groups = Counter(c.id.split(".")[2] for c in plan.cameras)
        report.check("camera design group census", groups == dict(door=11, ext=5, corr=18, yard=8, lobby=3), str(dict(groups)))
        fixed_yards = [c for c in plan.cameras if c.id.startswith("sec.cam.yard.") and ".fixed." in c.id]
        report.check("yard fixed IR provision", len(fixed_yards) == 6 and all(
                     not plan.security["camera_types"][c.type]["motorised"] and plan.security["camera_types"][c.type]["ir_range"] == 40
                     for c in fixed_yards), "6 fixed bullets, IR 40 m; geometric coverage is a separate study")
        report.check("lobby fixed provision", sum(c.id.startswith("sec.cam.lobby.fixed.") for c in plan.cameras) == 2, "2 fixed domes plus supplementary PTZ")
        report.check("recorder camera allowance", len(plan.cameras) <= 45, f"{len(plan.cameras)}/45")
        recorded = json.loads((ROOT/"manifests/demo-datacentre-01.json").read_text())
        report.check("45 retained camera GUIDs", {c.id: c.global_id for c in plan.cameras} == recorded["camera_ids"]
                     and len(recorded["camera_ids"]) == 45, "45/45; no camera added or removed")
        report.check("pinned semantic and identity manifest", manifest(plan) == recorded,
                     f"{recorded['identities']} resolved identities")
        if first:
            model = ifcopenshell.open(a/"ifc/demo-datacentre-01.ifc")
            security = ifcopenshell.open(a/"ifc/demo-datacentre-01-security.ifc")
            cams = model.by_type("IfcAudioVisualAppliance")
            heads = sum(len(json.loads(element.get_psets(e)["Pset_AecoCctv"]["Sensors"])) for e in cams)
            report.check("camera/head/type census", (len(cams), heads, len(model.by_type("IfcAudioVisualApplianceType"))) == (45,45,3), f"{len(cams)} cameras / {heads} heads / 3 types")
            report.check("41 doors, 12 alarms, 11 readers", (len(model.by_type("IfcDoor")), len(model.by_type("IfcAlarm")), len(model.by_type("IfcSensor"))) == (41,12,11))
            clearances = graph.door_column_clearances(plan)
            report.check("door/column clearance", min(clearances.values()) >= 0.3-1e-6,
                         f"0 intersections; minimum {min(clearances.values()):.3f} m")
            report.check("combined/federated camera identity", {e.GlobalId for e in cams} == {e.GlobalId for e in security.by_type("IfcAudioVisualAppliance")}, f"{len(cams)}/{len(cams)}")
            failures = cameras(model, plan)+cameras(security, plan)
            report.check("both IFC camera contract tiers", not failures, "; ".join(failures))
            covered, missing, exempt = status_census(model)
            report.check("Status on every applicable product", not missing,
                         f"{len(covered)}/{len(covered)+len(missing)}; {len(exempt)} no-template exception")
            report.check("Status exceptions are counted grids", Counter(e.is_a() for e in exempt) == {"IfcGrid": 1})
        command("second independent resolve", "-m", "dcbuild", "plan", "--out", str(b/"build_plan.json"), "--manifest-dir", str(b/"manifests"))
        second, _ = command("second independent IFC build", "-m", "dcbuild", "build-ifc", "--out", str(b/"ifc"), "--manifest-dir", str(b/"manifests"))
        if ok:
            report.check("canonical plan determinism", (a/"build_plan.json").read_bytes() == (b/"build_plan.json").read_bytes())
            report.check("target manifest determinism", (a/"targets.json").read_bytes() == (b/"targets.json").read_bytes())
        if first and second:
            for path in sorted((a/"ifc").glob("*.ifc")):
                report.check("STEP determinism "+path.stem, normalized_ifc(path) == normalized_ifc(b/"ifc"/path.name))
        baseline = json.loads((ROOT/"manifests/base-v0.3.4-bytes.json").read_text())
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        report.check("base plan bytes vs v0.3.4", digest(a/"build_plan.json") == baseline["plan_sha256"])
        report.check("base target bytes vs v0.3.4", digest(a/"targets.json") == baseline["targets_sha256"])
        if first:
            actual = {p.name: hashlib.sha256(re.sub(r"usdaeco-datacentre [0-9]+[.][0-9]+[.][0-9]+",
                        "usdaeco-datacentre <version>", normalized_ifc(p)).encode()).hexdigest()
                      for p in sorted((a/"ifc").glob("*.ifc"))}
            report.check("base IFC bytes vs v0.3.4", actual == baseline["ifc_sha256"],
                         "8 files; only FILE_NAME timestamp and generator version normalized")
        from dcbuild.qa.variants import manifest as variant_manifest
        from dcbuild.programme import build as build_programme
        for variant in spec.variants():
            print(f"== stage: variant {variant}", flush=True)
            vp = layout.resolve(spec.load(variant=variant))
            folder = args.out/"variants"/variant
            if variant == "base":
                first_dir, second_dir = a, b
            else:
                first_dir, second_dir = folder/"a", folder/"b"
                for target in (first_dir, second_dir):
                    command(variant+" independent plan "+target.name, "-m", "dcbuild", "plan", "--variant", variant,
                            "--out", str(target/"build_plan.json"), "--manifest-dir", str(target/"manifests"))
                command(variant+" IFC build", "-m", "dcbuild", "build-ifc", "--variant", variant,
                        "--out", str(first_dir/"ifc"), "--manifest-dir", str(first_dir/"manifests"))
                command(variant+" G1", "-m", "dcbuild", "validate-ifc", "--variant", variant,
                        "--dir", str(first_dir/"ifc"))
                from dcbuild.ifc.build import DISCIPLINES
                disciplines = [name for name in DISCIPLINES if name != "fitout" or vp.meta.get("fitout")]
                command(variant+" second IFC build", "-m", "dcbuild", "build-ifc", "--variant", variant,
                        "--out", str(second_dir/"ifc"), "--disciplines", *disciplines)
            failures = graph.run_all(vp)
            report.check("variant "+variant+" G0", not failures, "; ".join(failures))
            report.check("variant "+variant+" independent plan bytes",
                         (first_dir/"build_plan.json").read_bytes() == (second_dir/"build_plan.json").read_bytes())
            report.check("variant "+variant+" independent IFC bytes",
                         normalized_ifc(first_dir/"ifc/demo-datacentre-01.ifc") == normalized_ifc(second_dir/"ifc/demo-datacentre-01.ifc"))
            vm = ifcopenshell.open(first_dir/"ifc/demo-datacentre-01.ifc")
            expected_manifest = json.loads((ROOT/f"manifests/demo-datacentre-01.{variant}.json").read_text())
            report.check("variant "+variant+" measured manifest", variant_manifest(vp, vm) == expected_manifest,
                         json.dumps(expected_manifest["counts"], sort_keys=True))
            if vp.meta.get("programme"):
                build_programme(vp, first_dir/"programme")
                build_programme(vp, second_dir/"programme")
                files = sorted((first_dir/"programme").iterdir())
                report.check("variant "+variant+" programme bytes", len(files) == 8 and all(
                    p.read_bytes() == (second_dir/"programme"/p.name).read_bytes() for p in files), "2 XER, 2 MSPDI, 4 sidecars")
        print("== stage: family structure lint", flush=True)
        structure = check_structure(ROOT)
        for row in structure:
            print(f"{row.name} {'PASS' if row.ok else 'FAIL'} {row.detail}", flush=True)
        report.check("family structure lint", all(structure),
                     f"{len(structure)} rules; " + "; ".join(r.name + " " + r.detail for r in structure if not r))
        from dcbuild.publish import PUBLISHED, SIZE_CAP, verify_publication
        from dcbuild.render import verify_render
        from dcbuild.vanilla import check_example
        from pxr import Usd, UsdValidation
        baseline = json.loads((ROOT / "manifests/publication-v0.4.3.json").read_text())
        unchanged = json.loads((ROOT / "manifests/publication-v0.4.4.json").read_text())
        for variant in ("base", "pod", "clash", "iris"):
            files = {name: value for name, value in unchanged["sha256"].items()
                     if name.startswith(f"dist/{variant}/") or name.endswith(f".{variant}.json")
                     or name == f"manifests/cameras/{variant}.usda"}
            # Historical pixels and other evidence stay fixed; fresh vanilla
            # rendering records the current, independently verified toolchain.
            expected_receipts = json.loads(json.dumps(unchanged["receipts"]))
            expected_receipts["vanilla.json"][variant]["sources"]["toolchain"] = pin
            receipts_match = all(json.loads((ROOT / "manifests" / name).read_text())[variant] == records[variant]
                                 for name, records in expected_receipts.items())
            report.check(f"published {variant} bytes vs v0.4.4",
                         len(files) == 8 and all(digest(ROOT / name) == value for name, value in files.items())
                         and receipts_match, "8 files byte-identical; receipts differ only by the verified toolchain pin")
        print("== stage: published typical floors", flush=True)
        from dcbuild.qa.typical import verify as verify_typical
        floors = ROOT / "dist/floors"
        typical = verify_typical(Usd.Stage.Open(str(floors / "dc.usda")), spec.load(variant="floors").expected["drift"])
        report.check("floors exactly two planted differences by classification type placement",
                     typical == json.loads((floors / "dc.manifest.json").read_text())["typical"],
                     json.dumps(typical, sort_keys=True))
        print("== stage: published clash measurements", flush=True)
        from dcbuild.qa.clash import hard_fingerprint, verify_clash
        clash = ROOT / "dist/clash"
        report.check("clash hard body unchanged", hard_fingerprint(Usd.Stage.Open(str(clash / "dc.usda")))
                     == baseline["hard_body"], "points, topology and world transform vs v0.4.3")
        measured = verify_clash(clash, spec.load(variant="clash"))
        report.check("clash manifest matches source and published bodies", len(measured) == 3)
        for row in measured:
            report.check("clash published case " + row["id"], True, json.dumps(row, sort_keys=True))
        for variant in spec.variants():
            first_dir, second_dir = args.out/"publish-a", args.out/"publish-b"
            for target in (first_dir, second_dir):
                command(f"publish {variant} {target.name}", "-m", "dcbuild", "publish", "--variant", variant,
                        "--out", str(target))
            published = ROOT/"dist"/variant
            report.check(f"publish {variant} byte identity", all(
                (first_dir/variant/name).read_bytes() == (second_dir/variant/name).read_bytes()
                == (published/name).read_bytes() for name in PUBLISHED),
                "two independent publishes and committed data; 3 layers + manifest; no normalization")
            probe = verify_publication(published)
            report.check(f"publish {variant} plugin-free", True,
                         json.dumps(probe, sort_keys=True))
            total = sum(p.stat().st_size for p in published.iterdir() if p.is_file())
            report.check(f"publish {variant} size", total <= SIZE_CAP, f"{total}/{SIZE_CAP} bytes including overview")
            image = verify_render(variant)
            report.check(f"render {variant}", True, json.dumps(image, sort_keys=True))
            print(f"== stage: vanilla freshness {variant}", flush=True)
            image = check_example(variant)
            report.check(f"vanilla {variant} fresh and non-uniform", True, json.dumps(image, sort_keys=True))
            findings = validation.Validate(Usd.Stage.Open(str(published / "dc.usda")))
            errors = [e for e in findings if e.GetType() == UsdValidation.ValidationErrorType.Error]
            counts = Counter(e.GetName() for e in findings)
            report.check(f"core validation {variant}", not errors,
                         f"{len(errors)} errors; findings: {json.dumps(counts, sort_keys=True)}")
        payload = prepare(dataclasses.asdict(plan))
        report.check("Revit camera payload contract", len(payload["cameras"]) == 45,
                     "45 valid GUIDs, native levels, finite drivers and complete JSON payloads")
        report.check("Revit 45-camera type distribution", Counter(c["type"] for c in payload["cameras"])
                     == {"dome_5mp": 31, "bullet_4mp_outdoor": 11, "ptz_4k": 3}, "31 domes / 11 bullets / 3 PTZ")
        serialized = [json.loads(c["contract"]["Sensors"]) for c in payload["cameras"]]
        report.check("Revit one sensor per camera", len(serialized) == 45 and all(
            len(heads) == 1 and heads[0]["name"] == "Sensor_0" for heads in serialized), "45/45 serialized heads")
        report.check("Revit serialized pose drivers agree", all(
            heads[0]["drivers"]["aeco:cctvSensor:"+field] == camera[key]
            for camera, heads in zip(payload["cameras"], serialized)
            for field, key in (("pan", "pan"), ("tilt", "tilt"), ("roll", "roll"),
                               ("focalLength", "focal_length"), ("range", "range"))), "225/225 serialized driver values; offline only")
        report.check("Revit positive target density per type", all(
            c["target_density"] > 0 for c in payload["security"]["camera_types"].values()), "3/3 types")
        report.check("Revit finite user-radius inputs", all(c["native_target_density"] > 0 for c in payload["cameras"]), "45/45 cameras")
        report.check("Revit Status payload", payload["revit_status"]["value"] == "NEW"
                     and len(payload["revit_status"]["categories"]) >= 15, "NEW on every authored product category")
        report.check("Revit room and identity payload", sum(not s["external"] for s in payload["spaces"]) == 30
                     and all(payload["revit_identities"][c.id] == c.global_id for c in plan.cameras),
                     "30 interior rooms; camera GUIDs agree with the generator")
        from revit import driver
        from usdaeco_revit.transport import Client
        report.check("Revit shared client", driver.Client is Client and not (ROOT/"revit/transport.py").exists(),
                     dependency_pin("revit")["ref"] + "; verified runtime source; local transport removed")
        report.check("Revit script pack hashes", len(driver.verify_pack()) == 11, "11/11 scripts")
        command("Revit local dry run", "revit/driver.py", "--update", "--dry-run", "--plan", str(a/"build_plan.json"))
        recorded_revit(report)
        command("pytest", "-m", "pytest", "-q")
        hits = term_sweep()
        report.check("repository sanitization", not hits, ", ".join(hits) if hits else "0 hits")
    except Exception as exc:
        report.check("gate completed", False, str(exc))
    return report.finish(args.report)


if __name__ == "__main__":
    raise SystemExit(main())
