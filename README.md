# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

## Workbenches

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Simulation** — meshing, sewing constraints, body collision and cloth simulation.

The project starts as a pure-Python external workbench so the data model and UI can evolve quickly while simulation backends remain replaceable.

## Status

Early development. See [issue #1](https://github.com/Uhrendoktor/freecad-cloth/issues/1) for research and the implementation plan.

## Development

The repository has a single canonical GitHub Actions workflow, `canonical-execution.yml`, which runs the project tests on pushes and pull requests. A FreeCAD smoke test runs when a `freecadcmd` executable is available on the runner.

The core geometry/data-model tests intentionally run without FreeCAD so contributors can work on the algorithms independently of a GUI installation.
