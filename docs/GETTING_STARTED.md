# Getting started

This is the human-first entry point for FreeCAD Cloth. Install the workbenches, prove the basic cloth path, then move to sewing, fitting and simulation.

## 1. Install

Copy or clone the repository into the FreeCAD user `Mod` directory and restart FreeCAD. Keep `Init.py` and `InitGui.py` at the repository root.

The canonical CI baseline is FreeCAD 1.1.0 with Python 3.12. See [Installation](INSTALLATION.md) for environment details.

## 2. Prove the installation

Start with [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube). Create a native Sketcher pattern, select two blanket corners as pins, run the simulation, and confirm that cloth motion is visible between early and late states.

## 3. Build a garment

Use **Cloth Pattern** for native Sketcher-backed PatternPieces, then **Cloth Sewing** for semantic seams and correspondence. Inspect seam validation before committing operations.

Seam presentation is keyed by semantic `SeamId`, so each seam pair keeps its identity across recompute and 2D focus.

## 4. Fit the garment

Use a persistent `DrapeTarget` and a fitting scene. Arrange pieces with persistent arrangement metadata first.

For target-aware placement:
1. Create or select a PatternPiece and a current DrapeTarget.
2. Position the PatternPiece on one side of the target using the fitting arrangement tools.
3. In the avatar fitting task panel, press **Snap selected piece to Drape Target**.
4. Cloth derives a bounded rigid translation/rotation from two semantic garment anchors and the authoritative target surface.
5. The placement and anchors are persisted in the fitting scene.

The action fails closed when the target is missing/stale, the side is ambiguous, the target surface is unusable, or the requested transform exceeds its safety bound.

## 5. Simulate

Before Run or Step, verify that the DrapeTarget reports current/ready. Pin policy is explicit:
- **Automatic** preserves the legacy automatic-pin behavior.
- **Explicit** uses the persisted `PinSelection`.
- **None** deliberately runs without implicit solver pins.

The canonical tunic fixture uses target-aware starting placement and `PinMode=None`; fitting metadata, not global pinning, determines its starting pose.

## 6. Recover and inspect

After editing a pattern, seam or target, recompute and refresh the affected derived state. Use **Refresh Drape Target** when the collision surface is stale.

Treat CI-rendered screenshots and motion artifacts as executable evidence. Use the visible status messages, diagnostics and logs together rather than diagnosing a garment from one screenshot.
