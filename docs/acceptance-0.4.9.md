# Public re-pin acceptance — 0.4.9

The four active family inputs now select the supplied public release tags.
The toolchain also selects processing toolchain v0.4.0 recursively. Every
active family flake input is a tagged `github:criad-com` URL. The two frozen
generation runtimes are vendored; their historical tags are not flake inputs.
The supported Revit range remains `>=0.1,<0.2`.

| Input | Previous | Release | Checked revision |
|---|---|---|---|
| Toolchain | v0.3.9 | v0.3.10 | `59d3da5ff5114089b54efaaae38efdd7fe1b8e73` |
| Validation core | v0.9.2 | v0.9.4 | `80a099e14e7bb825b207548d0a4f8a93e9ffa62f` |
| Revit | v0.1.2 | v0.1.4 | `6840bbe8d1a42ffa4c456038e7ba42b8bc22acce` |
| Sync | v0.5.2 | v0.5.4 | `1d67810d7add1a23b825461e44cfdfb721b689f5` |

Each checked revision is the peeled release tag from the source forge.
Runtime fingerprints agree between the tagged checkout and a fresh archive
for all four active inputs. These revisions record the checked source;
public orphan release commits have different identities, so flake URLs use tags.

The [release audit](../artifacts/public-repin-0.4.9.json) records the pins,
file hashes and fresh render measurements. The [full gate receipt](../artifacts/generator-0.4.9.json)
records validation and deterministic rebuild results.

| Acceptance | Measured result |
|---|---|
| Full gate | **204 checks, 0 failed**: 162 passes, 38 timings, 4 native variants not run |
| Pytest | **213 passed**, 0 failed; full suite invoked by `check.py` |
| Structure | **29 rules, 0 failed** under toolchain v0.3.10, including S05 |
| Pin verification | **4/4** target revisions and pristine archive fingerprints agree |
| Family URLs | **4/4** tagged URLs covered by S05; **0** family hash refs; **0** legacy-org refs |
| Frozen runtimes | **2/2** vendored at recorded revisions; runtime hashes unchanged; **0** fixture flake inputs |
| Rebuild | **5** variants republished; **10** further gate publishes match committed bytes |
| Core validation | **8/8** callbacks loaded; **5/5** variants have **0** errors and 2 existing proxy warnings each |
| Rendering | **5/5** published fresh renders and **5/5** gate freshness proofs pass |
| Published bytes | **31/31** dist files unchanged, including **15/15** USD layers and **5/5** manifests |
| Cameras and history | **5/5** cameras and **27/27** history files byte-identical |
| Receipt scope | **5/5** vanilla receipts change only `sources.toolchain` |
| Requirements | **1/1** range retained; **0** widened ranges |
| Hygiene | `git diff --check` clean; repository term sweep **0** hits |
| Final publication sweep | **271 files, 0 findings** |
| Nix | **1** offline attempt, exit **1**; packaging **not proven** |

## Reproduction and output comparison

Use the [source setup](../README.md#build-and-check), selecting the four exact
tagged sources above and the bundled core v0.8.4 / IFC v0.1.0 fixtures.
The checked sources were frozen under ignored scratch space; no sibling
checkout was modified. No package installation or setuptools was required.

```sh
env -u PYTHONPATH "$PY" -m dcbuild publish --all
env -u PYTHONPATH "$PY" run.py --all --publish
env -u PYTHONPATH PYTHONPATH="$AECO_VALIDATION_CORE_ROOT:$PWD" "$PY" check.py --report out/check.json
```

The documented publisher rebuilt all five variants. All 15 USD layers and
five manifests are byte-identical to v0.4.8
(`9e22b14c4909e50806805e735f93b1b425ac48cb`), without normalization.
This includes all geometry, topology, transforms and authored metadata.
No pinned dependency changed the published geometry.

Five fresh stock USD renders produced non-uniform 1280×800 PNGs. Their
flattened-stage fingerprints, camera layers and source records match the
previous publication except for the toolchain pin. The audit retains fresh
image measurements. Following S28, sampled PNG bytes are not compared across
renders: the previously committed images and their image measurements were
retained after fresh rendering, and only `sources.toolchain` was refreshed
in each vanilla receipt. All 31 `dist/` files and five cameras therefore keep
their v0.4.8 bytes; historical overview and native receipts retain their
original measured pins.

Upstream changelogs explain the pin changes: toolchain 0.3.10 requires family
release tags and keeps its USD/nixpkgs revisions; core 0.9.3–0.9.4 preserve
the schema contract; Revit 0.1.3–0.1.4 update pins and the offline example;
Sync 0.5.3–0.5.4 update pins and public names. IFC and USD generation logic
is unchanged; dependency resolution now uses the bundled frozen runtimes.

## Fixtures vendored

The publisher and acceptance gate now resolve the two generation runtimes
from `dependencies.json.fixtures[*].path`. Their `flakeInput` fields are
`false`, and `flake.nix` has no core v0.8.4 or IFC v0.1.0 input. The Nix
setup uses the same bundled copies. Version remains **0.4.9**.

| Fixture | Exact runtime files | Bytes | Unchanged runtime SHA-256 |
|---|---:|---:|---|
| `fixtures/core-0.8.4` | 8 | 105,908 | `5fa7e009081defeaa427b1a3921cb93c15337140810a0f7af9459cc1be0c3ef6` |
| `fixtures/ifc-0.1.0` | 23 | 154,846 | `af2a5ba8127d0c00cb11fc57df71e1bf6388834e00261ff76f43b10abaaf2b20` |

Both file inventories and every file's bytes match a fresh archive of the
declared revision, limited to the declared `runtime_paths`. Source repos,
tags, revisions and the MIT note are in [fixtures/README.md](../fixtures/README.md).
The four active pins and both `*_recorded` fixtures are unchanged.

The full gate ran with `AECO_CORE_ROOT` and `AECO_IFC_ROOT` unset, exercising
automatic local resolution and hash verification. Its ten publishes match
all five committed variants. All **31/31** `dist/` files retain their exact
pre-vendoring SHA-256 hashes; the generator and frozen converter are unchanged.

## Deviations

- The checkout started with toolchain v0.3.9. It advances to the requested
  v0.3.10.
- Frozen generation tags core v0.8.4 and IFC v0.1.0 will not be published.
  Their exact runtimes are now vendored, so public input resolution no longer
  depends on those tags. Historical evidence pins remain unchanged.
- The frozen generated schema retains 19 lines with trailing whitespace and
  a blank line at EOF. A Git whitespace attribute for that one file preserves
  its recorded hash; `git diff --check` remains enforced for other files.
- Exactly one `nix flake check --offline --no-write-lock-file` attempt used
  six local sibling source overrides, disabled substitution and denied
  outbound IP connections. It exited 1 while resolving the uncached nested
  `toolchain/aeco-toolchain` v0.4.0 input. No lockfile was written and no
  second attempt was made, including after vendoring. Nix packaging and online
  resolution are **not proven**.
- Fresh Embree PNG bytes differ through sampling. Existing image bytes are
  retained after the five fresh render proofs, as in the preceding releases.
- Native floors, pod, clash and iris remain **NOT RUN**. This gate audits
  the recorded base measurements; native execution was not repeated.
