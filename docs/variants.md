# Generator variants

All coordinates are metres, Z up. The base plan and IFC bodies remain those
of 0.3.4. Each named overlay has its own plan, IFC files and public count manifest.
These are generator design options; they are not USD revision variant sets.

## Floors

L02 is generated from the six L01 office rooms and five doors. Its walls
therefore start as the same 19 segments. `DC_Typical.Prototype` on the IFC
storey names `lvl.l1`. The repeated room extents retain the baseline schedule;
the deliberate wall edit is independent of those nominal room boundaries.

Only `wall.l2.v.016` changes: its centreline moves 1 m east, from x=26 to
x=27, and extends south from y=-8 to y=-11.2, retaining its north end y=-3.
Length changes from 5.0 to 8.2 m. The extra door, `door.office.2b`, is at
(27, -5.5) in that same partition, connecting the meeting and kitchen spaces.
Putting its opening in the edited wall avoids a third changed wall body.
The extension enters the nominal WC extent; this is deliberate coordination
drift, not a reconciled room-boundary design. No other partitions are trimmed,
added or moved. Pure translation alone cannot change a length quantity.

The source manifest records the wall id, prototype, lateral offset, endpoints,
door id and expected +3.2 m net partition delta. The published
[`dc.manifest.json`](../dist/floors/dc.manifest.json) also measures all partition
bodies: L01 **43.0 m**, L02 **46.2 m**. The independent USD matcher uses
classification, inherited type and placement, then compares bodies; it finds
28 matched elements and exactly two differences. Its wall finding is
`changed`, because the wall is both moved and resized; the door is `extra`.
These expectations are manifest data, not authored typical-schema exemptions.

Both upper floors have matching notched floor slabs and ascending 3 m stair
flights. The top flight continues to the office roof datum; the ground flight
retains its 4 m rise. Roof slabs belong to the building, outside either floor's
element inventory. The main roof stays at 7 m and the office roof rises to
10 m. Roof values remain soffit elevations; slab tops add thickness. Roof
access/landing detailing is outside this fixture. Other variants retain their
historical slab and stair representations byte for byte.

## Pod and programme

`spec/fitout.yaml` supplies 23 products: two plasterboard ceilings (12.5 mm on
MF grid), two separate pod positions, six first-fix products (one tray, two
DN50 CHW pipes, one fan-coil, two conduit runs), ten second-fix products (six
lights and four grilles), and three third-fix products (DN100 drain, two sanitary
terminals). DN50 uses 60.3 mm OD and DN100 uses 110 mm OD; these are explicit
illustrative section selections. Services have placed, nested ports. The CHW
outlets connect to the fan-coil. Remaining ports are open endpoints for later
system completion; the generator does not claim a complete fit-out network.

The two voids occupy z=6.6..7.0 m. Ceiling boards occupy 6.5875..6.6 m: the
specified +2.6 datum is the board top / void bottom. Void space geometry is
independent of the occupied room volume and does not generate duplicate walls.
Products belong to their declared space; long service routes may cross other
spaces on their way from the comms room or to the fan-coil and drain riser.

The 2.4 by 3.6 m temporary pod at x=20..22.4 overhangs the 3 m corridor by
0.3 m on both sides. Its corridor containment records the obstructed workspace,
not full geometric inclusion. Its status is TEMPORARY; the final product in
the WC is NEW. Programme B's placement override parks the same temporary
identity at (17, -7.5, 4) in the office. The IFC depicts programme A's temporary
position; the B override is explicit input to a future 4D derivation.

```sh
env -u PYTHONPATH "$PY" -m dcbuild plan --variant pod
env -u PYTHONPATH "$PY" -m dcbuild build-ifc --variant pod
env -u PYTHONPATH "$PY" -m dcbuild build-programme --variant pod
```

