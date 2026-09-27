# Installation

## Requirements

- FreeCAD with a supported embedded Python runtime; the canonical development and CI baseline is **Python 3.12+**.
- triangle version 20250106 for constrained pattern meshing.
- A FreeCAD GUI session for visual workbench usage.
- Tissu is optional; the deterministic CPU backend remains the correctness reference.

## Install into FreeCAD

1. Download or clone the repository.
2. Copy the repository directory into FreeCAD's user Mod directory.
3. Restart FreeCAD.
4. Select **Cloth Pattern**, **Cloth Sewing**, or **Cloth Simulation** from the workbench selector.

The repository root contains the required Init.py and InitGui.py bootstrap files. Keep them at the repository root.

> **Tip:** When upgrading an existing installation, remove the previous freecad-cloth directory first. This prevents stale Python modules from remaining on the module search path.

## First run

Start with the **Blanket over Cube** example:

1. Open FreeCAD.
2. Switch to **Cloth Pattern**.
3. Create or open a simple pattern.
4. Switch to **Cloth Sewing** if seams are needed.
5. Switch to **Cloth Simulation**.
6. Select a valid target, pin the cloth and run the simulation.

![Blanket over cube](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif)

## What a healthy installation looks like

After restart, the Cloth workbenches should appear in FreeCAD's workbench selector.

If they do not, check:

- the repository is directly below the FreeCAD Mod directory;
- Init.py and InitGui.py are still at the repository root;
- FreeCAD was restarted after installation;
- your embedded Python version matches the supported environment.

## Developer note

The canonical CI image uses FreeCAD 1.1.0 with Python 3.12. The project documentation deliberately distinguishes that canonical environment from other locally packaged FreeCAD builds.
