# Typical floors and reproducible runtime acceptance — 0.4.5

L02 is generated from the L01 room and door schedule. Its only changed
partition is `wall.l2.v.016`, moved 1 m east and extended south from 5.0 to
8.2 m. The extra `door.office.2b` opens through that partition. Other walls
retain their axes and bodies, both upper floors retain matching ascending
stairs, and the roofs belong to the building outside either floor inventory.

The [published manifest](../dist/floors/dc.manifest.json) records the planted
ids, endpoints, lateral offset, level offset, expected net length delta and
measurements. Matching uses classification, inherited type and placement,
then compares body geometry. Exporter ids only label the resulting findings.

| Measurement | Verified result |
|---|---|
| Full gate | 203 checks, 0 failed: 161 passes, 38 informational timings, 4 native NOT RUN |
| pytest | 196 passed |
| Structure lint | 28 checks, 0 failed |
| IFC schema and semantics | 42 files clean across five variants |
| Publication reproduction | 10 fresh publications; all 3 layers and manifests match committed bytes |
| Vanilla freshness | 5/5 fresh, plugin-free and non-uniform |
| Core validation | 8/8 callbacks loaded through UsdValidation; 5/5 stages, zero errors, 2 existing proxy warnings each |
| Sanitization | 0 hits |
| Matched L01/L02 elements | 28 |
| Differences | Exactly 2: 1 changed partition, 1 extra door |
| Other walls, slab, stair and equipment | No differences |
| L01 partition length | 43.0 m |
| L02 partition length | 46.2 m |
| Net partition length delta | +3.2 m; mesh lengths agree with IFC quantities within 1 µm |
| Released typical consumer | v0.1.0 independently confirms both findings and +3.2 m |
| Other variants | 32/32 files byte-identical to v0.4.4: 24 publication files, 4 source manifests, 4 cameras |
| Rendering receipts | 8/8 retained; only the 4 unchanged vanilla toolchain digest fields are corrected |
| Floors vanilla | 1280×800, 145,777 bytes, plugin-free USD / Embree |
| Floors overview | 1280×800, 145,695 bytes |
| Floors publication | 2,112,410 bytes including both images; below 10 MB |
| Focused published-drift and digest tests | 10 passed |
| Licence | MIT |

The [full gate receipt](../artifacts/generator-0.4.5.json) records every row.
The [consumer receipt](../manifests/typical-consumer-probe-0.4.5.json) records
the exact consumer revision and measurements. The permanent gate has no
consumer dependency. Mutations exercise an extra roof, missing wall or stair,
changed type or placement, false quantity and incorrect declared offset.
A renamed exporter identity does not change matching.

`runtime_digest()` selects tracked runtime files and excludes package metadata
and caches. A fresh `git archive v0.3.2` independently reproduces the toolchain
digest `03530ed2dd7949017a607fe57daa9ffd65b4b8257a1f64c6ccfc5cbb822ce956`.
The regression adds untracked build debris, changes tracked source, and checks
both checkout and pinned archive behavior. Gates require the pinned toolchain
Git checkout for this reproduction; publishers also accept source archives.

Reproduce using the pinned environment and separate source overrides in the
[README](../README.md#build-and-check):

```sh
env -u PYTHONPATH "$PY" -m dcbuild plan --variant floors
env -u PYTHONPATH "$PY" -m dcbuild publish --variant floors
env -u PYTHONPATH "$PY" -m dcbuild render --variant floors
env -u PYTHONPATH "$PY" run.py --variant floors --publish
env -u PYTHONPATH PYTHONPATH="$AECO_VALIDATION_CORE_ROOT:$PWD" "$PY" check.py
```

## Deviations

- A pure translation preserves length. To produce +3.2 m with one changed
  partition, that same wall also extends 3.2 m south. The extra door is placed
  in it so its opening cannot change a third element. The room extents remain
  the copied baseline; the extension enters the nominal WC extent. This is an
  intentional drift fixture, not a reconciled room-boundary design.
- The consumer calls the partition `changed`, because its shape and placement
  both change. It reports the door as `extra`; no typical-schema deviations
  are authored in the source stage. Roof landing/access detailing is outside
  the fixture; the continuing top flight reaches the roof soffit datum.
- Other variant data, source manifests, cameras and pixels are byte-identical.
  Their shared vanilla provenance receipts need the corrected toolchain hash;
  retaining the old value would contradict the reproducible pin. The gate
  permits exactly that field correction and compares everything else.
- The single offline Nix attempt used direct source overrides with outbound
  connections disabled. It could not connect to the Nix daemon socket;
  evaluation did not start and no lockfile was written. Packaging is
  **not proven**. A toolchain source archive alone cannot run the new Git
  archive gate row; the publisher still supports archive inputs.
- Native execution remains unchanged; four native variants are NOT RUN.
  The exterior render proves vanilla composition; the manifests and consumer
  receipt expose the internal floor changes.
