# Revit builder

The Revit 2027 builder consumes the generated plan and owns one background
project. The driver imports the pinned `usdaeco_revit.transport.Client`; set
`AECO_REVIT_ROOT` to the released integration checkout (default
`../usdaeco-revit`). Source execution needs no package installation. Set `PY` to the project Python executable. Run the offline preparation:

```sh
env -u PYTHONPATH "$PY" -m dcbuild plan
env -u PYTHONPATH "$PY" revit/driver.py --update --dry-run
```

For a live build, set each of `AECO_REVIT_ENDPOINT`, `AECO_REVIT_WORKDIR`, and
`AECO_REVIT_FAMILY_DIR` separately to the authorized environment. Defaults are
placeholders (`http://<revit-endpoint>`, `<remote-work-directory>`,
`<camera-family-directory>`). The session is `dc-build`.

```sh
env -u PYTHONPATH "$PY" revit/driver.py --update
```

The [model script enclave](src/README.md) has a complete SHA-256 manifest.
The shared client verifies every uploaded file and checks `/status` before every evaluation, waits at least 120 seconds
when busy, serializes calls, and verifies complete paged replies by byte count
and SHA-256. A failed or ambiguous evaluation stops subsequent submissions;
inspect the native outcome before removing the reported local stop file.
There is no automatic mutation retry. The model stays open in the background.
No document is activated or closed. An existing exact model path is reused;
a foreground match is refused.

## Two-camera spike — measured before the full build

Measured with Revit 2027.2 and IFC4X3 on 2026-09-10. A disposable background
project held one P3277-LV dome and one Q6088-E PTZ. Both were created with
`NewFamilyInstance(point, symbol, level, StructuralType.NonStructural)`.
The category was Security Devices; both retained the native level.

| Observation | Measured |
|---|---|
| Native cameras / exported CAMERA entities | 2 / 2 |
| Required FOV controls writable | 2/2 cameras |
| Dome controls | `FOV Pan`, `FOV Tilt`, `FOV Desired Focal Length`, `FOV Distance to Object`, `FOV Target Pixel Density` |
| PTZ controls | `FOV 1–4 Pan/Tilt/Desired Focal Length/Distance to Object/Target Pixel Density`; `Preset 1–4` booleans |
| Dome exported pan / tilt / focal | 30° / 25° / 4 mm |
| PTZ preset 1 exported pan / tilt / focal | 45° / 35° / 8 mm |
| PTZ preset 2 exported pan / tilt / focal | 70° / 20° / 10 mm |
| Dome / PTZ pixels | 2592×1944 / 3840×2160 |
| Distance / target density | 12 m / 180 px/m on the dome and PTZ preset 1 |
| GUID stamping / exported agreement | 2/2 / 2/2 |
| Core conversion | 4 spatial, 5 elements, 5 meshes, 2 ports, 0 unparented |
| Stable CCTV v0.3.0 import | 2 cameras, 2 sensors, 2 types, 2 presets, 3 sub-instances folded, 0 unmatched |
| Authored phases from common Status | 0 |

Angles are native radians and exported degrees; distances are native feet and
exported millimetres; focal controls are Number parameters already in mm.
Pixel density is an integer parameter. Parameter read-back must follow
`Document.Regenerate()`; a spike edit/rollback probe preserved −90°, 0°, 90°
and 180° and restored the original pose. Formula outputs such as Actual Focal
Length are read-only and are never authored. The PTZ has no unnumbered base
pose controls: the old importer reads its numbered presets, while the default
sensor pose is not reconstructed from that dialect. This is a recorded reader
limitation, not proof of complete optical parity.

`IFC_GUID` is the built-in parameter enum, displayed as `IfcGUID` in this
Revit version. Looking up the literal string `IFC_GUID` misses it. Use
`get_Parameter(BuiltInParameter.IFC_GUID)` separately from Mark. Export with
`StoreIFCGUID=true` persists it; supplied contract GUIDs survive unchanged.

The export carries these property groups: Constraints (pose, distance),
Dimensions (focal/FOV envelopes), Graphics (pixels, desired/actual focal and
density), Identity Data (Mark, PTZ and manufacturer), Other (origin offsets),
IFC Parameters, Phasing, Construction, Photometrics and Visibility.
`Pset_ManufacturerTypeInformation`, `Pset_EnvironmentalImpactIndicators` and
`Pset_AudioVisualApplianceTypeCommon` also appear. The last contains Reference,
with **no Status**. Internal Phase Created is not a common Status property.
Base quantities are enabled, but no camera quantity set was observed.

