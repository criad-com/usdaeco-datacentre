# Changelog

## 0.5.0 — 2026-09-13

- Add the ordered `full` union: three storeys, all fitout, clash and reader fixtures.
- Publish nine normalized IFC4X3 deliveries with readable semantic twins, binary
  geometry, a USD-only root, a connected IFC root and a complete file inventory.
- Preserve cross-package handoff ports using IFC document references; restore
  their USD targets and retain types with a frozen-converter spatial post-pass.
- Gate monolithic parity, shared-only spatial definitions, eight package mute
  drills, plugin-free compliance, render freshness and the full-only 40 MB cap.
- Verify 244 checks, 0 failed; 229 tests; 29 structure rules; 12 fresh publications and
  six fresh S28 renders. Full occupies 22,038,135 / 40,000,000 bytes.
- Retain all five historical publication directories byte-for-byte. Fresh render
  receipts update renderer-code provenance while preserving reviewed pixels.
- Connected composition remains not proven pending the IFC file-format plugin
  and external-port-reference support. Nix evaluation is not proven: its resolved
  dependency set marks the selected IfcOpenShell package broken.

## 0.4.9 — 2026-09-12

- public re-pin: toolchain v0.3.10, validation core v0.9.4, Revit v0.1.4,
  Sync v0.5.4; the toolchain selects processing toolchain v0.4.0 recursively.
- Record exact tagged revisions and pristine runtime fingerprints. The
  supported Revit requirement remains `>=0.1,<0.2`.
- Vendor exactly the frozen core v0.8.4 and IFC v0.1.0 runtime paths with
  unchanged fingerprints. Remove their unpublished tags from flake inputs;
  retain historical generation pins as provenance records with local paths.
- Republish five variants and verify ten further independent publishes. All
  31 dist files and five cameras retain their bytes; five vanilla receipts
  change only toolchain provenance after fresh plugin-free rendering.
- Verify 204 checks, 0 failed; 213 tests; 29 structure rules; eight core
  validators and zero errors across all five variants. No ranges widened.
- Record one unsuccessful offline Nix attempt at nested processing toolchain
  v0.4.0. Nix packaging remains not proven; native variant rows remain not run.

## 0.4.8

- Verify 204 checks, 0 failed; 213 tests; 29 structure rules and five fresh
  plugin-free renders under toolchain v0.3.9. Nix packaging remains not proven.

- Expand two history archives into 26 inspectable files (24 JSON and two
  patches), preserving member paths and bytes; update historical links.
- Add the shared publication sweep to the gate and regression tests for
  tracked archives, including ignored directories and renamed binary content.
- Advance the toolchain to v0.3.9 to fix Nix package-version metadata;
  retain every other dependency pin. Refresh only the five vanilla receipts'
  toolchain provenance; all published stage, camera and image bytes stay fixed.

## 0.4.7

- public names → github.com/criad-com; pin toolchain v0.3.8.
- Retain every other dependency pin and all published stages and images.
  Refresh only the five vanilla receipts' toolchain provenance.
- Use the shared exact public-org exemption in the publication term sweep;
  retain rejection of private terms and hostnames.
- Verify 203 checks, 0 failed (4 native variants not run), 197 tests and
  29/0 structure rules. All five fresh renders pass with zero core errors.
- Record one unsuccessful offline Nix check: the uncached nested processing
  toolchain input cannot resolve; packaging remains not proven.

## 0.4.6

- Re-pin to train aeco-0.7.0: toolchain v0.3.5 and Revit v0.1.2;
  retain validation core v0.9.2 and the supported requirement ranges.
- Pin Sync v0.5.2 explicitly for Revit v0.1.2's package initialization,
  including the offline transport; make it available from source and Nix.
- Declare converter v0.1.0, generation core v0.8.4 and the recorded native
  Revit v0.1.0 evidence as fixtures, alongside historical toolchain v0.3.2
  rendering receipts. Preserve published USD and manifests.
- Refresh five vanilla toolchain receipts after fresh renders; retain all
  published stage, camera and image bytes. Sampled PNG bytes are not the
  S28 freshness criterion.
- Restrict pytest collection to this repository's tests so frozen dependency
  checkouts under `out/` do not run their own suites.
- Verify 203 checks, 0 failed (4 native variants not run), 196 tests and
  28/0 structure rules against frozen train sources; all 31 `dist/` files
  remain byte-identical to v0.4.5. Record the measured acceptance receipts.
