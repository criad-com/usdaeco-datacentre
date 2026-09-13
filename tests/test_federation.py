"""Full delivery contracts and failures that would hide missing packages."""
import json
from pathlib import Path
import shutil

import pytest

from dcbuild.dependencies import ROOT
from dcbuild.federation import PACKAGES, cross_package_links
from dcbuild.qa.federation import (connected_text, crossing_references, ifc_ownership,
                                   publication_baseline, spatial_ownership, twin_source_stamps,
                                   verify_publication)


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


def test_all_crossing_references_match_resolved_twin_targets(published):
    counts = crossing_references(published)
    assert {p: c["documentReferences"] for p, c in counts.items()} == {
        "site": 0, "arch": 0, "structure": 0, "cooling": 184, "electrical": 344,
        "it": 480, "fitout": 0, "security": 0, "shared": 0}
    assert sum(c["connectedPorts"] for c in counts.values()) == 1008
    assert sum(c["nativeServes"] for c in counts.values()) == 9


def test_twins_retain_content_and_other_publications_retain_released_bytes(published):
    assert publication_baseline(published) == {"twins": 29, "deliveries": 9, "images": 2, "historicalFiles": 30}


def test_all_twin_source_stamps_match_delivered_ifc_bytes(published):
    manifest = json.loads((published / "dc.manifest.json").read_text())
    sources = twin_source_stamps(published)
    assert len(sources) == 9
    assert sources == {name: manifest["files"][name] for name in sources}
    assert "twinSourceFiles" not in manifest


@pytest.mark.parametrize("mutation", ["missing_description", "wrong_path", "wrong_package",
                                      "missing_association", "duplicate_association", "missing_serves"])
def test_incomplete_or_incorrect_crossing_is_rejected(published, tmp_path, mutation):
    import ifcopenshell
    import ifcopenshell.guid
    folder = tmp_path / "full"
    shutil.copytree(published, folder)
    path = folder / "cooling.ifc"
    model = ifcopenshell.open(path)
    rel = model.by_type("IfcRelAssociatesDocument")[0]
    doc = rel.RelatingDocument
    if mutation == "missing_description":
        doc.Description = None
    elif mutation == "wrong_path":
        doc.Description = "/missing/port"
    elif mutation == "wrong_package":
        doc.Location = "shared.ifc"
    elif mutation == "missing_association":
        model.remove(rel)
    elif mutation == "duplicate_association":
        model.create_entity("IfcRelAssociatesDocument", GlobalId=ifcopenshell.guid.new(),
                            RelatedObjects=rel.RelatedObjects, RelatingDocument=doc)
    else:
        model.remove(model.by_type("IfcRelServicesBuildings")[0])
    model.write(str(path))
    with pytest.raises(ValueError, match="[Cc]rossing reference"):
        crossing_references(folder)


def test_ifc_description_change_invalidates_twin_source_stamp(published, tmp_path):
    import ifcopenshell
    shutil.copytree(published, tmp_path / "full")
    path = tmp_path / "full/cooling.ifc"
    model = ifcopenshell.open(path)
    model.by_type("IfcDocumentReference")[0].Description = "/changed/port"
    model.write(str(path))
    with pytest.raises(ValueError, match="Twin source stamp differs from delivered IFC"):
        twin_source_stamps(tmp_path / "full")


@pytest.mark.parametrize("suffix", [".usda", ".semantics.usda", ".geometry.usdc"])
def test_stale_twin_stamp_is_rejected_even_with_fresh_inventory(published, tmp_path, suffix):
    from pxr import Sdf
    from dcbuild.federation import refresh_inventory
    folder = tmp_path / "full"
    shutil.copytree(published, folder)
    layer = Sdf.Layer.FindOrOpen(str(folder / ("cooling" + suffix)))
    stamp = layer.customLayerData
    stamp["aeco:layer:sourceSha256"] = "0" * 64
    layer.customLayerData = stamp
    layer.Save()
    refresh_inventory(folder)
    with pytest.raises(ValueError, match="Twin source stamp differs from delivered IFC"):
        twin_source_stamps(folder)


@pytest.mark.parametrize("suffix", [".semantics.usda", ".geometry.usdc"])
def test_twin_content_change_cannot_hide_behind_updated_stamp(published, tmp_path, suffix):
    from pxr import Sdf
    folder = tmp_path / "full"
    shutil.copytree(published, folder)
    layer = Sdf.Layer.FindOrOpen(str(folder / ("site" + suffix)))
    layer.rootPrims[0].customData = {"altered": True}
    layer.Save()
    with pytest.raises(ValueError, match="Twin content differs from v0.5.1"):
        publication_baseline(folder)


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
    from dcbuild import ids
    import ifcopenshell.guid
    import uuid
    plan = layout.resolve(spec.load(variant="full"))
    stage = Usd.Stage.Open(str(published / "dc.usda"))
    owners = ownership(stage)
    indexed = {p.GetAttribute("aeco:id").Get(): p for p in stage.Traverse()
               if p.GetAttribute("aeco:id").Get()}
    def owner(identity):
        key = str(uuid.UUID(hex=ifcopenshell.guid.expand(ids.guid(identity))))
        return owners[str(indexed[key].GetPath())]
    assert owner("lvl.l2") == "shared"
    assert all(owner(s.id) == "shared" for s in plan.spaces if s.storey == "lvl.l2")
    assert all(owner(e.id) == "arch" for e in [*plan.walls, *plan.doors] if e.storey == "lvl.l2")
    assert all(owner(item["id"]) == ("cooling" if item["id"].startswith("pipe.clash.") else "fitout")
               for item in plan.meta["fitout"])
    assert all(owner(reader["id"]) == "security" for reader in plan.security["iris"])
