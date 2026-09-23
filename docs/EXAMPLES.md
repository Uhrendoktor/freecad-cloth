# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Visual validation |
|---|---|---|---|
| Blanket over Cube | Basic | one native Sketcher pattern, one FreeCAD collision target, pins, gravity and drape | five checkpoints + motion GIF |
| Tunic | Advanced | multiple native pattern pieces, semantic seams, mannequin collision, material/quality controls, diagnostics and production export | six views + diagnostic map + arranged/draped turntables + motion GIF |

## 1. Blanket over Cube

Create a simple rectangular pattern, place it above a cube, pin the rear corners and simulate under gravity.

The canonical visual script is `tests/freecad_visual_examples.py`. It proves that native Sketcher geometry is retained, the cube is used through the persistent `DrapeTarget` contract, the cloth mesh is finite and connected, mesh-edge outliers are rejected, the simulation changes between early and late frames, and the saved checkpoints are real FreeCAD viewport captures.

This fixture intentionally avoids the human avatar so users can isolate cloth, collision and pinning problems.

## 2. Tunic

The tunic is the full garment acceptance scenario. It uses two pattern pieces, semantic sewing, a production mannequin, persisted quality/material settings, diagnostics, save/reload and invalidation.

Use generated artifacts as validation evidence; the blanket example remains the smaller debugging case.

## Visual regression policy

Every public example has an executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The acceptance workflow validates the simple example, the production tunic, a moving simulation sequence, a fixed final turntable, and diagnostic/quality state where applicable.
