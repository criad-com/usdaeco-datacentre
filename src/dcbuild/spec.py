"""Validated base specifications and deterministic, inheritable YAML overlays."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

import yaml

from .model import Spec

SPEC_FILES = ("facility", "spaces", "power", "cooling", "it", "security")


def spec_dir(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        d = candidate / "spec"
        if (d / "facility.yaml").exists():
            return d
    raise FileNotFoundError("spec/facility.yaml not found — run from within the repo")


def merge(base, overlay):
    """Copy-on-merge: mappings recurse; record lists join by id in base order.

    Scalar lists replace. Duplicate record ids are rejected, including ids in
    the base, so an overlay never silently resolves an ambiguous identity.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = deepcopy(base)
        for key, value in overlay.items():
            result[key] = merge(result[key], value) if key in result else deepcopy(value)
        return result
    if isinstance(base, list) and isinstance(overlay, list):
        if base + overlay and all(isinstance(x, dict) and "id" in x for x in base + overlay):
            for records in (base, overlay):
                if len({x["id"] for x in records}) != len(records):
                    raise ValueError("duplicate id in overlay record list")
            result = deepcopy(base)
            positions = {x["id"]: i for i, x in enumerate(result)}
            for item in overlay:
                if item["id"] in positions:
                    i = positions[item["id"]]
                    result[i] = merge(result[i], item)
                else:
                    positions[item["id"]] = len(result)
                    result.append(deepcopy(item))
            return result
    return deepcopy(overlay)


def variants(directory: Path | None = None) -> list[str]:
    return ["base", *sorted(p.stem for p in ((directory or spec_dir()) / "variants").glob("*.yaml")
                            if p.stem != "base")]


def load(directory: Path | None = None, variant: str = "base") -> Spec:
    d = directory or spec_dir()
    parts = {stem: yaml.safe_load((d / f"{stem}.yaml").read_text()) for stem in SPEC_FILES}

    def overlay(name, stack=()):
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            raise ValueError(f"invalid variant name: {name!r}")
        if name in stack:
            raise ValueError("variant inheritance cycle: " + " -> ".join((*stack, name)))
        if name == "base":
            return {}
        path = d / "variants" / f"{name}.yaml"
        if not path.is_file():
            raise ValueError(f"unknown variant: {name}")
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"variant {name} must be a mapping")
        parent = data.pop("extends", "base")
        return merge(overlay(parent, (*stack, name)), data)

    parts = merge(parts, overlay(variant))
    # Repeated rooms and doors come from the prototype, so its unedited
    # partitions cannot drift through a second hand-maintained room schedule.
    for storey in parts["facility"]["storeys"]:
        prototype = storey.get("typical_of")
        if not prototype:
            continue
        suffix = "." + storey["id"].rsplit("l", 1)[-1]
        rooms = [s for s in parts["spaces"]["spaces"] if s["storey"] == prototype]
        if not rooms:
            raise ValueError("typical prototype must precede its instance")
        mapping = {s["id"]: s["id"] + suffix for s in rooms}
        doors = [d for d in parts["spaces"]["doors"] if set(d["between"]) <= mapping.keys()]
        copies = [dict(deepcopy(s), id=mapping[s["id"]], storey=storey["id"]) for s in rooms]
        door_copies = [dict(deepcopy(d), id=d["id"] + suffix,
                            between=[mapping[s] for s in d["between"]]) for d in doors]
        parts["spaces"]["spaces"].extend(copies)
        parts["spaces"]["doors"].extend(door_copies)
    for name in ("fitout", "programme"):
        config = parts.get(name)
        if config and config.pop("enabled", False):
            parts[name] = merge(yaml.safe_load((d / f"{name}.yaml").read_text()), config)
    parts["variant"] = variant
    return Spec.model_validate(parts)
