# Exterior approach acceptance — 0.3.2

The unchanged family study schedule passes 5/5 exterior doors with the same
45 cameras. The plant-yard approach has 56 samples: two inside closed pipe
bodies remain explicitly enclosed; all 54 evaluated samples have fixed
coverage at ≥125 px/m, with a minimum of **126.338858 px/m**. All five
exterior doors together have **334/334 evaluated samples covered**
([saved-sample audit](history/acceptance-through-0.4.0/artifacts/exterior-sample-coverage.json)).
The original close bullet supplies 52 samples, and the
shared wide-opening bullet supplies the remaining two. No target, density,
pass fraction, obstacle or camera identity is removed to obtain this result.

## Measured gates

| Check | Result |
|---|---:|
| Generator `check.py` | 59 checks, 0 failed: 51 correctness passes, 8 informational timings |
| Generator pytest | 75 passed |
| Final combined family acceptance | 59 checks, 0 failed: 56 PASS, 1 FINDING, 2 NOT RUN |
| Datacentre rows | 32 PASS, 1 column FINDING, 1 native NOT RUN |
| Complete datacentre schedule and cases | 177.554 s / 240 s limit |
| Critical doors / exterior / corridors | 11/11 · 5/5 · 7/7 |
| Yard day / night / lobby | 8/8 · 8/8 · 3/3 |
| Privacy / critical-door column blockers | 0 · 0 |
| Independent rebuilds / reusable views | 2 matching builds · 136/136 views reused |
| Vanilla composition / datacentre renders | 12 stages · 3 images |
| Final regression suite / link roots | 53 passed · 18/18 |
| Generator and artifact term sweep | 0 hits |

The [generator report](history/acceptance-through-0.4.0/artifacts/check-exterior.json),
[family table](../artifacts/exterior-family-gate.json), and
[datacentre results](../artifacts/exterior-study-acceptance.json) retain real
counts and the column/native statuses. The family table combines one complete
run with the three final checks repeated after metadata/layout repairs; it
also retains both original final-check failures. Full operational acceptance
is not claimed.

## Placement rule

A wide external opening (at least 3 m) may share its existing bullet with the
nearest smaller exterior door within 18 m. Both doors must have the same level,
facade plane and outward approach normal. The pole lies opposite the midpoint
between the neighbour's threshold centre and the wide opening's far jamb.
Setback is 18.25 m, height 8 m, focal length 7.5 mm, and aim height 1.2 m.
The high view clears the yard equipment. The original neighbour bullet keeps
its close view; the two directions see around the supply/return pipe pair.

In this plan the rule selects `sec.cam.ext.dock`, retaining its GUID and adding
`door.plant.ext` to its existing `door.dock` target association. The other 44
camera records are unchanged ([identity and driver diff](history/acceptance-through-0.4.0/artifacts/exterior-camera-change.json)). Both builders consume the same resolved drivers.
The independent optical check includes the complete inset primary door face
corners, with minimum density **126.712970 px/m**. The family ray study is still
required to establish actual visibility; the margin above 125 px/m is small.

## Column exception

| Camera | Target | Named column | Fixed coverage of target |
|---|---|---|---:|
| `sec.cam.corr.corr.spine.4` | `sp.corr.c` | `col.044` | 288/288 samples |
| `sec.cam.corr.corr.spine.5` | `sp.corr.e` | `col.071` | 288/288 samples |

These are cross-corridor views from cameras assigned to the spine. The centre
and east corridors have their own opposing fixed cameras, supplemented by
local door cameras. Their results have fraction 1.0 against a required 0.9;
critical-door results name zero columns. Moving a spine camera merely to change
its redundant ray's first blocker would not improve an uncovered requirement.
The two findings remain visible in `DC-column`, with this explicit exception.
Zero column blockers is not claimed. A separate rerun using only the four
assigned corridor cameras (both pairs, with all spine and door views removed)
still covers **288/288 samples in each corridor**. Reproduce it with
`scripts/column_views.py` as shown in the README. The complete before/after
results are in [column evidence](history/acceptance-through-0.4.0/artifacts/column-view-exception.json).

## Reproduction and boundaries

