# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository is the source tree; direct user installation places that tree in FreeCAD's user `Mod` directory.

## Supported runtime

For the current `main` branch:

- **Python 3.12 or newer** is the project-wide baseline. The supported development/CI FreeCAD runtime is also Python 3.12+.
- **`triangle==20250106`** is a project dependency for constrained pattern meshing and must be importable by the same Python runtime that runs FreeCAD Cloth.
- **Tissu** is optional for local use. The deterministic CPU reference backend remains the fallback; the canonical visual-regression environment includes Tissu.
- A **FreeCAD GUI session** is required for workbench use and visual acceptance.

The validated CI baseline is a conda-forge FreeCAD **1.1.0** environment with Python 3.12, `pytissu==1.1.0`, and `triangle==20250106`. This is a reproducible project reference, not a claim that every FreeCAD distribution with the same application version embeds the same Python runtime.

A FreeCAD build with an embedded Python older than 3.12 is outside the current supported project baseline. Check the embedded runtime before troubleshooting package imports.

## User installation

1. Download or clone the repository.
2. Copy the repository directory directly below FreeCAD's user `Mod` directory.
3. Keep the repository root files `Init.py`, `InitGui.py`, and `package.xml` at that same root level. Do not add another directory level around the workbench.
4. Make sure `triangle==20250106` is available to the FreeCAD Python runtime.
5. Restart FreeCAD.
6. In the workbench selector, verify that **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** are available.

For an existing installation, remove the previous `freecad-cloth` directory before replacing it. This avoids stale Python modules remaining on FreeCAD's module search path.

The project does not currently publish a separate binary installer or packaged wheel for end users; the repository tree is the supported installation artifact.

## First-run verification

Use the FreeCAD Python console to verify the runtime before starting the examples:

```python
import sys
print(sys.version)
import FreeCAD
print(FreeCAD.Version())
import triangle
print(triangle.__file__)
```

The important checks are:

- Python reports **3.12 or newer**.
- `triangle` imports successfully from the same interpreter that is running FreeCAD.
- The three Cloth workbenches appear after restarting FreeCAD.

Then follow [Examples](EXAMPLES.md), starting with **Blanket over Cube**. It is deliberately simpler than the tunic path and isolates cloth/collision problems from avatar fitting.

## Developer setup

For repository development, the canonical dependency installation is:

```bash
python3 -m pip install triangle==20250106
```

The non-GUI tests are regular Python tests. The FreeCAD/Xvfb acceptance tests run in the published project image so they exercise the actual FreeCAD GUI, solver backends, and rendering path.

There is exactly one GitHub Actions workflow: `.github/workflows/canonical-execution.yml`. Do not add a one-off replacement workflow for documentation or GUI validation.

## Troubleshooting

**The workbenches do not appear**

Verify that the repository directory is directly below FreeCAD's user `Mod` directory, that `InitGui.py` is at the repository root, and restart FreeCAD.

**Python or Triangle import errors**

Run the verification snippet above. If FreeCAD reports Python <3.12, the current project baseline is not met. If `triangle` fails to import, install the pinned dependency into the FreeCAD runtime rather than an unrelated system Python.

**A command is disabled**

Cloth commands intentionally check the active document and current selection. Read the tooltip/state message, select the required PatternPiece, seam, or target, and retry.

**Simulation is blocked or stale**

Select a current `DrapeTarget`. If its source geometry, placement, collision tessellation, or collision thickness changed, use **Refresh Drape Target** / `ClothDrape_RefreshTarget` before running the simulation.

**A seam becomes invalid after editing a Sketch**

Recompute the document and use the explicit seam repair/remap workflow. Cloth never silently retargets a seam to a different semantic edge.

**Local visuals differ from CI**

Compare the FreeCAD, Python, Triangle, and Tissu versions with the canonical environment before comparing screenshots. Do not edit generated evidence manually; regenerate the fixture and inspect the logs/artifacts.
