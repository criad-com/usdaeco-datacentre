# Public names acceptance — 0.4.7

Public URLs and GitHub owner fields now use `criad-com`. The toolchain advances
from v0.3.5 to v0.3.8; all other direct and fixture pins retain their v0.4.6
values. Library metadata, Python project metadata and the source package agree
on version 0.4.7.

The [full gate receipt](../artifacts/generator-0.4.7.json) and
[release audit](../artifacts/public-names-0.4.7.json) record the measurements.
Source execution follows the [README commands](../README.md#build-and-check),
using frozen dependency sources and an importable pinned core validator plugin.
No package installation is required.

| Acceptance | Measured result |
|---|---|
| Full gate | **203 checks, 0 failed**: 161 passes, 38 informational timings, 4 not run |
| Pytest | **197 passed**, 0 failed |
| Structure under toolchain v0.3.8 | **29 rules, 0 failed**; 22 explicitly inapplicable to a data repository |
| Public references | **0** old public references in tracked files and the contents of both history archives |
| Sanitization | **0** findings, including published USD, PNG metadata and history archives |
| Core registry | **8/8** validators loaded through UsdValidation from core v0.9.2 |
| Core validation | **5/5** variants with 0 errors; 2 existing proxy-classification warnings each |
| Vanilla rendering | **5/5** fresh non-uniform 1280×800 plugin-free renders |
| Published bytes versus v0.4.6 | **31/31** `dist/` files and **5/5** cameras identical |
| Other pins | **3/3** direct pins and **4/4** fixture pins unchanged |
| Rendering receipts | **5/5** records change only their toolchain provenance |
| Nix | **1** unsuccessful attempt; nested input unavailable; packaging not proven |

The toolchain tag resolves to `4ec5051c419ef056dba594e64be661cb41810275`.
Its tracked runtime digest is
`33eeeb8e4e04fe4f41982aaf696573256c5e1fd5b1f76413e9fc68a52cf8cd1e`,
independently reproduced from a pristine archive of v0.3.8.

## Deviations

- The publication sweep additionally adopts the toolchain's exact public-org
  exemption. One regression test proves that the public slug passes while
  private terms, extended slugs and private hostnames still fail.
- The existing freshness contract includes the toolchain pin. Five vanilla
  receipts therefore refresh that provenance after verification with fresh
  renders. No published stage, publication manifest, camera or image is
  republished or changed.
- The single offline Nix attempt used direct source overrides, disabled
  substitution and denied outbound IP connections while allowing the local
  daemon socket. The uncached nested `toolchain/aeco-toolchain` input at
  `e190680d3f94eb76e06abe77574fda1308af2c85` could not resolve. No lockfile was
  written and no second attempt was made.
- Native floors, pod, clash and iris remain **NOT RUN**: only base has recorded
  native evidence; these variants require further native family work,
  including pods and ceilings. The gate audits the retained base evidence
  without live execution.
