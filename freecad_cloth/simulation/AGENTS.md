# Simulation agent instructions

The simulation package is downstream of persistent FreeCAD/Cloth inputs and upstream of derived diagnostic evidence.

## Non-negotiable invariants

- PositionBasedDynamics is the only production runtime solver.
- `DrapeTarget` owns persistent collision-target identity and validity.
- `shared.CollisionSurface` is the neutral solver-facing collision contract.
- Meshes, particles, collision acceleration data and solver state are derived and rebuildable.
- Do not monkey-patch production classes to change solver, quality, collision or lifecycle behavior.
- Do not create a second simulation scene, solver registry or persistent physics database.

## Verification

Use deterministic headless tests for pure contracts and the canonical FreeCAD/Xvfb workflow for document, GUI or simulation changes.

For visual failures, inspect rendered evidence before relying on logs or metrics.
