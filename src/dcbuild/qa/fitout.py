"""G1 joins for new fixture data against actual IFC products and spaces."""
import math

import ifcopenshell.util.element as element
import ifcopenshell.util.placement as placement
import ifcopenshell.util.unit as unit

from ..ids import guid


def check(model, plan):
    fails = []
    products = {p.GlobalId: p for p in model.by_type("IfcProduct")}
    scale = unit.calculate_unit_scale(model)
    for item in plan.meta.get("fitout", []):
        product = products.get(guid(item["id"]))
        if product is None or not product.is_a(item["ifc_class"]):
            fails.append(f"fitout: missing {item['ifc_class']} {item['id']}")
            continue
        if element.get_psets(product).get("DC_Identity", {}).get("Id") != item["id"]:
            fails.append(f"fitout: identity differs for {item['id']}")
        container = element.get_container(product)
        if not container or container.GlobalId != guid(item["space"]):
            fails.append(f"fitout: wrong container for {item['id']}")
        nested = [p for rel in product.IsNestedBy for p in rel.RelatedObjects if p.is_a("IfcDistributionPort")]
        if len(nested) != len(item["ports"]):
            fails.append(f"fitout: wrong port count for {item['id']}")
        if not product.Representation:
            fails.append(f"fitout: missing body for {item['id']}")
    for space in (s for s in plan.spaces if s.type == "void"):
        product = products.get(guid(space.id))
        geometry = plan.meta["space_geometry"][space.id]
        if not product or element.get_psets(product).get("DC_Space", {}).get("SpaceType") != "void":
            fails.append(f"fitout: missing void {space.id}")
        else:
            z = placement.get_local_placement(product.ObjectPlacement)[2, 3]*scale
            expected = next(s.elevation for s in plan.storeys if s.id == space.storey)+geometry["z_offset"]
            if not math.isclose(z, expected, abs_tol=1e-8):
                fails.append(f"fitout: void elevation differs for {space.id}")
    for programme in plan.meta.get("programme", {}).get("programmes", []):
        for a in programme["activities"]:
            for id in a["scope"]:
                if guid(id) not in products:
                    fails.append(f"fitout: activity {a['id']} has unexported scope {id}")
    for id, rules in plan.meta.get("storey_rules", {}).items():
        if rules.get("typical_of"):
            product = products.get(guid(id))
            actual = element.get_psets(product).get("DC_Typical", {}).get("Prototype") if product else None
            if actual != rules["typical_of"]:
                fails.append(f"fitout: missing prototype on {id}")
    for reader in plan.security["iris"]:
        expected = plan.security.get("iris_mounting", {}).get(reader["door"])
        if expected:
            product = products.get(guid(reader["id"]))
            actual = element.get_psets(product).get("DC_Security", {}) if product else {}
            for key, value in expected.items():
                got = actual.get(key)
                if key != "Side" and isinstance(got, (int, float)):
                    got *= scale
                if got != value and not (isinstance(got, (float, int)) and isinstance(value, (float, int))
                                         and math.isclose(got, value, abs_tol=1e-8)):
                    fails.append(f"fitout: reader {reader['id']} wrong {key}")
    return fails
