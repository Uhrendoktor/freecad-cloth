# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository itself is the source tree; the supported runtime boundary is FreeCAD's user `Mod` directory.

## Requirements

- FreeCAD with an embedded Python 3.12-or-newer runtime for the supported project baseline.
- The Python package `triangle==20250106` in the same Python runtime used by FreeCAD for pattern meshing.
- A FreeCAD GUI session for the visual workbench checks.
- Tissu is optional; the deterministic CPU backend remains the correctness fallback when the optional package is unavailable.

The canonical CI image and dependency versions are recorded in `.github/workflows/canonical-execution.yml` and `docker/freecad-ci/Dockerfile`. The repository's current release notes also distinguish the supported Python baseline from FreeCAD builds that still embed Python 3.11.

## Find the user Mod directory

From the FreeCAD Python console, run:

```python
import FreeCAD as App
print(App.getUserAppDataDir())
```

Place the repository directly under the `Mod` directory below that user-data location. Do not guess a platform-specific path when FreeCAD can report it.

## User installation

1. Download or clone this repository.
2. Copy the complete repository directory into the FreeCAD user's `Mod` directory, for example `<FreeCAD user data>/Mod/freecad-cloth/`.
3. Keep the repository-root `Init.py` and `InitGui.py` files at that root level.
4. Ensure `triangle==20250106` is importable by the Python runtime embedded in FreeCAD.
5. Restart FreeCAD.
6. Confirm **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** appear in the workbench selector.

For an existing installation, remove the previous `freecad-cloth` directory before replacing it so stale Python modules cannot remain on the module search path.

## First run

Start with **Blanket over Cube** in [EXAMPLES.md](EXAMPLES.md). The first-run goal is to prove that a native Sketcher pattern becomes a PatternPiece, a FreeCAD cube can become a persistent `DrapeTarget`, the target reaches the **ready** state, and the cloth actually moves.

The canonical visual fixture is `tests/freecad_visual_examples.py`. It is stronger than a screenshot-only smoke test: it creates the native Sketcher source, records the persistent target, checks finite/connected cloth geometry, saves real viewport PNGs, and verifies that the simulated cloth changes between early and late frames.

The fixture sets the two opposite blanket corners in `PinSelection` and relies on the scene's persistent `PinMode` default of **Automatic**. The current quality panel does not provide a mesh-vertex picker for authoring those indices, so the human workflow should not invent a click-to-pin step that is not present in the UI.

After the blanket succeeds, continue with the tunic workflow in [EXAMPLES.md](EXAMPLES.md), then use [USER_GUIDE.md](USER_GUIDE.md) and [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) as the day-to-day references.

## Developer setup

The canonical dependency command is:

```bash
python3 -m pip install triangle==20250106
```

The repository's non-GUI tests are regular Python scripts. The FreeCAD/Xvfb acceptance tests exercise the actual GUI, collision path, solver backends and rendered artifacts, so they run inside the single canonical GitHub Actions workflow.

Do not create a second workflow for a one-off GUI or documentation check.

## Troubleshooting

**The workbenches do not appear:** verify that the repository directory is directly below FreeCAD's `Mod` directory, that `Init.py` and `InitGui.py` are still at the repository root, and restart FreeCAD.

**Pattern meshing fails:** verify that `triangle==20250106` is importable by the embedded FreeCAD Python runtime, not only by a separate system Python.

**A seam becomes invalid after editing a sketch:** recompute the document and use **ClothSewing_RepairSeam / Repair Seam** only when the original semantic edge still exists. If the edge identity disappeared, recreate the seam against the intended edge; Cloth never silently retargets it.

**Simulation is blocked:** inspect the persistent `DrapeTarget` status. A **stale**, **unbuilt**, **unassigned**, **invalid**, **missing** or **disabled** target must be rebuilt/refreshed before simulation can run.

**The tunic intersects the mannequin:** correct persistent arrangement/placements and refresh the `DrapeTarget` after source changes. The validated tunic path uses target-relative starting placement and `PinMode=None`; it does not establish a general automatic body-snap workflow.

**Local visual output differs from CI:** use the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow before comparing rendered artifacts. Published README media is generated from validated CI artifacts; do not replace it with ad-hoc screenshots.