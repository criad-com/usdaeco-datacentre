import math

import ifcopenshell
import ifcopenshell.util.placement as placement
import numpy as np
import pytest

from dcbuild import ids, layout, spec
from dcbuild.ifc import fitout, spatial
from dcbuild.ifc.builder import Builder
from dcbuild.dependencies import ROOT
from dcbuild.qa.clash import body, measure_cases, verify_clash


def test_clash_extends_all_pod_data():
    pod=spec.load(variant='pod');clash=spec.load(variant='clash')
    assert len(clash.fitout.elements)==len(pod.fitout.elements)+3
    assert clash.programme==pod.programme
    assert clash.spaces==pod.spaces
    assert len(clash.expected['clash'])==3


def test_near_and_tangent_analytic_distances():
    p=layout.resolve(spec.load(variant='clash'))
    cases={c['id']:c for c in p.meta['expected']['clash']}
    near=cases['pipe.clash.near']
    assert near['axis'][0][2]-near['od']/2-near['tray_top']==pytest.approx(.005)
    assert math.dist(*near['axis'])==2
    assert near['mesh']['combined_deflection_band']>=near['exact']['distance']
    tangent=cases['pipe.clash.tangent']
    assert tangent['axis'][0][1]-tangent['od']/2==pytest.approx(tangent['wall_face_plane']['offset'])
    hard=cases['pipe.clash.hard']
    assert hard['axis'][0][1] < -3-.075 < -3+.075 < hard['axis'][1][1]
    wall=next(w for w in p.walls if w.id==hard['partner'])
    floor=next(s.elevation for s in p.storeys if s.id==wall.storey)
    assert all(floor+op.height < hard['axis'][0][2]-hard['od']/2 for op in wall.openings)


@pytest.mark.parametrize('name',['hard','near','tangent'])
def test_clash_ifc_retains_circular_swept_axis(name):
    p=layout.resolve(spec.load(variant='clash'));b=Builder(p);spatial.build(b,p);fitout.build(b,p)
    case=next(c for c in p.meta['expected']['clash'] if c['id']=='pipe.clash.'+name)
    product=b.file.by_guid(ids.guid(case['id']))
    solid=product.Representation.Representations[0].Items[0]
    assert solid.is_a('IfcExtrudedAreaSolid')
    assert solid.SweptArea.Radius*2==pytest.approx(case['od'])
    local=placement.get_axis2placement(solid.Position)
    assert local[:3,3]==pytest.approx(case['axis'][0])
    end=local[:3,3]+local[:3,2]*solid.Depth
    assert end==pytest.approx(case['axis'][1])


def test_published_meshes_make_the_comparison():
    rows = verify_clash(ROOT / 'dist/clash', spec.load(variant='clash'))
    hard, near, tangent = rows
    assert hard['mesh']['signed_distance'] < -hard['mesh']['combined_deflection_band']
    assert 0 < near['mesh']['signed_distance'] <= near['mesh']['combined_deflection_band']
    assert near['mesh']['combined_deflection_band'] >= near['exact']['distance']
    assert near['exact']['distance'] == pytest.approx(.005)
    assert tangent['mesh']['signed_distance'] < -.0005
    assert abs(tangent['exact']['distance']) < 1e-9


@pytest.fixture
def published_clash():
    from pxr import Usd
    source = Usd.Stage.Open(str(ROOT / 'dist/clash/dc.usda'))
    return Usd.Stage.Open(source.Flatten()), spec.load(variant='clash')


@pytest.mark.parametrize('value', [None, .00022, .02])
def test_missing_understated_or_inflated_stamp_rejected(published_clash, value):
    stage, config = published_clash
    mesh, _, _ = body(stage, 'pipe.clash.near')
    attr = mesh.GetPrim().GetAttribute('aeco:body:tolerance')
    if value is None:
        attr.Clear()
    else:
        attr.Set(value)
    with pytest.raises(ValueError, match='Measured deflection differs'):
        measure_cases(stage, config.expected['clash'], config.publication['tessellation'])


def test_published_band_cannot_drift_from_spec(published_clash):
    stage, config = published_clash
    config.expected['clash'][1]['mesh']['combined_deflection_band'] = .006
    with pytest.raises(ValueError, match='Published band differs'):
        measure_cases(stage, config.expected['clash'], config.publication['tessellation'])


def test_tangent_inscribed_mesh_cannot_claim_false_penetration(published_clash):
    from pxr import Gf, Vt
    stage, config = published_clash
    mesh, points, _ = body(stage, 'pipe.clash.tangent')
    # Move the circumscribed vertices radially back to the exact circle.
    axis = config.expected['clash'][2]['axis'][0]
    for point in points:
        yz = point[1:] - axis[1:]
        point[1:] = np.array(axis[1:]) + yz / np.linalg.norm(yz) * .03015
    mesh.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    with pytest.raises(ValueError, match='Measured deflection differs|Published verdict differs'):
        measure_cases(stage, config.expected['clash'], config.publication['tessellation'])


def test_finite_wall_face_required(published_clash):
    stage, config = published_clash
    # An analytically matching face outside the finite wall is insufficient.
    from dcbuild.qa.clash import on_face
    _, points, triangles = body(stage, 'wall.l1.h.007')
    witness = np.array([points[:, 0].max()+1, points[:, 1].max(), 6.8])
    assert not on_face(witness, triangles, 1, points[:, 1].max())
