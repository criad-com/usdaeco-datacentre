#!/usr/bin/env python3
"""Run the pinned Revit integration's camera gate; the seed supplies its census."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcbuild.revit_runtime import setup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.work/dc-live.revit'))
    args, remaining = parser.parse_known_args(argv)
    source, pin = setup(live=True)
    from usdaeco_revit.transport import ReplClient
    source_path = source/'tools/usdaeco_revit/gates/cctv_revit.py'
    original = source_path.read_bytes()
    module = importlib.import_module('usdaeco_revit.gates.cctv_revit')
    if Path(module.__file__).resolve() != source_path or module.ReplClient is not ReplClient:
        raise RuntimeError('Imported runner must use the pinned Revit source and transport')
    args.output.mkdir(parents=True, exist_ok=True)
    retained = Path(tempfile.mkdtemp(prefix='runner-', dir=args.output))
    (retained/'released.py').write_bytes(original)
    (retained/'provenance.json').write_text(json.dumps({
        'releasedSha256': hashlib.sha256(original).hexdigest(),
        'changedAssertions': 0,
        'repo': pin['repo'], 'ref': pin['ref'], 'revision': pin['revision'],
    }, indent=2)+'\n')
    print('== stage: unmodified live gate; camera census from seed', flush=True)
    return module.main(['--case-set', 'datacentre', '--output', str(args.output), *remaining])


if __name__ == '__main__':
    raise SystemExit(main())
