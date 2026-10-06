# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository is the source tree; the supported user runtime is a FreeCAD `Mod` installation.

## Requirements

- FreeCAD **1.1.0 or newer** for user installation; this minimum is declared in `package.xml`.
- Python **3.12** for repository development/CI and the PositionBasedDynamics-capable canonical environment.
- `triangle==20250106` for constrained pattern meshing.
- PositionBasedDynamics for the production simulation path when simulation support is installed.
- A FreeCAD GUI session for the visual workbench tests.

The exact development/CI environment is defined by `pyproject.toml` and the canonical GitHub Actions workflow.

## User installation

1. Download or clone this repository.
2. Copy the repository directory into FreeCAD's user `Mod` directory.
3. Restart FreeCAD.
4. Select **Cloth Pattern**, **Cloth Sewing**, or **Cloth Simulation** from the workbench selector.

The classic root `Init.py`/`InitGui.py` loader and the modern namespaced loader both resolve to the same `freecad_cloth/` implementation package.

`package.xml` is the FreeCAD Addon Manager manifest. `pyproject.toml` describes the Python distribution and development environment; it is not the Addon Manager installer manifest.

For an existing installation, remove the previous `freecad-cloth` directory before replacing it so stale Python modules cannot remain on the module search path.

## First run

Use this order:

1. [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube)
2. [User guide](USER_GUIDE.md)
3. [Tunic](EXAMPLES.md#2-tunic) for the full garment path

Starting with the blanket avoids mixing installation problems with sewing, mannequin and production-garment problems.

## Developer setup

Install the development toolchain with:

```bash
python -m pip install -e ".[dev]"
pre-commit install
```

The canonical GUI tests run inside the published FreeCAD CI environment because they exercise the actual GUI, solver backend and rendering path.

The project keeps one canonical GitHub Actions workflow. See [DEVELOPMENT.md](DEVELOPMENT.md) for the validation matrix and [CI configuration](CI_CONFIGURATION.md) for the single authoritative runtime-budget setting.

## Troubleshooting

Use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) rather than repeating recovery instructions across installation and feature pages.