Each programme emits four files in `out/pod/programme/`: XER, MSPDI XML,
`scope.json` (activity id to scope ids), and `workspace.json` (the `activities`
map of access/enclosure/occupation ids, plus a `placements` map). Activity ids
are XER task_code and MSPDI Text2; scope is MSPDI Text1 JSON; IfcTask vocabulary
is Text3 and XER dc_task_type. XER task_type retains P6's native TT_Task.
MSPDI has WBS summary tasks as well as the ten leaf activities. Both formats
preserve authored dates and every predecessor link, including signed fractional
lags. The declared 24-hour elapsed-day calendar makes one lag day 24 XER hours
or 14,400 MSPDI tenths of minutes. No CPM or working-day arithmetic is inferred.

Programme A has the three expected rule families in `spec/programme.yaml`:
AccessAfterEnclosure, WorkspaceOccupied and EnclosureBeforeInspection. The
first-fix inspection itself is also too late for the closed voids. Programme B
finishes first fix and inspection before enclosure, and clears the parking
space before drylining. These are expected rule families, not an assertion of
exactly three individual space/activity pairs from every downstream validator.

The historical XER parser was run read-only in a scratch directory against
A.xer: 10 tasks, 9 predecessor links, 3 used WBS nodes, 1 project and 1 calendar
(24 hours/day). This proves parser compatibility, not an application import in
P6 or Microsoft Project. Independent readers test equivalent identities, dates,
scopes, task vocabulary, link types and lags across both emitted formats.

## Clash

`clash` extends `pod`, adding three DN50 (60.3 mm OD) circular swept pipes.
`expected.clash` gives each comparison partner, full world axis, OD and wall
face plane. The hard case crosses the meeting/corridor partition above its
door opening. The near case has 5 mm clear distance above the tray over 2 m.
The tangent case has zero analytical distance to the corridor face at y=-2.925.

Version 0.4.4 makes the mesh comparison measurable. The exact gap remains 5 mm;
coarsening the near pipe preserves that useful clearance example. The
`publication.tessellation` settings select a 6 mm maximum inscribed chordal
error for the near pipe and a 1.2 mm maximum circumscribed error for the tangent
pipe. A vertex points toward each partner. The resulting polygons have five
and twelve sides respectively; the five-sided pipe is deliberately coarse
comparison data, not a recommendation for normal export quality.

The pinned converter has no per-product settings interface. The local
[conversion adapter](../src/dcbuild/tessellation.py) reads the actual IFC circle,
extrusion and placements, replaces only these two tessellations before the
pinned USD authoring pass, and leaves every exact IFC sweep unchanged. For
radius `r` and `n` sides, inscribed error is `r * (1 - cos(pi/n))`;
circumscribed error is `r * (1/cos(pi/n) - 1)`. The setting selects the smallest
polygon below that bound. Circumscription puts vertices outside the circle,
so the tangent pipe's wall-facing vertex produces a false penetration.

| Case | Published mesh distance | Measured band | Mesh verdict | Analytic exact verdict |
|---|---:|---:|---|---|
| (a) hard | −75.000003 mm sampled interior depth | 0.2201 mm | hard | hard |
| (b) near | +5.000114 mm gap | 5.7582 mm | undecidable | 5 mm clearance |
| (c) tangent | −1.063541 mm penetration | 1.0636 mm | falsePenetration | tangent, 0 mm |

The [published manifest](../dist/clash/dc.manifest.json) carries `clash.expected`
and measured `clash.cases`: source axes/radii, settings, side counts, witnesses,
distances, per-body bands and both verdicts, in metres. Mesh bodies carry
`aeco:body:tolerance` and `aeco:derived:tolerance`; radial deviations are measured
from serialized vertices and chord interiors, then rounded outward to 0.1 µm.
The planar wall/tray partners have zero chordal error. The gate recomputes each
band and checks its stamp and YAML expectation, including both the actual
mesh distance and exact gap against the near band. Missing, understated or
inflated stamps fail. Witness projections must land on finite published
triangles. Case (a) uses an interior witness between both wall faces;
its depth is not a minimum translation distance or a Boolean volume.

The released clash engine independently reproduces all three distances and
finds `band_decides: false` for (b) and (c); its one-off
[probe receipt](../manifests/clash-engine-probe-0.4.4.json) records the source
revision and publication hash. The permanent gate is independent of that
consumer package. Exact verdicts here are analytic fixture checks; execution
of an exact-body engine remains downstream work.

