"""dcbuild — demo-datacentre-01 data centre, authored programmatically from one parametric spec.

Pipeline: spec/*.yaml -> dcbuild.spec.load() -> dcbuild.layout.resolve() -> Plan
(the fully-resolved build plan: every wall, rack, busway, manifold and graph edge
with world coordinates and deterministic ids). The Plan feeds BOTH builders:

  * dcbuild.ifc      — ifcopenshell (IFC4X3), runs anywhere
  * revit/           — C# via the revit-repl through a configured endpoint, reads plan JSON

so the two models stay comparable element-for-element (joined on the DC id).
"""

__version__ = "0.4.8"
