#!/usr/bin/env python3
"""Read-only compatibility probe against a supplied historical XER importer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--importer", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=Path("out/pod/programme/A.xer"))
    parser.add_argument("--output", type=Path, default=Path("out/programme-probe.json"))
    args = parser.parse_args()
    importer, input_path, output = args.importer.resolve(), args.input.resolve(), args.output.resolve()
    sys.dont_write_bytecode = True
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="programme-probe-") as scratch:
        try:
            os.chdir(scratch)
            module = runpy.run_path(str(importer), run_name="probe")
            tables = module["parse_xer"](input_path)
            programme = module["Programme"](tables)
        finally:
            os.chdir(previous)
    result = {"importer_sha256": hashlib.sha256(importer.read_bytes()).hexdigest(),
              "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
              "tables": {k: len(v) for k, v in tables.items()}, "tasks": len(programme.tasks),
              "predecessors": len(programme.preds), "used_wbs": len(programme.used_wbs),
              "day_hours": programme.day_hours}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
