"""Office fit-out products, swept bodies, identity, status and nested ports."""
from .geom import Z_UP, at, frame_between


def build(b, plan):
    elements = plan.meta.get("fitout", [])
    for item in elements:
        key = item["id"]
        product = b.entity(item["ifc_class"], predefined=item["predefined"], name=item["name"], key=key)
        if item["predefined"] == "USERDEFINED":
            product.ObjectType = "Prefabricated bathroom pod"
        if product.is_a("IfcElementAssembly"):
            product.AssemblyPlace = "FACTORY"
        if item["axis"]:
            solids = []
            for start, end in zip(item["axis"], item["axis"][1:]):
                frame, length = frame_between(start, end)
                profile = b.circle_profile(item["od"]/2) if item["od"] else b.rect_profile(*item["section"])
                rep = b.profile_rep(profile, length)
                for solid in rep.Items:
                    solid.Position = b.file.create_entity("IfcAxis2Placement3D",
                        Location=b.file.create_entity("IfcCartesianPoint", tuple(float(x) for x in start)),
                        Axis=b.file.create_entity("IfcDirection", tuple(float(x) for x in frame[:3, 2])),
                        RefDirection=b.file.create_entity("IfcDirection", tuple(float(x) for x in frame[:3, 0])))
                    solids.append(solid)
                # Retain only the final shape representation; intermediate
                # representation wrappers own no identity and are removed.
                b.file.remove(rep)
            rep = b.file.create_entity("IfcShapeRepresentation", ContextOfItems=b.body,
                                       RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=solids)
            b.assign_rep(product, rep)
            b.contain(product, at(Z_UP, (0, 0, 0)), structure=b.container_for(item["space"]))
        else:
            b.box(product, *item["size"], at(Z_UP, item["pos"]), structure=b.container_for(item["space"]))
        material = b.material(item["material"], "fitout", rgb=(0.72, 0.77, 0.80))
        b.assign_material([product], material)
        b.style_product(product, item["material"])
        if item["construction"]:
            b.pset(product, "DC_Construction", {"Description": item["construction"]})
        if item["od"]:
            properties = [("OutsideDiameter", "IfcPositiveLengthMeasure", item["od"])]
            if item["nominal_diameter"]:
                properties.append(("NominalDiameter", "IfcPositiveLengthMeasure", item["nominal_diameter"]))
            b.properties(product, "DC_Section", properties)
        for index, position in enumerate(item["ports"], 1):
            b.add_port(product, system_type=item["port_system"], predefined=item["port_medium"],
                       matrix=at(Z_UP, position), flow="SOURCEANDSINK", key=f"{key}.port.{index}")
    for item in elements:
        for source, destination in item["connects"]:
            b.connect(b.ports[source], b.ports[destination], direction="SOURCEANDSINK")
