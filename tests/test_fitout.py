from collections import Counter
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as element
import ifcopenshell.util.placement as placement
import numpy as np
import pytest

from dcbuild import ids, layout, spec
from dcbuild.ifc import fitout, spatial
from dcbuild.ifc.builder import Builder
from dcbuild.qa import cameras
from dcbuild.qa.validate_ifc import schema, ports, guids, orphans


@pytest.fixture(scope='module')
def fixture(tmp_path_factory):
    p=layout.resolve(spec.load(variant='pod'))
    b=Builder(p);spatial.build(b,p);fitout.build(b,p)
    path=b.write(tmp_path_factory.mktemp('fitout')/'fitout.ifc')
    return p,path


def test_fitout_ifc_schema_status_and_identity(fixture):
    p,path=fixture
    f=ifcopenshell.open(path)
    assert not schema(path)
    assert not cameras.statuses(f,p)
    assert not ports(f)+guids(f)+orphans(f)
    for item in p.meta['fitout']:
        e=f.by_guid(ids.guid(item['id']))
        assert e.is_a(item['ifc_class'])
        assert element.get_psets(e)['DC_Identity']['Id']==item['id']
        assert element.get_container(e).GlobalId==ids.guid(item['space'])
        nested=[p for rel in e.IsNestedBy for p in rel.RelatedObjects]
        assert len(nested)==len(item['ports'])
        actual=[placement.get_local_placement(p.ObjectPlacement)[:3,3] for p in nested]
        assert np.array(actual)==pytest.approx(np.array(item['ports']))


def test_fitout_census(fixture):
    p,path=fixture
    f=ifcopenshell.open(path)
    assert len(p.meta['fitout'])==23
    assert Counter(e['fix'] for e in p.meta['fitout'] if e['fix'])==dict(first=6,second=10,third=3)
    assert len(f.by_type('IfcCovering'))==2
    assert len(f.by_type('IfcElementAssembly'))==2
    assert len(f.by_type('IfcLightFixture'))==6
    assert len(f.by_type('IfcAirTerminal'))==4
    assert len(f.by_type('IfcSanitaryTerminal'))==2
    assert sum(e['status']=='TEMPORARY' for e in p.meta['fitout'])==1


@pytest.mark.parametrize('id,bounds', [
    ('sp.void.office', [[12,-12,6.6],[22,-3,7]]),
    ('sp.void.ocorr.1', [[15,-3,6.6],[30,0,7]]),
    ('clg.office', [[12,-12,6.5875],[22,-3,6.6]]),
    ('pod.wc.temp', [[20,-3.3,4],[22.4,.3,6.5]]),
    ('pod.wc', [[26.2,-11.8,4],[28.6,-8.2,6.5]])])
def test_fitout_world_geometry(fixture,id,bounds):
    _,path=fixture
    f=ifcopenshell.open(path)
    settings=ifcopenshell.geom.settings();settings.set(settings.USE_WORLD_COORDS,True)
    shape=ifcopenshell.geom.create_shape(settings,f.by_guid(ids.guid(id)))
    verts=np.array(shape.geometry.verts).reshape(-1,3)
    assert np.stack([verts.min(axis=0),verts.max(axis=0)])==pytest.approx(np.array(bounds))
