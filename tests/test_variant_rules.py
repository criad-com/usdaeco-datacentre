from copy import deepcopy
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from dcbuild import layout, spec
from dcbuild.qa import variant_rules as rules


@pytest.mark.parametrize('variant',['base','floors','pod','clash','iris'])
def test_variant_independent_process_resolves_and_gate(variant,tmp_path):
    # Separate interpreters with fresh randomized hash seeds; no manifest mutation.
    command = "from dcbuild import layout,spec;from pathlib import Path;import sys;layout.resolve(spec.load(variant=sys.argv[1])).write_json(Path(sys.argv[2]))"
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    for seed,name in [('17','a'),('71','b')]:
        env['PYTHONHASHSEED']=seed
        subprocess.run([sys.executable,'-c',command,variant,str(tmp_path/name)],env=env,check=True)
    assert (tmp_path/'a').read_bytes()==(tmp_path/'b').read_bytes()
    p=layout.resolve(spec.load(variant=variant))
    assert all(not check(p) for check in rules.CHECKS)
    if variant!='base':assert p.meta['expected']


@pytest.mark.parametrize('mutation',['missing','duplicate','no_programme'])
def test_bad_void_enclosure_rejected(mutation):
    p=layout.resolve(spec.load(variant='pod'))
    acts=p.meta['programme']['programmes'][0]['activities']
    closing=next(a for a in acts if a['workspace']['encloses'])
    if mutation=='missing':closing['workspace']['encloses']=[]
    elif mutation=='duplicate':acts.append(deepcopy(closing))
    else:p.meta.pop('programme')
    assert rules.void_enclosures(p)


@pytest.mark.parametrize('task',['installation','removal'])
def test_temporary_missing_activity_rejected(task):
    p=layout.resolve(spec.load(variant='pod'))
    programme=p.meta['programme']['programmes'][0]
    programme['activities']=[a for a in programme['activities'] if not (a['taskType']==task and 'pod.wc.temp' in a['scope'])]
    assert rules.temporary_lifecycle(p)


@pytest.mark.parametrize('mutation',['scope','workspace','duplicate','date','placement'])
def test_bad_activity_references_rejected(mutation):
    p=layout.resolve(spec.load(variant='pod'))
    programme=p.meta['programme']['programmes'][0];a=programme['activities'][0]
    if mutation=='scope':a['scope'].append('missing.product')
    elif mutation=='workspace':a['workspace']['occupies'].append('missing.space')
    elif mutation=='duplicate':programme['activities'].append(deepcopy(a))
    elif mutation=='date':a['plannedStart']='2026-01-01'
    else:programme['placements']['missing.product']={'space':'sp.office','pos':[1,2,3]}
    assert rules.activity_scopes(p)


@pytest.mark.parametrize('mutation',['cycle','self','dangling'])
def test_bad_predecessor_graph_rejected(mutation):
    p=layout.resolve(spec.load(variant='pod'));a=p.meta['programme']['programmes'][0]['activities']
    target=a[-1]['id'] if mutation=='cycle' else (a[0]['id'] if mutation=='self' else 'missing.activity')
    a[0]['predecessors'].append(dict(id=target,type='FS',lagDays=0))
    assert rules.predecessor_cycles(p)


@pytest.mark.parametrize('mutation',['extra_door','wall','declaration','prototype'])
def test_undeclared_typical_change_rejected(mutation):
    p=layout.resolve(spec.load(variant='floors'))
    if mutation=='extra_door':p.doors.append(dataclasses.replace(p.doors[-1],id='door.undeclared'))
    elif mutation=='wall':next(w for w in p.walls if w.storey=='lvl.l2').p1=(0,0)
    elif mutation=='declaration':p.meta['expected']['drift']['deviations'].pop(0)
    else:p.meta['storey_rules']['lvl.l2']['typical_of']='missing.level'
    assert rules.typical_deviations(p)


def test_scenario_evidence_and_bad_resequencing():
    p=layout.resolve(spec.load(variant='pod'));actual=rules.scenario_findings(p)
    assert {r['rule'] for r in actual['A']}=={'AccessAfterEnclosure','WorkspaceOccupied','EnclosureBeforeInspection'}
    assert actual['B']==[]
    b=p.meta['programme']['programmes'][1]
    next(a for a in b['activities'] if a['id']=='act.first')['plannedFinish']='2027-04-12'
    assert rules.expected_programmes(p)


def test_unexpected_reader_value_rejected():
    p=layout.resolve(spec.load(variant='iris'))
    p.security['iris_mounting']['door.hall.a.s']['MountingHeight']=2
    assert rules.requirement_files(p)
