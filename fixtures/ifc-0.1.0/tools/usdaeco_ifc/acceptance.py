"""Reproducible conversion and host acceptance; all generated inputs are scratch data."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
from .runtime import python


def generator_root():
    root = Path(os.environ.get('AECO_DATACENTRE_ROOT', Path(__file__).resolve().parents[3] / 'usdaeco-datacentre'))
    if not (root / 'src/dcbuild').is_dir():
        raise FileNotFoundError('Set AECO_DATACENTRE_ROOT to datacentre v0.4.0')
    return root


def build_base(directory):
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    source = generator_root()
    shutil.copytree(source / 'spec', directory / 'spec')
    code = 'import sys;sys.dont_write_bytecode=True;sys.path.insert(0,sys.argv.pop(1));from dcbuild.cli import main;raise SystemExit(main())'
    python(['-c', code, str(source / 'src'), 'build-ifc','--variant','base','--out','ifc','--manifest-dir','manifest'],
           cwd=directory,check=True,capture_output=True,text=True,timeout=240)
    return directory/'ifc/demo-datacentre-01.ifc', json.loads((directory/'manifest/demo-datacentre-01.base.json').read_text())


def convert_process(module, source, output):
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    code = 'import sys,json;from ' + module + ' import convert;stats=convert(sys.argv[1],sys.argv[2],threads=2);stats.pop("out",None);print(json.dumps(stats))'
    result = python(['-c',code,str(source),str(output)],check=True,capture_output=True,text=True,timeout=240)
    return json.loads(result.stdout.splitlines()[-1])


def converter_parity(source, directory, manifest):
    directory = Path(directory)
    reference = convert_process('ifc2usdaeco',source,directory/'reference/dc.usda')
    moved = convert_process('usdaeco_ifc.convert',source,directory/'moved/dc.usda')
    from pxr import Usd
    stage = Usd.Stage.Open(str(directory/'moved/dc.usda'))
    spaces = sum(p.GetTypeName() == 'AecoSpace' for p in stage.Traverse())
    layers = []
    for name in ('dc.usda','dc.semantics.usda','dc.geometry.usdc'):
        before = (directory/'reference'/name).read_bytes()
        after = (directory/'moved'/name).read_bytes()
        layers.append(dict(name=name,identical=before==after,bytes=len(after),sha256=hashlib.sha256(after).hexdigest()))
    return dict(reference=reference,moved=moved,spaces=spaces,rooms=manifest['counts']['rooms'],
                manifestSpaces=manifest['counts']['spaces'],layers=layers), directory/'moved/dc.usda'


def host_cases(directory):
    from scenarios.run import run_suite
    report = run_suite(Path(directory),hosts=('ifc',))
    kinds = {'synthetic': [],'camera': [],'datacentre': []}
    root = Path(__file__).resolve().parents[2]
    definitions = json.loads((root/'scenarios/cases.json').read_text())
    categories = {c['id']: c.get('family','synthetic') for c in definitions}
    for row in report['hosts']['ifc']:
        kinds[categories[row['id']]].append(dict(id=row['id'],passed=row['passed']))
    return kinds
