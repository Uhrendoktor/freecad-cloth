# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Visual validation |
|---|---|---|---|
| Blanket over Cube | Basic | one native Sketcher pattern, one FreeCAD collision target, pins, gravity and drape | five checkpoints + motion GIF |
| Tunic | Advanced | multiple native pattern pieces, semantic seams, mannequin collision, material/quality controls, diagnostics and production export | six views + diagnostic map + arranged/draped turntables + motion GIF |
| Prepare a mannequin for sewing | Focused | body-shape blend, breast fullness, named measurements, viewport dimension handles, and staged rebuild | seven-profile mannequin gallery, shape-editor screenshot, and two interaction GIFs in the [avatar-shape guide](wiki/09-avatar-shape.md) |

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

## 3. Prepare a mannequin for sewing

Use this focused setup when the garment's intended wearer differs from the default mannequin or when a more accurate bust, waist, hip, shoulder, or height is needed before pattern fitting.

1. Open the document containing the built-in MakeHuman mannequin, or create one from **Cloth Simulation → Avatar & Fitting → Create Avatar**.
2. Open **Avatar & Fitting → Edit Avatar**.
3. Set the feminine-to-masculine proportion blend and breast fullness in **Body shape**. Treat these as shape controls rather than replacements for measurements.
4. Drag the 3D height, shoulder, chest, waist, or hip handle in the viewport, or enter the exact value in the **Body measurements** or **Proportions** group. The handles stage changes; they do not immediately mutate the saved avatar.
5. Select **Apply & Rebuild**, then save and reopen the document to confirm the avatar shape and named measurement properties persist.
6. Move on to [Direct fitting and arrangement](wiki/03-fitting.md), then review [Pose Mode](wiki/04-pose.md) only if the garment needs a different posture.

The visual procedure and limitations are documented in [Avatar shape and dimensions](wiki/09-avatar-shape.md). Its GIFs show shape adjustment and a staged circumference-handle edit. The dedicated GUI acceptance fixture also checks that the overlay does not add document objects and that committed mesh geometry changes after rebuilding.

This is a mannequin setup example, not a complete garment construction. Use the [Tunic](#2-tunic) example for the integrated pattern-to-sewing-to-drape journey, and keep the [Blanket over Cube](#1-blanket-over-cube) example for isolating the core simulation path.

The blanket stays a separate deliberately simple example: it is the best way to tell whether a core drape/target issue is independent of garment complexity.

## Visual regression policy

Every public example must have at least one executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The acceptance workflow is expected to validate:

1. a simple example;
2. the production tunic;
3. a moving simulation sequence;
4. a fixed final turntable;
5. the diagnostic/quality state where the example supports it.