The six shared contract text parameters survive verbatim in Identity Data.
The tested user-defined property-set configuration did **not** produce an
actual `Pset_AecoCctv`, even with the exporter option names and file format
verified against the installed exporter. Thus Revit's proven exchange route
is **tier C**; tier A remains the generator IFC's authoritative contract.
The shared JSON is retained for audit, not advertised as a decoded tier A.

## Family recipe and sync handoff

The supplied family assets stay outside the repository. P3277-LV supplies the
dome and the permitted outdoor geometry substitute; Q6088-E supplies PTZ.
The camera phase selects the widest available source symbol, creates a
separate `DC <spec-type>` symbol, and sets its declared optics and resolution.
These are demo design types, not a claim that the substitute hardware has the
outdoor type's datasheet or environmental rating.

Every camera uses its space's storey level, world position and device-frame
rotation; pan zero is local +X. Pan/tilt remain FOV drivers. Mark is the spec
id; IFC_GUID is its deterministic contract identity; Revit UniqueId remains
the native binding. The sync reader expects that separation and top-level
Security Devices with FOV evidence. Home maps to numbered preset 1, with other
presets sorted by name. Named presets, dwell, home and tour are preserved in
shared JSON; the native family only exposes four numbered preset switches.

The driver batches camera authoring in groups of five. A repeated camera phase
finds instances by Mark and updates them; duplicate Marks or a changed native
level fail. It does not invent a second camera identity.

Phases: 00 helpers; 10 background project/levels/grids; 15 shared parameters;
20 architecture; 25 rooms; 30 structure; 40 equipment; 45 cameras;
50 containment; 60 piping; 90 save/IFC4x3 export.
Use `--skip-upload --phases ...` only after the same session has loaded helpers
and setup. The full-model census and parity are recorded separately in
[Revit acceptance](../docs/acceptance-revit.md).

Service phases retain fresh-build assumptions. Repeating the camera phase is
verified; repeating containment or piping can duplicate service segments.

## Repeating the 45-camera design

The base-only update reuses `demo-datacentre-01.rvt` in the configured work
folder. A missing file is refused. The existing model is reused in the background;
rooms, doors and services remain in place. No document is activated or closed.
The plan defaults to `out/base/build_plan.json`.

```sh
env -u PYTHONPATH "$PY" -m dcbuild plan
env -u PYTHONPATH "$PY" revit/driver.py --session dc-design --update
```

This selects 00 helpers, 10 setup, 15 parameters, nine camera batches and 90
IFC4X3 export. It expects zero cameras created and 45 updated. Non-base plans
are refused: floors, pod, clash and iris need further native family work,
including pods and ceilings. Their published IFC/USD variants remain available.
The creation-oriented service phases remain for fresh builds only.

Retrieve the export into ignored `out/revit/` and verify the transfer SHA-256
before comparing it with an independent generator build:

```sh
env -u PYTHONPATH "$PY" -m dcbuild build-ifc
env -u PYTHONPATH "$PY" -m dcbuild parity out/revit/demo-datacentre-01-revit.ifc --dir out/base/ifc
```

For the independent importer census, use converter v0.1.0, frozen core v0.8.4
and CCTV v0.4.8. Set the source paths separately:

```sh
export AECO_CORE_ROOT="../usdaeco-core-0.8"
export AECO_IFC_ROOT="../usdaeco-ifc"
export AECO_CCTV_ROOT="../usdaeco-cctv"
export AECO_REVIT_ROOT="../usdaeco-revit"
export AECO_SYNC_ROOT="../usdaeco-sync"
export PYTHONDONTWRITEBYTECODE=1
export PXR_PLUGINPATH_NAME="$AECO_CORE_ROOT/plugins/usdAeco/resources:$AECO_CCTV_ROOT/plugins/usdAecoCctv/resources"
env -u PYTHONPATH "$PY" - <<'PYCODE'
import os, sys
from pathlib import Path
for name in ('AECO_CORE_ROOT', 'AECO_IFC_ROOT', 'AECO_CCTV_ROOT'):
    sys.path.insert(0, str(Path(os.environ[name]).resolve()/'tools'))
from usdaeco_ifc.convert import convert
from usdaeco_cctv import register_plugins
from usdaeco_cctv.importer import import_cctv
register_plugins()  # before the converter creates the first USD stage
root = Path('out/revit/import')
root.mkdir(parents=True, exist_ok=True)
source = 'out/revit/demo-datacentre-01-revit.ifc'
print(convert(source, str(root/'core.usda')))
print(import_cctv(root/'core.usda', source, root/'cctv.usda'))
PYCODE
```

