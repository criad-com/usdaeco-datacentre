"""Partition a complete native architecture export over the issued spatial spine."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit

from . import ids
from .ifc.federation import subset

PRODUCER = ("Autodesk Revit 2027 IFC4X3 export of the native model built from the "
            "generator plan; partitioned to the architecture delivery")
ORIGINATING_SYSTEM = "Autodesk Revit 2027 27.2.0.39 IFC4X3 export + usdaeco-datacentre architecture partitioner"


def physical(model):
    return [e for e in model.by_type("IfcElement")
            if not e.is_a("IfcOpeningElement") and not e.is_a("IfcVirtualElement")]


def partition(source, reference, spine, target):
    """Keep native product geometry, identities, types, Psets and quantities.

    Units are normalized to metres without changing world geometry. The issued
    names and containment anchor those referents on the unchanged shared spine.
    No generator physical element or representation enters this delivery.
    """
    native = ifcopenshell.open(str(source))
    generator = ifcopenshell.open(str(reference))
    shared = ifcopenshell.open(str(spine))
    if native.schema != "IFC4X3" or shared.by_type("IfcElement"):
        raise ValueError("Expected IFC4X3 native export and an element-free shared spine")
    required = {e.GlobalId: e for e in physical(generator)}
    native_ids = Counter(e.GlobalId for e in physical(native))
    if any(native_ids[g] != 1 for g in required):
        raise ValueError("Native architecture identity coverage is incomplete or duplicated")
    for e in physical(native):
        if e.GlobalId in required and not e.is_a(required[e.GlobalId].is_a()):
            raise ValueError("Native architecture element kind differs: " + e.GlobalId)
    native = ifcopenshell.util.unit.convert_file_length_units(native, "METER")
    owners = {e.id(): "arch" for e in physical(native) if e.GlobalId in required}
    for rel in native.by_type("IfcRelVoidsElement"):
        if rel.RelatingBuildingElement.id() in owners:
            owners[rel.RelatedOpeningElement.id()] = "arch"
    result = subset(native, owners, "arch")
    for e in shared:
        result.add(e)
    containers = defaultdict(list)
    for guid, expected in sorted(required.items()):
        product = result.by_guid(guid)
        product.Name = expected.Name
        container = ifcopenshell.util.element.get_container(expected)
        if container is None:
            raise ValueError("Issued architecture product has no spatial container")
        containers[container.GlobalId].append(product)
    for guid, products in sorted(containers.items()):
        # Keep the native local-placement chain exactly. Containment joins the
        # issued referent; changing placement is neither necessary nor intended.
        result.create_entity("IfcRelContainedInSpatialStructure",
                             GlobalId=ids.guid("revit.arch.container:" + guid),
                             RelatedElements=products, RelatingStructure=result.by_guid(guid))
    # Exporter attribution is in the header; remove personal contact metadata.
    for person in result.by_type("IfcPerson"):
        for index in range(len(person)):
            person[index] = None
    for organization in result.by_type("IfcOrganization"):
        organization.Identification = None
        organization.Name = "Example"
        organization.Description = None
        organization.Roles = None
        organization.Addresses = None
    header = result.header.file_name
    header.name = Path(target).name
    header.time_stamp = "2000-01-01T00:00:00"
    header.author = ("",)
    header.organization = ("",)
    header.originating_system = ORIGINATING_SYSTEM
    header.preprocessor_version = "usdaeco-datacentre architecture partitioner 0.6.0"
    header.authorization = ""
    if {e.GlobalId for e in physical(result)} != set(required):
        raise ValueError("Partition leaked or lost a physical referent")
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    result.write(str(target))
    return {"elements": len(required), "classes": dict(Counter(e.is_a() for e in physical(result))),
            "spatial": len(result.by_type("IfcSpatialElement")),
            "property_sets": len(result.by_type("IfcPropertySet")),
            "quantity_sets": len(result.by_type("IfcElementQuantity")),
            "bytes": Path(target).stat().st_size,
            "sha256": hashlib.sha256(Path(target).read_bytes()).hexdigest()}


def union_deliveries(folder, target):
    """Reconstitute a monolithic comparison input from the actual deliveries.

    Shared roots join by GlobalId; relationship sets are unioned and external
    port documents become native IFC connections. Geometry stays producer-owned.
    """
    from .federation import PACKAGES
    result = ifcopenshell.file(schema="IFC4X3_ADD2")
    for package in ("shared", *(p for p in PACKAGES if p != "shared")):
        source = ifcopenshell.open(str(Path(folder) / (package + ".ifc")))
        for entity in source:
            result.add(entity)
    grouped = defaultdict(list)
    for entity in result.by_type("IfcRoot"):
        grouped[entity.GlobalId].append(entity)
    # Merge before removal; references are repaired in a separate pass.
    duplicates = []
    for group in grouped.values():
        first = group[0]
        for other in group[1:]:
            if other.is_a() != first.is_a():
                raise ValueError("Delivery union has a conflicting GlobalId kind")
            if first.is_a("IfcRelationship"):
                for name in ("RelatedElements", "RelatedObjects", "RelatedBuildings", "RelatedDefinitions"):
                    if hasattr(first, name):
                        setattr(first, name, tuple(dict.fromkeys((*getattr(first, name), *getattr(other, name)))))
            duplicates.append((other, first))
    for other, first in duplicates:
        for inverse in result.get_inverse(other):
            ifcopenshell.util.element.replace_attribute(inverse, other, first)
    for other, _ in duplicates:
        result.remove(other)
    # Canonical replacement can collapse entries in relationship SET attributes.
    for rel in result.by_type("IfcRelationship"):
        for name in ("RelatedElements", "RelatedObjects", "RelatedBuildings", "RelatedDefinitions"):
            if hasattr(rel, name):
                setattr(rel, name, tuple(dict.fromkeys(getattr(rel, name))))
    connections = {tuple(sorted((r.RelatingPort.GlobalId, r.RelatedPort.GlobalId)))
                   for r in result.by_type("IfcRelConnectsPorts")}
    for rel in result.by_type("IfcRelAssociatesDocument"):
        document = rel.RelatingDocument
        if not document.is_a("IfcDocumentReference") or document.Name != "aeco:connectedPorts":
            continue
        for source in rel.RelatedObjects:
            pair = tuple(sorted((source.GlobalId, document.Identification)))
            if pair in connections:
                continue
            result.create_entity("IfcRelConnectsPorts", GlobalId=ids.guid("delivery.union.port:" + ":".join(pair)),
                                 RelatingPort=result.by_guid(pair[0]), RelatedPort=result.by_guid(pair[1]))
            connections.add(pair)
    if len(result.by_type("IfcProject")) != 1:
        raise ValueError("Delivery union must have exactly one project")
    result.write(str(target))
    return result
