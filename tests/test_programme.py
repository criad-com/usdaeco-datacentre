"""Independent exchange readers verify dates, identities, links, lags and scope."""
import json
import xml.etree.ElementTree as ET

import pytest

from dcbuild import layout, spec
from dcbuild.programme import Programmes, Predecessor, build, xer, mspdi, NS


def read_xer(text):
    tables = {}
    name = fields = None
    for line in text.splitlines():
        cells = line.split('\t')
        if cells[0] == '%T':
            name = cells[1]; tables[name] = []
        elif cells[0] == '%F':
            fields = cells[1:]
        elif cells[0] == '%R':
            tables[name].append(dict(zip(fields, cells[1:], strict=True)))
    return tables


def read_xml(text):
    root = ET.fromstring(text)
    leaves = []
    for task in root.findall(f'{{{NS}}}Tasks/{{{NS}}}Task'):
        record = {p.tag.split('}')[-1]: p.text for p in task}
        if record['Summary'] == '1':
            continue
        ext = {x.findtext(f'{{{NS}}}FieldID'): x.findtext(f'{{{NS}}}Value')
               for x in task.findall(f'{{{NS}}}ExtendedAttribute')}
        record['id'] = ext['188743734'];record['scope'] = json.loads(ext['188743731'])
        record['taskType'] = ext['188743737']
        record['links'] = [{p.tag.split('}')[-1]: p.text for p in link}
                           for link in task.findall(f'{{{NS}}}PredecessorLink')]
        leaves.append(record)
    return leaves


@pytest.mark.parametrize('name', ['A','B'])
def test_programme_exchange_agreement(name, tmp_path):
    plan = layout.resolve(spec.load(variant='pod'))
    cfg = Programmes.model_validate(plan.meta['programme'])
    programme = next(p for p in cfg.programmes if p.id == name)
    build(plan,tmp_path/'a'); build(plan,tmp_path/'b')
    for path in (tmp_path/'a').iterdir():
        assert path.read_bytes() == (tmp_path/'b'/path.name).read_bytes()
    x = read_xer(xer(programme,cfg)); xml = read_xml(mspdi(programme,cfg))
    xids={a['task_id']:a['task_code'] for a in x['TASK']}
    mids={a['UID']:a['id'] for a in xml}
    scope=json.loads((tmp_path/'a'/f'{name}.scope.json').read_text())
    workspace=json.loads((tmp_path/'a'/f'{name}.workspace.json').read_text())
    assert len(x['TASK']) == len(xml) == 10
    for activity in programme.activities:
        xa=next(a for a in x['TASK'] if a['task_code']==activity.id)
        ma=next(a for a in xml if a['id']==activity.id)
        assert xa['task_name']==ma['Name']==activity.name
        assert xa['target_start_date'][:10]==ma['Start'][:10]==str(activity.plannedStart)
        assert xa['target_end_date'][:10]==ma['Finish'][:10]==str(activity.plannedFinish)
        assert xa['dc_task_type']==ma['taskType']==activity.taskType
        assert scope[activity.id]==ma['scope']==activity.scope
        assert workspace['activities'][activity.id]==activity.workspace.model_dump()
        xp=[(xids[p['pred_task_id']], p['pred_type'][3:], float(p['lag_hr_cnt'])/24)
            for p in x['TASKPRED'] if p['task_id']==xa['task_id']]
        mp=[(mids[p['PredecessorUID']], {0:'FF',1:'FS',2:'SF',3:'SS'}[int(p['Type'])],float(p['LinkLag'])/14400)
            for p in ma['links']]
        assert xp==mp==[(p.id,p.type,p.lagDays) for p in activity.predecessors]


@pytest.mark.parametrize('kind', ['FS','SS','FF','SF'])
@pytest.mark.parametrize('lag', [-.5, 1.25])
def test_all_link_types_and_fractional_lags(kind,lag):
    cfg=spec.load(variant='pod').programme
    p=cfg.programmes[0]
    p.activities[-1].predecessors=[Predecessor(id=p.activities[0].id,type=kind,lagDays=lag)]
    x=read_xer(xer(p,cfg))['TASKPRED'][-1]
    m=next(a for a in read_xml(mspdi(p,cfg)) if a['id']==p.activities[-1].id)['links'][0]
    assert x['pred_type']=='PR_'+kind and float(x['lag_hr_cnt'])==lag*24
    assert int(m['Type'])=={'FF':0,'FS':1,'SF':2,'SS':3}[kind]
    assert int(m['LinkLag'])==lag*14400


def test_programme_b_changes_parking_and_enclosure_dependencies():
    cfg=spec.load(variant='pod').programme
    a,b=cfg.programmes
    assert b.placements['pod.wc.temp'].space=='sp.office'
    byid={a.id:a for a in b.activities}
    assert byid['act.pod.remove'].plannedFinish < byid['act.ceiling.corridor'].plannedStart
    for ceiling in ('act.ceiling.office','act.ceiling.corridor'):
        assert any(p.id=='act.inspect' for p in byid[ceiling].predecessors)
        assert byid['act.inspect'].plannedFinish < byid[ceiling].plannedStart
    assert set(f['rule'] for f in cfg.expected['A'])=={'AccessAfterEnclosure','WorkspaceOccupied','EnclosureBeforeInspection'}
    assert cfg.expected['B']==[]
