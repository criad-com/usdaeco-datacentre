"""Structure: the reinforced-concrete frame — 400x400 columns on the grid
intersections the resolver selected, plus the roof-line ring beams around the
main block perimeter.

Columns rise from the ground slab (z = 0) to the roof plane; the square
profile is centred on the grid point (Builder.box/profile convention: profile
centre at the placement origin).
"""
from __future__ import annotations

from .geom import X_RUN, Y_RUN, Z_UP, at

RGB_CONCRETE = (0.62, 0.62, 0.60)

BEAM_WIDTH = 0.4
BEAM_DEPTH = 0.6


def _concrete(b):
    return b.material("Reinforced Concrete", "concrete", rgb=RGB_CONCRETE)


def _column_type(b, plan):
    size = int(round(plan.columns[0].size * 1000)) if plan.columns else 400
    new = f"RC Column {size}x{size}" not in b._types
    ct = b.typed("IfcColumnType", "COLUMN", f"RC Column {size}x{size}",
                 key="type.col.rc")
    if new:
        b.assign_material([ct], _concrete(b))
    return ct


def _beam_type(b):
    name = f"RC Ring Beam {int(BEAM_WIDTH * 1000)}x{int(BEAM_DEPTH * 1000)}"
    new = name not in b._types
    bt = b.typed("IfcBeamType", "BEAM", name, key="type.beam.ring")
    if new:
        b.assign_material([bt], _concrete(b))
    return bt


def _add_column(b, plan, ct, c):
    col = b.entity("IfcColumn", predefined="COLUMN", name=c.id, key=c.id)
    b.assign_type([col], ct)
    b.assign_rep(col, b.profile_rep(b.rect_profile(c.size, c.size), c.height))
    b.contain(col, at(Z_UP, (c.pos[0], c.pos[1], 0.0)),
              structure=b.storeys[plan.storeys[0].id])
    b.style_product(col, "Reinforced Concrete")
    b.identify(col, c.id)
    b.quantities(col, "Qto_ColumnBaseQuantities", [("Length", "length", c.height)])
    return col


def _add_ring_beams(b, plan):
    """Edge beams along the main block perimeter at the roof line (top of beam
    at the roof plane). Profile centred: width across the wall line, depth down
    from the roof."""
    bt = _beam_type(b)
    blk = plan.blocks["main"]
    x0, y0 = blk["x"], blk["y"]
    x1, y1 = x0 + blk["w"], y0 + blk["d"]
    zc = plan.roof["elevation"] - BEAM_DEPTH / 2.0
    runs = [
        ("s", X_RUN, (x0, y0, zc), blk["w"]),
        ("n", X_RUN, (x0, y1, zc), blk["w"]),
        ("w", Y_RUN, (x0, y0, zc), blk["d"]),
        ("e", Y_RUN, (x1, y0, zc), blk["d"]),
    ]
    for side, frame, start, length in runs:
        key = f"str.beam.ring.{side}"
        beam = b.entity("IfcBeam", predefined="BEAM", name=f"Ring Beam {side.upper()}",
                        key=key)
        b.assign_type([beam], bt)
        # X_RUN / Y_RUN: local X spans the beam width (world Y / X), local Y is
        # world +Z, extrusion runs along the perimeter edge.
        b.assign_rep(beam, b.profile_rep(b.rect_profile(BEAM_WIDTH, BEAM_DEPTH), length))
        b.contain(beam, at(frame, start), structure=b.storeys[plan.storeys[0].id])
        b.style_product(beam, "Reinforced Concrete")
        b.identify(beam, key)
        b.quantities(beam, "Qto_BeamBaseQuantities", [("Length", "length", length)])


def build(b, plan) -> None:
    ct = _column_type(b, plan)
    for c in plan.columns:
        _add_column(b, plan, ct, c)
    _add_ring_beams(b, plan)
