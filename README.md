# FreeCAD Cloth

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Finished garment draped over the FreeCAD mannequin" width="900"></p>

<p align="center"><strong>Pattern → Sewing → Fitting → Pose → Simulation → Diagnosis</strong></p>

FreeCAD Cloth adds a native garment workflow to FreeCAD. Use the **Cloth Pattern** workbench to author editable 2D pieces, **Cloth Sewing** to define persistent seam relationships, and **Cloth Simulation** to arrange, drape, and inspect the garment.

## Choose your next step

| Goal | Start here |
| --- | --- |
| Install the workbench | [Installation and requirements](docs/INSTALLATION.md) |
| Follow the garment workflow | [End-to-end user guide](docs/USER_GUIDE.md) |
| Learn one feature in detail | [Visual wiki and feature guides](docs/wiki/README.md) |
| Check a simple case before a full garment | [Examples and validation path](docs/EXAMPLES.md) |
| Diagnose a missing command, invalid seam, wrong arrangement, or stale simulation | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Contribute or improve the docs | [Development guide](docs/DEVELOPMENT.md) · [Documentation guide](docs/DOCUMENTATION_GUIDE.md) |

## See the interactions

These recordings are generated from real FreeCAD UI acceptance fixtures and are ordered as a workflow reference: sewing, fitting anchors, panel arrangement, and mannequin posing. They are task-focused captures rather than one continuous recording from a single saved document; the production tunic audit validates the integrated garment path separately. Each feature guide explains the interaction and what to check when the result differs.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/seam-assignment.gif" alt="Selecting two pattern edges, reviewing a seam preview, and committing the seam" width="235"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/arrangement-anchor.gif" alt="Naming and creating front and back surface snap points on the FreeCAD mannequin" width="235"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.gif" alt="Dragging the tunic front and back panels onto their mannequin snap points and releasing to commit both placements" width="235"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/pose-joint-rotation.gif" alt="Selecting a mannequin joint and changing its rotation in Pose Mode" width="235"></p>

<p align="center"><a href="docs/wiki/02-sewing.md">Create a seam</a> · <a href="docs/wiki/03-fitting.md">Arrange pieces</a> · <a href="docs/wiki/04-pose.md">Pose the mannequin</a></p>

## The workflow in six views

This gallery gives a static overview of each major stage; the recordings above show how selected interactions change over time.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Pattern authoring stage with native Sketcher-backed garment pieces" width="430"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png" alt="Sewing stage showing authored pattern pieces and semantic seam relationships" width="430"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.png" alt="Interactive Arrange task panel and garment placement in the viewport" width="430"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-pose-mode.png" alt="Pose Mode with visible mannequin joint overlay and selected rotation gizmo" width="430"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png" alt="Sewn garment arranged around the mannequin before simulation" width="430"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Final garment draped over the mannequin after simulation" width="430"></p>

## Feature guide

| Stage | What you can do | Guide |
| --- | --- | --- |
| Pattern | Build on native Sketcher geometry and add garment semantics, notches, marks, and grainlines | [Pattern authoring](docs/wiki/01-pattern.md) |
| Sewing | Pick matching edges, inspect A/B identity and direction, and commit validated seams | [Sewing and correspondence](docs/wiki/02-sewing.md) |
| Fitting | Place pieces directly in the viewport and use arrangement snapping | [Direct fitting](docs/wiki/03-fitting.md) |
| Pose | Rotate mannequin joints, use symmetry, and enter exact angles when needed | [Pose Mode](docs/wiki/04-pose.md) |
| Simulation | Choose a target, material, quality, and pinning mode before running cloth | [Cloth simulation](docs/wiki/05-simulation.md) |
| Diagnosis | Review motion, stress, stale state, and the garment from six sides | [Diagnostics](docs/wiki/06-diagnostics.md) |

For the complete route, start with the [workflow overview](docs/wiki/00-overview.md). For persistence rules and the technical evidence behind user-visible behavior, see [Data model](docs/wiki/07-data-model.md) and [Validation and visual evidence](docs/wiki/08-validation.md).

## First-run recommendation

1. Check supported versions and install the workbench using [Installation](docs/INSTALLATION.md).
2. Follow the [end-to-end user guide](docs/USER_GUIDE.md) with the **Tunic** example as the main pattern-to-drape journey.
3. Use [Blanket over Cube](docs/EXAMPLES.md#1-blanket-over-cube) when you specifically need to isolate pattern, target, pinning, or collision behavior from garment complexity.

The exact manual-install directory, embedded-Python dependencies, and replacement procedure are documented in Installation. Do not assume that the Python interpreter used by your system shell is the same interpreter embedded in FreeCAD.

## Visual evidence and source of truth

Public screenshots and animations are generated artifacts, not hand-edited product illustrations. The canonical workflow in [canonical-execution.yml](.github/workflows/canonical-execution.yml) runs the FreeCAD/Xvfb acceptance path and publishes rendered evidence to the docs/screenshots branch. The publisher checks the documented image inventory and its provenance.

When a UI or geometry change alters a screenshot, update its real capture fixture and let the canonical workflow regenerate it. A passing unit test is not visual proof, and a convincing image is not proof that the saved document persists correctly. The wiki pairs visual evidence with the relevant acceptance fixture and technical source.

The saved FreeCAD document is authoritative. Sketcher geometry and semantic garment relationships are persistent; simulation meshes and solver state are derived; hover highlights and drag previews are transient. See [Data model](docs/wiki/07-data-model.md) for the full dependency model.

## Scope and license

FreeCAD Cloth is an evolving workbench, not a claim of complete commercial garment-CAD parity. Advanced grading and nesting, production construction libraries, richer avatar providers, and measurement-grade fit analysis remain distinct from the workflows documented as implemented.

Licensed under LGPL-2.1-or-later. See [LICENSE](LICENSE).
