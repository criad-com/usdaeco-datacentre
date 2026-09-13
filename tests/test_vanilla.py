"""Publication evidence must reject changed data, images and presentation."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from dcbuild import vanilla
from dcbuild.dependencies import ROOT, clean_environment, dependency_source


@pytest.fixture
def publication(tmp_path, monkeypatch):
    kit, _ = dependency_source("toolchain")
    monkeypatch.syspath_prepend(str(kit / "tools"))
    for name in ("dist/base", "manifests/cameras", "src/dcbuild"):
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copyfile(ROOT / "manifests/vanilla.json", tmp_path / "manifests/vanilla.json")
    monkeypatch.setattr(vanilla, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("name", ["dist/base/dc.usda", "src/dcbuild/render.py"])
def test_changed_source_is_stale(publication, name):
    with (publication / name).open("a") as file:
        file.write("\n# changed\n")
    with pytest.raises(ValueError, match="VanillaSourceStale"):
        vanilla.check_example("base")


def test_changed_image_is_rejected(publication):
    with (publication / "dist/base/vanilla.png").open("ab") as file:
        file.write(b"changed")
    with pytest.raises(ValueError, match="VanillaManifestMismatch"):
        vanilla.check_example("base")


def test_blank_image_is_rejected_even_with_matching_receipt(publication):
    from PIL import Image
    from dcbuild.publish import digest
    image = publication / "dist/base/vanilla.png"
    Image.new("RGB", vanilla.SIZE).save(image)
    path = publication / "manifests/vanilla.json"
    data = json.loads(path.read_text())
    data["base"].update(sha256=digest(image), bytes=image.stat().st_size)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="uniform pixels"):
        vanilla.check_example("base")


def test_changed_camera_is_rejected(publication):
    with (publication / "manifests/cameras/base.usda").open("a") as file:
        file.write("\n# changed\n")
    with pytest.raises(ValueError, match="VanillaCameraStale"):
        vanilla.check_example("base")


def test_resealed_camera_still_requires_fresh_derivation(publication, monkeypatch):
    from dcbuild.publish import digest
    original = (publication / "manifests/cameras/base.usda").read_bytes()
    with (publication / "manifests/cameras/base.usda").open("a") as file:
        file.write("\n# changed\n")
    path = publication / "manifests/vanilla.json"
    data = json.loads(path.read_text())
    prepared = {key: data["base"][key] for key in ("frame", "normalized_sha256", "camera_sha256")}
    data["base"]["camera_sha256"] = digest(publication / "manifests/cameras/base.usda")
    path.write_text(json.dumps(data))

    def fresh(variant, output):
        (output / "cameras.usda").write_bytes(original)
        return prepared

    monkeypatch.setattr(vanilla, "prepare", fresh)
    with pytest.raises(ValueError, match="VanillaResultStale"):
        vanilla.check_example("base")


def test_core_validation_loads_verified_sources_without_pythonpath():
    code = ("import sys; sys.path.insert(0,sys.argv[1]); "
            "from check import core_validation_context; core_validation_context()")
    result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT)],
                            env=clean_environment(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("failure", ["missing_source", "unimportable_plugin"])
def test_core_validation_fails_without_importable_plugin(tmp_path, failure):
    code = "import sys; sys.path.insert(0,sys.argv[1]); "
    environment = clean_environment()
    if failure == "missing_source":
        environment["AECO_VALIDATION_CORE_ROOT"] = str(tmp_path)
    else:
        code += "sys.modules['usdAecoValidators'] = None; "
    code += "from check import core_validation_context; core_validation_context()"
    result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT)],
                            env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    expected = "runtime bytes differ" if failure == "missing_source" else "import of usdAecoValidators halted"
    assert expected in result.stderr
