"""Typed spec model (pydantic). Mirrors spec/*.yaml one-to-one.

The spec is the *design intent*; nothing here is resolved geometry. See
dcbuild.plan for the resolved build plan both builders consume.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from .fitout import Fitout
from .programme import Programmes


class Rect(BaseModel):
    x: float
    y: float
    w: float
    d: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.d

    def contains(self, px: float, py: float, eps: float = 1e-6) -> bool:
        return (self.x - eps <= px <= self.x2 + eps) and (self.y - eps <= py <= self.y2 + eps)

    def contains_interior(self, px: float, py: float, eps: float = 1e-6) -> bool:
        return (self.x + eps < px < self.x2 - eps) and (self.y + eps < py < self.y2 - eps)


# --------------------------------------------------------------------------- facility
class Storey(BaseModel):
    id: str
    name: str
    elevation: float
    blocks: list[str]
    expected_areas: dict[str, float]
    typical_of: str | None = None


class Roof(BaseModel):
    model_config = ConfigDict(extra="allow")
    elevation: float
    thickness: float


class GridAxis(BaseModel):
    start: float
    step: float
    count: int

    @property
    def values(self) -> list[float]:
        return [self.start + i * self.step for i in range(self.count)]


class Grid(BaseModel):
    x: GridAxis
    y: GridAxis


class WallType(BaseModel):
    thickness: float
    material: str
    fire_rating: str | None = None


class SlabType(BaseModel):
    thickness: float
    material: str | None = None


class ColumnSpec(BaseModel):
    size: float
    material: str


class StructureSpec(BaseModel):
    column: ColumnSpec
    internal_lines: dict[str, list[float]]


class Pad(BaseModel):
    id: str
    name: str
    x: float
    y: float
    w: float
    d: float
    thickness: float

    @property
    def rect(self) -> Rect:
        return Rect(x=self.x, y=self.y, w=self.w, d=self.d)


class ExternalWorks(BaseModel):
    pads: list[Pad]


class ProjectMeta(BaseModel):
    code: str
    name: str
    description: str


class Building(BaseModel):
    name: str
    blocks: dict[str, Rect]


class Facility(BaseModel):
    project: ProjectMeta
    site: dict
    building: Building
    storeys: list[Storey]
    roof: Roof
    split_upper_slabs: bool = True
    grid: Grid
    heights: dict[str, float]
    wall_types: dict[str, WallType]
    slabs: dict[str, SlabType]
    structure: StructureSpec
    external_works: ExternalWorks


# --------------------------------------------------------------------------- spaces
SpaceType = Literal[
    "hall", "electrical", "battery", "plant", "mmr", "fire", "water",
    "corridor", "loading", "office", "noc", "meeting", "lobby", "stair",
    "kitchen", "wc", "void",
]

# Space types whose boundary walls are fire-rated blockwork.
FIRE_TYPES: set[str] = {"hall", "electrical", "battery", "plant", "mmr", "fire", "water"}


class Space(BaseModel):
    id: str
    name: str
    type: SpaceType
    storey: str
    x: float
    y: float
    w: float
    d: float
    height: float

    z_offset: float = 0
    parent: str | None = None
    footprint: list[tuple[float, float]] | None = None

    @property
    def rect(self) -> Rect:
        return Rect(x=self.x, y=self.y, w=self.w, d=self.d)


class DoorSpec(BaseModel):
    id: str
    between: list[str]  # [space_id, space_id] or [space_id, "EXT"]
    at: tuple[float, float]
    kind: str
    name: str | None = None
    width: float | None = None
    height: float | None = None


class DoorKind(BaseModel):
    width: float
    height: float


class Spaces(BaseModel):
    spaces: list[Space]
    doors: list[DoorSpec]
    door_kinds: dict[str, DoorKind]


# --------------------------------------------------------------------------- power
class PowerNode(BaseModel):
    model_config = ConfigDict(extra="allow")  # rating_kva / rating_kw / voltage / fuel ...

    id: str
    cls: str = Field(alias="class")
    name: str
    side: Literal["A", "B"]
    space: str  # space id or "EXT"
    pos: tuple[float, float, float]
    pad: str | None = None

    def rating(self) -> dict:
        keep = {"rating_kva", "rating_kw", "rating_kwh", "voltage", "fuel", "volume_l"}
        return {k: v for k, v in (self.model_extra or {}).items() if k in keep}


class PowerEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    src: str = Field(alias="from")
    dst: str = Field(alias="to")
    kind: str


class PduRule(BaseModel):
    rating_kva: float
    offset_from_row_end: float


class BuswayCfg(BaseModel):
    z: float
    y_offset: dict[str, float]
    rating_a: dict[str, float]


class Power(BaseModel):
    sides: list[str]
    capacity_kw: dict[str, float]
    nodes: list[PowerNode]
    pdu_rules: dict[str, PduRule]
    edges: list[PowerEdge]
    mech_feeds: dict[str, list[str]]
    busway: BuswayCfg


# --------------------------------------------------------------------------- cooling
class CoolingNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    cls: str = Field(alias="class")
    name: str
    space: str
    pos: tuple[float, float, float]
    pad: str | None = None
    loop: str | None = None
    secondary_loop: str | None = None

    def rating(self) -> dict:
        keep = {"rating_kw", "flow_ls", "volume_l"}
        return {k: v for k, v in (self.model_extra or {}).items() if k in keep}


class RedundancyGroup(BaseModel):
    id: str
    members: list[str]
    duty_required: int
    serves_kw: float


class Cooling(BaseModel):
    elevations: dict[str, float]
    pipe_diameters: dict[str, float]
    nodes: list[CoolingNode]
    routing: dict[str, dict]
    tcs_manifolds: dict
    redundancy_groups: list[RedundancyGroup]


# --------------------------------------------------------------------------- it
class RackType(BaseModel):
    width: float
    depth: float
    height: float
    units: int


class HallSpec(BaseModel):
    id: str
    space: str
    cooling: Literal["dlc", "air"]
    rows: int
    racks_per_row: int
    rack_type: str
    rack_kw: float
    rack_pitch: float
    first_row_y: float
    row_pitch: float
    row_x_margin: float


class MeetMeRoom(BaseModel):
    id: str
    space: str
    serves: str
    racks: int
    rack_type: str


class ContainmentRoute(BaseModel):
    spine_x: float
    corridor_y: float
    mmr_entry: tuple[float, float]


class Containment(BaseModel):
    tray_z: float
    tray_size: tuple[float, float]
    dropper_size: tuple[float, float]
    spine_tray_size: tuple[float, float]
    routes: dict[str, ContainmentRoute]


class CameraType(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    target_density: float = Field(default=250, gt=0)
    focal_range: tuple[float, float]
    hfov_range: tuple[float, float]
    vfov_range: tuple[float, float]
    pixels: tuple[int, int]
    offset: tuple[float, float, float] = (0, 0, 0)
    pan_range: tuple[float, float] = (0, 0)
    tilt_range: tuple[float, float] = (0, 0)
    motorised: bool = False
    outdoor: bool = False
    ir_range: float = 0
    body_size: tuple[float, float, float]


class CameraRule(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    type: str
    tilt: float
    range: float = Field(gt=0)
    setback: float = Field(default=0, ge=0)
    height: float | None = None
    ceiling_offset: float = Field(default=0.1, ge=0)
    max_spacing: float = Field(default=18, gt=0)
    corner_inset: float = Field(default=0.5, gt=0)
    focal_length: float = Field(default=0, ge=0)
    lateral_offset: float = Field(default=0, ge=0)
    compact_tilt: float = 60


class SharedApproachRule(BaseModel):
    """Reuse a wide-opening bullet for a neighbouring coplanar approach."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    min_width: float = Field(gt=0)
    max_neighbour_distance: float = Field(gt=0)
    setback: float = Field(gt=0)
    height: float = Field(gt=0)
    aim_height: float = Field(ge=0)
    focal_length: float = Field(gt=0)


