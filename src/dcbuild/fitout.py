"""Typed fit-out inputs. Positions and axes are world metres, Z up."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Element(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str
    name: str
    ifc_class: Literal["IfcCovering", "IfcElementAssembly", "IfcCableCarrierSegment",
                       "IfcPipeSegment", "IfcUnitaryEquipment", "IfcLightFixture",
                       "IfcAirTerminal", "IfcSanitaryTerminal"]
    predefined: str
    space: str
    status: Literal["NEW", "TEMPORARY"] = "NEW"
    fix: Literal["first", "second", "third"] | None = None
    pos: tuple[float, float, float] | None = None
    size: tuple[float, float, float] | None = None
    axis: list[tuple[float, float, float]] | None = None
    od: float | None = Field(default=None, gt=0)
    nominal_diameter: float | None = Field(default=None, gt=0)
    section: tuple[float, float] | None = None
    material: str = "Fit-out equipment"
    construction: str | None = None
    port_system: str | None = None
    port_medium: Literal["PIPE", "DUCT", "CABLE", "CABLECARRIER"] | None = None
    ports: list[tuple[float, float, float]] = Field(default_factory=list)
    connects: list[tuple[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def geometry(self):
        if self.axis:
            if len(self.axis) < 2 or any(a == b for a, b in zip(self.axis, self.axis[1:])):
                raise ValueError("axis needs distinct endpoints")
            if not (self.od or self.section) or self.pos or self.size:
                raise ValueError("axis requires an OD or section, without a box")
        elif not self.pos or not self.size or min(self.size) <= 0:
            raise ValueError("box requires position and positive dimensions")
        if self.section and min(self.section) <= 0:
            raise ValueError("section dimensions must be positive")
        if self.ports and not (self.port_system and self.port_medium):
            raise ValueError("ports require system and medium")
        return self


class Fitout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    elements: list[Element]
