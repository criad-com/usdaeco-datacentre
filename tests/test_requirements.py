from pathlib import Path

import ifcopenshell.api.unit
import ifcopenshell.geom
import ifcopenshell.util.element as element
import ifcopenshell.util.placement as placement
import numpy as np
import pytest
from pydantic import ValidationError

from dcbuild import ids, layout, spec, requirements
from dcbuild.ifc import architecture, security, spatial
from dcbuild.ifc.builder import Builder


def test_reader_bands_and_overrides():
    p=layout.resolve(spec.load(variant='iris'))
    readers=p.security['iris_mounting']
    assert len(readers)==11
    assert sum(d['MountingHeight']==1.2 for d in readers.values())==10
    assert readers['door.office.link']['MountingHeight']==1.65
    documents=requirements.load(Path('spec/requirements'))
    assert len(documents)==3
    assert requirements.evaluate(readers,documents)==p.meta['expected']['readers']


@pytest.mark.parametrize('length',['METERS','MILLIMETERS'])
def test_ifc_mounting_height_matches_geometry(length):
    p=layout.resolve(spec.load(variant='iris'));b=Builder(p)
    ifcopenshell.api.unit.assign_unit(b.file,length={'is_metric':True,'raw':length})
    spatial.build(b,p);architecture.build(b,p);security.build(b,p)
    scale=1 if length=='METERS' else .001
    settings=ifcopenshell.geom.settings();settings.set(settings.USE_WORLD_COORDS,True)
    for entry in p.security['iris']:
        reader=b.file.by_guid(ids.guid(entry['id']))
        data=element.get_psets(reader)['DC_Security']
        expected=1.65 if entry['door']=='door.office.link' else 1.2
        assert data['MountingHeight']*scale==pytest.approx(expected)
        assert data['DoorEdgeOffset']*scale==pytest.approx(.35)
        assert data['Side']=='pull'
        shape=ifcopenshell.geom.create_shape(settings,reader)
        vertices=np.asarray(shape.geometry.verts).reshape(-1,3)
        assert (vertices[:,2].min()+vertices[:,2].max())/2==pytest.approx(expected)
        door=next(d for d in p.doors if d.id==entry['door'])
        transform=placement.get_local_placement(b.file.by_guid(ids.guid(door.id)).ObjectPlacement)
        assert transform[:2,1]==pytest.approx(layout.NORMALS[door.approach_normal])


@pytest.mark.parametrize('mutation', ['illustrative','unit','reversed','authority','operator'])
def test_invalid_requirement_rejected(mutation):
    doc=requirements.load(Path('spec/requirements'))['accessibility'].model_dump()
    if mutation=='illustrative':doc['illustrative']=False
    elif mutation=='unit':doc['requirements'][0]['unit']='mm'
    elif mutation=='reversed':doc['requirements'][0]['values']=[1.2,.9]
    elif mutation=='authority':doc['authority']=0
    else:doc['requirements'][0]['operator']='approx'
    with pytest.raises(ValidationError):requirements.Specification.model_validate(doc)


def test_reader_side_and_offset_are_drivers():
    source=spec.load(variant='iris')
    old=layout.resolve(source)
    source.security.iris_readers.side='push'
    source.security.iris_readers.door_edge_offset=.4
    new=layout.resolve(source)
    for entry in new.security['iris']:
        assert old.equip(entry['id']).space!=new.equip(entry['id']).space
        assert new.security['iris_mounting'][entry['door']]['DoorEdgeOffset']==.4
