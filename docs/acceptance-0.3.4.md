# 0.3.4 offline input refresh

This release updates the tested family inputs without changing generator
behaviour. The [offline gate](history/acceptance-through-0.4.0/artifacts/check-0.3.4.json) and
[output comparison](history/acceptance-through-0.4.0/artifacts/output-comparison-0.3.4.json) retain the
measurements and SHA-256 hashes. Native Revit acceptance is **NOT RUN** here;
the [0.3.3 native evidence](acceptance-revit.md) retains its original inputs.

| Tested input | Release tag | Commit |
|---|---|---|
| Core | v0.8.4 | `c818a1533bcfe36be47845252388a1c732ec69c0` |
| CCTV | v0.4.8 | `20c569d3ed43cc00513a662be9baa0f018d3c2bf` |
| Sync | v0.4.5 | `e527672e0fc20a0e26f2aa4f4617fe2d38ff5ecc` |

The baseline generator is v0.3.3, commit
`c3517940cd0f491112ee980d76024f6e7dcf66f1`. Both builds use the current
family inputs above and the unmodified scenarios v0.3.6 schedule at
`c6751418abdfbe8e07b3a7cbb49535bf95ed07e8`. This compares generator releases
at fixed family inputs, matching the existing v0.3.3 family-gate setup.
Equality between the older pinned converter releases and current converter
outputs is outside this comparison. Every supporting source revision is
recorded in the comparison JSON. Sources and built plugin manifests were
audited before generation; sibling checkouts were read only.

| Acceptance | Measured result |
|---|---:|
| `check.py` | **59 checks, 0 failed**; 51 PASS, 8 INFO timings |
| pytest, included in `check.py` | **75 passed** |
| Independent release output comparison | **31 checks, 0 failed** |
| Exact raw bytes | **15/31** |
| Only named timestamp fields differ | **16/31** |
| Other output differences | **0** |
| Camera identities / imported sensors / derived sectors, each build | **45 / 45 / 45** |
| Camera types / presets / tours, each build | **3 / 7 / 3** |
| Imported unmatched cameras / skipped derivations | **0 / 0** |
| Converted elements / authored element phases / space extents | **2,954 / 2,954 / 33** |
| Raw USD built-in / type / composition errors, each build | **0 / 0 / 0** |
| Vanilla composed stage entry points, each build | **15/15** |
| Repository and generated metadata sanitization | **0 hits**; 62 generated files scanned |
| Native Revit / live Sync | **NOT RUN** |
| Nix | **NOT PROVEN**; one offline attempt, no flake |

Both builds reproduce fixed coverage of **11/11 critical doors, 5/5 exterior
doors, 7/7 corridors, 8/8 yard targets by day and night, 3/3 lobby targets**
and **11/11 arc-compatibility door targets**, with zero privacy hits.
All eight study hashes and semantic reports match. The existing enclosed
samples and column exceptions remain governed by the family schedule;
this refresh makes no new physical-security or performance claim.

## Byte comparison and timestamp exceptions

The comparison retains both raw files, both raw SHA-256 hashes, both
comparison hashes, byte lengths and the result for each file. It compares
complete byte streams; it does not flatten, reorder or round USD values.
Binary USD geometry is included.

| Output population | Files | Raw identical | Timestamp only |
|---|---:|---:|---:|
| Combined and seven federated IFC files | 8 | 0 | 8 |
| Core, kind, derived, schedule and composed textual USD layers | 8 | 8 | 0 |
| Binary core geometry | 1 | 1 | 0 |
| Eight study result layers | 8 | 0 | 8 |
| Plan and target JSON | 2 | 2 | 0 |
| Build census, identity manifest, door optics and study QA JSON | 4 | 4 | 0 |
| **Total** | **31** | **15** | **16** |

The only comparison substitutions are:

- IFC: the second argument of `FILE_NAME`, its creation timestamp, in each
  of the eight IFC files. This is also the existing `check.py` STEP-determinism
  exception.
- USD: `customLayerData["aeco:cctv:time"]`, the receipt timestamp, in each
  `analysis/*.usda` study layer.

No release version stamp is removed. In particular the generator's existing
IFC originating-system stamp and manifest format version remain `0.1.0`.
The timestamp exceptions mean full raw byte identity is **not proven** for
those 16 files. Every other byte matches. Comparison negative controls
accepted timestamp changes and detected IFC and USD driver changes (4/4).

QA documents contain semantic data from the existing generator and family
functions. `qa/build.json` uses portable artifact-relative paths;
`qa/studies.json` uses the family's `stable_reports` projection. Build/study
timings are INFO measurements in the run log, outside that deterministic
output inventory. The timing-bearing `check.py` report is retained separately.
Core semantics and geometry are subordinate layers; their composed root
supplies `fallbackPrimTypes` for the vanilla check.

## Reproduce offline

Use the Python environment in the root README, including USD 26.8 and
Embree 4.4.0 for the family comparison. Set `PY` to that Python executable
and `AECO_FAMILY_ROOT` to the directory containing released sibling checkouts
with built plugins. Use the exact source revisions recorded in the evidence.
The commands below perform no network or live-host operations.

Keep the baseline checkout outside this repository so pytest does not collect
its duplicate test modules. Each comparison output directory must be new.

```sh
export BASELINE="$PWD/../datacentre-v0.3.3"
git clone --no-hardlinks --branch v0.3.3 --single-branch . "$BASELINE"
env -u PYTHONPATH "$PY" check.py --report out/check-0.3.4.json
env -u PYTHONPATH "$PY" scripts/compare_release.py \
  --baseline "$BASELINE" \
  --family-root "$AECO_FAMILY_ROOT" \
  --out out/release-comparison
```

The comparison audits source revisions and plugin metadata, assembles a
plugin descriptor under its own output directory, then runs independent
generator/conversion/import/derive/study processes. It fails on source drift,
missing outputs, failed coverage or any unapproved byte difference. Raw
artifacts remain under `baseline/` and `candidate/`; the summary is
`comparison.json`. No sibling is built or modified.

## Deviations

- Creation and receipt timestamps are the two exceptions above. They are
  runtime metadata, rather than release version stamps; no other output
  normalization is allowed.
- The first offline gate's pytest step collected an in-repository scratch
  baseline and failed with duplicate test module names. Moving that clone
  outside the repository resolved it; the complete rerun is the green
  59-check report linked above. No generator or test behaviour changed.
- Exactly one `nix --offline flake check --no-write-lock-file .` attempt
  exited 1 because this repository and its parents contain no `flake.nix`.
  There is no flake metadata to update, and no nested-input resolution or
  Nix build claim.
- Native Revit, live Sync, render generation and the complete family gate
  were not rerun. Historical native evidence retains its original versions;
  the current offline generator and eight-study comparison are the evidence
  for this release. No schema `requires` ranges were changed.
