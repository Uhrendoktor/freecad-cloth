# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | First-run purpose | What it demonstrates | Visual validation |
|---|---|---|---|---|
| Blanket over Cube | Basic | installation smoke test | one native Sketcher pattern, one FreeCAD collision target, manual pins, gravity and drape | five checkpoints + motion GIF |
| Tunic | Advanced | mannequin garment path | multiple native pattern pieces, semantic seams, explicit fitting/arrangement, mannequin collision, material/quality controls, diagnostics and production export | six views + diagnostic map + arranged/draped turntables + motion GIF |

The two examples validate different boundaries. A passing **Blanket over Cube** run proves that the installation can mesh, pin, collide and simulate simple cloth. It does **not** prove that mannequin fitting or garment arrangement is configured correctly.

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

The tunic is the full garment acceptance scenario, not the installation smoke test. It uses multiple pattern pieces, semantic sewing, a production MakeHuman mannequin, persisted quality/material settings, diagnostics, save/reload and invalidation.

On current main, the mannequin path includes an explicit fitting/arrangement stage before simulation. The fitting layer stores piece placements and arrangement metadata; it is not documented here as an automatic target-relative, pin-free placement feature. After arranging, create or refresh the mannequin **Drape Target** in **Cloth Simulation** and then run the simulation.

Use the generated artifacts only as evidence: the tunic is not a substitute for the simpler blanket when debugging a local installation.

## Visual regression policy

Every public example must have at least one executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The acceptance workflow is expected to validate:

1. a simple example;
2. the production tunic;
3. a moving simulation sequence;
4. a fixed final turntable;
5. the diagnostic/quality state where the example supports it.
