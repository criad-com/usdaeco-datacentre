"""IFC4X3 builder — demo-datacentre-01 authored with ifcopenshell from the resolved plan.

Helpers (ported from the proven dc-examples/dcgen conventions):
  geom      pure numpy placement frames (4x4 matrices, run frames)
  builder   Builder — file/contexts/spatial roots + entity/pset/port/system helpers
  run       Run — carrier/pipe/duct runs with ports at real connection points

Discipline modules (each `build(b, plan)`):
  spatial, architecture, structure, site, electrical, cooling, it, security

Orchestrated by build.build(plan, out_dir): one combined coordination model
plus per-discipline federated files sharing the same deterministic GUIDs.
"""