## Iris and illustrative requirements

Every value in the three requirement files is illustrative unless a cited
source document is present in the family's design record. The citations in
these files describe synthetic demo clauses; they do not assert the content
of a regulation, an employer's actual specification or a commercial datasheet.

| Source | Authority | Reader centre height | Other measures | Severity |
|---|---:|---|---|---|
| accessibility | 1 | 0.9–1.2 m | — | hard |
| employer-security | 2 | 1.05–1.2 m | 0.3–0.5 m to leaf edge; pull side | hard |
| reader-datasheet | 3 | 1.0–1.7 m | — | advisory |

`iris_readers` controls height, offset and side; per-door overrides merge onto
it. `reference: centre` makes height the actual body centre, verified against
IFC geometry. The base keeps `reference: base` and height 1.4 m because its
historical device box rises from that datum (centre 1.48 m). Only the centre
convention exports the new `DC_Security` measures; adding them to base would
break its byte contract. IFC lengths use project units (metres by default).
Controlled door geometry swings toward the recorded approach / pull side in
the iris variant. Selecting push moves the reader to the opposite space.

The variant's eleven readers have ten centres at 1.2 m and one at 1.65 m
(`door.office.link`): that reader fails the accessibility and employer bands
and passes the illustrative datasheet. All results are explicit per door in
the variant manifest. The measures and citations have no host-specific fields.

## Gate and reproduction evidence

The ordinary gate runs all five variants without writing their committed
manifests. It retains the original base rows, measures each variant's complete
IFC census, runs schema/EXPRESS and semantic validation on all federated files,
and compares independent plan and combined-IFC builds. The base additionally
compares all eight IFC files and the plan/target bytes against the captured
0.3.4 hashes in `manifests/base-v0.3.4-bytes.json`. IFC comparison permits only
the pre-existing header timestamp and the generator version stamp to differ.

G0 verifies exactly one enclosing activity per void per programme, temporary
installation/removal, valid scope/workspace ids, acyclic predecessors, declared
typical-floor changes, well-formed requirements and expected programme rule
families. Mutation tests reject missing and duplicate enclosures, missing
removals, dangling scopes, graph cycles, undeclared floor changes and unexpected
reader results. G1 joins these inputs to actual exported products, properties,
space placements and port counts. The new geometry tests inspect real IFC
vertices or swept-solid axes; exchange tests use independent XER/XML readers.

To repeat the compatibility probe, set `LEGACY_XER_IMPORTER` to the historical
importer file in an available read-only checkout:

```sh
env -u PYTHONPATH "$PY" scripts/probe_programme.py --importer "$LEGACY_XER_IMPORTER"
```

The script disables bytecode writing, executes only the parser in a temporary
working directory and emits counts plus source/input hashes. The measured
receipt is `manifests/programme-parser-probe.json`. Native scheduling-application
imports and downstream USD/mesh computations are not part of this gate.

The inherited corridor camera rule adds two cameras on L02, making 47 in the
floors variant. The historical recorder allowance and coverage evidence apply
to base. The pod assembly bodies are bounding envelopes; they do not model the
internal construction of a prefabricated bathroom.

## full

`full` merges `base` → `floors` → `pod` → `clash` → `iris`, using
`extends: [floors, pod, clash, iris]`. Parents resolve first, mappings recurse,
record lists merge by `id` in base order, and later scalar values win.
`clash` also inherits `pod`; merging its identical ids retains each fixture once.
The only interaction needing resolution is typical-room expansion: L02 copies
L01's six occupied rooms and doors, excluding ceiling voids. The two voids and
their programme enclosures remain on L01. Roof elevations and the partition
edit come from `floors`; controlled pipe tessellation comes from `clash`; the
1.65 m reader override comes from `iris`. There are no competing scalar values.

