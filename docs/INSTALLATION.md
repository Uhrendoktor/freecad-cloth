# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository itself is the source tree; a normal user installation is the repository directory placed directly in FreeCAD's user `Mod` directory.

## Prerequisites

Use a FreeCAD build with **Python 3.12 or newer** for the supported repository baseline. The project currently expects:

- FreeCAD with an embedded Python 3.12+ runtime.
- Python package `triangle==20250106` for constrained pattern meshing.
- A GUI session for the normal workbench and visual examples.

Tissu is optional for the canonical visual-regression environment; the deterministic CPU backend remains the correctness reference.

The exact CI image and dependency boundary are defined by [.github/workflows/canonical-execution.yml](../.github/workflows/canonical-execution.yml) and [docker/freecad-ci/Dockerfile](../docker/freecad-ci/Dockerfile).

## User installation

1. Download or clone the repository.
2. Copy the **repository directory itself** into FreeCAD's user `Mod` directory.
3. Keep `Init.py` and `InitGui.py` at the repository root; do not move them into another subdirectory.
4. Restart FreeCAD.
5. Open the workbench selector and verify that **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** are available.

For an existing installation, remove the previous `freecad-cloth` directory before replacing it. This prevents stale Python modules from remaining on FreeCAD's module search path.

## First launch and first successful result

Do the simplest smoke test before attempting the tunic:

1. Open **Cloth Simulation** and make sure the workbench loads without import errors.
2. Follow [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube). The basic example intentionally uses a simple FreeCAD collision target and two blanket corner pins.
3. The successful result is visible cloth motion toward and around the cube, not merely a static viewport.
4. Continue with [USER_GUIDE.md](USER_GUIDE.md) for the multi-piece garment workflow.

This sequence separates installation problems from garment-fitting problems. Do not use the tunic as the first installation test.

## Developer setup

The canonical test environment installs Triangle with:

    python3 -m pip install triangle==20250106

The repository's non-GUI tests are ordinary Python scripts. The real FreeCAD/Xvfb acceptance tests run inside the published CI image because they exercise the actual FreeCAD GUI, rendering path, and available solver backends.

The repository has one canonical workflow: [.github/workflows/canonical-execution.yml](../.github/workflows/canonical-execution.yml). Do not create a second workflow for a one-off GUI check.

## Troubleshooting

**The workbenches do not appear**

Verify that the repository directory is directly below FreeCAD's user `Mod` directory, that `Init.py` and `InitGui.py` are still at the repository root, and restart FreeCAD. If the problem started after replacing an older installation, remove the previous `freecad-cloth` directory before copying the new one.

**Simulation is blocked**

Select or create a persistent `DrapeTarget`. If the target source changed, use **Refresh Drape Target** before running simulation. The simulation task panel intentionally disables **Step** and **Run 30** while the target is stale, unbuilt, unassigned, invalid, missing, or disabled.

**A seam becomes invalid after editing a sketch**

Recompute the document, inspect the seam in **Cloth Sewing**, and repair the semantic reference explicitly. Use **Repair Seam** for supported correspondence repair, or recreate the seam. Cloth does not silently retarget a seam to a different generated edge.

**Simulation becomes invalid or non-finite**

Use **Reset** in the **Simulation Controls** task panel, inspect the target status, and rebuild/refresh the dependent target or mesh before trying again. Do not continue stepping a known invalid state.

**Visual results differ from the repository evidence**

Compare against the same FreeCAD/Triangle versions used by the canonical workflow. Use the CI artifact/log as evidence rather than editing generated screenshots manually.
