# demo-datacentre-01 — facility brief

A 2.8 MW dual-hall data centre, complete enough to exercise every discipline,
small enough to rebuild in seconds. G0 (`dcbuild check`) checks the stated power, redundancy, circulation,
door clearance and camera rule invariants. Coverage studies are separate.

## Building

Single-storey technical block (72 × 36 m, 6 m clear, roof at +7.0) with a
two-storey office wing (18 × 12 m) on the south face. 6 m setting-out grid
(numbers along X, letters along Y). Precast external envelope, blockwork fire
compartments (halls, electrical, battery, plant, MMRs, fire, water), stud
partitions elsewhere.

| Zone | Rooms |
|------|-------|
| North band | Data Hall A (30×18, DLC), Data Hall B (30×18, air), 3 access corridors |
| Spine | full-width corridor linking every technical room |
| South band | Electrical A + Battery A (west), corridor, MMR-1 + Fire Suppression, Cooling Plant, MMR-2 + Water Treatment, Loading & Storage, Electrical B + Battery B (east) |
| Office L00 | lobby, stair, security office, NOC, meeting, office comms room |
| Office L01 | open office, meeting, kitchen/break, WC |
| External | Generator Yard A (west), Generator Yard B (east), Heat Rejection Yard (south) |

Physical A/B separation: the two electrical rooms, battery rooms and generator
yards sit at opposite ends of the building.

## IT

- **Hall A** — 4 rows × 20 racks @ 25 kW = **2.0 MW**, direct liquid cooled
  (rack quick-connects at 2.2 m to per-row supply/return manifolds).
- **Hall B** — 4 rows × 20 racks @ 10 kW = **0.8 MW**, air cooled (perimeter
  CRAHs, hot-aisle containment).
- Two meet-me rooms (4 carrier racks each): MMR-1 serves Hall A, MMR-2 Hall B;
  per-row overhead data trays collect to spine trays into the serving MMR.

## Electrical — 2N

Two fully-independent trains, each sized for the whole facility
(IT 2800/0.95 + mech 600 + house 200 ≈ 3.75 MW → 4.2 MVA @ 0.9 pf):

```
UTIL-x (11 kV) → RMU-x → TX-x 5 MVA → MSB-x ← GEN-x 5 MVA diesel (FT-x 20 m³)
MSB-x → UPS-x1..x4 (4 × 800 kW, BAT-x1..x4) → UOB-x → 8 PDUs (one per row)
      → MCC-x (mechanical) → HDB-x (house/office)
```

Every rack row carries an A busway and a B busway; every rack is dual-corded.
G0 proves: each of the 160 racks has node-disjoint paths to both utility
intakes, and no equipment is shared between trains.

## Cooling

- **FWS** (facility water, glycol): DRC-1..4 dry coolers (4 × 700 kW, N+1) ↔
  CDU-A1..4 primaries (4 × 800 kW, N+1 vs 2.0 MW); FWP-1..3 pumps (N+1),
  buffer tank, dosing skid, trim plate-HX to CHW.
- **TCS** (Hall A secondary): CDUs → per-row manifolds → 160 hoses (80 racks
  × supply/return) at 2.2 m.
- **CHW**: CH-1/2 chillers (2 × 1 MW, N+1 vs 0.9 MW) ↔ CRAH-B1..6
  (6 × 200 kW, N+1 vs 0.8 MW) + AHU-1 (office) + trim HX; CHP-1..3 pumps.

Mechanical power is single-corded but alternated across MCC-A/MCC-B so no
N+1 group dies with one MCC (G0 `mech_diversity`).

## Security

Security rules in `spec/security.yaml` retain 12 volumetric alarms and 11
iris readers, and resolve 29 single-head cameras on three generic types:

| Rule | Cameras | Placement |
|---|---:|---|
| Access-controlled doors | 11 domes | Approach corridor, 1.7 m from door, clear height minus 0.1 m, tilt 45° |
| External doors | 5 outdoor bullets | 2.5 m outside, 3.5 m high, tilt 35° |
| Corridors | 10 domes | Long-axis interval centres, spacing at most 18 m, tilt 30° |
| Generator yards | 2 PTZs | 6 m poles, Home and pad preset, ordered tour |
| Lobby | 1 PTZ | 3.3 m corner mount, Home/MainDoor/LobbyCorridor tour |

The three yard spaces use the equipment-pad footprints. The five external
door approaches are associated with their nearest yard space; two camera
positions fall outside those pad footprints (entrance and loading aprons). That association is a spatial ownership convention,
not a claim that the pad covers each approach. The PTZ type is outdoor-capable
and is also used indoors in the lobby. Its IR range is zero.

The resolver exports approach-side normals (pointing from door into approach),
threshold sample height 1.6 m, 41 door targets, 11 corridor/yard/lobby polygons
and camera poses to `out/targets.json`. The 10 corridor cameras include both
office corridors. Seven presets and three tours are resolved from geometry.

Four doors move 3 m along their existing walls to clear columns. The centre
corridor's 4 m wall cannot accommodate that shift or a 1.8 m opening between
its three columns: it uses a 0.9 m single door shifted 1 m instead. All 41
openings have at least 0.3 m column clearance; the minimum is 0.35 m.

These are generated geometric inputs. Identify/recognise coverage, privacy,
night performance, PTZ duty and the final camera-count freeze require the
family's explicit-sample studies. No commissioning or coverage pass is claimed.
The requested placement schedule includes three PTZs; its separate allowance
of two supplementary PTZs therefore remains a study/design reconciliation.

## Deliberate v1 simplifications

- No raised floors (modern DLC slab-and-overhead design); no ductwork (AHU is
  placed and piped, distribution deferred); no fire-suppression pipework (room
  + bottles placed); no furniture beyond comms/MMR racks; generators/TX on
  open pads rather than enclosures; stair modelled as a massing flight.
