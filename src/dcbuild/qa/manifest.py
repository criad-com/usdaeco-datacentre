"""A compact pinned semantic/identity census of the complete resolved plan."""
from collections import Counter
import dataclasses
import hashlib
import json

from ..ids import guid


def manifest(plan):
    payload = dataclasses.asdict(plan)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    identities = sorted((kind, item["id"], guid(item["id"]))
                        for kind in ("storeys", "spaces", "walls", "doors", "columns", "slabs",
                                     "equipment", "racks", "runs", "routes", "systems", "cameras")
                        for item in payload[kind])
    return {"facility": plan.meta["code"], "version": "0.1.0",
            "plan_sha256": hashlib.sha256(encoded).hexdigest(),
            "identity_sha256": hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest(),
            "identities": len(identities),
            "counts": {name: len(payload[name]) for name in
                       ("spaces", "walls", "doors", "columns", "racks", "equipment", "cameras", "systems")},
            "camera_groups": dict(sorted(Counter(c.id.split(".")[2] for c in plan.cameras).items())),
            "heads": len(plan.cameras), "camera_types": len(plan.security["camera_types"]),
            "presets": sum(len(c.presets) for c in plan.cameras),
            "tours": sum(bool(c.tour) for c in plan.cameras),
            "camera_ids": {c.id: c.global_id for c in sorted(plan.cameras, key=lambda c: c.id)}}
