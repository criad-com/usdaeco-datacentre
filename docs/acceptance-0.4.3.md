# Publication acceptance — 0.4.3

This presentation-only patch preserves all five v0.4.2 publication manifests
and all fifteen USD layers byte for byte. The generator's data provenance
remains 0.4.2; the package version is 0.4.3.

Measured acceptance is recorded in [the gate receipt](../artifacts/generator-0.4.3.json).

| Check | Result |
|---|---|
| Gate | **193 checks, 0 failed**: 151 passes, 38 timings, 4 native variants NOT RUN |
| pytest | **179 passed** |
| Toolchain v0.3.2 structure | **28 checks, 0 failed**; reduced data-repository rules |
| IFC schema / semantics | **42 files clean** across all five variants |
| Core registry | **8/8** callbacks loaded through `UsdValidation` |
| Core stage validation | **5/5** stages, zero errors, two existing proxy warnings each |
| Published data | **15/15** layers and **5/5** manifests identical to v0.4.2 |
| Reproduction | **10** fresh publications; all match committed bytes without normalization |
| Vanilla proof | **5/5** independently rerendered, fresh and non-uniform |
| Sanitization | **0 hits**, including binary USD text and image metadata |
| Licence | **MIT**, accepted by S01 |

| Variant | Pixels | Committed PNG bytes | Freshness / content |
|---|---|---:|---|
| base | 1280×800 | 144,319 | PASS |
| floors | 1280×800 | 145,912 | PASS |
| pod | 1280×800 | 144,340 | PASS |
| clash | 1280×800 | 143,863 | PASS |
| iris | 1280×800 | 144,242 | PASS |

The gate uses toolchain v0.3.2 and the core v0.9.2 Python validation plugin.
The converter and generation core retain their exact v0.4.2 pins.

`run.py --all --publish` produces the five committed vanilla renders.
Each variant's `check_example()` rebuilds the flattened publication and camera,
compares source and image receipts, and calls the shared S28 `render_vanilla`
function. That function relocates the crate and camera into an empty directory
and invokes stock USD in an isolated process without family plugins.

The generic example harness requires `examples/.../result/`; this data
repository keeps its established `dist/<variant>/` contract. Its adapter uses
the same S28 renderer and adds per-variant freshness checks. Flattened crates
remain ignored scratch output, avoiding a second committed copy of every stage.
Published roots keep their two portable sibling sublayers.

PNG hashes identify committed images; independently rendered pixels need not
match between Embree runs. Images must be non-uniform, at most 1600 pixels per
dimension and at most 400,000 bytes. Facility bounds fit the camera frustum
with a 15% margin. The previews are exterior views, so internal variant
fixtures are not necessarily visible.

No tracked file at v0.4.2 exceeds 2,000,000 bytes. Regenerable plans, IFCs,
flattened rendering crates and fresh renders live under ignored `out/`.
Tracked sizes count file payload bytes, excluding Git history and scratch data.


The single Nix attempt used offline mode, direct source overrides and disabled
outbound connections. It could not resolve the nested
`toolchain/aeco-toolchain` source at revision
`e190680d3f94eb76e06abe77574fda1308af2c85`. No lockfile was written and no second
attempt was made. Nix packaging remains **not proven**.

Native execution was outside this publication refresh. The gate audits the
existing base evidence and retains four explicit NOT RUN rows for native
floors, pod, clash and iris. Core validation reports the existing two
`proxyClassified` warnings per variant for the utility intakes; these are
warnings, not a claim that every element has a specific product class.


| Tracked payload | v0.4.2 bytes | v0.4.3 bytes | Change |
|---|---:|---:|---:|
| `dist/` | 9,819,566 | 10,543,932 | +724,366 |
| Entire repository | 11,009,373 | 11,837,182 | +827,809 |

The v0.4.2 tree has 173 tracked files; v0.4.3 has 190. Sizes sum Git blob
payloads; symlinks count their link text, not the destination directory.
The largest tracked file is 1,485,167 bytes. Zero files exceed 2,000,000 bytes,
so no large generated artifact needed removal. The five new PNGs total
722,676 bytes; the remainder of the increase is cameras, code, receipts and
documentation, partly offset by the shorter licence. Git history, caches,
source archives and generated `out/` content are excluded.
