#!/usr/bin/env python3
"""Additional 1.6 m corridor study; keep the family's 1.5 m baseline untouched."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path, help='Completed scripts/study.py output')
    parser.add_argument('--scenarios', type=Path, required=True)
    parser.add_argument('--pluginset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New diagnostic output directory')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.scenarios.resolve()))
    from family import activate
    activate(args.pluginset.resolve())
    from pxr import Gf, Usd, Vt
    from usdaeco_cctv.study import run_study
    stage = Usd.Stage.Open(str(args.study.resolve()/'schedule.usda'))
    study_path = '/SecurityStudies/Corridors'
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        study = stage.GetPrimAtPath(study_path)
        for path in study.GetRelationship('collection:targets:includes').GetTargets():
            attr = stage.GetPrimAtPath(path).GetAttribute('aeco:cctvTarget:points')
            attr.Set(Vt.Vec3fArray([Gf.Vec3f(p[0],p[1],p[2]+.1) for p in attr.Get()]))
    args.output.mkdir(parents=True)
    print('== stage: additional corridor grid at 1.6 m', flush=True)
    report = run_study(stage, study_path, args.output/'coverage.usda', kernel='embree')
    rows = [dict(target=k, fraction=v['fraction'], fixedCoverage=v['fixedCoverage'], density=v['density'])
            for k,v in report['results'].items()]
    result = dict(height=1.6, spacing=.5, requiredDensity=62.5, passFraction=.9, rows=rows)
    (args.output/'report.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    good = sum(r['fixedCoverage'] for r in rows)
    print(f'{good}/{len(rows)} fixed-covered', flush=True)
    return int(good != 7 or len(rows) != 7)


if __name__ == '__main__':
    raise SystemExit(main())
