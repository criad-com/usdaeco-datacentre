# demo-datacentre-01 authoring conventions

Binding for BOTH builders (ifcopenshell + Revit). The parity gate assumes them.

## Identity

- Every product's IFC `GlobalId` = `ids.guid(spec_id)` — pass `key=spec_id` to
  `Builder.entity()`. Never let a *product* take a random GUID (relationships
  and psets are also assigned deterministic ids on serialization).
- Every product gets `b.identify(element, spec_id, ...)` → the `DC_Identity`
  pset (`Id`, `Discipline`, plus `Side`/`System`/`Loop` where meaningful).
- The Revit builder stamps the same dc id into the element's **Mark**
  parameter. Parity joins on it.
- Generated members of a run take keys derived from the run's base id (the
  `Run` class does this automatically via its `base`).

## Containment

- Elements inside a room: contained in the **IfcSpace** →
  `b.container_for(space_id)`. External equipment references its yard space; unresolved `EXT` falls back to the site.
- Every discipline module must work in BOTH the combined file and its own
  federated file, so: never reference another module's elements directly —
  only spaces/storeys (from `spatial`) and your own. The one exception:
  cross-discipline **port** connections (busway drop → rack) are owned by the
  upstream module and only authored when the downstream element exists
  (`b.ports.get(key)` / check before connecting).

## Class mapping (spec class → IFC4X3 → Revit category)

| spec class     | IFC4X3                                        | Revit                     |
|----------------|-----------------------------------------------|---------------------------|
| utility_intake | IfcBuildingElementProxy (ObjectType=UtilityIntake) | Generic Model        |
| rmu / msb / uob| IfcElectricDistributionBoard/SWITCHBOARD      | Electrical Equipment      |
| pdu / hdb      | IfcElectricDistributionBoard/DISTRIBUTIONBOARD| Electrical Equipment      |
| mcc            | IfcElectricDistributionBoard/MOTORCONTROLCENTRE| Electrical Equipment     |
| transformer    | IfcTransformer/CURRENT                        | Electrical Equipment      |
| generator      | IfcElectricGenerator/STANDALONE               | Electrical Equipment      |
| ups            | IfcElectricFlowStorageDevice/UPS              | Electrical Equipment      |
| battery        | IfcElectricFlowStorageDevice/BATTERY          | Electrical Equipment      |
| fuel_tank      | IfcTank/STORAGE                               | Mechanical Equipment      |
| dry_cooler     | IfcCoolingTower/USERDEFINED (ObjectType=DryCooler) | Mechanical Equipment |
| chiller        | IfcChiller/AIRCOOLED                          | Mechanical Equipment      |
| pump           | IfcPump/ENDSUCTION                            | Mechanical Equipment      |
| buffer_tank    | IfcTank/STORAGE                               | Mechanical Equipment      |
| dosing         | IfcUnitaryEquipment/USERDEFINED (ObjectType=DosingSkid) | Mechanical Equipment |
| heat_exchanger | IfcHeatExchanger/PLATE                        | Mechanical Equipment      |
| cdu            | IfcUnitaryEquipment/USERDEFINED (ObjectType=CDU) | Mechanical Equipment   |
| crah           | IfcUnitaryEquipment/AIRCONDITIONINGUNIT       | Mechanical Equipment      |
| ahu            | IfcUnitaryEquipment/AIRHANDLER                | Mechanical Equipment      |
| rack / carrier_rack | IfcFurniture/TECHNICALCABINET            | Specialty Equipment       |
| ava            | IfcAlarm/USERDEFINED (ObjectType=AVA)         | Security Devices          |
| dome_5mp / bullet_4mp_outdoor / ptz_4k | IfcAudioVisualAppliance/CAMERA + IfcAudioVisualApplianceType/CAMERA | Security Devices (camera phase pending) |
| iris           | IfcSensor/IDENTIFIERSENSOR                    | Security Devices          |
| busway         | IfcCableSegment/BUSBARSEGMENT                 | Cable Tray (type "Busway")|
| lv/hv/dc cable | IfcCableSegment/CABLESEGMENT                  | Cable Tray (type "Cable Run") |
| rack cord      | IfcCableSegment/CABLESEGMENT (DROPPER role)   | —                         |
| fuel_line      | IfcPipeSegment/RIGIDSEGMENT (SystemType FUEL) | Pipe                      |
| pipe           | IfcPipeSegment/RIGIDSEGMENT + IfcPipeFitting BEND/JUNCTION | Pipe + fittings |
| rack hose      | IfcPipeSegment/FLEXIBLESEGMENT                | Flex Pipe                 |
| data tray      | IfcCableCarrierSegment/CABLETRAYSEGMENT + fittings TEE/BEND | Cable Tray  |
| wall           | IfcWall (typed per kind) + IfcOpeningElement + IfcDoor | Wall + Door      |
| slab           | IfcSlab FLOOR / ROOF / BASESLAB (pads)        | Floor / Roof / Pad        |
| column         | IfcColumn                                     | Structural Column         |
| stair          | IfcStair                                      | Stair (or DirectShape)    |

Port SystemType per system: `sys.pwr.*` → ELECTRICAL (fuel legs FUEL),
`sys.fws` → CONDENSERWATER, `sys.chw` → CHILLEDWATER, `sys.data.*` → DATA,
`sys.sec` → SECURITY. `sys.tcs` → **USERDEFINED** (NOT "COOLING" — that value
does not exist in IfcDistributionSystemEnum; the system carries ObjectType
"TechnologyCooling", and TCS ports use SystemType USERDEFINED consistently).

