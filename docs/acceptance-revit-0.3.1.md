# Revit acceptance — 0.3.1

Measured 2026-09-11 with Revit 2027.2, core 0.8.1, CCTV 0.4.2,
Sync release v0.4.2, Python 3.13, IfcOpenShell 0.8.5 and USD 26.8.
The [export artifact](history/acceptance-through-0.4.0/artifacts/revit-export-acceptance.json),
[live numeric artifact](history/acceptance-through-0.4.0/artifacts/dc-live-acceptance.json),
[offline gate](history/acceptance-through-0.4.0/artifacts/check-revit.json) and
[source hashes](history/acceptance-through-0.4.0/artifacts/revit-provenance.json) record separate evidence.
This is historical evidence; the [Revit guide](../revit/README.md#repeating-the-45-camera-design)
now describes the later unmodified-runner acceptance.
Native exports and complete receipts remain under ignored output directories.

| Native authoring | Observed |
|---|---:|
| First camera phase: created / updated | 16 / 29 |
| Second camera phase: created / updated | 0 / 45 |
| Batches per camera phase | 9 |
| Native cameras / unique native bindings | 45 / 45 |
| Dome / bullet / supplementary PTZ | 31 / 11 / 3 |
| Original camera bindings and GUIDs retained | 29/29 |
| New cameras with Status NEW | 16/16 |
| Native bound products with Status NEW | 1,840/1,840 |
| Rooms unchanged, including identity, version and parameter values | 30/30 |
| Foreground changes | 0 |
| Native warnings before / after authoring | 464 / 466 |
| Additional duplicate-Mark warnings / duplicate top-level camera Marks | 2 / 0 |

| IFC4X3 and independent import | Observed |
|---|---:|
| Cameras / rooms / doors | 45 / 30 / 41 |
| Walls / columns | 92 / 80 |
| Required product joins | 527/527 |
| Racks / equipment / doors / walls / columns / camera joins | 160 / 109 / 41 / 92 / 80 / 45 |
| Camera GUID agreement | 45/45 |
| Camera position comparisons / maximum error | 45/45 / 7.10542736e-15 m |
| Pan comparisons / maximum error | 45/45 / 1.42108547e-13 deg |
| Tilt comparisons / maximum error | 45/45 / 2.84217094e-14 deg |
| Focal comparisons / maximum error | 45/45 / 0 mm |
| Camera position / driver tolerances | 0.001 m / 1e-6 deg or mm |
| Other-product placement / geometry-centre tolerance | 0.05 / 0.15 m |
| Physical elements with Common.Status NEW | 1,514/1,514 |
| Raw products with Common.Status NEW | 1,514/3,639 (41.605%) |
| Rooms: internal Status NEW / Common.Status | 30/30 / 0/30 |
| Levels: internal Status NEW / Common.Status | 3/3 / 0/3 |
| Missing Common.Status: ports / openings / spatial products | 2,048 / 40 / 35 |
| Grids without a Common template | 2 |
| Core physical elements / authored phases | 1,514 / 1,514 |
| Core spaces / authored space phases | 30 / 0 |
| Core conversion and census | 9.445 s |
| Stable CCTV imported cameras / sensors / presets | 45 / 45 / 7 |
| Imported catalog types / folded helpers / unmatched helpers | 23 / 1 / 48 |
| Plugin-free stages / composition errors / family plugins | 3 / 0 / 0 |
| Core / CCTV / Sync world transforms compared | 5,142 / 5,185 / 5,306 |
| Fallback types per stage | 9 |

| Live camera gate | Passed | Requests | Native rollback |
|---|---:|---:|---:|
| C-create | 1 | 1 | 1 |
| C-move | 1 | 1 | 1 |
| C-pan-tilt | 1 | 1 | 1 |
| C-zoom-clamped | 1 | 0 | 0 |
| C-preset | 1 | 1 | 1 |
| C-type-swap | 1 | 1 | 1 |
| C-delete | 1 | 1 | 1 |
| C-derived-authored | 1 | 0 | 0 |
| X-converge-cctv | 1 | 1 | 1 |
| D-live-nested-create | 1 | 1 | 1 |
| D-live-repeat | 1 | 1 | 1 |
| D-live-converge-all | 1 | 1 | 1 |

| Live measurements | Observed |
|---|---:|
| Cases / native rollbacks / zero-request refusals | 12/12 / 10/10 / 2/2 |
| Repeat mutations / repeat requests | 0 / 0 |
| Complete optical convergence | 45/45 |
| Half-angle comparisons / clipped radius comparisons | 98/98 / 245/245 |
| Maximum half-angle / radius error | 2.22044605e-16 rad / 3.55271368e-15 m |
| Half-angle / radius tolerance | 0.001 rad / 0.001 m |
| Native warnings retained per native case | 466 |
| Native blocking errors | 0 |
| Elapsed from run directory and report timestamps | 575.524 s |
| Cameras unchanged after live rollback / foreground changes | 45/45 / 0 |

| Offline release gate | Observed |
|---|---:|
| check.py | 56 checks, 0 failed |
| Correctness passes / informational timings | 48 / 8 |
| pytest | 64 passed |
| Serialized camera sensor heads / pose drivers | 45/45 / 225/225 |
| Term sweep | 0 hits |
| Nix attempts / passes / repository flakes | 1 / 0 / 0 |

## Deviations

- The released Sync v0.4.2 fixture runner asserts 29 cameras twice. The local
  launcher changes those two assertions to 45, retains the released and adapted
  source with hashes and a diff, and refuses an unexpected source layout.
  Native adapters, all 12 cases, rollback checks and optical tolerances are
  unchanged. This is acceptance with the disclosed census adaptation; the
  unmodified released runner does not accept 45 cameras. The released source
  still identifies its Python package as 0.4.1; the source revision is recorded.
- The native authoring reran setup, parameter binding, cameras and export.
  Rooms and the existing architecture, equipment and service geometry were
  retained. Repeating containment and piping can duplicate segments.
- Full raw-product Common.Status coverage is not met. Rooms and levels retain
  Status NEW only in internal data; ports, openings and other spatial products
  lack Common.Status. Core physical-element phases are complete; space phases
  remain unauthored. No export properties or native observations were repaired.
- The stable CCTV importer identifies all 45 cameras and heads, but the native
  export has 23 camera catalog types and 49 FOV helper rows; only one helper is
  folded and 48 remain unmatched. These are helper-association limitations,
  not missing cameras. Revit remains a tier C route; authoritative tier A
  export and complete independent helper import are not proven. Native Sync
  reads observations by family ownership for the live comparisons.
- Two additional native duplicate-Mark warnings were retained. All 45 top-level
  camera Marks and bindings are unique. The live cases preserve native warnings
  and verify rollback; the baseline model is not warning-free.
- The outdoor bullet uses the dome family's duplicated symbol, as the existing
  substitute recipe specifies. Geometric and optical agreement does not prove
  hardware, lighting, recording or security coverage. The 0.3.0 exterior and
  yard coverage findings remain; that design study was not rerun here.
- The single offline Nix attempt found no flake in this repository or its
  parents. No Nix pass or nested-input failure is claimed. Live evidence is
  recorded separately and is not enforced by the offline generator gate.