Use the README's generator checks and `scripts/study.py` commands with the
compatible re-pinned family (CCTV 0.4.4). The scenario schedule remains owned by
`usdaeco-scenarios`. The original 0.3.0 evidence is historical and retains its
then-current enclosed-sample findings.

The subsequent [0.3.3 native rerun](acceptance-revit.md) verifies the camera
move and optical tolerances. Pole support, installation access, lighting and
operational recognition remain unproven. The geometric study does not certify
these. The two pipe-enclosed approach points still describe a
physical obstruction; they are not labelled covered. No live host was used
for this exterior study.

## Family gate source and deviations

The re-pinned scenarios release had not reached `main` during this run.
An owned copy of scenarios revision
`577f3ec75c18d454954baea2d832e8e87f30636e` supplies the candidate gate; the
[provenance manifest](history/acceptance-through-0.4.0/artifacts/exterior-gate-provenance.json) records the
exact source revision and compatible dependency closure.

The [candidate runner patch](history/acceptance-through-0.4.0/artifacts/family-runner-adaptation.patch) changes
the generator dependency/Nix input records and the native-reference ancestry
assertion. The candidate lock hash is computed from its committed Git archive;
this is metadata preparation, not a Nix build.
The historical native evidence must be an ancestor of the candidate and its
artifact hash must still agree; its recorded release and version stay 0.3.1.
The sampling, provider selection, requirements and study functions are unchanged.
No branch or tag in a sibling checkout is modified. This is candidate evidence,
not a claim that a released scenarios pin already names generator 0.3.2.

The first integration launch was stopped after Sync found two physical copies
of the core plugin: the reused aggregate referred outside the disposable source
closure. The completed run uses an aggregate assembled from its own isolated
copies. That full run's final regression check then found the candidate Nix
pin still naming the preceding release, and its link check found the owned
runner lacked the conventional core sibling path. The candidate Nix input and
lock metadata were synchronized, and the sibling link restored. Only the last
three checks were repeated: 53 tests passed, 18/18 link roots passed and the
term sweep stayed clean. No coverage schedule was rerun or weakened for these
repairs. The gate audits and reuses the unchanged passing library evidence;
Sync, generator and family scenarios run afresh. The retained two column
findings are the explicit coverage exception described above.

One `nix flake check --offline` invocation found no `flake.nix` in this repository
or its parents. Nix is **not proven**; there was no nested-input resolution to
report and no second Nix attempt.

To reproduce the complete gate, start with the family source checkouts at the
revisions in the provenance manifest. `PY`, `AECO_FAMILY_ROOT`,
`AECO_SCENARIOS_SOURCE`, `USD_DEV` and the optional local Blender executable
follow the family README. Use new output directories for these disposable
checkouts; this retains the exact implementation revision tested here, even
when later commits only add reports:

```sh
export DC_GATE_REV=$(env -u PYTHONPATH "$PY" -c 'import json; print(json.load(open("docs/history/acceptance-through-0.4.0/artifacts/exterior-gate-provenance.json"))["generatorRevision"])')
export DC_SCENARIOS_REV=$(env -u PYTHONPATH "$PY" -c 'import json; print(json.load(open("docs/history/acceptance-through-0.4.0/artifacts/exterior-gate-provenance.json"))["scenariosRevision"])')
git clone --no-hardlinks . out/gate-generator
git -C out/gate-generator checkout -B wp/W12 "$DC_GATE_REV"
git clone --no-hardlinks "$AECO_SCENARIOS_SOURCE" out/family-runner
git -C out/family-runner checkout --detach "$DC_SCENARIOS_REV"
git -C out/family-runner apply "$PWD/docs/history/acceptance-through-0.4.0/artifacts/family-runner-adaptation.patch"
ln -s "$AECO_FAMILY_ROOT/usdaeco-core" out/usdaeco-core
export AECO_DATACENTRE_SOURCE="$PWD/out/gate-generator"
export PYTHONDONTWRITEBYTECODE=1
env -u PYTHONPATH "$PY" out/family-runner/check_all.py --output "$PWD/out/family-gate"
```

The command builds its plugin aggregate against its own isolated sources.
The recorded run additionally used `--reuse-library-report` for previously
passing unchanged libraries, guarded by the runner's exact source audit.
