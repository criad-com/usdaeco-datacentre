# Release packaging acceptance

For **0.4.2**, Python source execution uses the pinned Revit integration
v0.1.0 without installation. Its declared range is `>=0.1,<0.2`; the flake
adds the matching public input and exports `AECO_REVIT_ROOT`. The single
`nix flake check --offline --no-write-lock-file --option substituters ''`
attempt failed resolving core v0.8.4 (HTTP 404). No second attempt or lockfile
was made; native C# remains a declared non-Nix enclave. See the
[current acceptance](acceptance-revit-0.4.2.md). The following tables are
historical and retain their original inputs.

This is the historical packaging snapshot imported with the preceding release.
The 0.3.2 release had **59 checks, 0 failed** and **75 pytest tests**;
see [exterior acceptance](acceptance-exterior.md). Its one offline Nix check
invocation found no flake. The tables below preserve the earlier run and its
distinct attempt counts; they are not new 0.3.2 measurements.

The historical **0.3.4** tested inputs are **core v0.8.4, CCTV v0.4.8 and
Sync v0.4.5**. See the [offline refresh](acceptance-0.3.4.md) for exact revisions,
output hashes and the current single offline Nix attempt, which also found no flake.

The source set uses core v0.8.1, CCTV v0.4.2, Sync v0.4.1, generator v0.2.1,
scenarios v0.3.0, shared toolchain v0.1.0 and BuildUp/Wall/Pipe v0.1.2.
These are independently mergeable packaging changes; released tags are not
moved and no PR depends on an unmerged sibling branch.

| This repository | Measured result |
|---|---:|
| check.py | 40 checks, 0 failed |
| pytest | 53 passed |
| Source/metadata sanitization | 0 hits |
| Native family/project files committed | 0 |

## Nix closure results

Exactly one `nix flake check` was attempted per repository with a flake, using
an offline registry entry plus explicit path overrides. The other repositories
have no flake. Nested registry resolution succeeded; reporting every failure as
an unresolved nested input would be inaccurate.

| Repository | Outcome | Boundary |
|---|---|---|
| `usdaeco-cctv-exec` | PASS | Native check and pytest passed with explicit overrides. |
| `usdaeco-sync` | NOT PROVEN — unavailable build closure | Nested input resolved; source dependencies were not cached; stopped at 180 s. |
| `usdaeco-cctv` | NOT PROVEN — broken importer dependency | Nested input resolved; pinned Nixpkgs marks Python 3.14 IfcOpenShell 0.8.0 broken. |
| `usdaeco-scenarios` | NOT PROVEN — unavailable build closure | Nested input resolved; uncached toolchain/Python dependencies; interrupted without a second attempt. |
| `usdaeco-core` | NO FLAKE | No flake.nix; zero evaluation attempts. |
| `usdaeco-datacentre` | NO FLAKE | No flake.nix; zero evaluation attempts. |

Committed locks retain exact Git revisions and NAR hashes, with deployment-neutral
placeholder URLs. They were generated from local immutable Git snapshots by
metadata-only resolution after the single check attempts; no second flake check
was run. The final neutral lock serialization is **not proven** by a fresh Nix
build. A deployment must supply the overrides below; placeholder URLs are not
fetchable. Deployment addresses and absolute paths never enter committed locks.

## Reproduce the dependency closure

Set `PYTHON` to the Python environment described in the root README. The shared
builder needs USD 26.8, Jinja2 and packaging; full checks also need IfcOpenShell,
NumPy, pytest and the repository's declared Python dependencies. Native exec
instead uses the matching USD development Python 3.14.

Keep the released family repositories as siblings and check out the exact
revisions in the dependency manifest. Set `PROCESSING_TOOLCHAIN` to an owned
checkout at processing-toolchain revision
`d51bae1cf9023cb58e6aed8d39694a181ffe1899`, and `OPENUSD_SOURCE` to an owned
checkout at `47154dc7b5e28df623745495a7a508b69535ba24`.
These are source-root variables, not paths to installations. Registering the
processing toolchain alone is insufficient for nested inputs on some Nix versions.

```sh
nix registry add aeco-toolchain "path:$PROCESSING_TOOLCHAIN"
```

This repository has no flake; use its root README build/check commands.
The table records NO FLAKE, without inventing a Nix pass.

## Deviations

- No live host was contacted. Recorded native evidence and hardware, lighting,
  retention and between-sample security claims are **not enforced** offline.
- The stable scenarios checkout lacked v0.3.0 at the initial inspection. Sync's
  integration pin therefore records merged main revision
  `fcbc5469c590ba89cf6447ee62c46a5e1d2a5d63`, as directed. The working clone has
  the release tag; no tag was created or moved by this package.
- The optional shared contract-reader refactor is deferred. Sync retains its
  standalone reader for the no-USD Blender route; the existing four unit
  combinations still exercise fresh writer/importer exchange.
- Historical release commits retain their original compatible schema ranges.
  The scenarios gate verifies those `requires` against the current released
  tags; the separate strict candidate audit passes 29/29 declarations/tag checks.
- No redistribution licence is declared in these repositories; core's licence
  file also leaves the choice pending. Licence clearance is **not enforced**.
