# Getting started

This page is the human-first entry point for FreeCAD Cloth. It is intentionally task-oriented: install the workbenches, prove the basic cloth path, then move to garment sewing and avatar fitting.

## 1. Install

FreeCAD Cloth is installed as a FreeCAD user workbench. Copy or clone the repository into the user `Mod` directory and restart FreeCAD. Keep the repository root intact so `Init.py` and `InitGui.py` remain directly below the installed workbench directory.

The canonical development/CI baseline is FreeCAD 1.1.0 with Python 3.12 and `triangle==20250106`. The optional Tissu path is validated by the canonical GitHub Actions environment. See [Installation](INSTALLATION.md) for developer setup and troubleshooting.

## 2. Prove the installation with the blanket

Use the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

Start with [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube). It is the smallest end-to-end example and isolates cloth motion, collision, gravity and pinning from garment-specific problems.

The expected user journey is:

1. Create a native Sketcher pattern and turn it into a PatternPiece.
2. Create or select a collision target.
3. Select two blanket corners as pins.
4. Run the simulation.
5. Confirm that the cloth moves between early and late states and settles around the cube.

The repository's visual evidence is generated from the executable fixture rather than hand-edited screenshots. The current validated examples are linked from the [project README](../README.md).

## 3. Build a garment

For garment work, keep native Sketcher geometry as the editable authority.

In **Cloth Pattern**:
- create PatternPieces from Sketcher;
- add seam allowance, grainline, notches and other pattern metadata;
- recompute and validate before sewing.

In **Cloth Sewing**:
- select semantic PatternPiece edges;
- create a seam or sewing network;
- use Preview before Commit when the staged creation panel is offered;
- inspect correspondence, reversal and length diagnostics;
- use **Focus seam in 3D** or **Edit side A/B in Sketcher** when a seam needs inspection or repair.

Seam identity is semantic. Editing an upstream Sketcher edge can invalidate a downstream seam; Cloth does not silently retarget it.

## 4. Fit the garment to an avatar

Use the persistent fitting scene and the same `DrapeTarget` contract used by simulation.

The supported fitting workflow is:

`Create fitting scene → assign avatar/target → add PatternPieces → create arrangement points → apply arrangement → inspect/reset → create simulation`.

Arrangement points are avatar-relative fitting metadata. The project uses the same general concept as garment systems that place patterns using avatar arrangement points and bounding volumes before solving cloth. They are preparation state, not solver state.

A reset is always available: use **Reset Arrangement** to restore the saved pre-arrangement PatternPiece placements.

For mannequin fitting, the current canonical tunic fixture uses deterministic shoulder-wrap placement so sewn panels start around the avatar before the solver runs; it does not rely on global pinning as a substitute for fitting.

## 5. Simulate

Before pressing Run:

- verify the selected **DrapeTarget** is current;
- confirm the target status is ready;
- choose quality/material settings;
- keep target collision settings separate from fabric presentation controls.

Simulation is fail-closed for stale or invalid target state. When the target geometry changes, rebuild/refresh its collision surface before simulation.

Use:
- **Step** for controlled advancement;
- **Run** for a normal multi-step simulation;
- **Reset** to recover the simulation state without losing the authored scene settings.

The advanced solver-index pin/seam fields in the Simulation task panel are diagnostic overrides. The normal garment path should use named sewing objects plus fitting/arrangement metadata.

## 6. Inspect and recover

Treat the FreeCAD document as the source of truth. Do not diagnose a garment from a single screenshot.

When something is wrong:

1. Read the visible status message.
2. Check whether the seam, target or simulation is stale/invalid.
3. Recompute the document.
4. Rebuild or repair only the affected derived state.
5. Re-run the smallest relevant example before returning to the full garment.

Typical recovery cases are documented in [Installation](INSTALLATION.md) and [Workbench guide](WORKBENCH_GUIDE.md).

## 7. Visual references

The canonical workflow publishes validated GUI evidence to the `docs/screenshots` branch. The project README links the blanket motion example, tunic validation image, arranged/draped turntables and avatar turntable.

Use those artifacts as validation evidence, not as a replacement for the executable examples.

## Next references

- [Installation](INSTALLATION.md)
- [User guide](USER_GUIDE.md)
- [Workbench guide](WORKBENCH_GUIDE.md)
- [Examples](EXAMPLES.md)
- [Release gates](RELEASE_GATES.md)
