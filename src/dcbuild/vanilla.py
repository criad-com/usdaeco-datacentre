"""S28 publication and freshness checks for the data repository's dist layout."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .dependencies import ROOT, clean_environment, dependency_source
from .publish import PUBLISHED, digest, write_json
from .render import SIZE, frame_overview


def source_record(variant):
    """Bind pictures to data, camera code and the exact rendering toolchain."""
    return {
        "publication": {name: digest(ROOT / "dist" / variant / name) for name in PUBLISHED},
        "code": {name: digest(ROOT / name) for name in
                 ("src/dcbuild/vanilla.py", "src/dcbuild/render.py")},
        "toolchain": dependency_source("toolchain")[1],
    }


def prepare_worker(variant, output):
    """Flatten in a plugin-free process; keep presentation in a separate layer."""
    from pxr import Plug, Usd
    from usdaeco_check.example_result import normalized_layer
    if any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins()):
        raise ValueError("VanillaPluginLoaded: family plugin discovered")
    stage = Usd.Stage.Open(str(ROOT / "dist" / variant / "dc.usda"))
    if not stage or stage.GetCompositionErrors():
        raise ValueError("VanillaCompositionFailed: source does not compose")
    crate = output / "example.usdc"
    if not stage.Flatten(addSourceFileComment=False).Export(str(crate)):
        raise ValueError("VanillaFlattenFailed: could not export the composed publication")
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        frame = frame_overview(stage)
    # S28 renders default, proxy and render geometry; guides stay hidden.
    frame["purposes"] = "proxy,render"
    stage.GetSessionLayer().Export(str(output / "cameras.usda"))
    import hashlib
    write_json(output / "prepared.json", {
        "frame": frame,
        "normalized_sha256": hashlib.sha256(normalized_layer(crate)).hexdigest(),
        "camera_sha256": digest(output / "cameras.usda"),
    })


def prepare(variant, output):
    kit, _ = dependency_source("toolchain")
    output.mkdir(parents=True, exist_ok=True)
    code = ("import sys; sys.path[:0]=sys.argv[1:3]; del sys.argv[1:3]; "
            "from dcbuild.vanilla import prepare_worker; from pathlib import Path; "
            "prepare_worker(sys.argv[1],Path(sys.argv[2]))")
    subprocess.run([sys.executable, "-I", "-c", code, str(kit / "tools"), str(ROOT / "src"),
                    variant, str(output.resolve())], env=clean_environment(), check=True, timeout=90)
    return json.loads((output / "prepared.json").read_text())


def render_prepared(output):
    from usdaeco_check.example_result import render_vanilla
    from usdaeco_check.images import image_info
    target = output / "vanilla.png"
    render_vanilla(output / "example.usdc", output / "cameras.usda", target, SIZE)
    return image_info(target)


def publish_variant(variant, *, publish=False):
    output = ROOT / "out" / "vanilla" / variant
    prepared = prepare(variant, output)
    print(f"== stage: S28 vanilla render {variant}", flush=True)
    info = render_prepared(output)
    record = {"path": f"dist/{variant}/vanilla.png", **info, **prepared,
              "sources": source_record(variant), "renderer": "usdrecord/Embree",
              "camera": f"manifests/cameras/{variant}.usda"}
    write_json(output / "receipt.json", record)
    if publish:
        shutil.copyfile(output / "vanilla.png", ROOT / record["path"])
        camera = ROOT / record["camera"]
        camera.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / "cameras.usda", camera)
        path = ROOT / "manifests/vanilla.json"
        records = json.loads(path.read_text()) if path.exists() else {}
        records[variant] = record
        write_json(path, records)
    print(f"{variant}: {info['width']}x{info['height']}, {info['bytes']} bytes", flush=True)
    return record


def check_example(variant):
    """Data-layout equivalent of S27 freshness plus the shared S28 render proof."""
    from usdaeco_check.images import image_info
    record = json.loads((ROOT / "manifests/vanilla.json").read_text())[variant]
    if record["sources"] != source_record(variant):
        raise ValueError("VanillaSourceStale: data, camera code or toolchain changed; run with --publish")
    image = ROOT / "dist" / variant / "vanilla.png"
    info = image_info(image)
    if record["path"] != image.relative_to(ROOT).as_posix() or any(record[k] != v for k, v in info.items()):
        raise ValueError("VanillaManifestMismatch: image hash or size changed")
    if (info["width"], info["height"]) != SIZE:
        raise ValueError("VanillaManifestMismatch: image dimensions changed")
    camera = ROOT / "manifests" / "cameras" / (variant + ".usda")
    if record["camera"] != camera.relative_to(ROOT).as_posix() or digest(camera) != record["camera_sha256"]:
        raise ValueError("VanillaCameraStale: committed camera changed")
    with tempfile.TemporaryDirectory(prefix="vanilla-check-") as temporary:
        output = Path(temporary)
        prepared = prepare(variant, output)
        if any(record[k] != v for k, v in prepared.items()) or camera.read_bytes() != (output / "cameras.usda").read_bytes():
            raise ValueError("VanillaResultStale: fresh stage or camera differs")
        fresh = render_prepared(output)
    return {"committed": info, "fresh": fresh, "source_fresh": True,
            "all_corners_inside": prepared["frame"]["all_corners_inside"],
            "purposes": "proxy,render"}


def main():
    from .spec import variants
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--variant", choices=variants())
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--publish", action="store_true", help="commit-ready images, cameras and receipts")
    args = parser.parse_args()
    kit, _ = dependency_source("toolchain")
    sys.path.insert(0, str(kit / "tools"))
    for variant in variants() if args.all else [args.variant or "base"]:
        publish_variant(variant, publish=args.publish)


if __name__ == "__main__":
    main()
