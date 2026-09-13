# Revit architecture acceptance — 0.6.0

**The full architecture delivery is produced by Revit.** The native Revit 2027
build `27.2.0.39` was measured on 2026-09-13. The
[receipt](../artifacts/revit-0.6.0.json) binds the native scripts, status probes,
uploads, batches, warnings, export hashes and partitioned delivery.

| Acceptance | Measured result |
|---|---|
| Disposable spike | One wall and one door; 2/2 planned GlobalIds; IFC4X3_ADD2 |
| Slab spike | One native Floor, 250 mm thick, `NoEndCap`, background document |
| Native full architecture | 111 walls + 47 doors + six slabs/roofs + three stairs = 167 created, zero updated/skipped |
| Native rooms | 36 occupied + two voids = 38; all have positive area and matching exported GlobalIds |
| Native model state | Saved and open in the background; no document activated or closed |
| Full builder status probes | 33, zero busy responses; foreground unmodified in every recorded probe |
| Full phase timings | Helpers 0.342 s; setup 2.510 s; parameters 0.215 s; architecture 1.337 s; rooms 1.077 s; export 3.876 s |
| Native export | 1,138,440 bytes; SHA-256 verified after transfer; 2,202 Psets; 410 quantity sets |
| Delivered architecture | 864,497 bytes; 167 elements; 15 types; 167 meshes; 1,981 Psets; 375 quantity sets |
| G2 identity join | 167/167 GlobalIds, 100%; zero missing/duplicate identities or kind failures |
| Placement / centre tolerances | 115 placements within 50 mm; 52 use the 150 mm geometry-centre fallback |
| Maximum geometry-centre difference | 0.04956309110620069 m across all 167 elements |
| Shared spine | 46 spatial definitions, only in shared; 799 spatial/project overs |
| Delivered union comparison | 9,308 identities and 12,434 prims agree with the monolithic conversion |
| Mute drill | Eight packages; zero remaining prims moved; only the 1,008 declared external port targets can dangle |
| Preserved publication | 36/36 other full files and 30/30 historical variant files byte-identical |
| Full size | 22,940,413 / 40,000,000 bytes |
| Native warnings | 266: 194 wall/separation overlaps, 67 separation-line overlaps, five wall overlaps |
| Source suite | 251 passed in 121.58 s |
| Initial complete gate | 259 checks: 207 passed, 46 informational, five not run, one publication-byte failure corrected below |
| Corrective publication gate | 44 checks, 0 failed: 39 passed, four informational, one connected-composition not-run; 29 structure rules; zero sanitization findings |

The delivered architecture SHA-256 is
`a23ecdfe02b3ed94b47d62136b7b6d0c453672f9e90355c45217ef9266506593`.
The retained generator architecture baseline is
`8f301d7c8b6ee3045c6f7255e6929704ea70f9e9f5ddfeebb1f42e57a3305cc0`.
The raw native export SHA-256 is
`6873f80ae89cddfe4c6711fda92583e3fc4c46f285ca912a8b85acede6bdc92a`.
Two partitions of that export produce identical bytes.

## Delivery and proof

The native model consumes the same resolved `full` plan as the generator.
`IFC_GUID` contains the plan's compressed UUIDv5 identity. The 167 elements
include the moved L02 partition and extra door. Native roof slabs use the
plan's actual thickness; the two upper slabs have a 207 m² notched outline.
The three storeys are at 0, 4 and 7 m, with roof datums at 7 and 10 m and a
separate 6.6 m datum for the two void rooms.

The partitioner selects all owned native physical referents and their native
representations, types, Psets and quantities. It converts length units to
metres, strips personal contact metadata, carries the issued generator spatial
spine and anchors names/containment to it. It preserves native placement
chains and introduces no generator physical element or body. The fixed IFC
header names Revit 2027 `27.2.0.39`, IFC4X3 and the partitioner.

G2 joins by GlobalId only against an independent generator architecture IFC.
It rejects missing/duplicate identities, class/predefined-kind mismatches,
missing geometry and tolerance failures. Different native insertion origins
use the existing geometry-centre fallback; tolerances have not been widened.
Each of the three twin layers names the native producer and delivered SHA-256.
Manifest `producers.arch` retains both the generator hash and parity numbers.

