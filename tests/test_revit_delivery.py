"""Native delivery joins must reject incomplete identities and moved geometry."""
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.geometry
import ifcopenshell.api.root
import ifcopenshell.util.placement
import pytest

from dcbuild import layout, spec
from dcbuild.dependencies import ROOT
from dcbuild.qa.parity import architecture
from dcbuild.revit_delivery import partition, physical


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'moved', 'wrong-kind'])
def test_architecture_parity_rejects_bad_delivery(tmp_path, mutation):
    reference = ROOT/'dist/full/arch.ifc'
    model = ifcopenshell.open(str(reference))
    wall = model.by_type('IfcWall')[0]
    if mutation == 'missing':
        ifcopenshell.api.root.remove_product(model, product=wall)
    elif mutation == 'duplicate':
        wall.GlobalId = model.by_type('IfcWall')[1].GlobalId
    elif mutation == 'wrong-kind':
        wall.PredefinedType = 'RETAININGWALL'
        ifcopenshell.util.element.get_type(wall).PredefinedType = 'RETAININGWALL'
    else:
        matrix = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
        matrix[0, 3] += 0.5
        ifcopenshell.api.geometry.edit_object_placement(model, product=wall, matrix=matrix)
    target = tmp_path/'arch.ifc'; model.write(str(target))
    assert architecture(layout.resolve(spec.load(variant='full')), target, reference) == 1
    result = json.loads(target.with_suffix('.parity.json').read_text())
    assert result['failures']
    if mutation == 'missing':
        assert result['joined'] == 166


def test_partition_is_deterministic_and_keeps_only_owned_products(tmp_path):
    source = ROOT/'dist/full/arch.ifc'
    first, second = tmp_path/'a/arch.ifc', tmp_path/'b/arch.ifc'
    for target in (first, second):
        result = partition(source, source, ROOT/'dist/full/shared.ifc', target)
        assert result['elements'] == 167
        assert result['spatial'] == 46
    assert first.read_bytes() == second.read_bytes()
    before = ifcopenshell.open(str(source)); after = ifcopenshell.open(str(first))
    assert {e.GlobalId for e in physical(before)} == {e.GlobalId for e in physical(after)}
    assert len(after.by_type('IfcProject')) == 1
    assert not after.by_type('IfcDistributionPort')
