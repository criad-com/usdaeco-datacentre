"""Resolve read-only family sources and verify the recorded runtime bytes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def runtime_digest(root, paths):
    """Hash tracked runtime files; source archives use the same path inventory.

    Build metadata is never runtime input, including in unpacked source trees.
    The checkout revision is checked separately by dependency_source.
    """
    root = Path(root)
    tracked = None
    if (root / ".git").exists():
        tracked = set(subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "-z", "--", *paths]
        ).decode().split("\0"))
    digest = hashlib.sha256()
    for name in sorted(paths):
        source = root / name
        files = sorted(source.rglob("*")) if source.is_dir() else [source]
        for path in files:
            relative = path.relative_to(root)
            if (not path.is_file() or path.suffix == ".pyc"
                    or any(p in {"__pycache__", ".work"} or p.endswith((".egg-info", ".dist-info"))
                           for p in relative.parts)
                    or tracked is not None and relative.as_posix() not in tracked):
                continue
            digest.update(relative.as_posix().encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def archive_runtime_digest(source, pin):
    """Reproduce a pin from a fresh Git archive, without checkout build debris."""
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", pin["ref"] + "^{commit}"], text=True).strip()
    if revision != pin["revision"]:
        raise ValueError("Runtime archive tag differs from the pinned revision")
    with tempfile.TemporaryDirectory(prefix="runtime-archive-") as temporary:
        root = Path(temporary)
        archive = root / "source.tar"
        subprocess.run(["git", "-C", str(source), "archive", "--format=tar",
                        "--output", str(archive), pin["ref"]], check=True)
        unpacked = root / "source"
        with tarfile.open(archive) as stream:
            stream.extractall(unpacked, filter="data")
        return runtime_digest(unpacked, pin["runtime_paths"])


def dependency_pin(name):
    document = json.loads((ROOT / "dependencies.json").read_text())
    return document["repos"][name] if name in document["repos"] else document["fixtures"][name]


def dependency_source(name):
    pin = dependency_pin(name)
    override = os.environ.get("AECO_" + name.upper() + "_ROOT")
    if name == "toolchain":
        override = override or os.environ.get("AECO_TOOLCHAIN_SOURCE")
    version = pin["version"]
    candidates = [ROOT.parent / (pin["repo"] + "-" + ".".join(version.split(".")[:2])),
                  ROOT.parent / pin["repo"]]
    source = Path(override) if override else next((p for p in candidates if p.is_dir()), candidates[-1])
    source = source.resolve()
    if not source.is_dir():
        raise ValueError(f"Missing {pin['repo']} {pin['ref']}; set AECO_{name.upper()}_ROOT")
    # Also supports immutable source archives (e.g. Nix inputs) without .git.
    if runtime_digest(source, pin["runtime_paths"]) != pin["runtime_sha256"]:
        raise ValueError(f"{pin['repo']} runtime bytes differ from {pin['ref']}")
    if (source / ".git").exists():
        revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if revision != pin["revision"]:
            raise ValueError(f"{pin['repo']} checkout revision differs from {pin['ref']}")
    return source, pin


def clean_environment():
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PXR_PLUGINPATH_NAME", "PXR_AR_DEFAULT_SEARCH_PATH"):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