The federation gate's monolithic input is now the union of the actual nine
deliveries. It deduplicates shared roots by GlobalId, unions relationship sets
and reconstructs the external IFC port connections. It does not compare the
new native package against an obsolete all-generator monolithic stage.
All eight core validator callbacks load, and the complete candidate has zero
validator errors. The eight mute drills retain every remaining world transform.

## Deviations and limits

- Roof slabs are native Floors with `IfcSlab.ROOF` classification. The three
  stairs and one roller door are DirectShape solids built from analytical
  plan drivers; 46 doors are native family instances. No IFC mesh was fed back
  into Revit as an authoring driver.
- Native export represents openings differently: two separate opening entities
  versus 47 in the generator. Identity and centre parity do not certify exact
  topology or manufacturing detail.
- Revit reports 266 overlap warnings from the room-boundary construction.
  The saved native model and export nevertheless contain all 38 rooms with
  positive native area and all required identities. Warnings are retained in
  the receipt rather than treated as a clean native model.
- The frozen converter's overlay mode suppresses catalog classes and promotes
  spatial ancestors. The existing conversion/post-pass implements the required
  spatial overs and retains native catalog classes. Converter/core fixture
  hashes are unchanged; this does not claim an unmodified overlay-mode call.
- Revit's occurrence-specific stair types and slab tessellation add repeated-floor
  representation differences. The manifest records these observations. The
  planted wall axes, 3.2 m partition-length delta and extra door remain verified;
  whole-package identity/geometry parity is the separate G2 proof.
- Both published images retain generator 0.5.2 pixels, as required by the file
  preservation constraint. Their original provenance is retained in the image
  receipts; the current native stage has an independent fresh S28 render.
- The first complete gate found a publication-byte mismatch: the ordinary
  publisher adds two derived tolerance properties to the roller-door body.
  Both fresh builds agreed. Their canonical geometry layer replaced the earlier
  conversion, with its inventory and image receipts rebound. The initial gate
  result is retained; the affected publication proofs are repeated through
  `check.py --publication-only full`, using the same checks as the complete
  gate. The entire expensive gate was not repeated.
- The first compound-structure assignment needed `EndCapCondition.NoEndCap`.
  A disposable slab verified the correction; inspection confirmed a fully
  rolled-back architecture transaction before stale bindings were cleared and
  the full model continued. No uncertain mutation was replayed automatically.
- Exact repository pins remain Revit integration v0.1.4, Sync v0.5.4, validation
  core v0.9.4 and toolchain v0.3.10. Source archives supply the older tags without
  changing stable sibling checkouts. Historical 0.4.2 native results remain
  bound to their original three builder snapshots.
- Nix was not attempted. Packaging and connected composition remain not proven
  here; the portable USD publication and offline source gate are separate proofs.

## Reproduction and validation

The [initial complete-gate receipt](../artifacts/check-0.6.0-initial.json)
retains the publication-byte failure, and the [source-suite receipt](../artifacts/pytest-0.6.0.txt)
records 251 passing tests. The corrective publication run checks the canonical
output independently: its [receipt](../artifacts/check-0.6.0.json) records
**44 checks, 0 failed**, including two fresh exact publications, G2, S28,
all federation proofs and sanitization. The initial complete gate retains its
measured failure count.

Follow the source setup in the [README](../README.md#build-and-check) and the
[native builder guide](../revit/README.md). Published delivery reproduction
uses the committed native IFC and does not require a live authoring host:

```sh
env -u PYTHONPATH "$PY" -m dcbuild publish --variant full --out out/reproduced
env -u PYTHONPATH "$PY" check.py --report out/check-0.6.0.json
env -u PYTHONPATH "$PY" check.py --publication-only full --report out/check-0.6.0-publication.json
env -u PYTHONPATH "$PY" -m pytest -q
```

The gate repeats publication from the issued native IFC, checks all producer
and source stamps, runs G2 against a fresh generator architecture delivery,
checks the delivered union, renders with stock USD and drills package muting.
Focused tests also reject missing/duplicate identities, changed kinds and
translated native geometry. Native authoring itself is measured by the live
receipt; offline tests do not compile or execute Revit C#.
