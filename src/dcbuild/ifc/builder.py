"""The shared model Builder (IFC4X3), evolved from dc-examples/dcgen.

A thin convenience layer over the ifcopenshell API that holds the open file,
the geometric contexts and the spatial roots (project / site / building /
storeys / spaces), plus the helpers every discipline module needs. Discipline
modules take a ``Builder`` and add to it.

New over dcgen: multi-storey, first-class spaces, deterministic GUIDs from DC
ids (``key=``), colour styles per material, and the ``DC_Identity`` pset that
carries the DC id into every downstream consumer (and joins the IFC model to
the Revit model, which stamps the same id into its DC_ID parameter).
"""
from __future__ import annotations

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.profile
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.style
import ifcopenshell.api.system
import ifcopenshell.api.type
import ifcopenshell.api.unit
import ifcopenshell.util.unit
import ifcopenshell.util.pset
import ifcopenshell.util.element
import numpy as np

from .. import ids, __version__


class Builder:
    def __init__(self, plan, discipline: str = "coordination"):
        self.plan = plan
        self.discipline = discipline
        self._keys = {}
        self._identified = set()
        self._identity_psets = {}
        self._status_authored = set()
        self._containments = {}
        self._port_nests = {}
        self._status_templates = {}
        self.status_skipped = {}
        self.file = ifcopenshell.file(schema="IFC4X3")
        f = self.file

        self.project = self.entity("IfcProject", name=plan.meta["code"], key="project")
        self.project.Description = plan.meta["name"]
        ifcopenshell.api.unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"})
        angle = f.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")
        self.project.UnitsInContext.Units = [*self.project.UnitsInContext.Units, angle]
        self.model_ctx = ifcopenshell.api.context.add_context(f, context_type="Model")
        self.body = ifcopenshell.api.context.add_context(
            f, context_type="Model", context_identifier="Body",
            target_view="MODEL_VIEW", parent=self.model_ctx,
        )

        self.site = self.entity("IfcSite", name=f"{plan.meta['code']} Site", key="site")
        self.building = self.entity("IfcBuilding", name=plan.meta["code"], key="building")
        self.aggregate([self.site], self.project)
        self.aggregate([self.building], self.site)

        self.storeys: dict[str, ifcopenshell.entity_instance] = {}
        for s in plan.storeys:
            st = self.entity("IfcBuildingStorey", name=s.name, key=s.id)
            st.Elevation = s.elevation
            prototype = plan.meta.get("storey_rules", {}).get(s.id, {}).get("typical_of")
            if prototype:
                self.pset(st, "DC_Typical", {"Prototype": prototype})
            self.place(st, np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                                     [0, 0, 1, s.elevation], [0, 0, 0, 1]], dtype=float))
            self.storeys[s.id] = st
        self.aggregate(list(self.storeys.values()), self.building)

        self.spaces: dict[str, ifcopenshell.entity_instance] = {}
        self.systems: dict[str, ifcopenshell.entity_instance] = {}
        self.ports: dict[str, ifcopenshell.entity_instance] = {}   # shared port registry (dc key -> port)
        self._materials: dict[str, ifcopenshell.entity_instance] = {}
        self._styles: dict[str, ifcopenshell.entity_instance] = {}
        self._types: dict[str, ifcopenshell.entity_instance] = {}

    # -- storey helpers ----------------------------------------------------
    def storey(self, storey_id: str):
        return self.storeys[storey_id]

    def storey_elev(self, storey_id: str) -> float:
        return next(s.elevation for s in self.plan.storeys if s.id == storey_id)

    def container_for(self, space_id: str | None):
        """The spatial container for an element: its space if modelled, the
        site for EXT, else ground storey."""
        if space_id and space_id != "EXT" and space_id in self.spaces:
            return self.spaces[space_id]
        if space_id == "EXT":
            return self.site
        return self.storeys[self.plan.storeys[0].id]

    # -- entities / structure ----------------------------------------------
    def entity(self, ifc_class, predefined=None, name=None, key: str | None = None):
        e = ifcopenshell.api.root.create_entity(
            self.file, ifc_class=ifc_class, predefined_type=predefined, name=name
        )
        if key:
            e.GlobalId = ids.guid(key)
            self._keys[e.id()] = key
            if e.is_a("IfcProduct"):
                self.identify(e, key)
        return e

    def typed(self, type_class, predefined, type_name, key: str | None = None):
        """Get-or-create a shared element type (one per type_name)."""
        if type_name not in self._types:
            self._types[type_name] = self.entity(
                type_class, predefined=predefined, name=type_name,
                key=key or f"type.{type_name}")
        return self._types[type_name]

    def aggregate(self, children, parent):
        # The API reparents placements while iterating an unordered set.
        # One child per call fixes creation order as well as relation order.
        for child in children:
            ifcopenshell.api.aggregate.assign_object(
                self.file, products=[child], relating_object=parent
            )

    def assign_type(self, elements, relating_type):
        ifcopenshell.api.type.assign_type(
            self.file, related_objects=list(elements), relating_type=relating_type
        )

    def contain(self, element, matrix=None, structure=None):
        """Place (optional) + contain an element in a spatial structure."""
        container = structure if structure is not None else self.storeys[self.plan.storeys[0].id]
        # One legal containment relation per product avoids repeatedly copying
        # thousands of members of a storey-wide SET during generated authoring.
        relation = self._containments.get(element.id())
        if relation is None:
            relation = self.file.create_entity("IfcRelContainedInSpatialStructure",
                GlobalId=ifcopenshell.guid.new(), RelatedElements=[element], RelatingStructure=container)
            self._containments[element.id()] = relation
        else:
            relation.RelatingStructure = container
        if matrix is not None:
            self.place(element, matrix)
        return element

    def place(self, element, matrix):
        ifcopenshell.api.geometry.edit_object_placement(
            self.file, product=element, matrix=np.asarray(matrix, dtype=float), is_si=True
        )

    def add_space(self, space_plan):
        """Author an IfcSpace from a plan SpaceP and register it (aggregated in
        its storey; boundary geometry = its rect extruded to its height)."""
        sp = self.entity("IfcSpace", name=space_plan.name, key=space_plan.id)
        sp.LongName = space_plan.name
        parent = self.plan.meta.get("space_geometry", {}).get(space_plan.id, {}).get("parent")
        container = self.spaces[parent] if parent else (self.site if space_plan.external else self.storeys[space_plan.storey])
        self.aggregate([sp], container)
        polygon = self.plan.meta.get("space_geometry", {}).get(space_plan.id, {}).get("footprint")
        rep = self.profile_rep(self.arbitrary_profile(polygon) if polygon else
                               self.rect_profile(space_plan.w, space_plan.d), space_plan.height)
        self.assign_rep(sp, rep)
        cx = space_plan.x + space_plan.w / 2.0
        cy = space_plan.y + space_plan.d / 2.0
        if polygon:
            cx = cy = 0.0
        z = 0.0 if space_plan.external else self.storey_elev(space_plan.storey)
        z += self.plan.meta.get("space_geometry", {}).get(space_plan.id, {}).get("z_offset", 0)
        self.place(sp, np.array([[1, 0, 0, cx], [0, 1, 0, cy],
                                 [0, 0, 1, z], [0, 0, 0, 1]], dtype=float))
        self.spaces[space_plan.id] = sp
        return sp

    # -- identity ----------------------------------------------------------
    def identify(self, element, spec_id: str, **extra):
        """DC_Identity pset: the join key between spec / plan / IFC / Revit."""
        if element.id() in self._identified and not extra:
            return
        props = {"Id": spec_id, "Discipline": self.discipline}
        props.update({k: v for k, v in extra.items() if v is not None})
        if element.id() not in self._identity_psets:
            self._identity_psets[element.id()] = self.properties(
                element, "DC_Identity", [(k, "IfcIdentifier" if k == "Id" else "IfcLabel", v) for k, v in props.items()])
        else:
            ps = self._identity_psets[element.id()]
            present = {p.Name: p for p in ps.HasProperties}
            for name, value in props.items():
                if name in present:
                    present[name].NominalValue.wrappedValue = value
                else:
                    present[name] = self.file.create_entity("IfcPropertySingleValue", Name=name,
                        NominalValue=self.file.create_entity("IfcLabel", value))
            ps.HasProperties = list(present.values())
        self._keys[element.id()] = spec_id
        self._identified.add(element.id())
        self.status(element)

    def status(self, element):
        """NEW in the closest applicable Common Pset; count classes without one."""
        if element.id() in self._status_authored:
            return
        self._status_authored.add(element.id())
        cls = element.is_a()
        if cls not in self._status_templates:
            templates = ifcopenshell.util.pset.get_template(self.file.schema).get_applicable(cls, pset_only=True)
            common = [t for t in templates if t.Name.endswith("Common")]
            preferred = (f"Pset_{cls[3:]}Common", f"Pset_{cls[3:]}TypeCommon")
            common.sort(key=lambda t: (preferred.index(t.Name) if t.Name in preferred else 2, t.Name))
            self._status_templates[cls] = common[0] if common else None
        template = self._status_templates[cls]
        if template is None:
            self.status_skipped[element.id()] = cls
            return
        spec_id = self._keys.get(element.id())
        value = next((e["status"] for e in self.plan.meta.get("fitout", []) if e["id"] == spec_id), "NEW")
        enum = any(p.Name == "Status" and p.TemplateType == "P_ENUMERATEDVALUE"
                   for p in template.HasPropertyTemplates)
        if enum:
            prop = self.file.create_entity("IfcPropertyEnumeratedValue", Name="Status",
                EnumerationValues=[self.file.create_entity("IfcLabel", value)])
        else:
            prop = self.file.create_entity("IfcPropertySingleValue", Name="Status",
                NominalValue=self.file.create_entity("IfcLabel", value))
        self._attach_properties(element, template.Name, [prop])

    # -- materials / styles / property sets --------------------------------
    def material(self, name, category=None, rgb: tuple[float, float, float] | None = None):
        if name not in self._materials:
            m = ifcopenshell.api.material.add_material(self.file, name=name, category=category)
            self._materials[name] = m
            if rgb is not None:
                style = ifcopenshell.api.style.add_style(self.file, name=f"{name} Style")
                ifcopenshell.api.style.add_surface_style(
                    self.file, style=style, ifc_class="IfcSurfaceStyleShading",
                    attributes={"SurfaceColour": {"Name": None, "Red": rgb[0],
                                                  "Green": rgb[1], "Blue": rgb[2]}})
                ifcopenshell.api.style.assign_material_style(
                    self.file, material=m, style=style, context=self.body)
                self._styles[name] = style
        return self._materials[name]

    def assign_material(self, products, material):
        ifcopenshell.api.material.assign_material(
            self.file, products=list(products), type="IfcMaterial", material=material
        )

    def style_product(self, product, material_name):
        """Directly style a product's representation items with a material's
        colour (for viewers that ignore material-level styles)."""
        style = self._styles.get(material_name)
        if style is None or not product.Representation:
            return
        for rep in product.Representation.Representations:
            ifcopenshell.api.style.assign_representation_styles(
                self.file, shape_representation=rep, styles=[style])

    def pset(self, product, name, properties):
        ps = ifcopenshell.api.pset.add_pset(self.file, product=product, name=name)
        ifcopenshell.api.pset.edit_pset(self.file, pset=ps, properties=properties)
        return ps

    def properties(self, owner, name, items):
        """An IfcPropertySet of explicitly-typed IfcPropertySingleValues.

        `items` is ``(PropName, IfcMeasureType, value)``; authoring the measure
        type directly preserves the physical dimension (IfcPowerMeasure etc.).
        """
        props = [self.file.create_entity(
                     "IfcPropertySingleValue", Name=pname,
                     NominalValue=self.file.create_entity(measure, value))
                 for pname, measure, value in items]
        return self._attach_properties(owner, name, props)

    def _attach_properties(self, owner, name, props):
        ps = self.file.create_entity(
            "IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name=name, HasProperties=props)
        if owner.is_a("IfcTypeObject"):
            owner.HasPropertySets = list(owner.HasPropertySets or []) + [ps]
        else:
            self.file.create_entity(
                "IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[owner], RelatingPropertyDefinition=ps)
        return ps

    _QTY = {
        "length": ("IfcQuantityLength", "LengthValue"),
        "area": ("IfcQuantityArea", "AreaValue"),
        "volume": ("IfcQuantityVolume", "VolumeValue"),
        "weight": ("IfcQuantityWeight", "WeightValue"),
        "count": ("IfcQuantityCount", "CountValue"),
    }

    def quantities(self, element, name, items):
        """An IfcElementQuantity of typed IfcQuantity* records (project units)."""
        qs = []
        for qname, kind, value in items:
            cls, attr = self._QTY[kind]
            qs.append(self.file.create_entity(cls, Name=qname, **{attr: float(value)}))
        eq = self.file.create_entity(
            "IfcElementQuantity", GlobalId=ifcopenshell.guid.new(), Name=name, Quantities=qs
        )
        self.file.create_entity(
            "IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[element], RelatingPropertyDefinition=eq,
        )
        return eq

    def quantity_length(self, element, length, name="Qto_CableCarrierSegmentBaseQuantities"):
        return self.quantities(element, name, [("Length", "length", length)])

    # -- geometry representations ------------------------------------------
    def rect_profile(self, xdim, ydim):
        p = ifcopenshell.api.profile.add_parameterized_profile(
            self.file, ifc_class="IfcRectangleProfileDef"
        )
        scale = ifcopenshell.util.unit.calculate_unit_scale(self.file)
        p.XDim, p.YDim = xdim/scale, ydim/scale
        return p

    def circle_profile(self, radius):
        p = ifcopenshell.api.profile.add_parameterized_profile(
            self.file, ifc_class="IfcCircleProfileDef"
        )
        p.Radius = radius/ifcopenshell.util.unit.calculate_unit_scale(self.file)
        return p

    def profile_rep(self, profile, depth):
        return ifcopenshell.api.geometry.add_profile_representation(
            self.file, context=self.body, profile=profile, depth=depth
        )

    def slab_rep(self, depth, polyline):
        return ifcopenshell.api.geometry.add_slab_representation(
            self.file, context=self.body, depth=depth, polyline=polyline
        )

    def poly2d(self, pts):
        """Closed 2D IfcIndexedPolyCurve (coords in metres, scaled to model unit)."""
        scale = ifcopenshell.util.unit.calculate_unit_scale(self.file)
        loop = list(pts)
        if loop[0] != loop[-1]:
            loop = loop + [loop[0]]
        points = self.file.create_entity(
            "IfcCartesianPointList2D",
            [[float(x) / scale, float(y) / scale] for x, y in loop],
        )
        return self.file.create_entity("IfcIndexedPolyCurve", points)

    def arbitrary_profile(self, outer_pts):
        return self.file.create_entity(
            "IfcArbitraryClosedProfileDef", "AREA", None, self.poly2d(outer_pts))

    def voided_slab_rep(self, depth, outer, voids):
        """A slab profile `outer` with inner `voids` cut out, extruded `depth`
        along local +Z. Hand-authored (the 0.8.5 API helper emits a 3D outer
        curve which fails IfcArbitraryClosedProfileDef.WR1)."""
        profile = self.file.create_entity(
            "IfcArbitraryProfileDefWithVoids", "AREA", None,
            self.poly2d(outer), [self.poly2d(v) for v in voids],
        )
        return ifcopenshell.api.geometry.add_profile_representation(
            self.file, context=self.body, profile=profile, depth=depth
        )

    def assign_rep(self, product, representation):
        ifcopenshell.api.geometry.assign_representation(
            self.file, product=product, representation=representation
        )

    def box(self, element, width, height, depth, matrix, structure=None, length=None):
        """Author a rectangular box (width x height extruded `depth`) + place + contain."""
        self.assign_rep(element, self.profile_rep(self.rect_profile(width, height), depth))
        self.contain(element, matrix, structure=structure)
        if length is not None:
            self.quantity_length(element, length)
        return element

    def tube(self, element, radius, depth, matrix, structure=None, length=None):
        """Author a round tube (circle of `radius` extruded `depth`) + place + contain."""
        self.assign_rep(element, self.profile_rep(self.circle_profile(radius), depth))
        self.contain(element, matrix, structure=structure)
        if length is not None:
            self.quantity_length(element, length)
        return element

    # -- distribution ports / systems --------------------------------------
    def add_port(self, element, system_type="DATA", predefined="CABLECARRIER",
                 matrix=None, flow=None, key: str | None = None):
        """Nest an IfcDistributionPort under `element` (IfcRelNests), placed at
        its real physical connection point (matrix translation in metres,
        relative to the element through the Nests inverse). Connectable ports
        share SystemType and have opposite FlowDirection."""
        port = self.file.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new())
        nest = self._port_nests.get(element.id())
        if nest is None:
            nest = self.file.create_entity("IfcRelNests", GlobalId=ifcopenshell.guid.new(),
                RelatingObject=element, RelatedObjects=[port])
            self._port_nests[element.id()] = nest
        else:
            nest.RelatedObjects = [*nest.RelatedObjects, port]
        port.PredefinedType = predefined
        port.SystemType = system_type
        if key:
            port.GlobalId = ids.guid(key)
            self.ports[key] = port
            self.identify(port, key)
        if matrix is not None:
            ifcopenshell.api.geometry.edit_object_placement(
                self.file, product=port, matrix=np.asarray(matrix, dtype=float), is_si=True
            )
        if flow is not None:
            port.FlowDirection = flow
        return port

    def connect(self, port1, port2, direction="SOURCE"):
        ifcopenshell.api.system.connect_port(
            self.file, port1=port1, port2=port2, direction=direction
        )

    def add_system(self, key, name, predefined, ifc_class="IfcDistributionSystem"):
        if key in self.systems:
            return self.systems[key]
        system = ifcopenshell.api.system.add_system(self.file, ifc_class=ifc_class)
        ifcopenshell.api.system.edit_system(
            self.file, system=system, attributes={"Name": name, "PredefinedType": predefined}
        )
        system.GlobalId = ids.guid(key)
        self._keys[system.id()] = key
        self.systems[key] = system
        return system

    def system(self, key):
        """Get-or-create one of the plan's systems by id (sys.pwr.a, sys.fws...).

        NB: "COOLING" is NOT in IfcDistributionSystemEnum (IFC4X3_ADD2) — the
        TCS loop maps to USERDEFINED with ObjectType TechnologyCooling.
        """
        sp = next(s for s in self.plan.systems if s.id == key)
        predefined = sp.kind if sp.kind in (
            "ELECTRICAL", "CHILLEDWATER", "CONDENSERWATER", "DATA",
            "POWERGENERATION", "SECURITY",
        ) else "USERDEFINED"
        system = self.add_system(key, sp.name, predefined)
        if predefined == "USERDEFINED" and not system.ObjectType:
            system.ObjectType = "TechnologyCooling" if key == "sys.tcs" else sp.kind
        return system

    def assign_system(self, products, system):
        if products:
            ifcopenshell.api.system.assign_system(
                self.file, products=list(products), system=system
            )

    def serves_building(self, system, name):
        self.file.create_entity(
            "IfcRelServicesBuildings", GlobalId=ifcopenshell.guid.new(), Name=name,
            RelatingSystem=system, RelatedBuildings=[self.building],
        )

    # -- output ------------------------------------------------------------
    def write(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Non-referent records also need stable GUIDs for reproducible STEP output.
        for root in self.file.by_type("IfcRoot"):
            key = self._keys.get(root.id(), f"record.{self.discipline}.{root.is_a()}.{root.id()}")
            root.GlobalId = ids.guid(key)
        # IFC SETs have no order. The API often constructs them through Python
        # sets; sort only those attributes, preserving every EXPRESS LIST.
        # Its port helper also scrambles the ordered nesting LIST. This
        # generator defines port order as creation order, so restore that list.
        for relation in self.file.by_type("IfcRelNests"):
            if all(p.is_a("IfcDistributionPort") for p in relation.RelatedObjects):
                relation.RelatedObjects = sorted(relation.RelatedObjects, key=lambda p: p.id())
        set_indices = {}
        for entity in self.file:
            cls = entity.is_a()
            if cls not in set_indices:
                attrs = entity.wrapped_data.declaration().as_entity().all_attributes()
                set_indices[cls] = [i for i, a in enumerate(attrs) if str(a.type_of_attribute()).startswith("<set ")]
            for i in set_indices[cls]:
                values = entity[i]
                if values and len(values) > 1:
                    entity[i] = sorted(values, key=lambda v: v.id() if isinstance(v, ifcopenshell.entity_instance) else v)
        self.file.header.file_name.name = path.name
        self.file.header.file_name.author = ("",)
        self.file.header.file_name.organization = ("",)
        self.file.header.file_name.originating_system = f"usdaeco-datacentre {__version__}"
        self.file.header.file_name.preprocessor_version = "ifcopenshell"
        if self.status_skipped:
            from collections import Counter
            print("Status notes: no applicable Common Pset " + str(dict(Counter(self.status_skipped.values()))))
        self.file.write(str(path))
        return path
