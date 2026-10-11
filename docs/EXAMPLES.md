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

The tunic is the full garment acceptance scenario. It uses two pattern pieces, semantic sewing, a production MakeHuman mannequin, persisted quality/material settings, diagnostics, save/reload and invalidation.

The Pattern and Sewing screenshots are captured from the same native Sketcher pieces and semantic seams that the production tunic audit sends through fitting and simulation; they are not independent garment fixtures.

Use the generated artifacts only as evidence: the tunic is not a substitute for the simpler blanket when debugging a local installation.

## Recommended guided journey: one tunic

For a first garment, use the tunic as the narrative thread from editable pattern to sewn pieces, mannequin fitting, pose review, simulation, diagnostics, and export. Keep one saved FreeCAD document as the source of truth while following the [user guide](USER_GUIDE.md); each upstream edit should lead to the documented rebuild/recovery step before simulation.

The README animations currently come from focused acceptance fixtures, not one continuous GUI recording over the same saved tunic document. `arrangement-anchor.gif` and `interactive-arrange.gif` use tunic panels and a mannequin; `seam-assignment.gif` isolates sewing interaction, and `pose-joint-rotation.gif` isolates the posing controls. Treat them as feature demonstrations, not evidence that one FCStd session flowed between those exact screens. The integrated tunic audit validates the garment path; a single-document, start-to-finish interaction recording remains a worthwhile follow-up.

The blanket stays a separate deliberately simple example: it is the best way to tell whether a core drape/target issue is independent of garment complexity.

## Visual regression policy

Every public example must have at least one executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The acceptance workflow is expected to validate:

1. a simple example;
2. the production tunic;
3. a moving simulation sequence;
4. a fixed final turntable;
5. the diagnostic/quality state where the example supports it.