The union resolves to 3 storeys, 36 occupied rooms, 2 voids, 3 yards, 111 walls,
47 doors, 80 columns and 47 cameras. Fitout retains 2 ceilings, 2 pods and
6 / 10 / 3 first / second / third-fix products, plus the 3 planted pipes.
All 11 readers remain; ten are at 1.2 m and one at 1.65 m.

## Federation contract

`dcbuild publish --variant full` writes nine IFC4X3 deliveries and nine twins
in `dist/full/`. The delivery order, strongest first, is `site`, `arch`,
`structure`, `cooling`, `electrical`, `it`, `fitout`, `security`, then `shared`.
`dc.usda` sublayers those readable package roots. Each package root sublayers
`<package>.semantics.usda` before `<package>.geometry.usdc`. All nine roots
carry the same default prim, metres, Z up and eight stock fallbacks as the
historical variants. Keep the whole directory together when moving it.

The shared IFC contains project, site, facility, storeys, spaces and the
setting-out grid, with **zero elements**. The generator has no zones in this
fixture. Shared semantics alone defines the project and 46 spatial prims;
shared geometry carries 41 space extents with `purpose = guide`. Discipline
semantics has empty spatial `over`s, its own elements, ports and systems, and
its catalog **classes**, composed through `inherits` as required by core B5.
Geometry defines only owned bodies, with `over` ancestors. Catalog types stay
classes rather than changing the family type/occurrence contract.

| Delivery | Elements | Types | Systems | Ports | Meshes |
|---|---:|---:|---:|---:|---:|
| site | 3 | 0 | 0 | 0 | 3 |
| arch | 167 | 6 | 0 | 0 | 167 |
| structure | 84 | 2 | 0 | 0 | 84 |
| cooling | 737 | 22 | 3 | 1718 | 737 |
| electrical | 1254 | 21 | 2 | 2860 | 1254 |
| it | 671 | 8 | 3 | 1640 | 671 |
| fitout | 23 | 0 | 0 | 26 | 23 |
| security | 70 | 5 | 1 | 0 | 70 |
| shared | 0 | 0 | 0 | 0 | 41 |
| Total | 3009 | 64 | 9 | 6244 | 3050 |

The fixture mapping is L02 architecture → `arch`, with its spatial spine in
`shared`; pods, ceilings and 6/10/3 fix products → `fitout`; three clash pipes
→ `cooling`; all readers, including the 1.65 m example → `security`.
L02's architectural comparison has exactly the moved partition and extra door;
the partition totals remain 43.0 m / 46.2 m. The L01-only fitout is excluded
from that architectural comparison, and is separately counted in the union.

The full builder partitions the complete coordination IFC graph because the
legacy standalone builders omit intake ports that need an upstream discipline.
It selects owned referents, trims relationship sets, retains their reachable
geometry, properties and styling, and carries the same spatial skeleton in
each IFC. Spatial placement remains owned solely by shared in USD.
Header timestamps are fixed to `2000-01-01T00:00:00`; file names are basenames,
author/organization are empty, and the originating generator string is fixed
at `usdaeco-datacentre 0.5.0`. No comparison-time normalization is used for
published bytes. Historical build and publication paths are unchanged.

An IFC file cannot directly point to an entity in another IFC file. Each
external port target is therefore delivered as an `IfcDocumentReference`:
`Location` is the target package's IFC basename, `Identification` its port
GlobalId, and `Name` is `aeco:connectedPorts`. `Description` carries the target
port's absolute USD prim path exactly as authored in the twins.
`IfcRelAssociatesDocument` associates that reference with the local port.
A single-file reader authors the USD relationship target from `Description`
without defining the foreign prim or opening its delivery. Location,
Identification and Name retain their 0.5.0 values. The publisher resolves the
targets by identity in a preliminary authoring pass without geometry, using
the pinned converter's naming rules. It fills Description before converting
the delivered packages; all 504 connection pairs survive (1,008 directional
targets). The twin relationship post-pass reads those final descriptions.

