"""Spatial skeleton: spaces + structural grid.

Built first into every file (combined and federated) — all other modules
contain their elements in these spaces / storeys.
"""
from __future__ import annotations

import ifcopenshell.guid

from .geom import Z_UP, at


def build(b, plan) -> None:
    for sp in plan.spaces:
        space = b.add_space(sp)
        b.identify(space, sp.id)
        b.pset(space, "Pset_SpaceCommon", {
            "Reference": sp.id,
            "IsExternal": sp.external,
        })
        b.pset(space, "DC_Space", {"SpaceType": sp.type})
        from ..footprint import area
        polygon = plan.meta.get("space_geometry", {}).get(sp.id, {}).get("footprint")
        floor_area = area(polygon) if polygon else sp.w * sp.d
        b.quantities(space, "Qto_SpaceBaseQuantities", [
            ("GrossFloorArea", "area", floor_area),
            ("Height", "length", sp.height),
            ("GrossVolume", "volume", floor_area * sp.height),
        ])

    # Structural grid (shared setting-out for both builders)
    f = b.file

    def axis(label, p1, p2):
        pts = [f.create_entity("IfcCartesianPoint", [float(x), float(y)]) for x, y in (p1, p2)]
        poly = f.create_entity("IfcPolyline", pts)
        return f.create_entity("IfcGridAxis", AxisTag=label, AxisCurve=poly, SameSense=True)

    u_axes = [axis(g.label, (g.value, g.start), (g.value, g.end))
              for g in plan.grid_lines if g.axis == "x"]
    v_axes = [axis(g.label, (g.start, g.value), (g.end, g.value))
              for g in plan.grid_lines if g.axis == "y"]
    grid = f.create_entity(
        "IfcGrid", GlobalId=ifcopenshell.guid.new(), Name="Setting-Out Grid",
        UAxes=u_axes, VAxes=v_axes,
    )
    from .. import ids
    grid.GlobalId = ids.guid("grid")
    b.identify(grid, "grid")
    b.contain(grid, at(Z_UP, (0.0, 0.0, 0.0)), structure=b.storeys[plan.storeys[0].id])
