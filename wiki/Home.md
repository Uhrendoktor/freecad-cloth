# FreeCAD Cloth

> **Parametric pattern design → semantic sewing → cloth simulation — inside FreeCAD.**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FreeCAD](https://img.shields.io/badge/FreeCAD-1.1%2B-DA3434)](https://www.freecad.org/)
[![License](https://img.shields.io/badge/license-LGPL--2.1+-blue)](https://github.com/Uhrendoktor/freecad-cloth/blob/main/LICENSE)

<table>
<tr>
<td width="55%">

FreeCAD Cloth combines three native workbenches:

- **Cloth Pattern** — editable 2D pattern pieces, seam allowances, notches and grainlines.
- **Cloth Sewing** — semantic seams, correspondence and construction relationships.
- **Cloth Simulation** — targets, pinning, materials, draping and diagnostics.

</td>
<td>

![Draped tunic](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png)

</td>
</tr>
</table>

## The workflow

<pre>Pattern → Sewing → Arrange / Fit → Simulate → Inspect → Output</pre>

The project keeps the workflow FreeCAD-native: editable geometry stays in Sketcher and Part, garment meaning stays in Cloth, and physical simulation remains a derived layer.

## Start here

| I want to… | Start with |
| --- | --- |
| Install Cloth | [[Installation]] |
| Build a first project | [[User-Guide]] |
| Design pattern pieces | [[Pattern-Workbench]] |
| Create seams | [[Sewing-Workbench]] |
| Run a drape simulation | [[Simulation-Workbench]] |
| Fix a blocked workflow | [[Troubleshooting]] |

<details>
<summary><strong>First-run recommendation</strong></summary>

Start with the small **Blanket over Cube** example. It proves the installation, meshing and basic simulation path before you move to the larger tunic workflow.

![Blanket over cube](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif)

</details>

## Visual tour

<table>
<tr>
<td align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif" alt="Arranged cloth turntable" width="280"><br><sub>Arranged cloth</sub></td>
<td align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif" alt="Draped cloth turntable" width="280"><br><sub>Draped cloth</sub></td>
<td align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-turntable.gif" alt="Avatar turntable" width="280"><br><sub>Avatar</sub></td>
</tr>
</table>

## Runtime note

The supported development and canonical CI environment uses **Python 3.12 or newer**. See [[Installation]] before troubleshooting solver or backend differences.

## For developers and agents

The polished Wiki is the human-facing layer. Engineering contracts and agent execution rules remain in the repository under [docs/agents](https://github.com/Uhrendoktor/freecad-cloth/tree/main/docs/agents).
