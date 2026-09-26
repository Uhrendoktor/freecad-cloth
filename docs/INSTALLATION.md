# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository itself is the source tree; the supported runtime boundary is FreeCAD's user `Mod` directory.

## Requirements

- FreeCAD with Python 3.12 for the canonical development/CI environment.
- The Python package `triangle==20250106` for constrained pattern meshing.
- Optional: Tissu is used by the canonical visual regression path when the environment provides it. The reference CPU backend remains the fallback.
- A FreeCAD GUI session is required for the visual workbench tests.

The repository publishes its exact CI image and dependency versions in `.github/workflows/canonical-execution.yml` and `docker/freecad-ci/Dockerfile`.

## User installation

1. Download or clone this repository.
2. Copy the repository directory into FreeCAD's user `Mod` directory.
3. Restart FreeCAD.
4. Select **Cloth Pattern**, **Cloth Sewing**, or **Cloth Simulation** from the workbench selector.

The repository root contains the required FreeCAD bootstrap files `Init.py` and `InitGui.py`; do not move those files below another directory level.

For an existing installation, remove the previous `freecad-cloth` directory before replacing it so stale Python modules cannot remain on the module search path.

## First run

Start with the **Blanket over Cube** example in [EXAMPLES.md](EXAMPLES.md). It is deliberately smaller than the tunic and is the recommended smoke test for a new installation. Keep this first run separate from the tunic: the blanket isolates cloth, collision, gravity and explicit pinning without depending on the mannequin fitting path.

Then read the concise [User guide](USER_GUIDE.md) and run the tunic workflow documented in [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md). The tunic is the advanced path: it uses the Simulation → Arrange / Fit handoff and `PinMode=None` with zero solver pins.

## Developer setup

The canonical test environment installs the Triangle dependency with:

    python3 -m pip install triangle==20250106

The repository's non-GUI tests are regular Python scripts. The FreeCAD/Xvfb acceptance tests are intentionally run inside the published CI environment because they exercise the actual FreeCAD GUI, solver backends and rendering path.

The canonical command set is defined in `.github/workflows/canonical-execution.yml`; do not create a second workflow for a one-off GUI test.

## Troubleshooting

**The workbenches do not appear:** verify that the repository directory is directly below FreeCAD's `Mod` directory and restart FreeCAD.

**Simulation is blocked:** select a current `DrapeTarget` and rebuild it after changing the target geometry. Cloth intentionally refuses stale collision state.

**A seam becomes invalid after editing a sketch:** recompute the document and use the explicit seam repair/remap workflow. Cloth never silently retargets a seam to another edge.

**Visual CI differs from local FreeCAD:** use the same FreeCAD/Triangle/Tissu versions recorded by the canonical workflow before comparing screenshots.
