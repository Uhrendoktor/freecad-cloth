# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Simulation** — meshing, sewing constraints, body collision and cloth simulation.

Early development. See [issue #1](https://github.com/Uhrendoktor/freecad-cloth/issues/1) for research and the implementation plan.

The repository has a single canonical GitHub Actions workflow, `canonical-execution.yml`, which runs core tests and syntax checks on pushes and pull requests. A FreeCAD smoke test runs when a `freecadcmd` executable is available.
