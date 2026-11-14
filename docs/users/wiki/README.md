# FreeCAD Cloth feature guide index

This wiki-style manual is organised around reader tasks. Start with setup if you are new, use the user guide to follow the full garment workflow, and open a feature page when you need a particular interaction or its visual acceptance criteria.

## Start here

| I want to… | Read |
| --- | --- |
| Install Cloth and understand its runtime requirements | [Installation](../INSTALLATION.md) |
| Complete the pattern-to-drape workflow once | [End-to-end user guide](../USER_GUIDE.md) |
| Understand the simple and full-garment examples | [Examples](../EXAMPLES.md) |
| Adjust mannequin body shape and sewing dimensions | [Avatar shape and dimensions](09-avatar-shape.md) |
| Fix a missing workbench, invalid seam, wrong arrangement, or stale simulation | [Troubleshooting](../TROUBLESHOOTING.md) |
| Find user-facing command behavior | [Workbench guide](../WORKBENCH_GUIDE.md) |

The recommended learning sequence is **Sketcher pattern → semantic seams → avatar shape and dimensions → fitting arrangement → optional mannequin pose → simulation → multi-view diagnosis**. Set up the human target before fitting fabric. Start with a simple collision target when diagnosing basic cloth behavior.

## Follow the workflow

The overview shows the complete sequence and the resulting visual states. Each stage links to a focused feature guide. The mannequin shape/dimension step belongs before piece arrangement so sewing and fitting use the intended body surface.

| Stage | Guide | Visual evidence |
| --- | --- | --- |
| 1. Pattern | [Author a pattern piece](01-pattern.md) | Native Sketcher geometry plus Surface Pen task-panel screenshot, closure-to-extraction GIF, and extracted sketch |
| 2. Sewing | [Create and inspect seams](02-sewing.md) | Seam assignment and A/B identity |
| 3. Avatar shape | [Edit body shape and dimensions](09-avatar-shape.md) | Seven rendered body-shape examples, shape sliders, measurement rings, and staged dimension drag |
| 4. Fitting | [Arrange and snap pieces](03-fitting.md) | Drag preview and committed placement |
| 5. Pose | [Pose the mannequin](04-pose.md) | Joint selection and rotation gizmo |
| 6. Simulation | [Run a cloth simulation](05-simulation.md) | Arranged garment, motion, and final drape |
| 7. Diagnosis | [Inspect the result](06-diagnostics.md) | Diagnostic map and six-side audit |

## Understand and audit the result

The [end-to-end overview](00-overview.md) maps the stages and expected outputs.

## Engineering reference

The pages below are developer references for understanding behavior behind the user workflow; they are not additional steps for operating the workbench.

- [Data model, persistence, and architecture](../../developers/DATA_MODEL.md) — what is saved, rebuilt, and invalidated.
- [Validation and visual evidence](../../developers/VALIDATION.md) — automated acceptance, screenshot provenance, and review order.

Contributors who change these pages should follow the [Documentation guide](../../developers/DOCUMENTATION_GUIDE.md).
