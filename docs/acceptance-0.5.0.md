# Publication acceptance — 0.5.0

The complete facility is delivered as nine IFC4X3 files, nine three-layer USD
twins, a USD-only entry, a connected entry and two review images.
The [complete gate receipt](../artifacts/check-0.5.0.json) records
**244 checks, 0 failed**: 194 passes, 45 informational measurements and
5 explicit not-run rows (connected composition and four historical native
variants). The [final source suite](../artifacts/pytest-0.5.0.txt) passes
**229 tests**. The publication sweep has **0 findings**, and the repository
term sweep has **0 hits**.

| Proof | Measured result |
|---|---|
| Source tests | 229 passed; validator failure paths and fixture ownership included |
| Publication sweep | 0 findings; IFC text accepted, archives rejected by extension and signature |
| Family structure | 29/29 rules pass |
| Republication | 12 fresh publications; all 6 variants byte-identical to committed data (39 files for full, 4 per historical variant) |
| S28 renders | 6 fresh plugin-free renders pass; full PNGs 1280×800, overview 145,472 bytes and vanilla 145,789 bytes |
| Historical publications | 30/30 files byte-identical across base, floors, pod, clash and iris |
| Full G0 | 14 design invariants pass; 3 storeys, 41 spaces, 111 walls, 47 doors, 80 columns, 47 cameras |
| Fixture union | 36 rooms, 2 voids, 3 yards; 2 ceilings, 2 pods; 6/10/3 fix products; 3 clash pipes; 11 readers, including one at 1.65 m |
| IFC schema + EXPRESS | 10/10 files pass: coordination plus 9 deliveries |
| USD census | 3,009 elements; 6,244 ports; 3,050 meshes; 64 types; 9 systems; 0 unparented elements |
| Monolithic parity | 9,308 identities, 12,425 prims, 6,070 relationship properties and 97 classification codes match |
| Spatial ownership | 46 spatial definitions plus one project definition, all in shared semantics; 799 spatial ancestor overs |
| External targets | 1,008 directional port targets (504 pairs), 9 served-spine targets, 0 cross-package members |
| Full cap | 22,038,135 / 40,000,000 bytes, including both PNGs |
| Plugin-free USD | Eight complete fallbacks; stock usdchecker --strict exit 0 |
| Connected root | 9 exact IFC asset tokens and matching header; composition not proven |

| Muted package | Remaining prims | Moved | Dangling targets / validator errors |
|---|---:|---:|---:|
| site | 12419 | 0 | 0 |
| arch | 12085 | 0 | 0 |
| structure | 12255 | 0 | 0 |
| cooling | 9208 | 0 | 184 |
| electrical | 7034 | 0 | 344 |
| it | 9432 | 0 | 480 |
| fitout | 12353 | 0 | 0 |
| security | 12279 | 0 | 0 |

Every dangling target equals the manifest prediction for that mute. No other
validator errors are permitted. The complete federation has zero core errors.

## Deviations

- The frozen converter has an overlay option, but that implementation drops
  catalog types and promotes spatial ancestors. A publisher post-pass clears
  and demotes spatial specs after ordinary conversion, retains catalog classes
  for the core inheritance contract, and keeps extents solely in shared.
- Legacy standalone discipline builders omit cross-discipline intake ports.
  Full publication instead partitions the complete coordination IFC graph.
  External links are delivered as IFC document references and resolved by the
  publisher. The future IFC reader must implement that translation; connected
  composition and direct IFC/twin equivalence through that plugin are not proven.
- The frozen converter's namespace is preserved to keep monolithic parity and
  consumer paths stable. The setting-out grid is retained in each IFC spatial
  skeleton; the frozen converter does not create USD grid prims. No zones are
  generated in this facility.
- The manifest excludes its own hash because self-hashing is circular. Every
  other delivered file, including images, is inventoried; the external vanilla
  receipt binds the manifest hash. Historical PNG pixels stay unchanged while
  their receipts update renderer-code provenance after fresh S28 rendering.
- The gate now adds the verified validation-core source directory to the Python
  import path so it runs with `PYTHONPATH` unset. Exact pin hashes still gate
  loading. Tests exercise both an empty source directory and an unimportable
  validator module; both fail loudly. Shell and flake gate commands use the
  same source-loading route. No dependency ranges or active release pins change.
- IFC sweep handling excludes only parsed identity fields: compressed GlobalIds
  can accidentally contain short legacy terms. Names, properties, headers and
  document locations remain inspected. Archives remain rejected by extension
  and signature, including disguised IFC files.
- One offline Nix attempt used an external registry and local family input
  overrides. Evaluation resolved a dependency set selecting Python 3.14 with
  IfcOpenShell 0.8.0 marked broken. Packaging remains not proven; no second
  attempt or lockfile was made. Source checks use Python 3.13, IfcOpenShell 0.8.5
  and USD 26.8. Revit execution for full remains not run.
