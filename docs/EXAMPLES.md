# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Visual validation |
|---|---|---|---|
| Blanket over Cube | Basic | one native Sketcher pattern, one FreeCAD collision target, pins, gravity and drape | five checkpoints + motion GIF |
| Tunic | Advanced | native Sketcher pieces, semantic seams, persistent DrapeTarget, Arrange / Fit, target-aware placement, material/quality controls, diagnostics and simulation | six-side FreeCAD GUI audit + solver/visual metrics |

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

The tunic is the advanced end-to-end scenario. It uses two native Sketcher PatternPieces, semantic seams, a persistent mannequin DrapeTarget, fitting metadata, quality/material settings, diagnostics and a real FreeCAD GUI/simulation audit.

### Arrange / Fit

1. Create the mannequin and persistent DrapeTarget.
2. Create a Fitting Scene and add the front/back PatternPieces.
3. Use Arrangement Points or saved piece placements for deterministic manual positioning.
4. From **Cloth Simulation → Arrange / Fit**, use **Snap pieces to target** only when authored GarmentAnchors are present. The action is bounded by the persistent DrapeTarget and validates complete piece-surface clearance.
5. Use **Reset arrangement** to return to the saved home placements.
6. If the mannequin changes, use **Refresh target** before fitting or simulation.

The production audit exercises the same fitting command through the actual Simulation task-panel button; it is not a separate fixture-only placement path.

Use generated artifacts as evidence: the tunic remains more complex than the blanket smoke test.

## Visual regression policy

Every public example must have at least one executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The acceptance workflow is expected to validate:

1. a simple example;
2. the production tunic;
3. a moving simulation sequence;
4. a fixed final turntable;
5. the diagnostic/quality state where the example supports it.
