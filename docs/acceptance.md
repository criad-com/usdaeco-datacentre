# Acceptance — 0.1.0

This is the generator baseline. The 0.3.1 native update is recorded in
[Revit acceptance](acceptance-revit.md); the 0.2.2 gate is recorded in [offline acceptance](acceptance-offline.md).
The current camera design is recorded in [0.3.0 design acceptance](acceptance-design.md).

Measured on 2026-09-10 with Python 3.13, ifcopenshell 0.8.5, pydantic 2,
PyYAML, numpy, pytest and USD 26.8. Run `env -u PYTHONPATH "$PY" check.py`
from the checkout; the report is written to `out/check.json`.

| Claim | Observed |
|---|---:|
| Family-format gate | **35 checks, 0 failed** |
| pytest | **33 passed**, 4.12 s |
| G0 | 7 invariants green |
| G1 | 8/8 IFC files pass schema + EXPRESS; combined port graph, identities, containment and plan census green |
| Full CLI build (combined + seven federated files) | **14.095 s**; second independent build **13.909 s** |
| G1 elapsed time | 43.199 s |
| Cameras / heads / types | **29 / 29 / 3** in both combined and security files |
| Doors / column intersections | **41 / 0**, minimum opening-to-column clearance **0.350 m** |
| Retained alarms / readers | **12 / 11** |
| Camera GUID agreement between combined/security files | **29/29 (100%)** |
| Common Status NEW, applicable products | **9,228/9,228 (100%)** |
| Raw IfcProduct Status NEW | **9,228/9,229 (99.989%)**, one counted grid exception |
| Interior / exterior spaces | **30 / 3** |
| Presets / tours | **7 / 3** |
| Target doors / regions / cameras | **41 / 11 / 29** |
| Pinned plan identities | **753**, full canonical plan and identity digests checked |
| Independent resolve determinism | Plan JSON and targets JSON byte-identical |
| Independent IFC determinism | **8/8 files byte-identical** after replacing only FILE_NAME timestamp |
| Writer units | **4/4** metre/mm × radian/degree camera driver/placement reopen cases |
| Revit local dry run | 8/8 existing phases parse locally; uploaded plan has 29 camera records |
| Repository term sweep | **0 hits** |

The source specification, resolver and writer implement the complete
`usdaeco-cctv-ifc/1.0` tier A payload and tier B mirror. Negative tests reject
missing cameras, the original five door/column conflicts, malformed JSON,
wrong tilt units, wrong type/system, baked device rotation, missing presets,
and missing NEW status. Port tests verify world placement and nesting order.

## Stable family route

Read-only probe against core **v0.8.0** and CCTV **v0.3.0**, using their supplied
plugins. No sibling build or checkout was performed. Inputs were the generated
combined IFC and security IFC; outputs were written to disposable scratch.

| Step | Observed |
|---|---|
| Core conversion | **6.1 s**, 37 spatial prims (33 spaces), 2,938 elements, 2,971 meshes, 64 types, 9 systems, 6,212 ports, 3,024 port links |
| Phase/extent census | **2,938 phases / 2,938 elements (100%)**, **33 extents** |
| Spatial/classification census | **0 unparented**, 2 known utility-intake proxies |
| CCTV importer | **29 cameras, 29 sensors, 3 types, 7 presets, 0 unmatched** |
| Other importer counters | 174 promoted properties blocked; 0 sub-instances folded |
| Derivation using the old importer | **0 usable sensors, 29 skips**, missing physical sensor size/decoded optics |
| Vanilla stage composition | **0 errors**, 6,249 spatial/port Xform fallbacks; no family plugins loaded |

To repeat with the family siblings, set `AECO_CORE_ROOT` and `AECO_CCTV_ROOT` to
their checkouts, and `SCRATCH` to an empty output directory. Export each variable
on its own line. Run from the generator checkout:

```sh
export CORE_PLUGIN_DIR="$AECO_CORE_ROOT/plugins/usdAeco/resources"
export CCTV_PLUGIN_DIR="$AECO_CCTV_ROOT/plugins/usdAecoCctv/resources"
export PXR_PLUGINPATH_NAME="$CORE_PLUGIN_DIR:$CCTV_PLUGIN_DIR"
export PYTHONDONTWRITEBYTECODE=1
export IFC_INPUT="$PWD/out/ifc/demo-datacentre-01.ifc"
export IFC_SECURITY="$PWD/out/ifc/demo-datacentre-01-security.ifc"
(cd "$AECO_CORE_ROOT/tools" && env -u PYTHONPATH "$PY" -m ifc2usdaeco.cli "$IFC_INPUT" -o "$SCRATCH/core.usda")
env -u PYTHONPATH "$PY" "$AECO_CCTV_ROOT/tools/aeco-cctv-import" "$SCRATCH/core.usda" "$IFC_SECURITY" -o "$SCRATCH/kind.usda"
```

The old importer reads tier B and does not reconstruct the full tier A optics.
Its successful census is not proof of usable sensor derivation,
night performance or coverage. The core phase and extent counts above are
measured independently of CCTV import. The later importer and scenario packages own
those acceptance claims. A fresh derive on this old route explicitly fails.

## Deviations

- Four blocked doors move half a 6 m bay. The centre corridor has a 4 m wall
  with three columns; a 3 m shift and 1.8 m opening cannot fit. Its door changes
  to a 0.9 m single opening shifted 1 m, with 0.35 m clearance. Its wall stays
  the same. All 11 iris-reader door associations remain unchanged.
- IfcGrid has no applicable Common Pset. It is the single counted exception;
  all other IfcProducts receive NEW. Spatial/port Common templates that lack a
  standard Status field carry it as an IfcLabel extension.
- The main-entry and loading-apron camera positions lie outside the three pad
  footprints; their mounting/approach association uses the nearest yard space.
  Yard footprints stay faithful to the pads, rather than inventing apron areas.
- The explicit placement rules produce three supplementary PTZs and three
  tours. The separate two-PTZ allowance needs reconciliation in the coverage
  study. The 29-camera count is the current resolver census, not a study freeze.
- Empty IFC preset tables leave both optional aggregates unset, because the
  EXPRESS aggregates require at least one member when present. They reopen
  as zero-row tables and do not leave stale presets.
- The inherited render is omitted because image-label/metadata sanitization
  was not proven. All committed assets are generated code/spec/text.
- One `nix flake check --offline` attempt failed: this generator checkout has
  no flake. No network resolution or second attempt was made; Nix packaging is
  left for the family packaging work package.
- Native Revit cameras, rooms, IFC_GUID stamping, IFC4X3 export and live parity
  remain W5 work. Only the existing phases and camera plan payload ship here.
- The stable tier-B-only importer cannot prove full optical round trip or
  usable derived sensors. Explicit-sample coverage/privacy/night studies remain
  later family work, with no coverage pass claimed here.
