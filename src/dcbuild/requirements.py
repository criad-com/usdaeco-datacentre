"""Illustrative requirements as typed data, with explicit applicability and units."""
from __future__ import annotations
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Applicability(Input):
    classification: list[str] = Field(min_length=1)
    types: list[str] = Field(min_length=1)


class Requirement(Input):
    measure: Literal["MountingHeight", "DoorEdgeOffset", "Side"]
    operator: Literal["between", "eq", "in", "lt", "le", "gt", "ge", "ne"]
    values: list[float | str] = Field(min_length=1)
    unit: Literal["m", "1"]
    tolerance: float = Field(ge=0)
    severity: Literal["hard", "advisory"]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def well_formed(self):
        if self.measure == "Side":
            if self.unit != "1" or self.operator not in ("eq", "in", "ne") or not all(v in ("pull", "push") for v in self.values):
                raise ValueError("side must be a dimensionless pull/push requirement")
        else:
            if self.unit != "m" or not all(isinstance(v, float) for v in self.values):
                raise ValueError("length requirement needs numeric metre values")
        if self.operator == "between" and (len(self.values) != 2 or self.values[0] > self.values[1]):
            raise ValueError("between needs an ordered pair")
        if self.operator not in ("between", "in") and len(self.values) != 1:
            raise ValueError("comparison needs one value")
        return self


class Specification(Input):
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    kind: Literal["regulation", "specification", "datasheet"]
    authority: int = Field(ge=1)
    illustrative: Literal[True]
    appliesTo: Applicability
    requirements: list[Requirement] = Field(min_length=1)


def load(directory: Path):
    return {p.stem: Specification.model_validate(yaml.safe_load(p.read_text()))
            for p in sorted(directory.glob("*.yaml"))}


def evaluate(readers, documents):
    """Evaluate only this fixture's explicit measured reader quantities.

    The general compliance evaluator belongs to its use-case repository.
    """
    result = {}
    for door, data in readers.items():
        verdicts = {}
        for name, doc in documents.items():
            if ("IfcSensor.IDENTIFIERSENSOR" not in doc.appliesTo.classification
                    or "type.sec.iris" not in doc.appliesTo.types):
                continue
            verdicts[name] = True
            for requirement in doc.requirements:
                value = data[requirement.measure]
                bounds = requirement.values
                tolerance = requirement.tolerance
                op = requirement.operator
                if op == "between": ok = bounds[0]-tolerance <= value <= bounds[1]+tolerance
                elif op in ("eq", "ne"):
                    ok = abs(value-bounds[0]) <= tolerance if isinstance(value, (int,float)) else value == bounds[0]
                    if op == "ne": ok = not ok
                elif op == "in": ok = value in bounds
                elif op == "lt": ok = value < bounds[0]+tolerance
                elif op == "le": ok = value <= bounds[0]+tolerance
                elif op == "gt": ok = value > bounds[0]-tolerance
                else: ok = value >= bounds[0]-tolerance
                verdicts[name] &= ok
            verdicts[name] = "pass" if verdicts[name] else "fail"
        result[door] = verdicts
    return result