- Record one unsuccessful offline Nix attempt: the network-disabled sandbox
  cannot connect to the daemon socket; packaging remains not proven.

## 0.4.5

- Verify 203 checks, 0 failed; 196 tests; 28 structure rules; five fresh
  vanilla renders and zero core validation errors.

- Generate L02 from the L01 room and door schedule, keeping all unedited
  partitions and the continuing stair identical. Contain roofs by the building.
- Move `wall.l2.v.016` 1 m east and extend it from 5.0 to 8.2 m; place the
  extra `door.office.2b` in that wall. Published floor matching finds exactly
  these two differences; partition totals are 43.0 and 46.2 m (+3.2 m).
- Record both planted edits and measured quantities in the floors manifest;
  refresh its overview and vanilla render. Keep the other four publications,
  source manifests and cameras byte-identical to v0.4.4. MIT retained.
- Hash tracked runtime files, excluding build metadata, and reproduce the
  toolchain pin from a fresh archive of v0.3.2. Correct the toolchain digest
  in dependencies and rendering receipts without changing other images.

## 0.4.4

- Retain the 5 mm exact pipe/tray gap and circular IFC sweeps; publish the
  near pipe with a 6 mm inscribed tessellation setting and the tangent pipe
  with a 1.2 mm circumscribed setting. Actual serialized chordal bands are
  5.7582 mm and 1.0636 mm; the tangent mesh penetrates the wall by 1.06354 mm.
- Stamp measured tolerances on the planted Mesh bodies and their partners.
  Record axes, radii, settings, measurements and verdicts in the clash manifest.
  Verify finite mesh-face witnesses and reject missing or inaccurate stamps.
- Keep the hard pipe geometry and four other publications byte-identical to
  v0.4.3; refresh only the clash overview and vanilla render. MIT retained.

## 0.4.3 — 2026-09-11

- Verify 193 checks, 0 failed (151 passes, 38 timings, 4 native variants
  NOT RUN), 179 pytest tests and all 28 structure rules. Core v0.9.2 loads
  eight validators; every variant has zero errors and two existing proxy
  classification warnings. The full publication term sweep has zero hits.
- Record one unsuccessful Nix attempt: the nested toolchain source is
  unavailable with outbound connections disabled; packaging is not proven.

- Publish five 1280×800 vanilla renders through the toolchain S28 isolated
  renderer. Keep flattened scratch crates out of git; commit camera layers
  and receipts that bind each picture to its source, camera code and pins.
- Add per-variant fresh rendering and core validation gate rows, stale-result
  regression tests, and a measured publication inventory.

- Adopt MIT and document runtime dependency licences. Pin toolchain v0.3.2
  and core v0.9.2 for validation, retaining the frozen generation inputs.
- Keep published data provenance at 0.4.2 for this presentation-only release;
  all published layer and manifest bytes remain unchanged.

## 0.4.2 — 2026-09-11

- Move the builder and live launcher to Revit integration v0.1.0; remove the
  local transport. Declare its supported range and pin the tested source and
  runtime hashes. Source execution and tests need no installed package.
- Use the canonical client's hash-verified uploads and paged replies. Add the
  11-script SHA-256 manifest and declared native enclave documentation.
- Add a base-only update command that requires the existing model and selects
  setup, parameters, nine camera batches and IFC4X3 export. Refuse non-base
  plans; retain existing rooms, doors and services.
- Rerun natively: 0 cameras created, 45 updated; G2 joins 527/527; CCTV v0.4.8
  imports 45 cameras, 45 sensors, 3 types and 7 presets, with 49 helpers folded
  and 0 unmatched. Preserve the verified export hash and separate native audit.
- Add explicit recorded native checks and separately counted NOT RUN variants.
  Republish the five generator-version manifests; all 15 USD layers and five
  overviews retain their previous bytes. Archive the superseded receipts.
- Pass 181 gate rows (139 correctness, 38 timings, 4 native variants NOT RUN),
  172 tests, all 42 IFC validations and all 26 structure rules; sanitization
  finds zero hits.
- Record the follow-up read-only receipt-fetch compilation failure and retained
  transport stop latch; no native request or mutation retry followed it.
  The single Nix attempt cannot resolve core v0.8.4 (HTTP 404); packaging remains
  not proven. Native non-base variants and the optional rollback suite remain
  future work.


## 0.4.1 — 2026-09-11

- Publish all five variants as portable USD roots with binary semantic and
  geometry layers, exact converter/core receipts, measured counts and hashes.
