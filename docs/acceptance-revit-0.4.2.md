# Revit acceptance — 0.4.2

Measured 2026-09-11. The builder uses `usdaeco_revit.transport.Client` from
Revit integration v0.1.0. The existing base model was resident in the background;
the update reused it and selected helpers, setup, parameters, cameras and export.
The [native receipt](../artifacts/revit-0.4.2.json) records source hashes, exact
inputs and the export SHA-256. Raw native data and logs remain in ignored output.

| Native base update and export | Measured |
|---|---:|
| Initial GET /status | READY; no evaluation before it |
| Existing file / resident document / background match | yes / yes / yes |
| Baseline native warnings | 466 |
| Camera batches | 9 |
| Cameras created / updated | **0 / 45** |
| Driver exit code / export format | 0 / IFC4X3 |
| Native camera audit | **45/45**; GUID, level, position and optical drivers |
| Export bytes | 26,824,960 |
| Export transfer SHA-256 agreement | 1/1 |
| Exported cameras / rooms / doors / walls / columns | 45 / 30 / 41 / 92 / 80 |
| G2 required product joins / failures | **527/527 / 0** |
| Racks / equipment / doors / walls / columns / cameras joined | 160 / 109 / 41 / 92 / 80 / 45 |
| Maximum exported camera position error | 7.105427357601002e-15 m |
| Camera position tolerance | 0.001 m |
| Other-product placement / geometry-centre tolerances | 0.05 / 0.15 m |

The export hash is
`f7bfe155c9a44bdf776b9db026b05a37615d46ddc21a2bbd2a4600eb74358472`.
G2 used a separately generated base IFC from the current specification, with
its existing complete-join, identity, camera pose and optics assertions intact.
Architecture, rooms and service creation phases were not repeated.

| Independent family import | Measured |
|---|---:|
| Converter / core / CCTV inputs | v0.1.0 / v0.8.4 / v0.4.8 |
| Converted elements / element phases / unparented | 1,514 / 1,514 / 0 |
| Spatial referents / space extents / ports | 35 / 30 / 2,048 |
| Meshes / unclassified elements | 1,544 / 318 |
| Imported cameras / sensors | **45 / 45** |
| Types / presets | 3 / 7 |
| Folded helpers / unmatched | 49 / 0 |
| Plugin-free stage roots / composition errors | 2/2 / 0 |
| Fallback mappings / used concrete types, each root | 8 / 6 |

CCTV v0.4.8 now folds all 49 helper subinstances from this export. This differs
from the older reader's 48 unmatched helpers in the historical
[0.3.3 native receipt](acceptance-revit.md). Converter classification gaps and
the documented tier C / Common.Status limitations remain separate from camera
census and G2 success; no exported property was repaired or invented.

| Offline release acceptance | Measured |
|---|---|
| Shared transport | Imported by driver and live launcher; local transport removed |
| Script enclave | 11/11 source hashes; complete inventory checked before submission |
| Update dry run and fake endpoint | PASS through the real shared client |
| `check.py` | **181 checks, 0 failed**: 139 PASS / 38 INFO / 4 NOT RUN |
| Pytest | **172 passed** |
| Structure / sanitization | 26/26 rules; 0 term-sweep hits |
| Variant IFC validation | 42/42 files |
| Nix attempts / successes | 1 / 0; core v0.8.4 input returned HTTP 404 |
| Native floors / pod / clash / iris | NOT RUN; further families required, including pods and ceilings |
| Optional 12-case rollback suite | NOT RUN in this release |

The ordinary gate makes no native requests. It verifies the committed update,
parity and importer measurements against the recorded builder/script/transport
sources, and counts the four native-variant NOT RUN rows separately from passes.
All preceding generator, IFC, publication, render and determinism checks remain.
The [full gate receipt](../artifacts/generator-0.4.2.json) retains every row.
The 15 published USD layers and five PNG overviews retain their 0.4.1 bytes;
only each publication manifest's generator version changes to 0.4.2.

Follow the [builder guide](../revit/README.md#repeating-the-45-camera-design)
for source-checkout configuration, `--update`, export parity and importer census.
Source execution requires no installed package or setuptools. The optional
`revit/live.py` launcher imports the released Revit integration's camera runner
unchanged and records its source hash; it no longer imports the old Sync runner.

## Deviations

- After the completed native audit and hash-verified IFC download, a follow-up
  read-only fetch of the detailed camera receipt failed C# compilation because
  `Dc` was no longer available in the REPL session. The canonical client set its
  stop latch. No mutation was replayed, no further native request was made, and
  the latch remains for operator inspection. Post-transfer warning counts and
  the detailed camera receipt download are not proven. The earlier 45/45 native
  audit and complete IFC export remain valid independent evidence.
- The first importer invocation followed conversion in a process whose USD
  registry had already initialized without CCTV. It refused before importing.
  A fresh process registered the released plugins first and completed 45/45.
  The documented reproduction command now registers before the first USD stage.
- The update retains existing rooms, doors and services. It is not a rebuild of
  the non-base variants, and the optional rollback suite was not rerun. Its
  previous 12/12 evidence retains its original versions. Further native family
  work, including pods and ceilings, is deferred.
- Exactly one `nix flake check --offline --no-write-lock-file --option
  substituters ''` attempt failed resolving the public core v0.8.4 input (HTTP
  404). No second attempt or lockfile was made. Flake packaging and native C#
  compilation through Nix are not proven; the scripts are a declared enclave.
- Frozen core v0.8.4 remains the tested importer dependency because converter
  v0.1.0 and CCTV v0.4.8 target it. Dependency checkouts were read only. The
  superseded generator and native receipts remain in the
  [history directory](history/acceptance-through-0.4.1/).
