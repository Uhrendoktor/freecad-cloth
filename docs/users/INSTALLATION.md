# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository is the source tree; the supported user runtime is a FreeCAD `Mod` installation.

## Requirements

- FreeCAD **1.1.0 or newer** for user installation; this minimum is declared in `package.xml`.
- Python **3.12** for repository development/CI and the PositionBasedDynamics-capable canonical environment.
- `triangle==20250106` for constrained pattern meshing.
- `pydantic>=2.11,<3` for validated geometry, mesh, and seam inputs.
- `scipy>=1.14,<2` for exact spatial-index nearest-vertex clearance.
- `shapely>=2,<3` for GEOS-backed polygon simplicity checks.
- `anny>=0.6,<0.7` and `clad-body[anny]>=0.6.1,<0.7` for the built-in parametric mannequin and anthropometric measurement fitting; these are normal project dependencies.
- PositionBasedDynamics for the production simulation path when simulation support is installed.
- A FreeCAD GUI session for the visual workbench tests.

The exact development/CI environment is defined by `pyproject.toml` and the canonical GitHub Actions workflow. The FreeCAD runtime must have the project's dependencies available in its embedded Python environment; the canonical CI image installs and prewarms them automatically. Installing the Python project with pip installs its required dependencies as part of the normal package install. Copying the workbench folder into FreeCAD's `Mod` directory or installing it through Addon Manager does not execute `pyproject.toml`, so those installation paths must ensure the declared dependencies are installed in FreeCAD's embedded Python environment.

## User installation

1. Download or clone this repository.
2. Copy the repository directory into FreeCAD's user `Mod` directory.
3. Restart FreeCAD.
4. Select **Cloth Pattern**, **Cloth Sewing**, or **Cloth Simulation** from the workbench selector.

The classic root `Init.py`/`InitGui.py` loader and the modern namespaced loader both resolve to the same `freecad_cloth/` implementation package.

`package.xml` is the FreeCAD Addon Manager manifest. `pyproject.toml` describes the Python distribution and development environment; it is not the Addon Manager installer manifest.

For an existing installation, remove the previous `freecad-cloth` directory before replacing it so stale Python modules cannot remain on the module search path.

## First run

Recommended first run:

1. Open the [end-to-end user guide](USER_GUIDE.md) and follow its Tunic path from pattern through simulation.
2. Use the [Tunic example](EXAMPLES.md#2-tunic) as the acceptance reference for the full garment path.
3. Run [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube) when diagnosing a basic target, pinning, or collision problem independently of sewing and mannequin complexity.

## Developer setup

Install the development toolchain with:

```bash
python -m pip install -e ".[dev]"
pre-commit install
```

SciPy, Shapely, Anny, and clad-body are required dependencies and are installed with the main package. The built-in mannequin is a standard workbench feature; its model assets are initialized and cached on first use.

The benchmark under `tools/benchmarks/benchmark_geometry_libraries.py` compares the required
library outputs with independent test/reference calculations before reporting timings.

The canonical GUI tests run inside the published FreeCAD CI environment because they exercise the actual GUI, solver backend and rendering path.

The project keeps one canonical GitHub Actions workflow. See [DEVELOPMENT.md](../developers/DEVELOPMENT.md) for the validation matrix and [CI configuration](../developers/CI_CONFIGURATION.md) for the single authoritative runtime-budget setting.

## Troubleshooting

Use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) rather than repeating recovery instructions across installation and feature pages.
