# Native model script enclave

These phased C# scripts are a declared non-Nix enclave. Revit compiles them
in its own REPL; Python dry runs verify the source inventory and SHA-256
hashes in `manifest.json`, not native compilation or API behaviour.
The driver checks the complete pack before any submission and rechecks each
selected phase immediately before execution.

The pack owns the demo model. `usdaeco_revit.transport.Client` owns status
polling, endpoint serialization, verified uploads, checked reply pages and
the failure latch. The integration's sync path also owns recovery journals.
A failed or ambiguous builder phase is never replayed automatically.

`driver.py --update` selects helpers, setup, parameters, cameras and export.
It requires the existing base model in `AECO_REVIT_WORKDIR`, reuses its exact
background path and refuses a foreground match. Existing rooms and doors
remain in place. Fresh service phases can duplicate segments when repeated.
The `full` architecture scope selects setup, parameters, architecture, rooms
and export, prepending helpers. It uses a separate new model path and no
camera assets. Its 0.6.0 native run exported all 167 architecture referents
and 38 rooms. Floor compound structures use `NoEndCap`. Standalone floors,
pod, clash and iris plans are still refused.
See [the builder guide](../README.md) for configuration and measured limits.