class IrisMount(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    height: float = Field(gt=0)
    door_edge_offset: float = Field(ge=0)
    side: Literal["pull", "push"]
    reference: Literal["base", "centre"] = "base"


class IrisOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    height: float | None = Field(default=None, gt=0)
    door_edge_offset: float | None = Field(default=None, ge=0)
    side: Literal["pull", "push"] | None = None


class Security(BaseModel):
    iris_readers: IrisMount
    iris_reader_overrides: dict[str, IrisOverride] = Field(default_factory=dict)
    ava_spaces: list[str]
    iris_doors: list[str]
    camera_types: dict[str, CameraType]
    door_cameras: CameraRule
    external_door_cameras: CameraRule
    external_shared_approaches: SharedApproachRule | None = None
    corridor_cameras: CameraRule
    yard_cameras: CameraRule
    yard_fixed_cameras: CameraRule
    lobby_ptz: CameraRule
    lobby_fixed_cameras: CameraRule


class IT(BaseModel):
    rack_types: dict[str, RackType]
    halls: list[HallSpec]
    meet_me_rooms: list[MeetMeRoom]
    containment: Containment
    office_it: dict


# --------------------------------------------------------------------------- root
class WallEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    p1: tuple[float, float]
    p2: tuple[float, float]


class Spec(BaseModel):
    wall_edits: list[WallEdit] = Field(default_factory=list)
    publication: dict = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")
    variant: str = "base"
    fitout: Fitout | None = None
    programme: Programmes | None = None
    expected: dict = Field(default_factory=dict)
    facility: Facility
    spaces: Spaces
    power: Power
    cooling: Cooling
    it: IT
    security: Security

    def space(self, space_id: str) -> Space:
        return self._space_index[space_id]

    def model_post_init(self, __context) -> None:
        self._space_index = {s.id: s for s in self.spaces.spaces}
