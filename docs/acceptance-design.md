# Camera design acceptance — 0.3.0

Measured on 2026-09-11 with Python 3.13, OpenUSD 26.8, IfcOpenShell 0.8.5
and Embree. Full security-design acceptance is **not achieved**. The generator
now resolves 45 cameras; all feasible indoor studies pass, while fixed
exterior geometry prevents three required study rows from passing.

[Study JSON](history/acceptance-through-0.4.0/artifacts/camera-study.json) records the unchanged family
schedule, exact source revisions, file hash, results and timings. Use the
[README commands](../README.md#camera-design-rules) with a fresh output directory.

| Real study row | Fixed-covered | Status |
|---|---:|---|
| DC-critical-doors | 11/11 | PASS; every face sample, ≥250 px/m, ≤3 m |
| DC-corridors | 7/7 | PASS; 0.5 m grid, ≥62.5 px/m, fraction ≥0.9 |
| DC-external | 4/5 | FINDING; plant approach pipes |
| DC-yard-day | 4/8 | FINDING; three pads and plant approach |
| DC-yard-night | 4/8 | FINDING; same fixed coverage as day |
| DC-lobby | 3/3 | PASS; ≥125 px/m, all samples |
| DC-privacy-baseline | 0 hits | PASS |
| DC-hall-rule-baseline | 0 errors | PASS |
| DC-revit-parity | 11/11 | PASS; arc geometry only, no native acceptance |

Critical-door minimum density is 343.741953 px/m and maximum lens distance
2.945658 m. The corridor spine fraction is 0.976852; the other six corridors
reach 1.0. Lobby area and both door faces reach 1.0. Generator-yard fixed
fractions are 0.870536 each; heat-rejection yard is 0.736111. The plant-door
external fraction is 0.928571, and its yard approach fraction is 0.964286.
Four other external approaches reach 1.0 in both day and night studies.

The fresh conversion contains 2,954 elements and 2,954 authored phases,
33 space extents and zero unparented elements. Import and derivation reproduce
45/45 sensors, three types, seven presets and three tours, with zero skips.

## Generator gate

The [generator report](history/acceptance-through-0.4.0/artifacts/check-design.json), produced inside the
isolated family run, reports **53 checks, 0 failed**: 45 correctness passes
and eight informational timing rows. Pytest reports **63 passed**. G0's seven
invariants and G1 schema/EXPRESS checks on all eight IFC files pass. Combined
and federated camera identities agree 45/45. All 9,244 applicable products
carry NEW Status; the single grid exception is counted. Both independent
plan/target resolves and all eight normalized IFC files are deterministic.
The pinned semantic and identity manifest contains 769 identities.

## Why exterior acceptance is impossible with camera changes alone

[sample-obstructions.json](history/acceptance-through-0.4.0/artifacts/sample-obstructions.json) contains
strict interior tests against actual closed convex IFC body meshes, using a
1e-6 m tolerance. Every body is checked for convexity and closed topology.
The unchanged study includes these points inside solid geometry:

| Target | Samples inside solids / total | Maximum possible fraction |
|---|---:|---:|
| Generator yard A | 76/672 | 0.886905 |
| Generator yard B | 76/672 | 0.886905 |
| Heat-rejection yard | 128/576 | 0.777778 |
| Plant door face | 2/56 | 0.964286 |

The yard pass fraction is 0.9, and door faces require 1.0. Even ideal camera
coverage outside these bodies cannot meet either requirement. Plant supply
and return pipes physically cross the door approach. The retained targets,
obstacles, densities and pass fractions are unchanged. The next design action
requires coordination of the plant-door pipe route and the intended accessible
yard surveillance domain; that action is outside this camera-only release.

## Identities and native follow-up

[Camera manifest diff](history/acceptance-through-0.4.0/artifacts/camera-manifest-diff.json): 29/29 existing
GUIDs retained; zero removals or replacements; 16 new rule-derived ids.
All three original PTZ records are unchanged. The other 26 existing cameras
receive new pose/range/focal/mount drivers as applicable. The 11 iris readers
retain identity and door association, with positions corrected onto the
approach face. The pinned resolved manifest contains 769 identities.

New ids are corridor `corr.spine.5/.6`, `corr.w.2`, `corr.c.2`, `corr.e.2`,
`corr.s.2`, `ocorr.0.2`, `ocorr.1.2` under `sec.cam.corr.`, two
`sec.cam.yard.<gen.a|gen.b|hr>.fixed.<1|2>` per pad, and
`sec.cam.lobby.fixed.1/.2`.

The native model needs a **W-live rerun**. Existing camera instances update by
Mark; the camera phase creates the 16 additions. Re-export and fresh import
must then verify 45 camera identities and drivers. Earlier native acceptance
of 29 cameras does not certify this revision. No native endpoint was contacted.

## Deviations

- Exterior 5/5 and yards 8/8 are not met for the geometric reasons above.
- The upper office corridor has 3.0 m clear height. Its mount is capped at
  2.9 m above its floor instead of placing a 3.5 m mount above the roof.
- Two fixed domes are used in the lobby to cover both ends and the complete
  area. The total remains at the declared 45-camera recorder allowance.
- The schedule uses a 1.5 m region grid and door heights 0.3–2.05 m, including
  0.25 m increments. These existing samples were retained. The independent
  door optical preflight additionally checks the unsampled 2.1 m top corners.
- Sampling is finite. Geometric density does not certify lighting, compression,
  recognition quality or operational night illumination.

- One `nix flake check --offline` attempt failed because this generator and
  its parents contain no `flake.nix`. No second attempt or network resolution
  was made; Nix packaging is not proven.

## Family integration run

The stable scenarios checkout is read only. A disposable copy uses the
[recorded patch](history/acceptance-through-0.4.0/artifacts/family-runner.patch): exact candidate/core pins
and matching flake revisions, 45 cameras / 2,954 elements in the census,
and an explicit PTZ-only camera scope in the sole-PTZ negative control.
The [five schedule function hashes](history/acceptance-through-0.4.0/artifacts/family-schedule-hashes.json)
are identical before and after the patch. No baseline scope, density,
sampling, phase, pass fraction or privacy exclusion changed.

The initial aggregate referenced stable plugin paths while the CCTV closure
builder referenced isolated copies, and rejected the duplicate core descriptor.
The run resumed with one isolated aggregate and a checkpoint for the four
completed libraries: core 42/42, buildup 20/20, wall 48/48 and pipe 41/41.
The patch lets the existing reuse option accept a partial checkpoint; those
four checks were not repeated. Their timing values are explicitly unrecorded.

The Sync library check still asserts a 29-camera seed. It stops after importing
45 cameras / 45 sensors / zero unmatched from this candidate. This is retained
as an integration failure; the owning library needs a census update. Its
source and assertions were not modified in this lane.

An [additional 1.6 m corridor study](history/acceptance-through-0.4.0/artifacts/corridor-height-1.6.json)
also passes 7/7. It raises each corridor grid point by 0.1 m in an anonymous
session and reruns the same coverage engine, leaving the original 1.5 m
schedule and report untouched. After the README's main study command:

```sh
env -u PYTHONPATH "$PY" scripts/corridor_height.py out/study --scenarios "$AECO_SCENARIOS_SOURCE" --pluginset "$AECO_PLUGINSET" --output out/corridor-height-1.6
```

Final [family rows](family-gate.md) and [JSON evidence](history/acceptance-through-0.4.0/artifacts/family-gate.json):
**54 rows, 2 failed**; 42 PASS, four FINDING, four NOT RUN and two SKIP.
Full acceptance is false. The other failed row, `DC-column`, counts columns
on secondary sightlines to the centre and east corridors. Both target regions
have fraction 1.0 and fixed coverage; all critical-door results have zero
column blockers. The unchanged row requires no column blocker on any attempted
view, a stronger condition than target coverage. No column or obstacle was
removed to satisfy it.

The datacentre portion takes **149.771 s** (240 s limit), has zero unexplained
implementation errors, nine security design errors, 160 existing native port
gaps and 4,000 warnings. Independent builds produce identical normalized
stages, study hashes/results and findings; repeat study execution reuses
**136/136 views**. IFC camera sync accepts three mutations, preserves the GUID,
has zero position error/pending edits and sends zero mutations on repeat.
Ten resulting stages compose without family plugins. Gate regression tests:
**48 passed**. Source/artifact sanitization and links pass.

The tray negative control lowers the actual spine tray by 0.9 m: critical doors
change from 11/11 covered to one uncovered, with `Data_Spine_A_Seg_1` named in
the finding for `door_hall_a_s`. The inherited runner retains its conservative
FINDING label; the recorded before/after results now provide that attribution.
The seeded privacy/hall tests detect the intrusion (one expected hall error);
the unchanged baseline still has zero privacy hits and zero hall errors.

Bonsai and Revit are NOT RUN. Renders are SKIP because the usd-dev renderer is
unavailable. These rows do not count as passes, and no native host was contacted.


## Release integration follow-up

Reviewer steering classifies the Sync failure as: **sync D-* expectations
pinned to 29 cameras; fixed in sync (IMP3)**. That fix was not rerun here;
the recorded gate still shows the measured failure at Sync v0.4.1.
Bonsai remains honestly NOT RUN from the explicit IFC-only execution.

The preceding packaging release merged after this branch and PR were already
published. Its documentation and dependency pins were incorporated by merging
main, preserving the no-force-push rule. The requested rebase would have
rewritten the published branch. Generated plan, resolver, IFC writer and their
tests are unchanged from the accepted 53-check run. Newly announced core/CCTV
releases were not substituted into the recorded, exactly pinned evidence.
