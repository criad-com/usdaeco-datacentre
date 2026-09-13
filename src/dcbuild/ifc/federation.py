"""Partition the complete IFC graph, retaining handoff ports and external links."""
from pathlib import Path

import ifcopenshell

from .. import ids

DELIVERY_ORDER = ("site", "arch", "structure", "cooling", "electrical", "it", "fitout", "security")


def ownership(builder, modules, plan):
    """Record element/system ownership at authoring time, including later ports."""
    owners = {e.id(): "shared" for e in builder.file.by_type("IfcObjectDefinition")}
    for package, module in modules:
        before = {e.id() for e in builder.file.by_type("IfcObjectDefinition")}
        module.build(builder, plan)
        for e in builder.file.by_type("IfcObjectDefinition"):
            if e.id() not in before:
                owners[e.id()] = package
    # Clash fixtures are authored with the existing fitout helper, delivered by cooling.
    for e in builder.file.by_type("IfcElement"):
        if builder._keys.get(e.id(), "").startswith("pipe.clash."):
            owners[e.id()] = "cooling"
    for rel in builder.file.by_type("IfcRelNests"):
        for child in rel.RelatedObjects:
            owners[child.id()] = owners[rel.RelatingObject.id()]
    for rel in builder.file.by_type("IfcRelVoidsElement"):
        owners[rel.RelatedOpeningElement.id()] = owners[rel.RelatingBuildingElement.id()]
    return owners


def external_links(model, owners):
    links = []
    for rel in model.by_type("IfcRelConnectsPorts"):
        a, b = rel.RelatingPort, rel.RelatedPort
        if owners[a.id()] != owners[b.id()]:
            for source, target in ((a, b), (b, a)):
                links.append(dict(source=source.GlobalId, target=target.GlobalId,
                                  package=owners[source.id()], targetPackage=owners[target.id()]))
    return sorted(links, key=lambda r: (r["package"], r["source"], r["target"]))


def subset(model, owners, package):
    """Copy selected referents and their reachable data, trimming IFC relation sets.

    Inverses are not copied by file.add. Relationships are selected explicitly;
    style assignments are recovered from the selected representation items.
    No unowned product is pulled in by an inverse relationship.
    """
    clone = ifcopenshell.file.from_string(model.to_string())
    selected = {i for i, owner in owners.items() if owner in {"shared", package}}
    if package == "shared":
        selected = {i for i in selected if not clone.by_id(i).is_a("IfcElement")}
    # Type definitions follow actual occurrences. Catalog sharing is by stable type identity.
    selected -= {e.id() for e in clone.by_type("IfcTypeObject")}
    for rel in clone.by_type("IfcRelDefinesByType"):
        if any(e.id() in selected for e in rel.RelatedObjects):
            selected.add(rel.RelatingType.id())
    roots = [clone.by_id(i) for i in sorted(selected)]
    for rel in clone.by_type("IfcRelationship"):
        keep, touches = True, False
        for index, value in enumerate(rel):
            if isinstance(value, ifcopenshell.entity_instance) and value.is_a("IfcObjectDefinition"):
                touches = True
                keep &= value.id() in selected
            elif isinstance(value, tuple) and value and all(
                    isinstance(v, ifcopenshell.entity_instance) and v.is_a("IfcObjectDefinition") for v in value):
                touches = True
                remaining = tuple(v for v in value if v.id() in selected)
                if not remaining:
                    keep = False
                elif remaining != value:
                    rel[index] = remaining
        if touches and keep:
            roots.append(rel)
    reachable = {e.id(): e for root in roots for e in clone.traverse(root)}
    # Styling lives in inverse StyledByItem relationships.
    for e in list(reachable.values()):
        if e.is_a("IfcRepresentationItem"):
            for style in getattr(e, "StyledByItem", ()):
                reachable.update({v.id(): v for v in clone.traverse(style)})
    leaked = {i for i, e in reachable.items() if e.is_a("IfcObjectDefinition")} - selected
    if leaked:
        raise ValueError("IFC partition pulled in an unowned referent")
    result = ifcopenshell.file(schema=model.schema_identifier)
    for e in sorted(reachable.values(), key=lambda e: e.id()):
        result.add(e)
    return result


def write_packages(builder, owners, out_dir):
    links = external_links(builder.file, owners)
    written = []
    for package in (*DELIVERY_ORDER, "shared"):
        print(f"== stage: IFC delivery {package}", flush=True)
        model = subset(builder.file, owners, package)
        for row in links:
            if row["package"] != package:
                continue
            document = model.create_entity("IfcDocumentReference", Location=row["targetPackage"] + ".ifc",
                                           Identification=row["target"], Name="aeco:connectedPorts")
            model.create_entity("IfcRelAssociatesDocument",
                                GlobalId=ids.guid("external-port:" + row["source"] + ":" + row["target"]),
                                RelatedObjects=[model.by_guid(row["source"])], RelatingDocument=document)
        path = Path(out_dir) / (package + ".ifc")
        header = model.header.file_name
        header.name = path.name
        header.time_stamp = "2000-01-01T00:00:00"
        header.author = ("",)
        header.organization = ("",)
        header.originating_system = "usdaeco-datacentre 0.5.0"
        header.preprocessor_version = "ifcopenshell"
        model.write(str(path))
        written.append(path)
    return written
