"""Published-stage mutations exercise the floor contract independently of YAML."""
import copy
import json
from pathlib import Path

import pytest
from pxr import Sdf, Usd, UsdGeom

from dcbuild import spec
from dcbuild.qa.typical import compare, source_id, verify


@pytest.fixture
def floors():
    stage = Usd.Stage.Open("dist/floors/dc.usda")
    stage.SetEditTarget(stage.GetSessionLayer())
    indexed = {source_id(p): p for p in stage.Traverse() if source_id(p)}
    return stage, indexed, spec.load(variant="floors").expected["drift"]


def test_published_exactly_two_and_measured_quantity(floors):
    stage, indexed, expected = floors
    measured = verify(stage, expected)
    assert measured["matched_elements"] == 28
    assert measured["partition_length_m"] == {"lvl.l1": 43.0, "lvl.l2": 46.2}
    assert measured["net_partition_length_delta_m"] == 3.2
    assert measured == json.loads(Path("dist/floors/dc.manifest.json").read_text())["typical"]
    for level in ("lvl.l1", "lvl.l2"):
        assert len([p for p in Usd.PrimRange(indexed[level]) if p.GetAttribute("aeco:class:ifc:code").Get() == "IfcStair.STRAIGHT_RUN_STAIR"]) == 1
        assert not any(source_id(p).startswith("slab.roof.") for p in Usd.PrimRange(indexed[level]))


@pytest.mark.parametrize("mutation", ["wall", "stair", "roof", "type", "placement", "quantity", "offset"])
def test_published_undeclared_drift_rejected(floors, mutation):
    stage, indexed, expected = floors
    wall = indexed["wall.l2.h.001"]
    if mutation == "wall":
        wall.SetActive(False)
    elif mutation == "stair":
        indexed["arch.stair.3"].SetActive(False)
    elif mutation == "roof":
        roof = stage.DefinePrim(indexed["lvl.l2"].GetPath().AppendChild("UnexpectedRoof"), "Xform")
        roof.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["AecoElementAPI"]))
        roof.CreateAttribute("aeco:class:ifc:code", Sdf.ValueTypeNames.String).Set("IfcSlab.ROOF")
    elif mutation == "type":
        wall.GetInherits().SetInherits([])
    elif mutation == "placement":
        transform = UsdGeom.Xformable(wall).GetOrderedXformOps()[0]
        matrix = transform.Get()
        matrix.SetTranslateOnly(matrix.ExtractTranslation() + (0.1, 0, 0))
        transform.Set(matrix)
    elif mutation == "quantity":
        indexed["wall.l2.v.016"].GetAttribute("aeco:props:Qto_WallBaseQuantities:Length").Set(5.0)
    else:
        expected = copy.deepcopy(expected)
        expected["deviations"][0]["offset_m"] = [2, 0, 0]
    with pytest.raises(ValueError):
        verify(stage, expected)


def test_matching_ignores_exporter_identity(floors):
    stage, indexed, expected = floors
    indexed["wall.l2.h.001"].GetAttribute("aeco:props:DC_Identity:Id").Set("renamed.wall")
    pairs, changes = compare(stage, indexed["lvl.l1"], indexed["lvl.l2"], expected["offset_m"])
    assert len(pairs) == 28 and len(changes) == 2
