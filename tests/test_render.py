"""Camera framing excludes extent guides and receipts detect stale sources."""
import json
import shutil

import pytest

from dcbuild import render
from dcbuild.dependencies import ROOT, dependency_source


def test_extent_does_not_enlarge_facility_frame():
    from pxr import Sdf, Usd, UsdGeom
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Cube.Define(stage, "/Body")
    extent = UsdGeom.Cube.Define(stage, "/Extent")
    extent.CreateSizeAttr(2000)
    extent.GetPrim().CreateAttribute("aeco:derived:role", Sdf.ValueTypeNames.Token).Set("extent")
    extent.CreatePurposeAttr("guide")
    frame = render.frame_overview(stage)
    assert frame["bounds"] == [[-1, -1, -1], [1, 1, 1]]
    assert frame["hidden_space_extents"] == 1
    assert frame["all_corners_inside"]
    assert UsdGeom.Imageable(extent).ComputeVisibility() == "invisible"


def test_render_rejects_changed_stage(tmp_path, monkeypatch):
    import sys
    sys.dont_write_bytecode = True
    kit, _ = dependency_source("toolchain")
    monkeypatch.syspath_prepend(str(kit / "tools"))
    shutil.copytree(ROOT / "dist/base", tmp_path / "dist/base")
    (tmp_path / "manifests").mkdir()
    shutil.copyfile(ROOT / "manifests/renders.json", tmp_path / "manifests/renders.json")
    monkeypatch.setattr(render, "ROOT", tmp_path)
    with (tmp_path / "dist/base/dc.usda").open("a") as file:
        file.write("\n# source changed\n")
    with pytest.raises(ValueError, match="source layers are stale"):
        render.verify_render("base")
