# Frozen generation runtimes

MIT family code, copied without changes from exactly the `runtime_paths` in
[dependencies.json](../dependencies.json); the publisher and gate verify the
recorded `runtime_sha256` before use. These copies require no flake inputs.

- `core-0.8.4`: [criad-com/usdaeco-core](https://github.com/criad-com/usdaeco-core), tag `v0.8.4`, revision `c818a1533bcfe36be47845252388a1c732ec69c0`.
- `ifc-0.1.0`: [criad-com/usdaeco-ifc](https://github.com/criad-com/usdaeco-ifc), tag `v0.1.0`, revision `43935df9e059b724f8d1ae3d0ea324dbae7efd29`.

The tags and revisions identify the historical generation sources; they are
provenance records, not public download requirements. The two `*_recorded`
fixtures remain provenance-only entries and are not vendored.

`revit-builder-0.4.2/` preserves the three local builder source files bound by
the [historical native receipt](../artifacts/revit-0.4.2.json), copied verbatim
from this repository's `v0.4.2` tag. The gate checks their original SHA-256
values. These snapshots are evidence, not runnable dependencies, and do not
certify the current builder after its architecture changes.
