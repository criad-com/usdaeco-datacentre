"""Deterministic identity.

Every object in the spec / resolved plan has a stable DC id (e.g. ``pwr.msb.a``,
``rack.a.r1.07``). IFC GlobalIds are derived from those ids via UUIDv5 in a fixed
namespace, so rebuilding the model yields byte-identical GUIDs and the Revit and
IFC models can be joined element-for-element. The Revit builder stamps the spec id into Mark and the compressed GUID into
the built-in IFC_GUID parameter.
"""
from __future__ import annotations

import uuid

import ifcopenshell.guid

# Fixed namespace for demo-datacentre-01. Never change this, or every GUID in every rebuilt
# model changes with it.
NAMESPACE = uuid.NAMESPACE_DNS
PREFIX = "usdaeco-datacentre"


def guid(spec_id: str) -> str:
    """IFC GlobalId (22-char base64) deterministically derived from a DC id."""
    return ifcopenshell.guid.compress(uuid.uuid5(NAMESPACE, f"{PREFIX}:{spec_id}").hex)


def sub(spec_id: str, *parts: object) -> str:
    """A child id: ``sub('rack.a.r1', 7) -> 'rack.a.r1.07'`` (ints zero-padded)."""
    tail = [f"{p:02d}" if isinstance(p, int) else str(p) for p in parts]
    return ".".join([spec_id, *tail])
