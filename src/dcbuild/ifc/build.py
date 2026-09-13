"""IFC build orchestrator.

Authors the demo-datacentre-01 coordination model (everything, full cross-discipline port
graph) plus federated per-discipline files. Because every product GUID derives
from its DC id, the same element carries the same GlobalId in every file —
the federation is join-consistent by construction.

Contract: each discipline module exposes ``build(b: Builder, plan: Plan)`` and
authors ONLY its own elements (plus their ports/systems/psets). Cross-
discipline port connections (e.g. busway drop -> rack) live with the module
that owns the upstream element.
"""
from __future__ import annotations

from pathlib import Path

from .builder import Builder

# discipline key -> (module name, file suffix)
DISCIPLINES: dict[str, str] = {
    "arch": "architecture",
    "structure": "structure",
    "site": "site",
    "electrical": "electrical",
    "cooling": "cooling",
    "it": "it",
    "security": "security",
    "fitout": "fitout",
}


def _modules(names):
    import importlib
    return [(k, importlib.import_module(f".{DISCIPLINES[k]}", __package__)) for k in names]


def build(plan, out_dir: Path, disciplines: list[str] | None = None) -> list[Path]:
    from . import spatial  # always built: the shared skeleton

    names = ([k for k in DISCIPLINES if k != "fitout" or plan.meta.get("fitout")]
             if not disciplines else disciplines)
    written: list[Path] = []

    # Combined coordination model
    b = Builder(plan, discipline="coordination")
    spatial.build(b, plan)
    full = plan.meta.get("variant") == "full"
    if full:
        from .federation import ownership
        owners = ownership(b, _modules(names), plan)
    else:
        for _key, mod in _modules(names):
            mod.build(b, plan)
    written.append(b.write(out_dir / "demo-datacentre-01.ifc"))

    if full and not disciplines:
        from .federation import write_packages
        return written + write_packages(b, owners, out_dir)

    # Federated per-discipline files (same GUIDs, own spatial skeleton)
    if not disciplines:  # only on full builds
        for key, mod in _modules(names):
            fb = Builder(plan, discipline=key)
            spatial.build(fb, plan)
            mod.build(fb, plan)
            written.append(fb.write(out_dir / f"demo-datacentre-01-{key}.ifc"))
    return written
