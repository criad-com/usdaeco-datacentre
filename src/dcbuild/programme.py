"""Programme inputs and deterministic P6 XER / MSPDI exchange emitters.

Dates are authored data. The explicit 24-hour calendar makes lagDays elapsed
calendar days in both formats; no critical-path or working-day calculation.
"""
from __future__ import annotations
from datetime import date
import json
from pathlib import Path
from typing import Literal
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, model_validator

NS = "http://schemas.microsoft.com/project"
LINK_TYPES = {"FF": 0, "FS": 1, "SF": 2, "SS": 3}
TASK_TYPES = Literal["construction", "demolition", "installation", "removal", "move",
                     "logistic", "maintenance", "operation", "attendance", "notDefined"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Workspace(Input):
    requiresAccess: list[str] = Field(default_factory=list)
    encloses: list[str] = Field(default_factory=list)
    occupies: list[str] = Field(default_factory=list)


class Predecessor(Input):
    id: str
    type: Literal["FS", "SS", "FF", "SF"] = "FS"
    lagDays: float = 0


class Activity(Input):
    id: str
    name: str
    wbs: list[str] = Field(min_length=1)
    taskType: TASK_TYPES
    scope: list[str] = Field(min_length=1)
    workspace: Workspace = Field(default_factory=Workspace)
    plannedStart: date
    plannedFinish: date
    predecessors: list[Predecessor] = Field(default_factory=list)

    @model_validator(mode="after")
    def dates(self):
        if self.plannedFinish < self.plannedStart:
            raise ValueError("finish precedes start")
        return self


class Placement(Input):
    space: str
    pos: tuple[float, float, float]


class Programme(Input):
    id: str
    name: str
    activities: list[Activity]
    placements: dict[str, Placement] = Field(default_factory=dict)


class Programmes(Input):
    epoch: date
    timeCodesPerDay: float = Field(gt=0)
    hoursPerDay: int = Field(default=24, ge=1, le=24)
    programmes: list[Programme]
    expected: dict[str, list[dict]]


def _wbs(activities):
    paths = []
    for activity in activities:
        for depth in range(1, len(activity.wbs)+1):
            path = tuple(activity.wbs[:depth])
            if path not in paths:
                paths.append(path)
    return paths, {path: str(i) for i, path in enumerate(paths, 1)}


def xer(programme, cfg):
    paths, wbs_ids = _wbs(programme.activities)
    task_ids = {a.id: str(i) for i, a in enumerate(programme.activities, 1)}
    lines = [f"ERMHDR\t8.4\t{cfg.epoch}\tProject\tUSD"]

    def table(name, fields, rows):
        lines.extend(["%T\t"+name, "%F\t"+"\t".join(fields)])
        for row in rows:
            values = [str(v) for v in row]
            if any("\t" in v or "\n" in v or "\r" in v for v in values):
                raise ValueError("XER fields cannot contain tabs or newlines")
            lines.append("%R\t"+"\t".join(values))

    table("ERMHDR", ["version", "export_date"], [["8.4", cfg.epoch.isoformat()]])
    table("PROJECT", ["proj_id", "proj_short_name", "project_flag", "clndr_id", "plan_start_date"],
          [["1", programme.id, "Y", "1", str(cfg.epoch)]])
    table("CALENDAR", ["clndr_id", "clndr_name", "day_hr_cnt", "week_hr_cnt", "clndr_type"],
          [["1", "Elapsed days", cfg.hoursPerDay, cfg.hoursPerDay*7, "CA_Project"]])
    table("PROJWBS", ["wbs_id", "proj_id", "parent_wbs_id", "wbs_short_name", "wbs_name", "seq_num"],
          [[wbs_ids[p], "1", wbs_ids.get(p[:-1], ""), p[-1], p[-1], i]
           for i, p in enumerate(paths, 1)])
    table("TASK", ["task_id", "proj_id", "task_code", "task_name", "wbs_id", "task_type", "clndr_id",
                   "target_start_date", "target_end_date", "phys_complete_pct", "status_code", "dc_task_type"],
          [[task_ids[a.id], "1", a.id, a.name, wbs_ids[tuple(a.wbs)], "TT_Task", "1",
            str(a.plannedStart)+" 00:00", str(a.plannedFinish)+" 00:00", 0, "TK_NotStart", a.taskType]
           for a in programme.activities])
    table("TASKPRED", ["task_pred_id", "proj_id", "task_id", "pred_task_id", "pred_type", "lag_hr_cnt"],
          [[i, "1", task_ids[a.id], task_ids[p.id], "PR_"+p.type, format(p.lagDays*cfg.hoursPerDay, ".12g")]
           for i, (a, p) in enumerate(((a, p) for a in programme.activities for p in a.predecessors), 1)])
    lines.append("%E")
    return "\n".join(lines)+"\n"


def mspdi(programme, cfg):
    ET.register_namespace("", NS)
    root = ET.Element(f"{{{NS}}}Project")

    def node(parent, name, value=None):
        child = ET.SubElement(parent, f"{{{NS}}}{name}")
        if value is not None:
            child.text = str(value)
        return child

    node(root, "UID", 1)
    node(root, "Name", programme.name)
    node(root, "StartDate", str(cfg.epoch)+"T00:00:00")
    node(root, "MinutesPerDay", cfg.hoursPerDay*60)
    node(root, "MinutesPerWeek", cfg.hoursPerDay*60*7)
    node(root, "CalendarUID", 1)
    calendar = node(node(root, "Calendars"), "Calendar")
    node(calendar, "UID", 1)
    node(calendar, "Name", "Elapsed days")
    node(calendar, "IsBaseCalendar", 1)
    node(calendar, "BaseCalendarUID", -1)
    days = node(calendar, "WeekDays")
    for day in range(1, 8):
        weekday = node(days, "WeekDay")
        node(weekday, "DayType", day)
        node(weekday, "DayWorking", 1)
        working = node(node(weekday, "WorkingTimes"), "WorkingTime")
        node(working, "FromTime", "00:00:00")
        node(working, "ToTime", "23:59:59")
    definitions = node(root, "ExtendedAttributes")
    for field, name, alias in [(188743731, "Text1", "Scope ids"), (188743734, "Text2", "Activity id"),
                               (188743737, "Text3", "IfcTask type")]:
        definition = node(definitions, "ExtendedAttribute")
        node(definition, "FieldID", field)
        node(definition, "FieldName", name)
        node(definition, "Alias", alias)
    tasks = node(root, "Tasks")
    paths, _ = _wbs(programme.activities)
    # Summary tasks carry WBS hierarchy; leaf UIDs are independent of nesting.
    task_ids = {a.id: i for i, a in enumerate(programme.activities, 1)}
    summary_ids = {p: len(task_ids)+i for i, p in enumerate(paths, 1)}

    def emit(parent_path=()):
        for path in paths:
            if path[:-1] != parent_path:
                continue
            summary = node(tasks, "Task")
            for key, value in [("UID", summary_ids[path]), ("Name", path[-1]), ("OutlineLevel", len(path)),
                               ("WBS", ".".join(path)), ("Summary", 1)]:
                node(summary, key, value)
            emit(path)
            for a in programme.activities:
                if tuple(a.wbs) != path:
                    continue
                task = node(tasks, "Task")
                for key, value in [("UID", task_ids[a.id]), ("Name", a.name), ("OutlineLevel", len(path)+1),
                                   ("WBS", ".".join(path)+"."+a.id), ("Summary", 0),
                                   ("Start", str(a.plannedStart)+"T00:00:00"),
                                   ("Finish", str(a.plannedFinish)+"T00:00:00"), ("PercentComplete", 0)]:
                    node(task, key, value)
                for p in a.predecessors:
                    link = node(task, "PredecessorLink")
                    node(link, "PredecessorUID", task_ids[p.id])
                    node(link, "Type", LINK_TYPES[p.type])
                    node(link, "LinkLag", round(p.lagDays*cfg.hoursPerDay*600))
                    node(link, "LagFormat", 7)
                for field, value in [(188743731, json.dumps(a.scope, separators=(",", ":"))),
                                      (188743734, a.id), (188743737, a.taskType)]:
                    ext = node(task, "ExtendedAttribute")
                    node(ext, "FieldID", field)
                    node(ext, "Value", value)
    emit()
    ET.indent(root)
    return '<?xml version="1.0" encoding="utf-8"?>\n'+ET.tostring(root, encoding="unicode")+"\n"


def build(plan, directory: Path):
    if not plan.meta.get("programme"):
        raise ValueError("variant has no programme")
    cfg = Programmes.model_validate(plan.meta["programme"])
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for programme in cfg.programmes:
        payloads = {"xer": xer(programme, cfg), "xml": mspdi(programme, cfg),
                    "scope.json": {a.id: a.scope for a in programme.activities},
                    "workspace.json": {"activities": {a.id: a.workspace.model_dump() for a in programme.activities},
                                       "placements": {k: v.model_dump() for k, v in programme.placements.items()}}}
        for suffix, data in payloads.items():
            path = directory/f"{programme.id}.{suffix}"
            path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2, sort_keys=True)+"\n",
                            encoding="latin-1" if suffix == "xer" else "utf-8")
            written.append(path)
    return written
