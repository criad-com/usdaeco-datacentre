#!/usr/bin/env python3
"""Check whether column findings affect coverage by each corridor's own pair."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path, help='Output of scripts/study.py')
    parser.add_argument('--scenarios', type=Path, required=True)
    parser.add_argument('--pluginset', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('out/column-views'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory to preserve prior evidence')
    sys.dont_write_bytecode = True
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['AECO_DATACENTRE_SOURCE'] = str(ROOT)
    sys.path.insert(0, str(args.scenarios.resolve()))
    from family import activate
    activate(args.pluginset)
    from pxr import Usd
    from usdaeco_cctv.study import run_study

    before = json.loads((args.study/'report.json').read_text())['studies']['Corridors']['results']
    affected = {p: r for p, r in before.items()
                if any(Path(b).name.startswith('col_') for b in r['blockers'])}
    if not affected:
        parser.error('The supplied baseline has no corridor column findings')
    plan = json.loads((args.study/'out/build_plan.json').read_text())
    selected = {c['id'] for c in plan['cameras'] if c['id'].startswith('sec.cam.corr.')
                and '/SecurityTargets/'+c['targets'][0].replace('.', '_') in affected}
    stage = Usd.Stage.Open(str((args.study/'schedule.usda').resolve()))
    stage.SetEditTarget(stage.GetSessionLayer())
    study = stage.GetPrimAtPath('/SecurityStudies/Corridors')
    Usd.CollectionAPI(study, 'targets').CreateIncludesRel().SetTargets(sorted(affected))
    names = {name.replace('.', '_') for name in selected}
    cameras = [p.GetPath() for p in stage.Traverse() if p.GetName() in names]
    if len(cameras) != len(selected) or not cameras:
        parser.error('Camera identities do not resolve uniquely')
    Usd.CollectionAPI(study, 'cameras').CreateIncludesRel().SetTargets(cameras)
    args.output.mkdir(parents=True)
    print('== stage: corridor pairs without supplementary spine views', flush=True)
    result = run_study(stage, str(study.GetPath()), args.output/'analysis.usda', kernel='embree')
    passed = set(result['results']) == set(affected) and all(
        r['fixedCoverage'] and r['fraction'] == 1 and r['enclosedSamples'] == 0
        for r in result['results'].values())
    evidence = dict(passed=passed, originalResults=affected,
                    selectedCameras=sorted(selected), results=result['results'])
    (args.output/'report.json').write_text(json.dumps(evidence, indent=2, sort_keys=True)+'\n')
    for path, value in result['results'].items():
        print(path, value['evaluatedSamples'], 'samples', value['fraction'], 'fixed', value['fixedCoverage'])
    print(f"{len(affected)} corridor checks, {int(not passed)} failed")
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
