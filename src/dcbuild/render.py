"""Facility-bound overview cameras and measured renders of published stages."""
from itertools import product
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .dependencies import ROOT, clean_environment, dependency_source
from .publish import LAYERS, SIZE_CAP, digest, write_json

SIZE = (1280, 800)
PURPOSES = "guide,proxy,render"


def frame_overview(stage):
    """Hide only space extents and fit all physical facility geometry."""
    from pxr import Gf, Usd, UsdGeom
    hidden = []
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Gprim) and prim.GetAttribute("aeco:derived:role").Get() == "extent":
            UsdGeom.Imageable(prim).CreateVisibilityAttr().Set("invisible")
            hidden.append(str(prim.GetPath()))
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "guide", "proxy", "render"])
    bounds = Gf.Range3d()
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Gprim) and UsdGeom.Imageable(prim).ComputeVisibility() != "invisible":
            bounds.UnionWith(cache.ComputeWorldBound(prim).ComputeAlignedRange())
    if bounds.IsEmpty() or bounds.GetSize().GetLength() == 0:
        raise ValueError("Facility has no visible geometry bounds")
    camera = UsdGeom.Camera.Define(stage, "/Renders/overview")
    value = camera.GetCamera()
    value.verticalAperture = value.horizontalAperture * SIZE[1] / SIZE[0]
    center = bounds.GetMidpoint()
    back = Gf.Vec3d(1, -1.6, 1.2).GetNormalized()
    up = Gf.Vec3d(0, 0, 1)
    view = Gf.Matrix4d().SetLookAt(center + back, center, up)
    corners = [Gf.Vec3d(*p) for p in product(*zip(bounds.GetMin(), bounds.GetMax()))]
    local = [view.TransformDir(p - center) for p in corners]
    tan_x = value.horizontalAperture / (2 * value.focalLength)
    tan_y = value.verticalAperture / (2 * value.focalLength)
    distance = max(p[2] + 1.15 * max(abs(p[0]) / tan_x, abs(p[1]) / tan_y) for p in local)
    eye = center + back * distance
    value.transform = Gf.Matrix4d().SetLookAt(eye, center, up).GetInverse()
    depths = [distance - p[2] for p in local]
    value.clippingRange = Gf.Range1f(min(depths) * .5, max(depths) * 1.5)
    camera.SetFromCamera(value)
    projection = value.frustum.ComputeViewMatrix() * value.frustum.ComputeProjectionMatrix()
    inside = all(all(-1 <= v <= 1 for v in projection.Transform(p)) for p in corners)
    if not inside:
        raise ValueError("Facility bounds do not fit the overview frustum")
    return {"bounds": [list(bounds.GetMin()), list(bounds.GetMax())], "position": list(eye),
            "direction": list(value.frustum.ComputeViewDirection()), "all_corners_inside": inside,
            "hidden_space_extents": len(hidden), "purposes": PURPOSES, "size": list(SIZE)}


def render_worker(variant, output):
    from pxr import Sdf, Usd
    from usdaeco_render import render
    from usdaeco_check.images import image_info
    publication = Path.cwd() / "dist" / variant
    source = publication / "dc.usda"
    recorder = os.environ.get("USDRECORD") or shutil.which("usdrecord")
    if not recorder:
        raise ValueError("Set USDRECORD or put usdrecord on PATH")
    scratch = Path("out").resolve()
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="overview-", dir=scratch) as temporary:
        temporary = Path(temporary)
        # Presentation edits stay in this scratch root; published data is read-only.
        layer = Sdf.Layer.CreateNew(str(temporary / "display.usda"))
        layer.subLayerPaths = [str(source)]
        original = Sdf.Layer.FindOrOpen(str(source))
        layer.defaultPrim = original.defaultPrim
        layer.pseudoRoot.SetInfo("fallbackPrimTypes", original.pseudoRoot.GetInfo("fallbackPrimTypes"))
        stage = Usd.Stage.Open(layer)
        frame = frame_overview(stage)
        layer.Save()
        render(layer.realPath, output=temporary / "renders", size=SIZE, views=["overview"],
               purposes=PURPOSES, executable=recorder)
        image = temporary / "renders/overview.png"
        record = {"path": f"dist/{variant}/overview.png", **image_info(image), "frame": frame,
                  "source_layers": {name: digest(publication / name) for name in LAYERS},
                  "renderer": "usdrecord/Embree", "toolchain": dependency_source("toolchain")[1]["ref"]}
        total = sum(p.stat().st_size for p in publication.iterdir() if p.is_file() and p.name != "overview.png")
        if total + record["bytes"] > SIZE_CAP:
            raise ValueError("Overview would exceed the variant publication cap")
        shutil.copyfile(image, publication / "overview.png")
        write_json(output, record)
        print(f"rendered {variant}: {record['width']}x{record['height']}, {record['bytes']} bytes", flush=True)


def render_variant(variant):
    kit, _ = dependency_source("toolchain")
    env = clean_environment()
    code = ("import sys; sys.path[:0]=sys.argv[1:3]; del sys.argv[1:3]; "
            "from dcbuild.render import render_worker; from pathlib import Path; "
            "render_worker(sys.argv[1],Path(sys.argv[2]))")
    scratch = Path("out") / "renders"
    scratch.mkdir(parents=True, exist_ok=True)
    receipt = (scratch / (variant + ".json")).resolve()
    subprocess.run([sys.executable, "-c", code, str(kit / "tools"), str(ROOT / "src"), variant,
                    str(receipt)], env=env, check=True)
    record = json.loads(receipt.read_text())
    manifest = Path("manifests/renders.json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(manifest.read_text()) if manifest.exists() else {}
    data[variant] = record
    write_json(manifest, data)
    return record


def verify_render(variant):
    from usdaeco_check.images import image_info
    record = json.loads((ROOT / "manifests/renders.json").read_text())[variant]
    info = image_info(ROOT / record["path"])
    if any(record[key] != value for key, value in info.items()):
        raise ValueError("Overview pixels differ from their receipt")
    hashes = {name: digest(ROOT / "dist" / variant / name) for name in LAYERS}
    if record["source_layers"] != hashes:
        raise ValueError("Overview source layers are stale")
    if record["frame"]["purposes"] != PURPOSES or not record["frame"]["all_corners_inside"]:
        raise ValueError("Overview framing contract differs")
    counts = json.loads((ROOT / "dist" / variant / "dc.manifest.json").read_text())["counts"]
    if record["frame"]["hidden_space_extents"] != counts["spaces"]:
        raise ValueError("Overview must exclude all space extents")
    return info