- Add independent byte comparisons, plugin-free composition and a 10 MB
  per-variant publication cap. Source runtime fingerprints enforce the pins.
- Adopt the data-repo skeleton, fixed README, use-case document, Apache-2.0
  licence, public flake inputs and a default `dcbuild` package. The gate uses
  the shared report and all applicable structure rules.
- Render one bounded Embree overview per variant using guide/proxy/render
  purposes, with space extents hidden in a temporary display layer. Record
  image hashes, camera bounds and source hashes; reject stale render receipts.
- Keep only the latest acceptance JSON per gate in `artifacts/`; preserve
  superseded receipts and diagnostics in one portable history archive.
  `build.sh` now invokes the publisher; `out/` remains ignored.
- Pass 172 gate rows (134 correctness, 38 informational), 164 tests and all
  42 IFC validations, with zero term-sweep hits. The single Nix attempt fails
  on public input resolution; packaging remains not proven.

## 0.4.0 — 2026-09-11

- Add deterministic inheritable YAML variants with dedicated output directories
  and measured count manifests; preserve the base plan and IFC geometry.
- Generate the repeated office floor, per-block roofs, stair continuation,
  declared partition/door drift and consequential boundary edits.
- Add ceiling voids, 23 fit-out products, temporary/final pods, and programmes
  A/B in XER and MSPDI with scope/workspace sidecars. Probe the historical XER
  parser: 10 tasks, 9 predecessor links, 3 WBS nodes.
- Plant three clash comparisons with numerical circular sweep geometry.
- Parameterize iris reader centre heights and publish three explicitly
  illustrative requirement files with expected per-reader verdicts.
- Pass 132 gate rows (103 correctness, 29 informational), zero failures,
  150 tests, and G1 across all 42 variant IFC files.
- Extend G0/G1, determinism and regression tests. Native Revit, published USD,
  template migration and measured downstream mesh verdicts remain separate.

## 0.3.4 — 2026-09-11

- Refresh tested inputs to core v0.8.4, CCTV v0.4.8 and Sync v0.4.5,
  recording release tags and exact revisions without changing generator behaviour.
- Pass 59 offline checks, zero failed, and 75 pytest tests. Native Revit and
  live Sync remain NOT RUN for this refresh.
- Rebuild v0.3.3 and the candidate against the same current family inputs:
  31 output comparisons pass, including binary USD geometry and all eight
  studies. Fifteen files are byte-identical; eight IFC creation timestamps
  and eight USD study receipt timestamps are the only differences. Retain
  raw hashes, a reproducible comparison command and explicit exceptions.
- Record clean sanitization and one offline Nix attempt: no flake is present.

## 0.3.3 — 2026-09-11

- Apply the shared exterior approach camera's new native pose. Both camera
  phases create zero and update 45; retain all camera GUIDs and bindings,
  all 30 rooms and the foreground model.
- Verify IFC4x3 parity at 527/527 products, 45/45 camera drivers, stable import
  at 45 cameras/45 sensors, and 1,514/1,514 physical-element phases.
- Replace the local census patch with direct execution of unmodified Sync 0.4.3.
  Pass 12/12 live cases, ten native rollbacks and 45/45 optical convergence
  within 0.001 rad / 0.001 m. Retain numeric evidence and source hashes.
- Pass 59 offline checks, zero failed, and 75 pytest tests. Retain the exact
  core 0.8.1 dependency, tier C/helper and phase limitations, native warnings,
  hardware boundaries and absent Nix flake as documented deviations.


## 0.3.2 — 2026-09-11

- Reuse a wide exterior opening's bullet for a shared approach, deriving the
  pole and aim from neighbouring door geometry. Preserve all 45 camera GUIDs;
  move one camera, with no additions, removals or per-camera coordinates.
- Pass exterior 5/5, including all 54 accessible plant-yard samples at
  recognition density; retain the engine's two enclosed samples as explicit
  exclusions from evaluation. Keep every other security-study target passing.
- Document the two supplementary column-blocked spine views as non-critical:
  both affected corridors have fixed coverage on all 288 samples.
- Pass 59 generator checks, 0 failed, and 75 pytest tests. Add full-face
  exterior optical checks and geometric rule regressions.
  Publish the full datacentre rows (177.554 s), unchanged-schedule provenance,
  and final family acceptance with the candidate metadata repairs disclosed.
  The native pole update remains a later live task.

