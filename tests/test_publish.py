"""Published data is readable without schemas; corrupt receipts fail closed."""
import json
from pathlib import Path
import shutil

import pytest

from dcbuild import spec
from dcbuild.dependencies import ROOT, dependency_source
from dcbuild.publish import LAYERS, plugin_free_census, verify_publication


@pytest.mark.parametrize("variant", spec.variants())
def test_published_variant(variant):
    result = verify_publication(ROOT / "dist" / variant)
    assert result["counts"]["unparented"] == 0
    assert result["counts"]["elements"] >= 2954
    assert result["counts"]["spaces"] >= 33


@pytest.mark.parametrize("filename", LAYERS)
def test_tampered_layer_rejected(tmp_path, filename):
    shutil.copytree(ROOT / "dist/base", tmp_path / "base")
    with (tmp_path / "base" / filename).open("ab") as stream:
        stream.write(b"altered")
    with pytest.raises(ValueError, match="differs from its manifest"):
        verify_publication(tmp_path / "base")


def test_missing_fallback_rejected(tmp_path):
    from pxr import Sdf
    shutil.copytree(ROOT / "dist/base", tmp_path / "base")
    root = Sdf.Layer.FindOrOpen(str(tmp_path / "base/dc.usda"))
    root.pseudoRoot.ClearInfo("fallbackPrimTypes")
    root.Save()
    import subprocess
    with pytest.raises(subprocess.CalledProcessError):
        plugin_free_census(tmp_path / "base/dc.usda")


def test_wrong_dependency_bytes_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AECO_CORE_ROOT", str(tmp_path))
    with pytest.raises(ValueError, match="runtime bytes differ"):
        dependency_source("core")


def test_base_converter_census():
    manifest = json.loads((ROOT / "dist/base/dc.manifest.json").read_text())
    assert (manifest["counts"]["elements"], manifest["counts"]["spaces"],
            manifest["counts"]["unparented"]) == (2954, 33, 0)