The optional rollback suite now lives in the Revit integration v0.1.0, using
Sync v0.5.0. Prepare a Sync session from the same native export, without
`--kind-import`, and perform native camera read-back as described in the
[Revit integration guide](https://github.com/criad-com/usdaeco-revit/blob/v0.1.0/docs/host.md).
Set `AECO_REVIT_DOCUMENT` to the exact resident model and
`AECO_REVIT_BACKGROUND=1`, then run:

```sh
env -u PYTHONPATH "$PY" revit/live.py \
  --stage out/revit/sync/stage.usda --output out/revit/live
```

The launcher imports `usdaeco_revit.gates.cctv_revit` unchanged, verifies that
it uses the canonical transport, and retains its exact source hash and release
pin beside the results. It does not write to dependency checkouts. The seed
supplies the camera count; all 12 case assertions remain in the integration.
Native update, export/import parity and the optional rollback suite are separate
measurements. Ordinary `check.py` stays offline.

## Optical guide correction — 0.2.1

A disposable two-camera probe reproduced the stale 6 m clipping with zero
`FOV Target Pixel Density`. After `Document.Regenerate()`, the parent and nested
`FOV Distance to Object` read 12 m, while the formula-derived radii still read
6 m. Supplying **250 px/m** refreshed the whole nested formula chain.
The governing writable inputs are the **parent instance's distance and target
density**; PTZ uses the numbered `FOV 1–4` inputs. No additional type clip or
nested override is needed. Actual Focal Length and every `RG_Length_*` output
remain read-only.

The [parameter inventory](clip-parameter-inventory.json) lists instance, type,
and nested parameters matching Distance, Range, Max, Clip, Length, Density,
or Resolution, with storage types, units, writability, and original values.
It also includes the half-angles, density thresholds and effective sensor width.
The [numeric probe](../artifacts/revit-clipping-probe.json) records five rolled
back trials on a dome and two enabled PTZ cones:

| Distance | Density | Result |
|---|---:|---|
| 6 m | 0 | stale formula outputs; invalid user threshold |
| 12 m | 0 | distance updates; radii retain the 6 m cap |
| 12 / 20 / 40 m | 250 | 45/45 radii agree; maximum error 7.11e-15 m |

`RG_Length_Max` is a visibility-dependent shell extent, not a second distance
control: the dome's 40 m trial has Detect = 40 m and Max = 28.449 m. Compare
individual clipped band radii with `min(range, pixels / (2 * halfAngle * density))`.
The family's observed Detect/Observe thresholds are 26/62 px/m.

The specification explicitly supplies 250 px/m for each of the three types.
Type defaults are 12 m for domes, 40 m for bullets, and 20 m for PTZ; current
placement rules override some dome ranges. An occurrence's
positive target density wins; an authored zero uses the type's positive
fallback only in the native payload. The IFC tier A driver remains the authored
value. All four PTZ inputs get valid distance and density, including disabled
presets. The phase checks nested inputs and all five radii after regeneration,
and commits only matching read-backs. Repeating by Mark retains native identity.

## Status and updating an existing model

Phase 15 binds instance text `Status` under Identity Data for the payload's
product categories: architecture, rooms, equipment, security devices, service
segments, fittings, generic models and levels. Every subsequent transaction
stamps NEW and verifies it after regeneration, including unmarked segments and
nested elements. The shared-parameter filename is restored after binding.

Use the [45-camera update commands](#repeating-the-45-camera-design) above for
the current design. The Status pass covers existing containment and piping
without repeating their segment-creation phases. Native optical convergence
requires the independent live gate; the offline payload gate does not certify it.

### Export coverage and independent acceptance

The native exporter writes Common.Status for every exported physical element.
Rooms and levels retain NEW in internal Identity Data. The installed 2027.2
exporter's `InitPset_SpaceCommon` defines no Status property; the ordinary
Common export therefore supplies no space phase to the core converter.
Ports and openings also lack Common.Status, and grids have no applicable
Common template. Count these separately; do not claim 100% of raw IfcProduct
entities from physical-element coverage. No exported IFC is repaired to
supply missing Status or camera observations.

After retrieving the export as `out/native/export.ifc`, run parity against
an independently generated IFC:

```sh
env -u PYTHONPATH "$PY" -m dcbuild build-ifc
env -u PYTHONPATH "$PY" -m dcbuild parity out/native/export.ifc --dir out/base/ifc
```

The historical 0.3.3 acceptance used Sync **0.4.3**, core **0.8.1** and CCTV
**0.4.4**. Current measured inputs belong to the release acceptance record. The generator IFC
is the parity source; the native IFC seeds the live gate. Keep output outside
read-only dependency checkouts and disable Python bytecode there. Retain raw
receipts locally and publish only numeric acceptance artifacts.