Note: cable fittings (`IfcCableFitting`) have no BEND value — use `JUNCTION`
for cable/busway direction changes (`Run(bend_predef="JUNCTION", ...)`).

## Cross-module port hand-off

Build order is: arch, structure, site, **electrical, cooling, it**, security.
An upstream module REGISTERS its terminal ports under well-known keys in
`b.ports`; the downstream module (later in the order) looks them up and makes
the connection if present (absent in federated single-discipline files):

- `"{rack_id}.pwr.a"` / `"{rack_id}.pwr.b"` — busway drop-cord bottom port at
  each rack (registered by electrical; consumed by it, which authors the rack's
  own intake ports and connects SOURCE drop → SINK rack)
- `"{rack_id}.clg.s"` / `"{rack_id}.clg.r"` — TCS hose ends at each DLC rack
  (registered by cooling; consumed by it)

Register explicitly (`b.ports[key] = port`) — do NOT rely on Run's auto-keys
for cross-module lookups.

## Geometry

- Metres, site-local coordinates straight from the plan (`is_si=True`
  placements). The Revit builder converts to internal units at the boundary
  (`UnitUtils.ConvertToInternalUnits(value, UnitTypeId.Meters)`).
- Equipment `pos` = footprint centre at FFL; `size` = (w, d, h), w along local
  X before `rot` (CCW degrees about +Z). Profiles are CENTRED on the placement
  origin and extrude along local +Z, so `Builder.box(el, w, d, h,
  at(Z_UP, (pos.x, pos.y, pos.z)))` gives a box centred at pos rising h from
  FFL — no corner offsets. Rotated units: `geom.rot_z(rot, (x, y, z))`.
- Runs/routes carry their own z. Route polylines are orthogonal; use
  `Run.polyline()` which places bends automatically.
- Every material gets an RGB via `b.material(name, category, rgb=(r,g,b))` —
  colour-code by system (power A warm red, power B blue, FWS green, TCS teal,
  CHW light blue, data yellow, security purple, neutral greys for fabric).

## Data

- Authored ratings → typed psets via `b.properties()` (IfcPowerMeasure for kW,
  IfcElectricVoltageMeasure, etc.), named `DC_<Class>Rating`.
- Standard psets where they exist (`Pset_WallCommon`, `Pset_DoorCommon`, ...).
- Base quantities on fabric elements (`Qto_WallBaseQuantities`, slabs, spaces).
- Systems: `b.system("sys.pwr.a")` etc., members via `b.assign_system`, then
  one `b.serves_building(system, name)` per system per module (or Run.commit).

## Testing your module

```bash
env -u PYTHONPATH uv run dcbuild build-ifc --disciplines <yours>   # + spatial
env -u PYTHONPATH uv run python -c "import ifcopenshell; f=ifcopenshell.open('out/ifc/demo-datacentre-01.ifc'); print(len(f.by_type('IfcProduct')))"
```
(`env -u PYTHONPATH` matters in environments with a global USD path — a stale OpenUSD PYTHONPATH segfaults
python otherwise.)


## Cameras, phase and study targets

The exchange version is **usdaeco-cctv-ifc/1.0**. The family contract lives at
`usdaeco-cctv/docs/ifc-camera-contract.md`; `dcbuild.camera_contract` constructs
the writer's tier A payload. Every type carries Contract/Type/Sensors; every
occurrence carries Contract/Drivers/Sensors with named presets and tour order.
All JSON properties are IfcText. Tier A angles are degrees (tilt down-positive),
focals mm, range/offset metres, density px/m, dwell seconds. Heads have no GUID.

Tier B mirrors head 0 on `Pset_AudioVisualApplianceTypeCamera`: CameraType VIDEO,
IsOutdoors from the type, integer resolution, PanHorizontal in degrees despite
its length template, TiltHorizontal up-positive in project plane-angle units,
and Zoom in project length units. Preset table names are `Sensor_0:Name`, with
JSON tilt up-positive and focalLength in mm. Empty tables have both optional
value aggregates unset: IFC requires at least one item if an aggregate is
present. Both missing aggregates mean zero rows.

IFC occurrence placement is the device frame: +X pan-zero, +Z up. Pan, tilt
and roll remain drivers, never baked into placement. Type bodies use one
representation map each. Cameras belong to `sys.sec` and their resolved space.
Yards are exterior IfcSpaces under the site. Apron cameras use the nearest yard
association even where their points lie beyond the pad footprint.

`identify()` invokes one Status helper, selecting the closest applicable
Common Pset from the ifcopenshell template library. Every eligible product,
including spaces and ports, receives Status NEW. Spatial and port templates
without a standard Status field receive an IfcLabel extension. IfcGrid has no
applicable Common Pset and is the counted exception. Status coverage always
reports this denominator explicitly. Existing Common properties are retained.

`DC_DoorApproach` on each door records ApproachSpace, ApproachNormal (+X/-X/+Y/-Y,
pointing from the threshold toward the approach) and ThresholdHeight 1.6 m.
`out/targets.json` uses world metres and degree pose drivers, compressed
GlobalIds, open polygon vertex lists, and centre at threshold sample height.

`manifests/demo-datacentre-01.json` pins the canonical resolved plan and identity
digests, counts and camera GlobalIds. Update it deliberately after a design
change. `check.py` compares it before checking two independent STEP builds;
only the FILE_NAME timestamp is normalized. IFC SET attributes are sorted;
LISTs (including tour/preset-table order) retain their order; generated port
nesting follows deterministic creation order.
