"""
Headless Bonsai (Blender) import + render of the data-centre IFC.

This is the *Bonsai* half of the hybrid workflow: it loads the IFC authored by
the dcbuild IFC builder into Blender via the Bonsai extension and renders a
solid (Workbench) image so the geometry and the cable containment route can be
eyeballed. Run with Blender in background mode::

    blender -b \
        --python scripts/render_bonsai.py -- \
        out/ifc/demo-datacentre-01.ifc out/render.png

After loading, the IFC is fully editable in the Bonsai UI (open the same file
interactively to extend the model).
"""
import sys
import math

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ifc_path = argv[0] if argv else "out/ifc/demo-datacentre-01.ifc"
out_png = argv[1] if len(argv) > 1 else "out/render.png"

# -- Enable the Bonsai extension -------------------------------------------
for mod in ("bl_ext.blender_org.bonsai", "bl_ext.user_default.bonsai", "bonsai"):
    try:
        bpy.ops.preferences.addon_enable(module=mod)
        print(f"[render] enabled addon: {mod}")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"[render] could not enable {mod}: {exc}")

# -- Load the IFC project via Bonsai ---------------------------------------
print(f"[render] loading IFC: {ifc_path}")
bpy.ops.bim.load_project(filepath=ifc_path)

# -- Colour objects by IFC class so the containment system stands out ------
# Bonsai names objects "IfcClass/Name", so we colour off the prefix.
IFC_COLOURS = {
    "IfcCableCarrierSegment": (0.95, 0.55, 0.10, 1.0),  # orange - tray/conduit
    "IfcCableCarrierFitting": (0.95, 0.75, 0.10, 1.0),  # yellow - fittings
    "IfcFurniture": (0.20, 0.45, 0.85, 1.0),            # blue   - racks
    "IfcSlab": (0.55, 0.55, 0.58, 1.0),                 # grey   - floor
    "IfcWall": (0.82, 0.78, 0.68, 1.0),                 # tan    - walls
    "IfcDoor": (0.45, 0.27, 0.12, 1.0),                 # brown  - door
    "IfcAlarm": (0.90, 0.10, 0.10, 1.0),                # red    - AVA (inside)
    "IfcSensor": (0.10, 0.80, 0.35, 1.0),               # green  - iris (outside)
    "IfcElectricGenerator": (0.55, 0.10, 0.10, 1.0),    # maroon - generators
    "IfcElectricDistributionBoard": (0.95, 0.65, 0.10, 1.0),  # amber - switchboard / PDU
    "IfcSwitchingDevice": (0.60, 0.30, 0.75, 1.0),      # purple - ATS
    "IfcElectricFlowStorageDevice": (0.30, 0.65, 0.30, 1.0),  # green - UPS
    "IfcCommunicationsAppliance": (0.10, 0.80, 0.80, 1.0),    # cyan  - OLT (MMR)
    "IfcPipeSegment": (0.20, 0.55, 0.95, 1.0),          # blue  - cooling pipework
    "IfcPipeFitting": (0.20, 0.55, 0.95, 1.0),
    "IfcCoolingTower": (0.15, 0.40, 0.75, 1.0),         # deep blue - cooling plant
    "IfcChiller": (0.15, 0.40, 0.75, 1.0),
    "IfcTank": (0.15, 0.40, 0.75, 1.0),
    "IfcHeatExchanger": (0.15, 0.40, 0.75, 1.0),
    "IfcPump": (0.15, 0.40, 0.75, 1.0),
    "IfcCableSegment": (0.65, 0.20, 0.85, 1.0),         # violet - busway / cables
    "IfcCableFitting": (0.65, 0.20, 0.85, 1.0),
    "IfcUnitaryEquipment": (0.10, 0.60, 0.60, 1.0),     # teal  - CDU / CRAH / AHU
    "IfcTransformer": (0.95, 0.65, 0.10, 1.0),          # amber
    "IfcColumn": (0.60, 0.60, 0.62, 1.0),               # grey  - structure
    "IfcBeam": (0.60, 0.60, 0.62, 1.0),
    "IfcStair": (0.70, 0.66, 0.58, 1.0),
    "IfcBuildingElementProxy": (0.50, 0.50, 0.52, 1.0), # utility intakes
}
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    ifc_class = obj.name.split("/", 1)[0]
    # Hide IfcSpaces (room volumes) + library type representations that Bonsai
    # places at the origin (e.g. IfcFurnitureType) -- neither is a real occurrence.
    if ifc_class in ("IfcSpace", "IfcOpeningElement") or ifc_class.endswith("Type"):
        obj.hide_render = True
        continue
    colour = IFC_COLOURS.get(ifc_class)
    if "Conduit" in obj.name:
        colour = (0.85, 0.15, 0.15, 1.0)                # red - conduit drop
    if any(k in obj.name for k in ("Power Bus", "Power Drop", "Power Busway",
                                   "Gen Ladder", "Gen Dropper", "PDU Riser", "ATS Riser")):
        colour = (0.65, 0.20, 0.85, 1.0)                # violet - power containment
    if any(k in obj.name for k in ("Desk", "Chair", "Table")):
        colour = (0.20, 0.70, 0.65, 1.0)                # teal - office furniture
    if colour:
        obj.color = colour

# -- Frame the model with a camera -----------------------------------------
# Compute the scene bounds from visible mesh objects (skip the hidden spaces +
# type representations so they don't throw off the framing).
mins = [1e9, 1e9, 1e9]
maxs = [-1e9, -1e9, -1e9]
for obj in bpy.context.scene.objects:
    if obj.type != "MESH" or obj.hide_render:
        continue
    for corner in obj.bound_box:
        world = obj.matrix_world @ __import__("mathutils").Vector(corner)
        for i in range(3):
            mins[i] = min(mins[i], world[i])
            maxs[i] = max(maxs[i], world[i])
center = [(mins[i] + maxs[i]) / 2 for i in range(3)]
size = max(maxs[i] - mins[i] for i in range(3))
print(f"[render] bounds min={mins} max={maxs} center={center}")

cam_data = bpy.data.cameras.new("DCCam")
cam = bpy.data.objects.new("DCCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
# Place the camera at an iso-ish vantage and aim it at the centre.
import mathutils  # noqa: E402
cam.location = (center[0] + size * 0.85, center[1] - size * 1.05, center[2] + size * 1.35)
direction = mathutils.Vector(center) - mathutils.Vector(cam.location)
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam

# -- Workbench render (robust headless, solid shaded) ----------------------
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 1280
scene.render.resolution_y = 800
scene.render.film_transparent = False
scene.render.filepath = out_png
try:
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "OBJECT"
    shading.show_cavity = True
    # See-through walls so the interior (racks, tray, AVA) stays visible.
    shading.show_xray = True
    shading.xray_alpha = 0.55
except Exception as exc:  # noqa: BLE001
    print(f"[render] shading tweak skipped: {exc}")

print(f"[render] rendering -> {out_png}")
bpy.ops.render.render(write_still=True)
print("[render] done")
