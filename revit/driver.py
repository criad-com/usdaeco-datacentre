#!/usr/bin/env python3
"""Drive the demo Revit build through the configured revit-repl endpoint.

Uploads the resolved plan through /eval, then runs the C# phases in order.
Use --dry-run for local validation. See revit/README.md.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcbuild.revit_payload import prepare
from dcbuild.revit_runtime import setup

setup()
from usdaeco_revit.transport import Client

ROOT = os.path.dirname(os.path.abspath(__file__))            # revit/
REPO = os.path.dirname(ROOT)
SRC = os.path.join(ROOT, "src")
MAX_CSX = 900 * 1024                                          # each file is one /eval body
UPDATE_PHASES = ["00_lib", "10_setup", "15_parameters", "45_cameras", "90_finish"]


def verify_pack():
    directory = Path(SRC)
    expected = json.loads((directory / "manifest.json").read_text())
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(directory.glob("*.csx"))}
    if actual != expected:
        raise ValueError("Revit script pack manifest differs from source bytes")
    return actual


def find_phases(names: list[str] | None) -> list[str]:
    if not names:
        return sorted(glob.glob(os.path.join(SRC, "*.csx")))
    out = []
    for n in names:
        if os.path.isfile(n):
            out.append(os.path.abspath(n))
            continue
        cand = (sorted(glob.glob(os.path.join(SRC, n)))
                or sorted(glob.glob(os.path.join(SRC, n + "*.csx")))
                or sorted(glob.glob(os.path.join(SRC, "*" + n + "*.csx"))))
        if not cand:
            sys.exit(f"driver: phase not found: {n}")
        out.append(cand[0])
    return out


def validate_csx(path: str) -> tuple[str, int, list[str]]:
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    size = len(src.encode("utf-8"))
    problems = []
    if size >= MAX_CSX:
        problems.append(f"size {size} >= {MAX_CSX}")
    for o, c in (("{", "}"), ("(", ")"), ("[", "]")):
        no, nc = src.count(o), src.count(c)
        if no != nc:
            problems.append(f"unbalanced {o}{c}: {no} vs {nc}")
    if "namespace " in src:
        problems.append("contains a namespace declaration (not allowed in csx)")
    return src, size, problems


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--endpoint", default=os.environ.get("AECO_REVIT_ENDPOINT", "http://<revit-endpoint>"))
    ap.add_argument("--workdir", default=os.environ.get("AECO_REVIT_WORKDIR", "<remote-work-directory>"))
    ap.add_argument("--family-dir", default=os.environ.get("AECO_REVIT_FAMILY_DIR", "<camera-family-directory>"))
    ap.add_argument("--session", default="dc-build")
    ap.add_argument("--plan", default=os.path.join(REPO, "out", "base", "build_plan.json"))
    ap.add_argument("--update", action="store_true",
                    help="update the existing base model only; never create a project or repeat services")
    ap.add_argument("--phases", nargs="*", default=None,
                    help="phase files or fragments (default: all revit/src/*.csx sorted)")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate csx files + plan locally, print phase plan, exit")
    ap.add_argument("--skip-upload", action="store_true")
    args = ap.parse_args(argv)
    if args.update and args.phases is not None:
        ap.error("--update selects its own phases")

    hashes = verify_pack()
    phases = find_phases(UPDATE_PHASES if args.update else args.phases)
    plan = os.path.abspath(args.plan)
    ok = True

    print(f"demo-datacentre-01 Revit driver -- {len(phases)} phases, session={args.session}")
    for p in phases:
        src, size, problems = validate_csx(p)
        if Path(p).parent != Path(SRC) or hashlib.sha256(src.encode()).hexdigest() != hashes.get(Path(p).name):
            problems.append("phase is outside the verified script pack")
        status = "ok" if not problems else "; ".join(problems)
        print(f"  {os.path.basename(p):<24} {size:>7} B  {status}")
        ok &= not problems

    if not os.path.isfile(plan):
        print(f"  plan MISSING: {plan}")
        ok = False
    else:
        try:
            with open(plan, encoding="utf-8") as fh:
                pj = prepare(json.load(fh))
            if pj.get("meta", {}).get("variant", "base") != "base":
                raise ValueError("Native builds currently support the base variant only")
            print(f"  plan ok: {plan} ({os.path.getsize(plan)} B, "
                  f"{len(pj.get('walls', []))} walls, {len(pj.get('equipment', []))} equipment, "
                  f"{len(pj.get('racks', []))} racks, {len(pj.get('runs', []))} runs, "
                  f"{len(pj.get('routes', []))} routes, {len(pj.get('cameras', []))} cameras)")
        except Exception as e:  # noqa: BLE001
            print(f"  plan INVALID: {e}")
            ok = False

    if args.dry_run:
        print("dry-run", "OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)
    if not ok:
        sys.exit("driver: validation failed")

    if any("<" in v for v in (args.endpoint, args.workdir, args.family_dir)):
        sys.exit("driver: set AECO_REVIT_ENDPOINT, AECO_REVIT_WORKDIR and AECO_REVIT_FAMILY_DIR")
    base = args.endpoint.rstrip("/")
    client = Client(base, args.session, workdir=args.workdir)

    def evaluate(code):
        return client.evaluate(code + '\nreturn "configured";')

    remote = json.dumps(args.workdir)
    evaluate('System.Environment.SetEnvironmentVariable("AECO_REVIT_WORKDIR", ' + remote + ');')
    evaluate('System.Environment.SetEnvironmentVariable("AECO_REVIT_FAMILY_DIR", ' + json.dumps(args.family_dir) + ');')
    evaluate('System.Environment.SetEnvironmentVariable("AECO_REVIT_UPDATE", ' + json.dumps("1" if args.update else "0") + ');')
    if not args.skip_upload:
        for local, filename in ((plan, "build_plan.json"), (os.path.join(ROOT, "families.yaml"), "families.yaml"), (os.path.join(ROOT, "camera-psets.txt"), "camera-psets.txt"), (os.path.join(ROOT, "shared-parameters.txt"), "shared-parameters.txt")):
            with open(local, "rb") as stream:
                data = json.dumps(pj, allow_nan=False).encode() if filename == "build_plan.json" else stream.read()
            receipt = client.upload(data, filename)
            print(f"== stage: upload {filename}: {receipt['bytes']} bytes SHA-256 verified", flush=True)

    for p in phases:
        name = os.path.basename(p)
        with open(p, encoding="utf-8") as fh:
            code = fh.read()
        if hashlib.sha256(code.encode()).hexdigest() != hashes[name]:
            sys.exit("driver: script changed after validation: " + name)
        print(f"== stage: {name}", flush=True)
        t0 = time.time()
        try:
            if name.startswith("45_"):
                results = []
                for start in range(0, len(pj["cameras"]), 5):
                    print(f"== stage: cameras {start+1}–{min(start+5, len(pj['cameras']))}", flush=True)
                    client.evaluate(f'Dc.CameraStart={start}; Dc.CameraCount=5; return "batch configured";')
                    results.append(client.phase(code))
                resp = {"result": "\n".join(results)}
            else:
                resp = {"result": client.phase(code)}
        except Exception as e:
            sys.exit(f"[{name}] transport error after {time.time() - t0:.0f}s: {e}")
        dt = time.time() - t0
        if isinstance(resp, dict) and resp.get("error"):
            print(f"[{name}] FAILED after {dt:.1f}s")
            print(f"  error: {resp['error']}")
            if resp.get("exception"):
                print(f"  exception: {resp['exception']}")
            sys.exit(1)
        result = resp.get("result") if isinstance(resp, dict) else resp
        text = str(result)
        print(f"[{name}] {dt:.1f}s -> {text[:2500]}{' ...' if len(text) > 2500 else ''}")

    print("all phases complete; export is in AECO_REVIT_WORKDIR")


if __name__ == "__main__":
    main()
