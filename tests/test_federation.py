"""Full delivery contracts and failures that would hide missing packages."""
import json
from pathlib import Path
import shutil

import pytest

from dcbuild.dependencies import ROOT
from dcbuild.federation import PACKAGES, cross_package_links
from dcbuild.qa.federation import connected_text, ifc_ownership, spatial_ownership, verify_publication


@pytest.fixture
def published():
    return ROOT / "dist/full"


def test_only_shared_defines_spatial_structure(published):
    result = spatial_ownership(published)
    assert result["spatialDefs"] == 46
    assert result["projectDefs"] == 1
    assert result["spatialOvers"] > 0


def test_delivered_ifc_has_disjoint_elements_and_complete_twins(published):
    counts = ifc_ownership(published)
    assert counts["shared"]["elements"] == 0
    assert counts["shared"]["ports"] == 0
    assert counts["shared"]["grids"] == 1
    assert sum(r["elements"] for r in counts.values()) > 3000


def test_connected_root_text_without_opening_ifc(published):
    assert connected_text(published) == {"assets": 9, "composition": "not proven"}


@pytest.mark.parametrize("name", ["cooling.ifc", "security.semantics.usda", "shared.geometry.usdc"])
def test_twin_or_delivery_tampering_is_rejected(published, tmp_path, name):
    shutil.copytree(published, tmp_path / "full")
    with (tmp_path / "full" / name).open("ab") as stream:
        stream.write(b"altered")
    with pytest.raises(ValueError, match="differ from its manifest"):
        verify_publication(tmp_path / "full")


def test_spatial_def_in_discipline_is_rejected(published, tmp_path):
    from pxr import Sdf
    shutil.copytree(published, tmp_path / "full")
    layer = Sdf.Layer.FindOrOpen(str(tmp_path / "full/arch.semantics.usda"))
    layer.rootPrims[0].specifier = Sdf.SpecifierDef
    layer.Save()
    with pytest.raises(ValueError, match="Spatial specifier"):
        spatial_ownership(tmp_path / "full")


def test_manifest_lists_serves_and_external_ports(published):
    from pxr import Usd
    stage = Usd.Stage.Open(str(published / "dc.usda"))
    links = cross_package_links(stage)
    manifest = json.loads((published / "dc.manifest.json").read_text())
    assert links == manifest["crossPackageLinks"]
    assert {r["relationship"] for r in links} >= {"aeco:connectedPorts", "aeco:serves"}
    assert set(manifest["packages"]) == set(PACKAGES)


def test_text_ifc_is_swept_and_disguised_archive_rejected(tmp_path, monkeypatch):
    from dcbuild.dependencies import dependency_source
    monkeypatch.syspath_prepend(str(dependency_source("toolchain")[0] / "tools"))
    from usdaeco_check.publication import inspect_tree
    for name in ("LICENSE", "library.json"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    (tmp_path / "README.md").write_text("## Licence\n\nMIT.\n")
    path = tmp_path / "shared.ifc"
    path.write_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
    assert inspect_tree(tmp_path)["ok"]
    path.write_bytes(b"PK\x03\x04")
    result = inspect_tree(tmp_path)
    assert not result["ok"]
    assert any(r["rule"] == "ArchiveNotInspected" for r in result["sweep"]["findings"])


def test_ifc_sweep_exempts_identity_but_keeps_name_and_property_text():
    import ifcopenshell
    from check import ifc_sweep_text
    word = "n" + "pg"
    guid = "0" + word + "0" * 18
    model = ifcopenshell.file(schema="IFC4X3")
    model.create_entity("IfcProject", GlobalId=guid, Name=word)
    model.create_entity("IfcPropertySingleValue", Name="Example", NominalValue=model.create_entity("IfcLabel", guid))
    text = ifc_sweep_text(model.to_string())
    assert "IFCPROJECT('<uuid>'" in text
    assert "'" + word + "'" in text
    assert "IFCLABEL('" + guid + "')" in text


def test_fixture_delivery_map_matches_authored_owners(published):
    from pxr import Usd
    from dcbuild import layout, spec
    from dcbuild.federation import ownership
    plan = layout.resolve(spec.load(variant="full"))
    stage = Usd.Stage.Open(str(published / "dc.usda"))
    owners = ownership(stage)
    indexed = {p.GetAttribute("aeco:props:DC_Identity:Id").Get(): p for p in stage.Traverse()
               if p.GetAttribute("aeco:props:DC_Identity:Id").Get()}
    def owner(identity):
        return owners[str(indexed[identity].GetPath())]
    assert owner("lvl.l2") == "shared"
    assert all(owner(s.id) == "shared" for s in plan.spaces if s.storey == "lvl.l2")
    assert all(owner(e.id) == "arch" for e in [*plan.walls, *plan.doors] if e.storey == "lvl.l2")
    assert all(owner(item["id"]) == ("cooling" if item["id"].startswith("pipe.clash.") else "fitout")
               for item in plan.meta["fitout"])
    assert all(owner(reader["id"]) == "security" for reader in plan.security["iris"])
