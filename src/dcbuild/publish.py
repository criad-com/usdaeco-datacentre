"""Publish portable, deterministic core stages from the combined generated IFC."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from . import layout, spec
from .dependencies import ROOT, clean_environment, dependency_source

LAYERS = ("dc.usda", "dc.semantics.usdc", "dc.geometry.usdc")
PUBLISHED = (*LAYERS, "dc.manifest.json")
SIZE_CAP = 10_000_000
# Unchanged variants retain their original data provenance.
DATA_VERSION = "0.4.2"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def convert_worker(source, target, variant="base"):
    # The pinned converter intentionally tessellates before importing pxr.
    from usdaeco_ifc.convert import convert
    config = spec.load(variant=variant)
    if config.publication:
        import ifcopenshell
        from .tessellation import extract_geometry
        model = ifcopenshell.open(source)
        geo = extract_geometry(model, config.publication["tessellation"])
        from usdaeco_ifc.convert.author import author
        stats = author(model, geo, str(target))
        from pxr import Sdf, Usd
        from .qa.clash import body, measure_cases
        stage = Usd.Stage.Open(str(target))
        layer = Sdf.Layer.FindOrOpen(str(target.with_name("dc.geometry.usdc")))
        stage.SetEditTarget(layer)
        cases = measure_cases(stage, config.expected["clash"], config.publication["tessellation"], stamp=True)
        for row in cases:
            mesh, _, _ = body(stage, row["id"])
            if row["id"] in config.publication["tessellation"]:
                mesh.GetPrim().GetAttribute("aeco:derived:stamp").Set(
                    "dcbuild circular-sweep tessellation " + json.dumps(row["tessellation"], sort_keys=True))
                mesh.CreateSubdivisionSchemeAttr().Set("none")
        layer.Save()
        write_json(target.with_name("clash.json"), dict(units="metres", expected=config.expected["clash"], cases=cases))
    else:
        stats = convert(str(source), str(target), threads=1)
    from pxr import Sdf
    semantics = target.with_name("dc.semantics.usda")
    layer = Sdf.Layer.FindOrOpen(str(semantics))
    if not layer.Export(str(target.with_name("dc.semantics.usdc"))):
        raise RuntimeError("Could not export binary semantic layer")
    root = Sdf.Layer.FindOrOpen(str(target))
    root.subLayerPaths = ["dc.semantics.usdc", "dc.geometry.usdc"]
    root.Save()
    semantics.unlink()
    write_json(target.with_name("conversion.json"), {k: v for k, v in stats.items() if k != "out"})


def stage_census(path):
    """Inspect authored APIs and fallback resolution without family plugins."""
    from pxr import Plug, Usd, UsdGeom
    if any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins()):
        raise ValueError("Plugin-free probe discovered a family plugin")
    stage = Usd.Stage.Open(str(path))
    if not stage or stage.GetCompositionErrors() or not stage.GetDefaultPrim():
        raise ValueError("Published stage does not compose with a default prim")
    root = stage.GetRootLayer()
    if root.subLayerPaths != ["dc.semantics.usdc", "dc.geometry.usdc"]:
        raise ValueError("Published stage must have exactly two portable sublayers")
    if not (stage.HasAuthoredMetadata("metersPerUnit") and UsdGeom.GetStageMetersPerUnit(stage) == 1
            and stage.HasAuthoredMetadata("upAxis") and UsdGeom.GetStageUpAxis(stage) == "Z"):
        raise ValueError("Published stage must explicitly declare metres and Z up")
    fallbacks = dict(stage.GetMetadata("fallbackPrimTypes") or {})
    spatial = {"AecoSite", "AecoFacility", "AecoFacilityPart", "AecoLevel", "AecoSpace"}
    counts = dict.fromkeys(("elements", "spaces", "levels", "ports", "meshes", "unparented", "unclassified"), 0)
    used = set()
    for prim in stage.Traverse():
        name = prim.GetTypeName()
        if name.startswith("Aeco"):
            used.add(name)
            expected = UsdGeom.Scope if name in {"AecoSystem", "AecoZone"} else UsdGeom.Xform
            if not fallbacks.get(name) or not prim.IsA(expected):
                raise ValueError(f"Incomplete stock fallback for {name}")
        counts["spaces"] += name == "AecoSpace"
        counts["levels"] += name == "AecoLevel"
        counts["ports"] += name == "AecoPort"
        counts["meshes"] += prim.IsA(UsdGeom.Mesh)
        # GetAppliedSchemas filters unknown APIs; inspect the authored list op.
        apis = prim.GetMetadata("apiSchemas")
        if apis and "AecoElementAPI" in apis.GetAppliedItems():
            counts["elements"] += 1
            parent = prim.GetParent()
            while parent and parent.GetTypeName() not in spatial:
                parent = parent.GetParent()
            counts["unparented"] += not bool(parent)
            code = prim.GetAttribute("aeco:class:ifc:code").Get() or ""
            counts["unclassified"] += not code or code.split(".")[0] == "IfcBuildingElementProxy"
    return {"counts": counts, "fallback_types": sorted(used)}


def plugin_free_census(path):
    code = ("import sys; sys.path.insert(0,sys.argv.pop(1)); "
            "from dcbuild.publish import stage_census; import json; "
            "print(json.dumps(stage_census(sys.argv[1])))")
    result = subprocess.run([sys.executable, "-c", code, str(ROOT / "src"), str(path.resolve())],
                            env=clean_environment(), capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def verify_publication(folder):
    """Verify bytes, formats, counts and vanilla composition of a publication."""
    folder = Path(folder)
    data = json.loads((folder / "dc.manifest.json").read_text())
    if set(data["layers"]) != set(LAYERS):
        raise ValueError("Publication must contain three declared layers")
    for name in LAYERS:
        path = folder / name
        if data["layers"][name] != {"bytes": path.stat().st_size, "sha256": digest(path)}:
            raise ValueError(f"Published {name} differs from its manifest")
        if name.endswith(".usdc") and path.read_bytes()[:8] != b"PXR-USDC":
            raise ValueError(f"Published {name} is not a USDC crate")
    if sum(p.stat().st_size for p in folder.iterdir() if p.is_file()) > SIZE_CAP:
        raise ValueError("Publication exceeds the size cap")
    probe = plugin_free_census(folder / "dc.usda")
    if probe["counts"] != data["counts"]:
        raise ValueError("Published counts differ from the stage")
    return probe


def publish(variant, output=Path("dist")):
    converter, converter_pin = dependency_source("ifc")
    core, core_pin = dependency_source("core")
    plugin = core / "plugins/usdAeco/resources"
    if not (plugin / "plugInfo.json").is_file():
        raise ValueError("The pinned core needs its built resource plugin")
    plan = layout.resolve(spec.load(variant=variant))
    from .ifc.build import DISCIPLINES, build
    disciplines = [k for k in DISCIPLINES if k != "fitout" or plan.meta.get("fitout")]
    scratch = Path("out").resolve()
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"publish-{variant}-", dir=scratch) as temporary:
        work = Path(temporary)
        print(f"== stage: publish {variant} combined IFC", flush=True)
        source = build(plan, work / "ifc", disciplines=disciplines)[0]
        target = work / "dc.usda"
        env = clean_environment()
        env["AECO_CORE_ROOT"] = str(core)
        env["PXR_PLUGINPATH_NAME"] = str(plugin)
        code = ("import sys; sys.path[:0]=sys.argv[1:4]; del sys.argv[1:4]; "
                "from dcbuild.publish import convert_worker; from pathlib import Path; "
                "convert_worker(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3])")
        print(f"== stage: publish {variant} pinned converter", flush=True)
        subprocess.run([sys.executable, "-c", code, str(converter / "tools"), str(core / "tools"),
                        str(ROOT / "src"), str(source), str(target), variant], env=env, check=True)
        census = plugin_free_census(target)
        stats = json.loads((work / "conversion.json").read_text())
        for name in ("elements", "ports", "meshes", "unparented", "unclassified"):
            if stats[name] != census["counts"][name]:
                raise ValueError(f"Plugin-free {name} differs from converter census")
        if census["counts"]["spaces"] != len(plan.spaces) or census["counts"]["levels"] != len(plan.storeys):
            raise ValueError("Published spatial census differs from the resolved plan")
        metadata = {"variant": variant, "facility": "demo-datacentre-01",
                    "generator": {"version": {"clash": "0.4.4", "floors": "0.4.5"}.get(variant, DATA_VERSION)},
                    "converter": {k: converter_pin[k] for k in ("repo", "version", "ref", "revision")},
                    "core": {k: core_pin[k] for k in ("repo", "version", "ref", "revision")},
                    "counts": census["counts"],
                    "layers": {name: {"bytes": (work / name).stat().st_size, "sha256": digest(work / name)}
                               for name in LAYERS}}
        if variant == "clash":
            metadata["clash"] = json.loads((work / "clash.json").read_text())
        if variant == "floors":
            from pxr import Usd
            from .qa.typical import verify
            metadata["typical"] = verify(Usd.Stage.Open(str(target)), plan.meta["expected"]["drift"])
        write_json(work / "dc.manifest.json", metadata)
        total = sum((work / name).stat().st_size for name in PUBLISHED)
        destination = Path(output) / variant
        preview = destination / "overview.png"
        if total + (preview.stat().st_size if preview.exists() else 0) > SIZE_CAP:
            raise ValueError(f"{variant} exceeds the {SIZE_CAP}-byte publication cap; no files published")
        destination.mkdir(parents=True, exist_ok=True)
        for name in PUBLISHED:
            shutil.copyfile(work / name, destination / name)
        print(f"published {variant}: {total} bytes; {json.dumps(census['counts'], sort_keys=True)}", flush=True)
        return metadata
