"""The resolved build plan.

Everything a builder needs to author the model, with world coordinates,
dimensions and deterministic DC ids — no further design decisions downstream.
Serializes to out/build_plan.json for the Revit builder; the IFC builder
consumes it in-process.

Conventions:
  * metres, site-local; X east, Y north, Z up
  * equipment `pos` is the FOOTPRINT CENTRE at FFL; `size` = (w, d, h) with w
    along local X before `rot` (degrees CCW about Z) is applied
  * runs (busways, trays, manifolds) are straight X-aligned spans with `taps`
    (the x of each served rack); routes are 3D orthogonal waypoint polylines
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StoreyP:
    id: str
    name: str
    elevation: float


@dataclass
class GridLineP:
    id: str
    label: str
    axis: str          # "x" | "y"
    value: float
    start: float       # extent along the other axis
    end: float


@dataclass
class SpaceP:
    id: str
    name: str
    type: str
    storey: str
    x: float
    y: float
    w: float
    d: float
    height: float
    external: bool = False


@dataclass
class OpeningP:
    door_id: str
    at: tuple[float, float]     # centre of opening on the wall line
    width: float
    height: float


@dataclass
class WallP:
    id: str
    storey: str
    kind: str                   # external | fire | internal
    p1: tuple[float, float]
    p2: tuple[float, float]
    height: float
    thickness: float
    left: str | None            # space id on the left of p1->p2 (None = outside)
    right: str | None
    openings: list[OpeningP] = field(default_factory=list)


@dataclass
class DoorP:
    id: str
    name: str
    kind: str                   # single | double | roller
    wall_id: str
    storey: str
    pos: tuple[float, float]
    width: float
    height: float
    external: bool
    approach_space: str = ""
    approach_normal: str = ""
    threshold_height: float = 1.6


@dataclass
class CameraP:
    id: str
    global_id: str
    type: str
    space: str
    pos: tuple[float, float, float]
    pan: float
    tilt: float
    focal_length: float
    range: float
    scenario: str
    mount: str
    targets: list[str]
    roll: float = 0.0
    device_rotation: float = 0.0
    phase: str = "NEW"
    system: str = "sys.sec"
    target_density: float = 0.0
    presets: dict = field(default_factory=dict)
    tour: list[str] = field(default_factory=list)


@dataclass
class ColumnP:
    id: str
    pos: tuple[float, float]
    height: float
    size: float


@dataclass
class SlabP:
    id: str
    kind: str                   # ground | upper | roof | pad
    x: float
    y: float
    w: float
    d: float
    top_elevation: float        # top of slab
    thickness: float
    voids: list[tuple[float, float, float, float]] = field(default_factory=list)  # (x,y,w,d)


@dataclass
class EquipP:
    """Any placed plant/electrical/IT device (racks are separate)."""
    id: str
    cls: str                    # spec class: transformer, cdu, crah, pdu, ...
    name: str
    discipline: str             # power | cooling | it | security
    space: str                  # space id or "EXT"
    pad: str | None
    pos: tuple[float, float, float]
    size: tuple[float, float, float]
    rot: float                  # degrees CCW about Z
    shape: str = "box"          # box | cylinder
    side: str | None = None     # A | B (power)
    loop: str | None = None     # fws | tcs | chw (cooling)
    rating: dict = field(default_factory=dict)


@dataclass
class RackP:
    id: str
    hall: str
    row: str                    # row id, e.g. it.row.a1
    index: int                  # 1-based along the row
    pos: tuple[float, float]    # footprint centre
    size: tuple[float, float, float]
    kw: float
    space: str
    cooling: str                # dlc | air


@dataclass
class RowP:
    id: str
    hall: str
    space: str
    index: int                  # 1-based
    y: float                    # row centreline
    x_start: float              # face of first rack
    x_end: float
    rack_xs: list[float]        # rack centres
    cooling: str


@dataclass
class RunP:
    """A straight X-aligned overhead run with per-rack taps (busway / tray / manifold)."""
    id: str
    kind: str                   # busway | tray | manifold_supply | manifold_return
    row: str
    side: str | None            # A | B for busways
    y: float
    z: float
    x_start: float
    x_end: float
    taps: list[float]           # x of each tap/dropper
    size: tuple[float, float]   # (w, h) rectangular, or (d, d) for pipes
    shape: str = "box"          # box | pipe
    feed: str | None = None     # id of the feeding equipment (pdu / cdu header)


@dataclass
class RouteP:
    """3D orthogonal polyline route (pipes / spine trays / cable runs)."""
    id: str
    kind: str                   # pipe | tray | cable
    system: str                 # fws.supply / chw.return / data.hall.a / pwr.a ...
    waypoints: list[tuple[float, float, float]]
    diameter: float | None = None       # pipes
    size: tuple[float, float] | None = None  # rectangular trays
    from_id: str | None = None
    to_id: str | None = None


@dataclass
class EdgeP:
    src: str
    dst: str
    kind: str
    system: str


@dataclass
class SystemP:
    id: str
    name: str
    kind: str                   # ELECTRICAL | POWERGENERATION | CHILLEDWATER | ... | DATA | SECURITY
    side: str | None = None


@dataclass
class Plan:
    meta: dict
    storeys: list[StoreyP]
    roof: dict
    grid_lines: list[GridLineP]
    blocks: dict                       # name -> {x,y,w,d}
    wall_types: dict
    heights: dict
    spaces: list[SpaceP]
    walls: list[WallP]
    doors: list[DoorP]
    columns: list[ColumnP]
    slabs: list[SlabP]
    equipment: list[EquipP]
    racks: list[RackP]
    rows: list[RowP]
    runs: list[RunP]
    routes: list[RouteP]
    edges: list[EdgeP]
    systems: list[SystemP]
    redundancy_groups: list[dict]
    mech_feeds: dict
    security: dict                     # {"ava": [{id, space}], "iris": [{id, door}]}
    cooling_cfg: dict                  # elevations, diameters, routing hints (passthrough)
    it_cfg: dict                       # containment config (passthrough)
    cameras: list[CameraP] = field(default_factory=list)

    # -- convenience -------------------------------------------------------
    def space(self, space_id: str) -> SpaceP:
        return next(s for s in self.spaces if s.id == space_id)

    def equip(self, equip_id: str) -> EquipP:
        return next(e for e in self.equipment if e.id == equip_id)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dataclasses.asdict(self), indent=1, sort_keys=True, allow_nan=False) + "\n")
        return path

    def targets(self) -> dict:
        from .ids import guid
        elevations = {s.id: s.elevation for s in self.storeys}
        doors = [{"id": d.id, "GlobalId": guid(d.id),
                  "centre": [*d.pos, elevations[d.storey] + d.threshold_height],
                  "approach_normal": d.approach_normal, "approach_space": d.approach_space,
                  "width": d.width, "height": d.height, "external": d.external,
                  "access_controlled": d.id in {r["door"] for r in self.security["iris"]}}
                 for d in self.doors]
        regions = [{"id": s.id, "GlobalId": guid(s.id), "type": s.type,
                    "polygon": [[x, y, elevations.get(s.storey, 0.0)] for x, y in
                                [(s.x, s.y), (s.x+s.w, s.y), (s.x+s.w, s.y+s.d), (s.x, s.y+s.d)]]}
                   for s in self.spaces if s.type in {"corridor", "yard", "lobby"}]
        cameras = [{"id": c.id, "GlobalId": c.global_id, "type": c.type, "space": c.space,
                    "pose": {"position": c.pos, "device_rotation": c.device_rotation,
                             "pan": c.pan, "tilt": c.tilt, "roll": c.roll}}
                   for c in self.cameras]
        return {"contract": "usdaeco-datacentre-targets/1.0", "units": "metres/degrees",
                "facility": self.meta["code"], "doors": doors, "regions": regions, "cameras": cameras}

    def write_targets(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.targets(), indent=2, sort_keys=True, allow_nan=False) + "\n")
        return path
