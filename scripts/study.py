#!/usr/bin/env python3
"""Run the family's unchanged security schedule against this generator checkout.

A failed design remains a failed design: this command returns nonzero when any
required study target lacks fixed coverage, violates distance, or sees privacy.
The generator's independent check.py gate does not claim security acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenarios', type=Path, required=True, help='Family scenarios source checkout (read only)')
    parser.add_argument('--pluginset', type=Path, required=True, help='Built family plugin aggregate')
    parser.add_argument('--output', type=Path, default=Path('out/study'))
    parser.add_argument('--kernel', choices=['embree', 'numpy'], default='embree')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Use a new output directory to preserve prior evidence')
    os.environ['AECO_DATACENTRE_SOURCE'] = str(ROOT)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT/'src'), str(args.scenarios.resolve())]
    from dcbuild import layout, spec
    from dcbuild.qa.design import door_optics
    print('== stage: door plane optics before the scene study', flush=True)
    optical = door_optics(layout.resolve(spec.load(ROOT/'spec')))
    assert len(optical) == 11 and all(v['passed'] for v in optical.values()), optical
    print(f"11/11; {max(v['maxDistance'] for v in optical.values()):.6f} m maximum; "
          f"{min(v['minDensity'] for v in optical.values()):.6f} px/m minimum", flush=True)
    from family import activate, repos
    activate(args.pluginset.resolve())
    path = args.scenarios.resolve()/'scenarios/datacentre.py'
    definition = importlib.util.spec_from_file_location('family_datacentre', path)
    dc = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(dc)
    from datacentre_validators import policy
    from usdaeco_cctv import validators
    stats = dc.prepare(output)
    stage, config = dc.author_schedule(output)
    reports = dc.run_schedule(stage, output, args.kernel)
    dc.save_composed(stage, output)
    mapping = dict(CriticalDoors='DC-critical-doors', ExternalDoors='DC-external',
                   Corridors='DC-corridors', Yards='DC-yard-day', YardsNight='DC-yard-night',
                   Lobby='DC-lobby', Privacy='DC-privacy-baseline', RevitParity='DC-revit-parity')
    rows = []
    for name, report in reports.items():
        fixed = sum(bool(v['views']) and v['fixedCoverage'] for v in report['results'].values())
        expected = len(config[name][0])
        distance_errors = list(validators._too_far(stage.GetPrimAtPath(dc.STUDY_ROOT+'/'+name), None))
        ok = (fixed == expected and not report['exclusionsCovered'] and not distance_errors
              and len(report['results']) == expected and bool(report['inputHash']))
        rows.append(dict(gate=mapping[name], status='PASS' if ok else 'FINDING', passed=ok,
                         targets=expected, fixedCovered=fixed, exclusions=len(report['exclusionsCovered']),
                         distanceErrors=len(distance_errors), seconds=round(report['seconds'],3)))
    hall = [e for e in policy(stage) if e.GetName() == 'dcHallCamera']
    rows.append(dict(gate='DC-hall-rule-baseline', status='PASS' if not hall else 'FINDING', passed=not hall, errors=len(hall)))
    sources = {}
    for name, source in {'scenarios': args.scenarios, **repos()}.items():
        sources[name] = dict(revision=subprocess.check_output(['git','rev-parse','HEAD'], cwd=source, text=True).strip(),
                             modified=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'], cwd=source, text=True).strip()))
    result = dict(rows=rows, build=stats, studies=reports, optics=optical, sources=sources,
                  planSha256=hashlib.sha256(json.dumps(json.loads((output/'out/build_plan.json').read_text()),
                                           sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                  scheduleSha256=hashlib.sha256(path.read_bytes()).hexdigest(), kernel=args.kernel)
    dc.write_json(output/'report.json', dc.portable(result, output))
    for row in rows:
        print(row['status'], row['gate'], json.dumps({k:v for k,v in row.items() if k not in ('gate','status','passed')}), flush=True)
    findings = sum(not row['passed'] for row in rows)
    print(f'{len(rows)} studies/policies, {findings} design findings', flush=True)
    return int(bool(findings))


if __name__ == '__main__':
    raise SystemExit(main())