## 0.3.1 — 2026-09-11

- Rerun native authoring for the 45-camera design: create 16 and update 29;
  repeat with zero creations and 45 updates. Retain all original camera
  bindings, all 30 rooms and the foreground model.
- Record fresh IFC4x3 parity: 527/527 required products, 45/45 cameras, and
  complete phases on 1,514 physical elements. The stable CCTV importer reads
  45 cameras and 45 sensors; helper-association and export limits remain explicit.
- Pass 12/12 live camera cases with 10 native rollbacks and two zero-request
  refusals; converge all 45 cameras over 98 half-angles and 245 clipped radii.
  Adapt the released Sync runner's two fixture census assertions from 29 to 45,
  preserving its native adapter, case logic, rollback checks and tolerances.
- Expand the offline payload gate to 56 checks, 0 failed, with 64 pytest tests;
  publish numeric native evidence, source hashes and reproduction commands.
- Retain tier C export, incomplete raw-product Status, unmatched FOV helpers,
  native warnings, the bullet-family substitute and absent Nix flake as deviations.

## 0.3.0 — 2026-09-11

- Resolve 45 cameras from shared placement rules, preserving all 29 existing
  GUIDs: 3.0 m door mounts, opposing corridor views, six fixed yard IR bullets
  and two fixed lobby domes. Keep three PTZ records unchanged.
- Verify 11/11 critical doors, 7/7 corridors and 3/3 lobby targets on the
  unchanged family schedule, with zero privacy hits or baseline hall errors.
- Retain exterior 4/5 and day/night yard 4/8 as findings. Actual IFC bodies
  contain schedule samples; camera placement alone cannot meet those targets.
- Add door optical preflight, study and IFC obstruction diagnostics, expanded
  generator claims, camera identity diff and measured acceptance evidence.
- Native model update remains a W-live follow-up; no live host was contacted.

## 0.2.2

- Report all gate command timings as INFO with numeric seconds in JSON;
  shared-machine elapsed time cannot fail a correctness check. Count
  informational rows separately from passes and preserve blocking failures.
- Document measured build times, Revit Common.Status coverage by product
  category, and the 12/40/20 m range and 250 px/m density defaults with the
  native formula-regeneration reason.
- Add regressions for slow measurements and retained correctness failures;
  record the offline release gate and packaging limitation separately from
  the existing live Revit evidence.

## 0.2.1

- Supply positive native target density so nested optical formulas refresh;
  verify all clipped band radii before committing each camera batch.
- Declare 250 px/m per camera type and ranges of 12/40/20 m for dome,
  bullet and PTZ. Preserve an explicitly authored zero in the IFC contract
  while supplying the native family's positive fallback.
- Bind and populate Identity Data Status NEW across authored product
  categories, including rooms and existing service segments. Record the
  exporter's Common.Status coverage separately from native input coverage.
- Retain camera identity on repeat, add payload regression checks, and record
  the disposable probe, native export parity and independent live acceptance.

## 0.2.0

- Author native level-based cameras in bounded batches, update by Mark, and
  retain contract IFC_GUIDs separately from Revit UniqueId.
- Add 30 interior rooms and a geometric door for the roller opening; export
  IFC4x3 with internal/common properties and base quantities.
- Validate native camera payloads offline; serialize live requests with status
  checks, checked reply pages and fail-stop handling.
- Require complete product joins, GUID agreement and camera pose/optical
  tolerances in Revit IFC parity. Record the spike and live acceptance,
  including the exporter and stable importer limitations.


## 0.1.0 — 2026-09-10

- Import a neutral, reproducible data-centre generator with a dedicated UUID
  namespace, Python CLI, IFC builder and environment-configured Revit driver.
- Resolve 29 cameras, 29 heads and three types from security rules; retain
  12 alarms and 11 iris readers. Emit door, area and camera study targets.
- Clear the five door/column collisions, with the constrained centre-corridor
  single-door deviation recorded in the facility brief.
- Write both IFC camera contract tiers, shared type representations, seven
  presets and three tours; add three exterior spaces and door approaches.
- Author NEW status through applicable Common Psets and count the grid
  exception. Stabilize all STEP ids, SET ordering and port nesting order.
- Add the blocking family-format gate, pinned semantic/identity manifest,
  resolver and writer tests, four camera unit combinations, and negative probes.

Native Revit cameras and full optical/coverage acceptance require the later
host and importer packages. Nix packaging is not supplied in this release.
