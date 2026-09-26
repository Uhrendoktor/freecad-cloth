# Getting started

This page is the human-first entry point for FreeCAD Cloth. Use it to prove the basic cloth path first, then move to sewing and avatar fitting.

## 1. Install

Install FreeCAD Cloth as a FreeCAD user workbench by copying or cloning the repository into the user `Mod` directory, then restart FreeCAD. Keep `Init.py` and `InitGui.py` directly below the installed workbench directory.

The canonical development/CI baseline is FreeCAD 1.1.0 with Python 3.12 and `triangle==20250106`. See [Installation](INSTALLATION.md) for the supported host/runtime boundary and troubleshooting.

## 2. Prove the installation

Open **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** from the FreeCAD workbench selector.

Run [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube): create a native Sketcher pattern, make a PatternPiece, assign the collision target, pin two blanket corners, and run the simulation. Confirm that the cloth moves between early and late states and settles around the cube.

## 3. Build and sew a garment

In **Cloth Pattern**, keep native Sketcher geometry as the editable authority.

In **Cloth Sewing**, create semantic seams from PatternPiece edges, review correspondence/reversal/length diagnostics, and use the existing **Focus seam in 3D** or Sketcher side-A/B edit actions for inspection and repair.

## 4. Arrange the garment

Use the persistent fitting scene and the same **DrapeTarget** contract used by simulation.

The supported path is:

`Create fitting scene → assign avatar/target → add PatternPieces → create/apply arrangement → inspect/reset → create simulation`

Target-aware garment placement is solver-neutral. It derives a bounded rigid transform from authored garment anchors and the current target surface, proves an outward step-0 clearance, and fails closed for stale/missing/ambiguous targets. **Reset arrangement** restores the saved home placements.

## 5. Choose pin policy and simulate

The simulation task panel exposes three pin policies:

- **Auto (compatibility)** — retains the historical default corner-pin behavior when no explicit pins are supplied.
- **Explicit pins only** — uses only the persisted `PinSelection`.
- **None (pinless)** — creates no implicit pins and rejects a non-empty pin selection.

For the canonical two-panel tunic, fitting/arrangement is the placement mechanism and the fixture uses **None (pinless)**. The DrapeTarget remains the collision authority.

Before Run/Step, confirm the target is ready. Stale or invalid target state is fail-closed. Use **Reset** to recover solver state without losing authored scene settings.

## 6. Inspect and recover

Treat the FreeCAD document as the source of truth. Do not diagnose a garment from a single screenshot.

When something is wrong, read the status, recompute, repair only the affected stale/invalid derived state, and rerun the smallest relevant example before returning to the full garment.

## References

- [Installation](INSTALLATION.md)
- [Examples](EXAMPLES.md)
- [User guide](USER_GUIDE.md)
- [Workbench guide](WORKBENCH_GUIDE.md)
- [Release gates](RELEASE_GATES.md)
