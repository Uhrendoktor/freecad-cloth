# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Visual validation |
|---|---|---|---|
| Blanket over Cube | Basic | one native Sketcher pattern, one FreeCAD collision target, pins, gravity and drape | five checkpoints + motion GIF |
| Tunic | Advanced | multiple native pattern pieces, semantic seams, mannequin collision, material/quality controls, diagnostics and production export | six views + diagnostic map + arranged/draped turntables + motion GIF |

## 1. Blanket over Cube

Create a simple rectangular pattern, place it above a cube, pin the rear corners and simulate under gravity.

The canonical visual script is `tests/freecad_visual_examples.py`. It proves all of the following in one deterministic scenario:

- native Sketcher source geometry is retained;
- the cube is used through the persistent `DrapeTarget` contract;
- the cloth mesh remains finite and connected;
- the drape has no extreme mesh-edge spike signature;
- the simulation changes the cloth between early and late frames;
- the saved checkpoints and motion frames are real FreeCAD viewport captures.

This fixture intentionally avoids the human avatar so users can isolate cloth, collision and pinning problems.

## 2. Tunic

The tunic is the full garment acceptance scenario. It uses two pattern pieces, semantic sewing, a production MakeHuman mannequin, persisted quality/material settings, diagnostics, save/reload and invalidation. Start it through the Simulation → Arrange / Fit handoff so the fitting stage carries the same persistent `DrapeTarget` used by simulation.

The canonical tunic fixture uses `PinMode=None` with an empty `PinSelection`, so it runs with zero solver pins; target placement is a fitting concern, not a global-pin workaround. The target-aware placement integration exposes the production `ClothFitting_SnapPiecesToTarget` action. When present, that action applies a bounded rigid translation against the persistent `DrapeTarget`, proves clearance for the full selected pieces, and keeps **Reset arrangement** as the rollback path. It does not perform conformal deformation.

Use the generated artifacts only as evidence: the tunic is not a substitute for the simpler blanket when debugging a local installation.

## Visual regression policy

Every public example must have at least one executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The acceptance workflow is expected to validate:

1. a simple example;
2. the production tunic;
3. a moving simulation sequence;
4. a fixed final turntable;
5. the diagnostic/quality state where the example supports it.
