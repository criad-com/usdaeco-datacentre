# Published USD 0.4.1 acceptance

Five design-option publications are committed, each with a portable root,
binary semantics, binary geometry, a measured manifest and one exterior
overview. Both independent publishes agree with the committed three layers
and manifest byte-for-byte, with no normalization.

| Variant | Elements / spaces / levels / ports / meshes / unparented / unclassified | Root bytes | Semantics bytes | Geometry bytes | Manifest bytes | PNG bytes | Total bytes |
|---|---|---:|---:|---:|---:|---:|---:|
| base | 2954 / 33 / 2 / 6212 / 2987 / 0 / 2 | 517 | 1471556 | 332637 | 990 | 144133 | 1949833 |
| floors | 2983 / 39 / 3 / 6212 / 3022 / 0 / 2 | 517 | 1479303 | 338756 | 992 | 145848 | 1965416 |
| pod | 2977 / 35 / 2 / 6238 / 3012 / 0 / 2 | 517 | 1483117 | 344521 | 989 | 144082 | 1973226 |
| clash | 2980 / 35 / 2 / 6244 / 3015 / 0 / 2 | 517 | 1485167 | 347084 | 991 | 144140 | 1977899 |
| iris | 2954 / 33 / 2 / 6212 / 2987 / 0 / 2 | 517 | 1471930 | 332637 | 990 | 144529 | 1950603 |

The total includes every file in each variant directory. All five remain
below 10,000,000 bytes, so no large-file storage exception is needed.
All PNGs are non-uniform, 1280×800 and below 400,000 bytes. Camera receipts
record facility bounds, all eight bounds corners inside the frustum and
33/39/35/35/33 hidden space extents for base/floors/pod/clash/iris. Rendering
uses `usdaeco_render`, `usdrecord` and Embree with `guide,proxy,render` purposes.

Plugin-free probes discover no family plugins, compose each root with no
errors, verify explicit metres/Z/default prim, resolve all six used Aeco
concrete types to stock Xform/Scope definitions, and reproduce every manifest
census. Mesh counts include space extents. The two unclassified elements in
each variant are the existing utility intake proxies, retained explicitly.

The shared structure lint reports **26 checks, 0 failed**. S01–S05, S25 and
S26 apply and pass; S06–S24 explicitly report not applicable for `kind: data`.
The gate supplies the missing data-specific coverage for committed `dist/`
roots, binary text sanitization and render caps/provenance. No rule was waived
or supplied with a fake schema/example tree.

The full gate passed **172 checks, 0 failed**: **134 correctness passes and
38 informational timings**. Pytest passed **164 tests**. The original 132
rows are retained in substance (the unavailable structure row is now a
blocking pass), with 40 publication/render rows added. All **42 IFC files**
passed G1. The repository sweep, including decoded binary USD and all
archived text, found **0 hits**. See the
[complete gate receipt](history/acceptance-through-0.4.1/artifacts/generator-0.4.1.json).

The source CLI launcher was also run from a separate working directory with
an explicitly selected compatible `USDRECORD`; image and manifest outputs
stayed in that working directory. This does not prove the unresolved Nix
build.

Reproduction, with `PY` set to the prepared Python environment and the pinned
family sources as documented in the [README](../README.md):

```sh
env -u PYTHONPATH "$PY" -m dcbuild publish --all
env -u PYTHONPATH "$PY" -m dcbuild render --all
env -u PYTHONPATH "$PY" check.py --report artifacts/generator-0.4.1.json
env -u PYTHONPATH "$PY" -m pytest -q
```

The gate itself performs two independent publishes per variant in scratch
storage; ordinary checks do not overwrite committed data or image expectations.
Exact refs and runtime source fingerprints are in
[dependencies.json](../dependencies.json); image and camera measurements are
in [render receipts](../manifests/renders.json).

## Deviations

- The one Nix attempt, `nix flake check --offline --no-write-lock-file
  --option substituters ''`, failed resolving the public core v0.8.4 input
  (HTTP 404). No second attempt or lockfile was made. Flake packaging and the
  two target platform builds are **not proven**. Source execution is verified
  separately; local input overrides are documented.
- Converter 0.1.0 writes semantic USDA. The publisher losslessly exports it
  to USDC and updates the root sublayer reference without changing the pinned
  converter. Published semantics intentionally target frozen core 0.8.4.
- `library.json` uses the requested keys unchanged. This schema-free data
  repo retains its existing `src/dcbuild/` and `tests/` layout under the reduced
  rules. A conftest adds source/tools paths; no installed package or setuptools
  is required by tests.
- Superseded evidence was archived, not discarded: 24 files are in
  [one history directory](history/acceptance-through-0.4.0/). Only the latest
  generator/native export/live Sync/exterior study/combined family acceptance
  JSON per gate remains in `artifacts/`. Historical source hashes and diagnostic
  detail remain recoverable; [the history index](history/README.md) explains how.
- Native Revit work is outside this release. Its existing offline payload and
  dry-run rows remain enforced, and earlier live receipts remain labelled as
  historical. Exact clash conclusions and verified regulatory requirements
  remain subject to the [existing variant limitations](variants.md).
