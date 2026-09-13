"""Federation proofs: inventory, IFC ownership, transforms and delivery muting."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from ..federation import (DATA_FILES, DELIVERY_ORDER, FULL_CAP, LAYERS, LINKS, PACKAGES,
                          SPATIAL, cross_package_links, identity_paths, inventory, layer_specs, package_counts)
from ..dependencies import ROOT


def publication_baseline(folder):
    """Require the released twins and five historical directories byte-for-byte."""
    from ..publish import digest
    baseline = json.loads((ROOT / "manifests/publication-v0.5.0.json").read_text())
    groups = ((folder, {n: baseline["full"][n] for n in LAYERS}),
              (folder.parent, baseline["historical"]))
    for parent, files in groups:
        for name, expected in files.items():
            path = parent / name
            if {"bytes": path.stat().st_size, "sha256": digest(path)} != expected:
                raise ValueError("Publication bytes differ from v0.5.0: " + name)
    for variant in ("base", "floors", "pod", "clash", "iris"):
        if {p.name for p in (folder.parent / variant).iterdir()} != {
                Path(n).name for n in baseline["historical"] if n.startswith(variant + "/")}:
            raise ValueError("Historical publication inventory changed: " + variant)
    return {"twins": len(LAYERS), "historicalFiles": len(baseline["historical"])}


def crossing_references(folder):
    """Join every IFC crossing to the actual twin relationship, with multiplicity."""
    import ifcopenshell
    import ifcopenshell.guid
    import uuid
    from pxr import Sdf, Usd
    stage = Usd.Stage.Open(str(folder / "dc.usda"))
    paths = identity_paths(stage)
    expected = cross_package_links(stage)
    key = lambda r: (r["package"], r["source"], r["relationship"], r["targetPackage"], r["target"])
    path_for = lambda guid: paths[str(uuid.UUID(hex=ifcopenshell.guid.expand(guid)))]
    actual, result = [], {}
    for package in PACKAGES:
        model = ifcopenshell.open(folder / (package + ".ifc"))
        counts = dict(documentReferences=0, connectedPorts=0, serves=0, nativeServes=0)
        documents = {d.id() for d in model.by_type("IfcDocumentReference")
                     if d.Name in {"aeco:connectedPorts", "aeco:serves"}}
        associated = set()
        for rel in model.by_type("IfcRelAssociatesDocument"):
            doc = rel.RelatingDocument
            if doc.id() not in documents:
                continue
            target = path_for(doc.Identification)
            if doc.Description != target or not Sdf.Path(target).IsAbsoluteRootOrPrimPath():
                raise ValueError("Crossing reference Description differs from its resolved twin target")
            if doc.Location not in {p + ".ifc" for p in PACKAGES if p != package}:
                raise ValueError("Crossing reference Location must name the foreign IFC basename")
            associated.add(doc.id())
            counts["documentReferences"] += 1
            for source in rel.RelatedObjects:
                actual.append((package, path_for(source.GlobalId), doc.Name, doc.Location[:-4], target))
                counts["connectedPorts" if doc.Name == "aeco:connectedPorts" else "serves"] += 1
        if associated != documents:
            raise ValueError("Crossing reference has no local document association")
        # The native IFC relationship includes the building in each local spine;
        # conversion resolves its path locally, then demotes that spine to overs.
        for rel in model.by_type("IfcRelServicesBuildings"):
            for target in rel.RelatedBuildings:
                actual.append((package, path_for(rel.RelatingSystem.GlobalId), "aeco:serves",
                               "shared", path_for(target.GlobalId)))
                counts["serves"] += 1
                counts["nativeServes"] += 1
        result[package] = counts
    if Counter(actual) != Counter(key(r) for r in expected):
        raise ValueError("IFC crossing references differ from resolved twin relationships")
    if Counter(r[2] for r in actual) != {"aeco:connectedPorts": 1008, "aeco:serves": 9}:
        raise ValueError("Expected 1,008 external port targets and nine serves targets")
    return result


def twin_source_files(folder):
    """Undo only reference descriptions and prove exact released conversion inputs."""
    import ifcopenshell
    baseline = json.loads((ROOT / "manifests/publication-v0.5.0.json").read_text())["full"]
    sources = {}
    for package in PACKAGES:
        name = package + ".ifc"
        model = ifcopenshell.open(folder / name)
        for doc in model.by_type("IfcDocumentReference"):
            if doc.Name in {"aeco:connectedPorts", "aeco:serves"}:
                doc.Description = None
        original = model.to_string().encode()
        record = {"bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}
        if record != baseline[name]:
            raise ValueError("IFC changed beyond crossing reference descriptions: " + name)
        sources[name] = record
    return sources


def connected_text(folder):
    text = (folder / "dc.connected.usda").read_text()
    expected = [p + ".ifc:SDF_FORMAT_ARGS:spine=over" for p in DELIVERY_ORDER] + ["shared.ifc"]
    assets = re.findall(r"@([^@]+)@", text)
    usd = (folder / "dc.usda").read_text()
    header = lambda s: re.sub(r"subLayers = \[.*?\]", "subLayers = []", s, flags=re.S)
    if assets != expected or header(text) != header(usd):
        raise ValueError("Connected root text differs from the delivery/header contract")
    return {"assets": len(assets), "composition": "not proven"}


def spatial_ownership(folder):
    from pxr import Sdf
    shared = Sdf.Layer.FindOrOpen(str(folder / "shared.semantics.usda"))
    spatial = {str(p.path) for p in layer_specs(shared) if p.typeName in SPATIAL}
    project = "/" + Sdf.Layer.FindOrOpen(str(folder / "shared.usda")).defaultPrim
    paths = spatial | {project}
    overs = 0
    for package in PACKAGES:
        for suffix in (".semantics.usda", ".geometry.usdc"):
            layer = Sdf.Layer.FindOrOpen(str(folder / (package + suffix)))
            for prim in layer_specs(layer):
                if str(prim.path) in paths:
                    owner = package == "shared" and suffix == ".semantics.usda"
                    expected = Sdf.SpecifierDef if owner else Sdf.SpecifierOver
                    if prim.specifier != expected:
                        raise ValueError(f"Spatial specifier conflict in {package}{suffix}: {prim.path}")
                    if not owner and (prim.typeName or prim.properties or prim.HasInfo("apiSchemas")):
                        raise ValueError("A package authors foreign spatial opinions")
                    overs += not owner
                elif prim.typeName in SPATIAL:
                    raise ValueError("Package declares a spatial path absent from shared")
    return {"spatialDefs": len(spatial), "projectDefs": 1, "spatialOvers": overs}


def verify_publication(folder):
    from pxr import Sdf, Usd
    from ..publish import plugin_free_census
    data = json.loads((folder / "dc.manifest.json").read_text())
    if not set(DATA_FILES) <= data["files"].keys() or data["files"] != inventory(folder):
        raise ValueError("Full files differ from its manifest")
    if set(data["layers"]) != set(LAYERS) or any(data["layers"][n] != data["files"][n] for n in LAYERS):
        raise ValueError("Full layers differ from its manifest")
    if sum(p.stat().st_size for p in folder.iterdir()) > FULL_CAP:
        raise ValueError("Full publication exceeds the size cap")
    crossing_references(folder)
    sources = twin_source_files(folder)
    if data.get("twinSourceFiles") != sources:
        raise ValueError("Twin conversion inputs differ from the manifest")
    root = Sdf.Layer.FindOrOpen(str(folder / "dc.usda"))
    for package in PACKAGES:
        if package_counts(folder, package) != data["packages"][package]:
            raise ValueError("Package census differs from its manifest")
        for suffix in (".usda", ".semantics.usda", ".geometry.usdc"):
            path = folder / (package + suffix)
            if suffix.endswith("usdc") and path.read_bytes()[:8] != b"PXR-USDC":
                raise ValueError("Geometry must be a binary USD crate")
            layer = Sdf.Layer.FindOrOpen(str(path))
            stamp = layer.customLayerData
            if (stamp.get("aeco:layer:role") != ("spine" if package == "shared" else "package")
                    or stamp.get("aeco:layer:package") != package
                    or stamp.get("aeco:layer:producer") != "usdaeco-datacentre generator 0.5.0"
                    or stamp.get("aeco:layer:source") != package + ".ifc"
                    or stamp.get("aeco:layer:sourceSha256") != sources[package + ".ifc"]["sha256"]):
                raise ValueError("Twin provenance differs from its verified conversion input")
            if suffix == ".usda" and layer.subLayerPaths != [package + ".semantics.usda", package + ".geometry.usdc"]:
                raise ValueError("Twin root must sublayer semantics then geometry")
            if suffix == ".usda" and any(layer.pseudoRoot.GetInfo(key) != root.pseudoRoot.GetInfo(key)
                    for key in ("defaultPrim", "metersPerUnit", "upAxis", "fallbackPrimTypes")):
                raise ValueError("Twin root header differs from the facility root")
    spatial_ownership(folder)
    connected_text(folder)
    stage = Usd.Stage.Open(str(folder / "dc.usda"))
    if stage.GetRootLayer().subLayerPaths != [p + ".usda" for p in PACKAGES]:
        raise ValueError("USD delivery order differs")
    if cross_package_links(stage) != data["crossPackageLinks"]:
        raise ValueError("Cross-package links differ from manifest")
    fallbacks = dict(stage.GetMetadata("fallbackPrimTypes") or {})
    expected = {t: ["Scope" if t in {"AecoSystem", "AecoZone"} else "Xform"]
                for t in SPATIAL | {"AecoSystem", "AecoZone", "AecoPort"}}
    if {k: list(v) for k, v in fallbacks.items()} != expected:
        raise ValueError("All eight core fallbacks must be present")
    probe = plugin_free_census(folder / "dc.usda")
    if probe["counts"] != data["counts"]:
        raise ValueError("Federated census differs from manifest")
    return probe


def snapshot(stage):
    from pxr import UsdGeom
    cache = UsdGeom.XformCache()
    identities, prims, classes, relationships = {}, {}, Counter(), {}
    for prim in stage.TraverseAll():
        path = str(prim.GetPath())
        matrix = cache.GetLocalToWorldTransform(prim)
        world = tuple(float(matrix[i][j]) for i in range(4) for j in range(4))
        prims[path] = (prim.GetTypeName(), world)
        uid = prim.GetAttribute("aeco:id").Get()
        if uid:
            if uid in identities:
                raise ValueError("Duplicate identity in stage")
            identities[uid] = world
        code = prim.GetAttribute("aeco:class:ifc:code").Get()
        if code:
            classes[code] += 1
        for rel in prim.GetRelationships():
            if rel.GetName() in LINKS and rel.GetTargets():
                relationships[str(rel.GetPath())] = sorted(str(p) for p in rel.GetTargets())
    return dict(identities=identities, prims=prims, classes=classes, relationships=relationships)


def compare_monolithic(folder, source, output):
    from pxr import Usd
    from ..federation import run_conversion
    output.mkdir(parents=True, exist_ok=True)
    target = output / "dc.usda"
    run_conversion(source, target, monolithic=True)
    mono = snapshot(Usd.Stage.Open(str(target)))
    federated = snapshot(Usd.Stage.Open(str(folder / "dc.usda")))
    for key in mono:
        if mono[key] != federated[key]:
            missing = set(mono[key]) - set(federated[key])
            added = set(federated[key]) - set(mono[key])
            changed = [k for k in mono[key].keys() & federated[key].keys() if mono[key][k] != federated[key][k]]
            raise ValueError(f"Monolithic {key} differs: {len(missing)} missing, {len(added)} added, "
                             f"{len(changed)} changed; examples: {list(missing)[:2]}, {list(added)[:2]}, {changed[:2]}")
    return {"identities": len(mono["identities"]), "prims": len(mono["prims"]),
            "relationshipProperties": len(mono["relationships"]), "classificationCodes": len(mono["classes"])}


def mute_drill(folder, validation):
    from pxr import Usd, UsdValidation
    stage = Usd.Stage.Open(str(folder / "dc.usda"))
    baseline = snapshot(stage)
    links = json.loads((folder / "dc.manifest.json").read_text())["crossPackageLinks"]
    error_type = UsdValidation.ValidationErrorType.Error
    initial = [e for e in validation.Validate(stage) if e.GetType() == error_type]
    if initial:
        raise ValueError("Complete federation has validator errors")
    results = []
    for package in DELIVERY_ORDER:
        layer = str((folder / (package + ".usda")).resolve())
        stage.MuteLayer(layer)
        try:
            if stage.GetCompositionErrors():
                raise ValueError("Muted federation has composition errors")
            remaining = snapshot(stage)
            moved = [p for p, (_, matrix) in remaining["prims"].items() if
                     p not in baseline["prims"] or baseline["prims"][p][1] != matrix]
            if moved:
                raise ValueError(f"Muting {package} moved {len(moved)} remaining prims")
            expected = [r for r in links if r["targetPackage"] == package and r["package"] != package]
            actual = []
            for prim in stage.Traverse():
                for rel in prim.GetRelationships():
                    if rel.GetName() not in LINKS:
                        continue
                    for target in rel.GetTargets():
                        remote = stage.GetPrimAtPath(target.GetPrimPath())
                        if not remote or not remote.IsDefined():
                            actual.append((str(prim.GetPath()), rel.GetName(), str(target)))
            if sorted(actual) != sorted((r["source"], r["relationship"], r["target"]) for r in expected):
                raise ValueError("Dangling links differ from the manifest mute prediction")
            findings = validation.Validate(stage)
            errors = [e for e in findings if e.GetType() == error_type]
            expected_ports = sum(r["relationship"] == "aeco:connectedPorts" for r in expected)
            if len(errors) != expected_ports or any(not e.GetName().endswith("danglingPortLink") for e in errors):
                raise ValueError(f"Muting {package} introduced unexpected validator errors: "
                                 + str(Counter(e.GetName() for e in errors)))
            results.append(dict(package=package, remainingPrims=len(remaining["prims"]), moved=0,
                                danglingLinks=len(actual), validatorErrors=len(errors)))
        finally:
            stage.UnmuteLayer(layer)
    return results


def ifc_ownership(folder):
    import ifcopenshell
    import ifcopenshell.guid
    import uuid
    from pxr import Sdf
    all_elements = set()
    result = {}
    for package in PACKAGES:
        model = ifcopenshell.open(folder / (package + ".ifc"))
        if model.schema != "IFC4X3":
            raise ValueError("Delivered schema must be IFC4X3")
        elements = {e.GlobalId for e in model.by_type("IfcElement")
                    if not e.is_a("IfcOpeningElement") and not e.is_a("IfcVirtualElement")}
        if all_elements & elements or package == "shared" and model.by_type("IfcElement"):
            raise ValueError("An IFC element belongs to multiple packages or shared")
        all_elements |= elements
        layer = Sdf.Layer.FindOrOpen(str(folder / (package + ".semantics.usda")))
        authored = {p.attributes["aeco:id"].default for p in layer_specs(layer)
                    if p.GetInfo("apiSchemas") and "AecoElementAPI" in p.GetInfo("apiSchemas").GetAppliedItems()}
        if authored != {str(uuid.UUID(hex=ifcopenshell.guid.expand(g))) for g in elements}:
            raise ValueError("Twin element ownership differs from its IFC")
        result[package] = dict(elements=len(elements), ports=len(model.by_type("IfcDistributionPort")),
                               grids=len(model.by_type("IfcGrid")))
    return result


def usdchecker(path):
    """Run the stock compliance executable with family plugin paths removed."""
    import os
    import shutil
    import subprocess
    from ..dependencies import clean_environment
    executable = os.environ.get("USDCHECKER") or shutil.which("usdchecker")
    if not executable:
        raise ValueError("Set USDCHECKER or put usdchecker on PATH")
    result = subprocess.run([executable, "--strict", str(path.resolve())], env=clean_environment(),
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise ValueError("usdchecker failed: " + result.stdout + result.stderr)
    return {"exitCode": result.returncode, "pluginPathsRemoved": True, "strict": True}
