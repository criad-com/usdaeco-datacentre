# Revit acceptance — 0.3.3

Measured 2026-09-11 on Revit 2027.2 with the 0.3.2 camera design,
core 0.8.1, CCTV 0.4.4, unmodified Sync 0.4.3, Python 3.13,
IfcOpenShell 0.8.5 and USD 26.8. The [native/export measurements](history/acceptance-through-0.4.1/artifacts/revit-rerun-acceptance.json),
[live measurements](../artifacts/dc-live-rerun-acceptance.json) and
[source hashes](history/acceptance-through-0.4.0/artifacts/revit-rerun-provenance.json) retain separate evidence.
The [0.3.1 record](acceptance-revit-0.3.1.md) and its artifacts remain historical.
Raw exports, snapshots and complete receipts stay in ignored output directories.

Both camera phases created **0** and updated **45**. The existing
`sec.cam.ext.dock` moved to **(49.375, −18.25, 8.0) m**, with pan **90°**,
tilt **20.435531438°** and focal length **7.5 mm**. Its position error was
**7.16072335e-15 m**, against 0.001 m. All camera identities
survived; the other 44 positions stayed unchanged. The full live gate passed
**12/12**, including **45/45** optical convergence, with no runner patch.

| Native authoring and preservation | Observed |
|---|---:|
| First camera phase: created / updated / batches | 0 / 45 / 9 |
| Repeat phase: created / updated / batches | 0 / 45 / 9 |
| Native cameras / retained bindings / retained GUIDs | 45 / 45 / 45 |
| Dome / bullet / supplementary PTZ | 31 / 11 / 3 |
| Changed / unchanged camera positions | 1 / 44 |
| Repeat camera positions unchanged | 45/45 |
| Maximum native camera position error | 1.46549439e-14 m |
| Native bound products with Status NEW | 1,840/1,840 |
| Rooms unchanged, including version and parameter fingerprints | 30/30 |
| Foreground element fingerprints unchanged / foreground changes | 6,190/6,190 / 0 |
| Native warnings before / after authoring | 466 / 466 |
| After live gate: cameras / rooms unchanged | 45/45 / 30/30 |

| IFC4X3 and independent import | Observed |
|---|---:|
| Export transfer SHA-256 agreement | 1/1 |
| Cameras / rooms / doors / walls / columns | 45 / 30 / 41 / 92 / 80 |
| Required product joins | 527/527 |
| Racks / equipment / doors / walls / columns / cameras joined | 160 / 109 / 41 / 92 / 80 / 45 |
| Camera GUID agreement | 45/45 |
| Position comparisons / maximum error | 45/45 / 7.10542736e-15 m |
| Pan comparisons / maximum error | 45/45 / 1.42108547e-13 deg |
| Tilt comparisons / maximum error | 45/45 / 2.84217094e-14 deg |
| Focal comparisons / maximum error | 45/45 / 0 mm |
| Camera position / angle and focal tolerances | 0.001 m / 1e-6 deg or mm |
| Other-product placement / geometry-centre tolerance | 0.05 / 0.15 m |
| Physical elements with Common.Status NEW | 1,514/1,514 |
| Raw products with Common.Status NEW | 1,514/3,639 (41.605%) |
| Rooms: internal Status NEW / Common.Status | 30/30 / 0/30 |
| Levels: internal Status NEW / Common.Status | 3/3 / 0/3 |
| Missing Common.Status: ports / openings / spatial products | 2,048 / 40 / 35 |
| Grids without a Common template | 2 |
| Core physical elements / authored phases | 1,514 / 1,514 |
| Core spaces / authored space phases | 30 / 0 |
| Core conversion and census | 9.440 s |
| Stable CCTV imported cameras / sensors / presets | 45 / 45 / 7 |
| Imported catalog types / folded helpers / unmatched helpers | 24 / 1 / 48 |
| Plugin-free stages / composition errors / family plugins | 3 / 0 / 0 |
| Core / CCTV / Sync world transforms compared | 5,142 / 5,185 / 5,305 |
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
| Seed-derived expected / observed cameras | 45 / 45 |
| Changed runner assertions | 0 |
| Cases / native rollbacks / zero-request refusals | 12/12 / 10/10 / 2/2 |
| Repeat mutations / repeat requests | 0 / 0 |
| Complete optical convergence | 45/45 |
| Half-angle comparisons / clipped radius comparisons | 98/98 / 245/245 |
| Maximum half-angle / radius error | 2.22044605e-16 rad / 3.55271368e-15 m |
| Half-angle / radius tolerance | 0.001 rad / 0.001 m |
| Native warnings retained per native case | 466 |
| Native blocking errors | 0 |
| Complete gate elapsed time | 657.742 s |
| After live gate: foreground changes | 0 |

| Offline release gate | Observed |
|---|---:|
| check.py | 59 checks, 0 failed |
| Correctness passes / informational timings | 51 / 8 |
| pytest | 75 passed |
| Serialized camera sensor heads / pose drivers | 45/45 / 225/225 |
| Term sweep | 0 hits |
| Nix attempts / passes / repository flakes | 1 / 0 / 0 |

## Reproduce

Follow the [Revit guide](../revit/README.md#repeating-the-45-camera-design):
resolve the plan; run helpers, setup, parameter binding and cameras; repeat
cameras and export in the same session. Retrieve the IFC by the authorized
file-transfer route into ignored `out/revit/`, verify its hash, and run
`dcbuild parity` against an independently generated IFC. Convert that native
export with core, import with CCTV, then initialize Sync without `--kind-import`,
read back cameras and run `revit/live.py`. The launcher imports the released
runner directly, retains its exact source and hash, and lets the seed supply
the expected census. Ordinary `check.py` and pytest are offline; they do not
re-execute or certify this native acceptance.

## Deviations and boundaries

- The shared core source had advanced to 0.8.3, while CCTV 0.4.4 and Sync 0.4.3
  declare an exact core 0.8.1 dependency. This run extracted the previously
  verified 0.8.1 revision and its committed codeless resources into owned
  scratch space. No dependency manifest, sibling checkout or runner was patched.
  Exact source and plugin hashes are in the provenance record.
- Only setup, parameter binding, cameras and export were rerun. Existing
  architecture, rooms, equipment and services were retained; repeating service
  creation phases can duplicate segments. The first read-only audit probe
  needed a missing collector filter corrected before any authoring began.
- Common.Status remains incomplete across raw products. Physical-element phases
  are complete; space phases remain unauthored. No export properties were repaired.
- Revit remains a tier C camera route. The importer recovers all 45 cameras and
  heads, but 48 of 49 FOV helpers remain unmatched and the exported catalog
  produces 24 imported types. Authoritative tier A export and complete helper
  association are not proven. Native Sync uses family ownership for optical
  observations; its arc-model convergence is separate from IFC driver parity.
- The 466 baseline native warnings remain, including duplicate-Mark warnings;
  the 45 top-level camera Marks and bindings are unique. This is not a
  warning-free model.
- The outdoor bullet retains the specified dome-family substitute. The native
  position and optical guides are verified; pole structure, mounting hardware,
  installation access, lighting, recording and operational recognition are not.
  The [exterior study's](acceptance-exterior.md) column exceptions and two
  pipe-enclosed samples remain separate design evidence.
- One `nix flake check --offline` attempt found no flake in this repository or
  its parents. Nix is not proven; no nested input was resolved and no second
  attempt was made.
