# Generator 0.4.0 acceptance

The full gate completed with **132 checks, 0 failed**: **103 correctness
passes and 29 informational rows**, including 28 timing observations and one
unavailable structure-lint row. Pytest passed **150 tests**. The captured
0.3.4 baseline independently passed its original **59 checks / 75 tests**.
No native host or USD publisher was used.

| Row | Measured result |
|---|---|
| base | Plan and targets match 0.3.4 byte-for-byte; all 8 IFC files match after only timestamp/version normalization. Original 59 gate rows retained. 2 storeys, 30 rooms, 3 yards, 92 walls, 41 doors, 80 columns, 45 cameras, 11 readers. |
| floors | 3 storeys; L01 and L02 each have 6 rooms. 36 rooms, 3 yards, 112 walls, 47 doors, 47 cameras. One moved partition and one extra door, plus explicitly declared return/trim consequences. Prototype property and two stair flights verified. All 8 IFC files pass G1. |
| pod | 2 voids, 2 ceilings, 2 pod products (1 TEMPORARY); 6 first-fix, 10 second-fix, 3 third-fix products. 23 added products total. Both ten-activity programmes emit XER, MSPDI and two sidecars each. All 9 IFC files pass G1. |
| programme probe | Historical importer parses A.xer: 10 tasks, 9 predecessor links, 3 used WBS nodes, 1 project, 1 calendar at 24 hours/day. A produces the 3 expected rule families (4 access pairs, 1 occupation pair, 2 inspection findings); B produces none. |
| clash | 3 additional circular pipe sweeps; hard crossing, 5 mm clearance over 2 m, zero-distance tangency. Axes, OD and wall plane recorded and verified in IFC. All 9 IFC files pass G1. Default tangent mesh has 0 m gap; false penetration is not reproduced. |
| iris | 11 readers: 10 at 1.2 m centre, 1 at 1.65 m. 3 illustrative requirement files; 10 pass all, office-link fails accessibility/employer and passes datasheet. IFC measures/geometry verified in metres and millimetres. All 8 IFC files pass G1. |
| determinism | 5/5 variants: independent plan bytes and combined IFC bytes agree (IFC header timestamps normalized). Both programmes and all sidecars agree independently for pod and clash. |
| gate | 132 checks, 0 failed; 150 pytest tests; 42/42 primary IFC files pass G1; repository term sweep 0 hits. |

Commands (set `PY` to the prepared Python environment):

```sh
env -u PYTHONPATH "$PY" check.py --report out/check.json
env -u PYTHONPATH "$PY" -m pytest -q
```

Evidence: [gate receipt](history/acceptance-through-0.4.0/docs/check-result.json),
[portable acceptance summary](history/acceptance-through-0.4.0/artifacts/generator-0.4.0.json),
[base byte hashes](../manifests/base-v0.3.4-bytes.json),
[XER parser receipt](../manifests/programme-parser-probe.json),
[tangent mesh probe](../manifests/clash-mesh-probe.json), and the five
`manifests/demo-datacentre-01.<variant>.json` files. Tested family refs remain
in [dependencies.json](../dependencies.json).

## Deviations

- IFC creation timestamps already varied in 0.3.4. The comparison normalizes
  that FILE_NAME field and the new generator version stamp; raw timestamped
  IFC byte identity is not claimed. Plan and target bytes have no exceptions.
- Keeping the WC unchanged while moving only the meeting/kitchen partition
  requires an L-shaped meeting footprint. One 1 m return is added and three
  connected wall ends change; every consequence is declared. There is no claim
  of a 3.2 m partition quantity delta. The base retains its historical split
  slab; floors uses one notched slab per upper storey/block.
- The specified temporary pod depth exceeds the corridor width. Its requested
  x=20..22.4 position overhangs by 0.3 m at each side. The +2.6 ceiling datum is
  treated as board top / void bottom; board soffit is +2.5875. Pod bodies are
  bounding envelopes. Programme B's alternative parking is in its placement
  sidecar; the IFC depicts A's temporary position.
- The exact tangent fixture cannot guarantee false mesh penetration. Default
  tessellation (1 mm linear / 0.5 rad angular deflection, 52 vertices) measured
  zero gap. The requested 1.2 mm false penetration remains an illustrative
  downstream expectation, not a proven result. Exact geometry is preserved.
- The base reader's historic 1.4 m datum is its body base. Iris uses real centre
  heights and adds mounting properties and matching pull-side door swings;
  those new properties are absent from base to preserve its byte contract.
- The one offline Nix attempt found no flake. Installed toolchain v0.1.0 has no
  structure subcommand; lint is informational NOT RUN. Template migration,
  native Revit changes, USD publishing and application-level P6/MS Project
  imports remain outside this generator change. Open fit-out port endpoints
  do not imply a complete services network.
