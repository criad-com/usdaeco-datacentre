"""Delivered IFC packages and portable USD twins for the complete facility."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from .dependencies import ROOT, clean_environment, dependency_source
from .ifc.federation import DELIVERY_ORDER
from .publish import digest, write_json

PACKAGES = (*DELIVERY_ORDER, "shared")
FULL_CAP = 40_000_000
SPATIAL = {"AecoSite", "AecoFacility", "AecoFacilityPart", "AecoLevel", "AecoSpace"}
LINKS = {"aeco:connectedPorts", "aeco:serves", "collection:members:includes"}
LAYERS = ("dc.usda", "dc.connected.usda", *(name + suffix for name in PACKAGES
          for suffix in (".usda", ".semantics.usda", ".geometry.usdc")))
DATA_FILES = (*LAYERS, *(name + ".ifc" for name in PACKAGES))


def layer_specs(layer):
    result = []
    layer.Traverse("/", lambda p: result.append(layer.GetPrimAtPath(p)) if p.IsPrimPath() else None)
    return [p for p in result if p]


def stamp(layer, package, source):
    layer.customLayerData = {
        "aeco:layer:role": "spine" if package == "shared" else "package",
        "aeco:layer:package": package,
        "aeco:layer:producer": "usdaeco-datacentre generator 0.5.0",
        "aeco:layer:source": source.name,
        "aeco:layer:sourceSha256": digest(source),
        "aeco:layer:tag": "v0.5.2",
    }


def convert_package(source, target):
    """Frozen authoring plus a spatial-ownership repair; retain catalog classes.

    The frozen overlay mode suppresses types and DefinePrim promotes spatial
    ancestors again. Convert normally, then clear spatial opinions and demote
    ancestors after both authoring passes. The frozen runtime stays untouched.
    """
    import ifcopenshell
    from . import ids, spec
    from .tessellation import extract_geometry
    model = ifcopenshell.open(source)
    available = {e.GlobalId for e in model.by_type("IfcElement")}
    policies = {k: v for k, v in spec.load(variant="full").publication["tessellation"].items()
                if ids.guid(k) in available}
    geo = extract_geometry(model, policies)
    from usdaeco_ifc.convert.author import author
    stats = author(model, geo, str(target))
    from pxr import Sdf
    package = source.stem
    sem = Sdf.Layer.FindOrOpen(str(target.with_suffix(".semantics.usda")))
    geometry = Sdf.Layer.FindOrOpen(str(target.with_suffix(".geometry.usdc")))
    root = Sdf.Layer.FindOrOpen(str(target))
    if package != "shared":
        for prim in layer_specs(sem):
            if prim.typeName in SPATIAL or str(prim.path) == "/" + root.defaultPrim:
                for prop in list(prim.properties.values()):
                    prim.RemoveProperty(prop)
                for key in prim.ListInfoKeys():
                    if key not in {"specifier", "primChildren", "propertyChildren"}:
                        prim.ClearInfo(key)
                prim.specifier = Sdf.SpecifierOver
        for prim in layer_specs(geometry):
            role = prim.attributes.get("aeco:derived:role")
            if role and role.default == "extent":
                del prim.nameParent.nameChildren[prim.name]
    # Defining a Mesh can promote all its ancestors, including foreign spaces.
    for prim in layer_specs(geometry):
        if prim.typeName != "Mesh":
            prim.specifier = Sdf.SpecifierOver
    for layer in (root, sem, geometry):
        stamp(layer, package, source)
        layer.Save()
    return stats


def run_conversion(source, target, *, monolithic=False, paths_only=False):
    converter, _ = dependency_source("ifc")
    core, _ = dependency_source("core")
    env = clean_environment()
    env["AECO_CORE_ROOT"] = str(core)
    env["PXR_PLUGINPATH_NAME"] = str(core / "plugins/usdAeco/resources")
    call = ("from dcbuild.publish import convert_worker; convert_worker(a,b,'full')" if monolithic else
            "from dcbuild.federation import convert_package; convert_package(a,b)")
    if paths_only:
        # Use the frozen author's naming rules without tessellating any bodies.
        call = ("import ifcopenshell; from usdaeco_ifc.convert.author import author; "
                "author(ifcopenshell.open(a),{},str(b))")
    code = ("import sys; sys.path[:0]=sys.argv[1:4]; del sys.argv[1:4]; "
            "from pathlib import Path; a,b=map(Path,sys.argv[1:3]); " + call)
    subprocess.run([sys.executable, "-c", code, str(converter / "tools"), str(core / "tools"),
                    str(ROOT / "src"), str(source), str(target)], env=env, check=True)


def roots(folder):
    from pxr import Sdf
    template = Sdf.Layer.FindOrOpen(str(ROOT / "dist/base/dc.usda"))
    for connected in (False, True):
        root = Sdf.Layer.CreateAnonymous("root.usda")
        for key in ("defaultPrim", "fallbackPrimTypes", "metersPerUnit", "upAxis"):
            root.pseudoRoot.SetInfo(key, template.pseudoRoot.GetInfo(key))
        root.subLayerPaths = ([p + ".ifc:SDF_FORMAT_ARGS:spine=over" for p in DELIVERY_ORDER] + ["shared.ifc"]
                              if connected else [p + ".usda" for p in PACKAGES])
        # Serialization does not open IFC layers; connected composition is not proven.
        root.Export(str(folder / ("dc.connected.usda" if connected else "dc.usda")))


def identity_paths(stage):
    return {p.GetAttribute("aeco:id").Get(): str(p.GetPath()) for p in stage.Traverse()
            if p.GetAttribute("aeco:id").Get()}


def enrich_external_links(folder, paths):
    """Finish delivered IFC bytes before they become twin conversion inputs."""
    import ifcopenshell
    import ifcopenshell.guid
    for package in PACKAGES:
        path = folder / (package + ".ifc")
        model = ifcopenshell.open(path)
        for doc in model.by_type("IfcDocumentReference"):
            if doc.Name == "aeco:connectedPorts":
                target_id = str(uuid.UUID(hex=ifcopenshell.guid.expand(doc.Identification)))
                doc.Description = paths[target_id]
        model.write(str(path))


def restore_external_links(folder):
    """Read final IFC descriptions into the twins; the frozen converter omits them."""
    import ifcopenshell
    import ifcopenshell.guid
    from pxr import Sdf, Usd
    stage = Usd.Stage.Open(str(folder / "dc.usda"))
    paths = identity_paths(stage)
    for package in PACKAGES:
        model = ifcopenshell.open(folder / (package + ".ifc"))
        layer = Sdf.Layer.FindOrOpen(str(folder / (package + ".semantics.usda")))
        with Usd.EditContext(stage, layer):
            for rel in model.by_type("IfcRelAssociatesDocument"):
                doc = rel.RelatingDocument
                if not doc.is_a("IfcDocumentReference") or doc.Name != "aeco:connectedPorts":
                    continue
                for source in rel.RelatedObjects:
                    source_id = str(uuid.UUID(hex=ifcopenshell.guid.expand(source.GlobalId)))
                    stage.GetPrimAtPath(paths[source_id]).CreateRelationship(doc.Name).AddTarget(doc.Description)
        layer.Save()


def ownership(stage):
    """Path to defining package, using the semantic layer rather than hierarchy labels."""
    result = {}
    for prim in stage.TraverseAll():
        for spec in prim.GetPrimStack():
            package = spec.layer.customLayerData.get("aeco:layer:package")
            if package and spec.specifier.name in {"SpecifierDef", "SpecifierClass"}:
                result[str(prim.GetPath())] = package
                break
    return result


def cross_package_links(stage):
    owners = ownership(stage)
    rows = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        for rel in prim.GetRelationships():
            if rel.GetName() not in LINKS:
                continue
            for target in rel.GetTargets():
                target_path = str(target.GetPrimPath())
                if path in owners and target_path in owners and owners[path] != owners[target_path]:
                    rows.append(dict(source=path, relationship=rel.GetName(), target=str(target),
                                     package=owners[path], targetPackage=owners[target_path]))
    return sorted(rows, key=lambda r: (r["source"], r["relationship"], r["target"]))


def package_counts(folder, package):
    from pxr import Sdf
    sem = Sdf.Layer.FindOrOpen(str(folder / (package + ".semantics.usda")))
    geo = Sdf.Layer.FindOrOpen(str(folder / (package + ".geometry.usdc")))
    counts = dict.fromkeys(("spatial", "elements", "types", "systems", "zones", "ports", "meshes"), 0)
    for prim in layer_specs(sem):
        counts["spatial"] += prim.typeName in SPATIAL and prim.specifier == Sdf.SpecifierDef
        apis = prim.GetInfo("apiSchemas")
        apis = apis.GetAppliedItems() if apis else []
        counts["elements"] += "AecoElementAPI" in apis
        counts["types"] += prim.specifier == Sdf.SpecifierClass and "AecoTypeAPI" in apis
        counts["systems"] += prim.typeName == "AecoSystem"
        counts["zones"] += prim.typeName == "AecoZone"
        counts["ports"] += prim.typeName == "AecoPort"
    counts["meshes"] = sum(p.typeName == "Mesh" for p in layer_specs(geo))
    return counts


def inventory(folder):
    return {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)}
            for p in sorted(folder.iterdir()) if p.is_file() and p.name != "dc.manifest.json"}


def refresh_inventory(folder):
    path = folder / "dc.manifest.json"
    data = json.loads(path.read_text())
    data["files"] = inventory(folder)
    write_json(path, data)


def typical_architecture(stage, expected):
    """Compare the architectural prototype, excluding the L01-only fitout fixtures."""
    from .qa.typical import verify
    muted = [str(Path(stage.GetRootLayer().realPath).parent / (p + ".usda"))
             for p in DELIVERY_ORDER if p != "arch"]
    try:
        stage.MuteAndUnmuteLayers(muted, [])
        return {**verify(stage, expected), "scope": "arch over shared"}
    finally:
        stage.MuteAndUnmuteLayers([], muted)


def publish(output):
    from . import layout, spec
    from .ifc.build import build
    from .publish import plugin_free_census
    plan = layout.resolve(spec.load(variant="full"))
    scratch = ROOT / "out"
    scratch.mkdir(exist_ok=True)
    destination = Path(output) / "full"
    with tempfile.TemporaryDirectory(prefix="federation-", dir=scratch) as tmp:
        work = Path(tmp)
        build(plan, work)
        print("== stage: resolve delivery reference paths and enrich IFC", flush=True)
        with tempfile.TemporaryDirectory(prefix="reference-paths-", dir=work) as reference_tmp:
            target = Path(reference_tmp) / "dc.usda"
            run_conversion(work / "demo-datacentre-01.ifc", target, paths_only=True)
            from pxr import Usd
            enrich_external_links(work, identity_paths(Usd.Stage.Open(str(target))))
        for package in PACKAGES:
            print(f"== stage: convert delivery {package}", flush=True)
            run_conversion(work / (package + ".ifc"), work / (package + ".usda"))
        roots(work)
        restore_external_links(work)
        from pxr import Plug, Sdf, Usd
        core, _ = dependency_source("core")
        Plug.Registry().RegisterPlugins(str(core / "plugins/usdAeco/resources"))
        from .qa.clash import body, measure_cases
        stage = Usd.Stage.Open(str(work / "dc.usda"))
        geo = Sdf.Layer.FindOrOpen(str(work / "cooling.geometry.usdc"))
        stage.SetEditTarget(geo)
        config = spec.load(variant="full")
        def body_layer(prim):
            return next(s.layer for s in prim.GetPrimStack() if s.typeName == "Mesh")
        cases = measure_cases(stage, config.expected["clash"], config.publication["tessellation"],
                             stamp=True, stamp_layer=body_layer)
        controlled = []
        for row in cases:
            if row["id"] in config.publication["tessellation"]:
                mesh, _, _ = body(stage, row["id"])
                mesh.GetPrim().GetAttribute("aeco:derived:stamp").Set(
                    "dcbuild circular-sweep tessellation " + json.dumps(row["tessellation"], sort_keys=True))
                mesh.CreateSubdivisionSchemeAttr().Set("none")
                controlled.append(dict(path=str(mesh.GetPrim().GetPath()),
                                       delivery=body_layer(mesh.GetPrim()).customLayerData["aeco:layer:package"],
                                       twinPointCount=len(mesh.GetPointsAttr().Get()),
                                       reason="IFC retains the swept solid; the twin uses controlled facets. "
                                              "Independent IFC readers may produce different tessellation."))
        for package in PACKAGES:
            Sdf.Layer.FindOrOpen(str(work / (package + ".geometry.usdc"))).Save()
        census = plugin_free_census(work / "dc.usda")
        from .qa.variants import manifest
        metadata = dict(variant="full", facility="demo-datacentre-01", generator={"version": "0.5.2"},
                        tessellationControlled=controlled,
                        counts=census["counts"], deliveryOrder=list(PACKAGES),
                        packages={p: package_counts(work, p) for p in PACKAGES},
                        fixturePackages={"L02": ["arch", "shared"], "pods": ["fitout"], "ceilings": ["fitout"],
                                         "fixProducts": ["fitout"], "clashPipes": ["cooling"], "readers": ["security"]},
                        crossPackageLinks=cross_package_links(stage),
                        census=manifest(plan)["counts"], typical=typical_architecture(stage, config.expected["drift"]),
                        clash=dict(units="metres", expected=config.expected["clash"], cases=cases),
                        connectedComposition="not proven; requires usdIfc from usdaeco-ifc >= 0.3",
                        converterPostPass="spatial overs, retained catalog classes, shared-only extents, external port references",
                        inventoryExcludes={"dc.manifest.json": "A manifest cannot hash its own bytes; render receipts bind it externally."},
                        sizeCapBytes=FULL_CAP)
        for name in ("ifc", "core"):
            pin = dependency_source(name)[1]
            metadata["converter" if name == "ifc" else name] = {k: pin[k] for k in ("repo", "version", "ref", "revision")}
        metadata["layers"] = {name: {"bytes": (work / name).stat().st_size, "sha256": digest(work / name)} for name in LAYERS}
        # Preserve existing images when republishing; fresh rendering updates them explicitly.
        for name in ("overview.png", "vanilla.png"):
            if (destination / name).exists():
                shutil.copyfile(destination / name, work / name)
        (work / "demo-datacentre-01.ifc").unlink()
        metadata["files"] = inventory(work)
        write_json(work / "dc.manifest.json", metadata)
        total = sum(p.stat().st_size for p in work.iterdir() if p.is_file())
        if total > FULL_CAP:
            raise ValueError(f"full exceeds {FULL_CAP} bytes: {total}")
        destination.mkdir(parents=True, exist_ok=True)
        for path in work.iterdir():
            shutil.copyfile(path, destination / path.name)
        print(f"published full: {total} bytes; {json.dumps(census['counts'], sort_keys=True)}", flush=True)
        return metadata
