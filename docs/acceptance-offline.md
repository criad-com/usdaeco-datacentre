# Offline acceptance — 0.2.2

Measured 2026-09-11 using Python 3.13, ifcopenshell 0.8.5, numpy,
pydantic 2, PyYAML and pytest. Set `PY` to the environment's Python executable
and run from the checkout:

```sh
env -u PYTHONPATH "$PY" check.py --report out/check.json
```

The gate runs pytest itself. The committed [JSON report](history/acceptance-through-0.4.0/)
is the output of this run. All timing rows print `INFO` and retain numeric
`seconds` alongside `status: "INFO"` and `ok: null`. They cannot change the
exit status and do not count as passes. The family's final line counts all
rows: `total = passed + failed + informational`. There are no elapsed-time
correctness budgets; subprocess exit codes and semantic checks still block.

| Acceptance | Observed |
|---|---:|
| Family-format gate | **47 checks, 0 failed** |
| Correctness passes / informational timing rows | **39 / 8** |
| pytest | **57 passed**, 5.66 s reported by pytest |
| Timing regression smoke | **4 passed**: 15.17, 45 and 120 s stay INFO; a failed build still fails |
| First / independent second full IFC build | **14.297 / 14.318 s (INFO)** |
| G1 schema and EXPRESS validation | **8/8 files**, 43.417 s (INFO) |
| Plan / target determinism | **2/2** |
| STEP determinism after normalizing only FILE_NAME timestamp | **8/8** |
| Pinned resolved identities | **753/753** |
| Cameras / heads / types | **29 / 29 / 3** |
| Combined / federated camera identity agreement | **29/29** |
| Applicable generated IFC products with Common.Status NEW | **9,228/9,228**; one counted grid exception |
| Revit local dry run | **11/11 phases**, 29 camera payloads |
| Repository term sweep | **0 hits** |
| Revit service requests | **0**; dry run exits before creating the transport client; transport tests use injected requests |
| Nix attempts / passes | **1 / 0**, offline |

The 0.2.1 gate counted one timing threshold as a pass among 40 rows.
This release retains its 39 correctness checks, removes that threshold and
records eight subprocess durations as informational rows. The four new pytest
cases verify timing accounting and preservation of a correctness failure.
The build durations above are single-run observations on a shared machine,
not runtime guarantees or scenario measurements. The combined generator-suite
and scenario duration belongs to `usdaeco-scenarios`.

For this historical run, the README's Revit Status table was checked against
the then-current export census: physical elements
1,482/1,482; spaces 0/30, ports 0/2,032, openings 0/40, grids 0/2, and other
spatial products 0/5. No live build, export, or sync was repeated for 0.2.2.
The [current native acceptance](acceptance-revit.md) and
[export census](history/acceptance-through-0.4.0/artifacts/revit-export-acceptance.json) now record the later
45-camera rerun.
The 12/40/20 m ranges and 250 px/m type densities remain unchanged.

## Deviations

- One `nix flake check --offline` attempt failed because this repository
  has no `flake.nix`. No network resolution or second attempt was made.
  Nix packaging remains unproven.
