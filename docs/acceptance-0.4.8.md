# Inspectable history acceptance — 0.4.8

Historical receipts and patches are directly inspectable under
[`docs/history/`](history/README.md). Two compressed bundles are replaced by
plain directories preserving their original member paths and bytes.
The gate now invokes the pinned toolchain's `usdaeco_check.publication`
sweep, which rejects archives by extension or signature across tracked files
and non-ignored candidate files, including published data.

The [release audit](../artifacts/history-0.4.8.json) records every expanded
member's SHA-256, all dist hashes, reference counts and the Nix result.
The [full gate receipt](../artifacts/generator-0.4.8.json) records the checks.

| Acceptance | Measured result |
|---|---|
| Full gate | **204 checks, 0 failed**: 162 passes, 38 informational timings, 4 not run |
| Pytest | **213 passed**, 0 failed |
| Structure | **29 rules, 0 failed** under toolchain v0.3.9 |
| Core validation and vanilla rendering | **8/8** validators loaded; **5/5** variants with 0 errors and fresh plugin-free renders |
| Expanded records through 0.4.0 | **24 files**: 22 JSON and 2 patches |
| Expanded records through 0.4.1 | **2 JSON files** |
| Preservation | **26/26** original member paths and byte hashes retained; **482,433 bytes** |
| Archive references | **34 links in 12 documents** updated; **2** extraction commands removed |
| Final publication sweep | **235 files, 0 findings, 0 archives**; repository term sweep **0 hits** |
| Expanded-file family term sweep | **26 files, 0 findings**; 0 redactions and 0 drops |
| Dist versus v0.4.7 | **20/20** `dist/*/dc.*` files identical across **5** variants; **31/31** total dist files identical |
| Frozen repin receipt | `artifacts/repin-0.4.6.json` unchanged |
| Archive regression tests | **16 added**: whole-repository sweep, 10 extension cases and 5 renamed signature cases; tracked files in ignored directories are included |
| Version metadata | `library.json`, `pyproject.toml` and source package agree on **0.4.8** |
| Toolchain | **v0.3.9**, exact commit and pristine runtime digest verified |
| Pin-change scope | **3/3** other direct pins and **4/4** fixture pins unchanged; **5/5** vanilla receipts change only `sources.toolchain` |
| Nix | **1** unsuccessful offline attempt; packaging **not proven** |

Hash comparison uses v0.4.7 commit
`2f87b6f40eb276888a0be831096fd8247c223f70`. The gate independently rebuilds
and publishes each variant twice and compares its three USD layers and
manifest with committed `dist/` bytes, without normalization.
Generator implementation, example inputs, cameras, images and published
data retain their preceding versions. The toolchain advances to v0.3.9
(commit `d8f09dfd2ddfb6e8a08a9528e90f949248d5a1c2`) to fix Nix package-version
metadata. Five vanilla receipts update only their toolchain provenance;
every other dependency pin stays fixed.

Source execution follows the [README commands](../README.md#build-and-check).
The gate uses the exact pinned sources without installing this package or
setuptools, and requires all eight core validators through `UsdValidation`.

## Deviations

- The older bundle contains 22 JSON files and two patches; the newer bundle
  contains two JSON files. All 26 files are retained without redaction.
- The single offline Nix attempt used local source overrides, disabled
  substitution and denied outbound IP connections. Its uncached nested
  `toolchain/aeco-toolchain` input at
  `e190680d3f94eb76e06abe77574fda1308af2c85` could not resolve. No lockfile was
  written and no second attempt was made. This attempt used v0.3.8 before
  the pin update; Nix packaging with v0.3.9 remains not proven.
- Sibling checkouts had advanced, so exact tagged core, Revit and Sync sources
  were unpacked into ignored `out/dependencies/` and selected with existing
  overrides. The IFC gate used its frozen checkout. Sibling repositories and
  all other dependency pins were not changed.
- During the initial full run, the shared toolchain checkout advanced from
  v0.3.8 to v0.3.9. Its pin checks rejected that change during pytest: the gate
  finished with 204 checks and one failed row, comprising 205 passed tests,
  two failed tests and six setup errors. An owned checkout frozen at v0.3.8
  replaced that moving input and 213 tests passed. A preliminary rerun was
  stopped when the toolchain v0.3.9 update became required. The final gate uses
  an owned checkout frozen at v0.3.9; these attempts are an exception to the
  single-run plan.
- Native floors, pod, clash and iris remain **NOT RUN**; this offline gate
  audits the retained base evidence without repeating native execution.
