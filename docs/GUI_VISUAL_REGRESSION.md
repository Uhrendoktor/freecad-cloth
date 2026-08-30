# GUI visual regression coverage

The canonical `gui-screenshots` job runs real FreeCAD under Xvfb with software rendering and captures the complete 1280x720 main window. The scenarios deliberately fail before capture when required document geometry, task-panel controls, or simulation state are missing; a non-empty file alone is not considered a valid screenshot.

## Screenshots

| Artifact | Workbench/state | What it proves |
| --- | --- | --- |
| `cloth-pattern-design.png` | Pattern Workbench | Two deterministic 140 x 90 mm pattern pieces are visible with their native 10 mm seam allowance geometry. The Pattern Piece task panel visibly exposes piece name, width, height, seam allowance, and grainline angle. Deterministic notch and grainline marker fixtures are visible over the real pattern geometry. |
| `cloth-sewing.png` | Sewing Workbench | The real semantic seam and Sewing Operation produce non-empty seam visualization and stitch geometry. The task panel exposes seam identity, alignment, normalized ranges, tolerance, stitch samples, status, seam lengths, correspondence diagnostics, and repair control. Deterministic direction arrows exercise the visual direction affordance. |
| `cloth-simulation-arranged.png` | Simulation Workbench, steps=0 | A deterministic humanoid avatar/DrapeTarget and two non-empty arranged garment panels are visible together. The Simulation task panel exposes quality, fabric, collision, run controls, and ready state before stepping. |
| `cloth-simulation-draped.png` | Simulation Workbench, steps=24 | The same avatar/garment scene after 24 real solver steps is captured. The regression requires non-empty drape meshes, positive simulated time, a finite solver state, and the task panel reporting the advanced step count. |

## Determinism and validation

- Window geometry is fixed to 1280x720.
- Pattern and sewing use top view; simulation uses FreeCAD's axonometric view.
- Pattern placements, seam references, avatar construction, simulation preset, particle distance, solver settings, and step batches are fixed in the test.
- Progress is appended to `gui-progress.log` at each major phase and simulation batch.
- `gui-screenshot-manifest.txt` records the proof represented by each image.
- The FreeCAD process is run under `DISPLAY=:99`, `QT_QPA_PLATFORM=xcb`, `LIBGL_ALWAYS_SOFTWARE=1`, and Xvfb's fixed 1280x720x24 screen.
- The GUI script checks task-panel visibility/content and document geometry/state before saving.
- The workflow additionally verifies each PNG exists, is at least 20 KB, has a PNG signature, and is exactly 1280x720 before uploading it.

The images and diagnostics are Actions artifacts named `cloth-gui-screenshots` and `cloth-gui-diagnostics`. Merged PRs publish all four images under `docs/images/generated/merged-pr-<number>/`.