The nine `aeco:serves` targets into shared use native
`IfcRelServicesBuildings`, not document references. Each delivery includes the
target building and its spatial ancestry, so a single-file reader resolves
`RelatedBuildings` locally and authors `aeco:serves` on `RelatingSystem`.
In USD the discipline's spatial ancestors are `over`s; only shared defines
them. No foreign prim definition is needed. There are zero cross-package
member targets. Every crossing target appears once in the manifest with
source, relationship, target and both package names.

| Delivery | Port document references | Native serves targets | Total crossings |
|---|---:|---:|---:|
| site | 0 | 0 | 0 |
| arch | 0 | 0 | 0 |
| structure | 0 | 0 | 0 |
| cooling | 184 | 3 | 187 |
| electrical | 344 | 2 | 346 |
| it | 480 | 3 | 483 |
| fitout | 0 | 0 | 0 |
| security | 0 | 1 | 1 |
| shared | 0 | 0 | 0 |
| Total | 1,008 | 9 | 1,017 |

The bundled converter exposes `overlay_spine`, but its frozen implementation
suppresses catalog classes and its later `DefinePrim` calls promote spatial
ancestors. The publisher uses its ordinary conversion, then clears spatial
opinions, demotes ancestors, retains classes and removes discipline space
extents. The frozen converter and frozen core bytes remain unchanged. The
three clash bodies use the same controlled tessellation as `clash`; measured
tolerance opinions are written in each body's owning geometry layer.
The IFC carries the swept solid while the near and tangent twins carry the
publisher's controlled facets. An independent IFC reader may tessellate those
same solids differently. Manifest `tessellationControlled` lists both mesh
paths, their `cooling` delivery, twin point counts (10 near, 24 tangent), and
the reason. This disclosure changes no geometry; the hard pipe retains the
converter's ordinary tessellation.

Every twin layer records `aeco:layer:role`, `package`, `producer`, `source`,
`sourceSha256` and `tag` in `customLayerData`. The producer is
`usdaeco-datacentre generator 0.5.0`, identifying the unchanged IFC generator.
The release tag is `v0.5.2`. A twin's source stamp is the delivered file:
`sourceSha256` equals SHA-256 of the adjacent `<package>.ifc` bytes, after
Description enrichment, on its root, semantics and geometry layers. The gate
checks all 27 stamps against the nine delivered IFCs directly. Manifest `files`
records those same delivered hashes and sizes; no `twinSourceFiles` indirection
is needed. The 0.5.1 baseline compares every twin opinion, excluding only the
source hash and release tag lines (geometry crates are exported as USDA for
comparison). Delivered IFCs, both images and historical variants retain their
released bytes. Census, identities, relationships, transforms and meshes stay
unchanged.
The manifest records package counts,
fixture mapping, source pins, relationship crossings and SHA-256/bytes for
all delivered files and both images. Its sole inventory exclusion is itself:
a file cannot include its own SHA-256; the vanilla receipt binds the manifest
externally. Run `run.py --all --publish` after changing rendered content to seal
both full images and their inventory. The 0.5.2 stamp correction retains
both full images and updates the full render receipts' source hashes;
the gate repeats the fresh render. Historical image bytes stay frozen while their
receipts bind the current renderer code and a fresh render is checked.

The full directory cap is **40,000,000 bytes**, including IFCs and images.
The five historical directories retain their **10,000,000-byte** caps.
The publication sweep treats `.ifc` as text and still rejects archives,
including archives disguised with an IFC extension.

## Connected root

`dc.connected.usda` uses the same header and order as `dc.usda`, with
`@<discipline>.ifc:SDF_FORMAT_ARGS:spine=over@` and finally `@shared.ifc@`.
It needs the **usdIfc plugin from usdaeco-ifc ≥ 0.3**. This repository checks
its header, exact asset tokens, arguments and ordering as text. It never
opens that root through Sdf or claims connected composition: **not proven**.
The reader must preserve catalog classes and translate the delivered external
port document references to reproduce the complete twin graph. That reader
integration remains to be verified when the plugin is available.

`dist/<variant>/dc.usda` remains the consumer entry for all six variants.
No consumer schema, hook, stage namespace or existing publication is changed.
