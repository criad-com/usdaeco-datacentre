"""Site groundworks: the external equipment pads (generator yards, heat
rejection yard).

Pattern from dc-examples/dcgen/site.py: ground-bearing IfcSlab/BASESLAB laid
on the *site* (outside the building's spatial decomposition), top flush with
the yard ground plane (``top_elevation``), extruded down into the ground.
Outdoor plant placed at z = 0 by later disciplines rests on them.
"""
from __future__ import annotations

from .geom import Z_UP, at

RGB_CONCRETE = (0.62, 0.62, 0.60)


def _add_pad(b, s):
    slab = b.entity("IfcSlab", predefined="BASESLAB", name=s.id, key=s.id)
    b.assign_rep(slab, b.profile_rep(b.rect_profile(s.w, s.d), s.thickness))
    b.contain(slab,
              at(Z_UP, (s.x + s.w / 2.0, s.y + s.d / 2.0, s.top_elevation - s.thickness)),
              structure=b.site)
    b.assign_material([slab], b.material("Reinforced Concrete", "concrete",
                                         rgb=RGB_CONCRETE))
    b.style_product(slab, "Reinforced Concrete")

    b.identify(slab, s.id)
    b.pset(slab, "Pset_SlabCommon", {"IsExternal": True, "LoadBearing": True})
    gross = s.w * s.d
    b.quantities(slab, "Qto_SlabBaseQuantities", [
        ("Width", "length", s.thickness),
        ("GrossArea", "area", gross),
        ("GrossVolume", "volume", gross * s.thickness),
    ])
    return slab


def build(b, plan) -> None:
    for s in plan.slabs:
        if s.kind == "pad":
            _add_pad(b, s)
