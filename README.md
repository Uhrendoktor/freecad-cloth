# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Simulation** — meshing, sewing constraints, body collision and cloth simulation.

The first interactive drafting tools now create native, editable `Part::FeaturePython` pattern pieces. Width and height are exposed as FreeCAD length properties and changing either dimension regenerates the deterministic rectangle while preserving the pattern topology. Pattern pieces also carry stable IDs, seam-allowance and grainline metadata, plus a JSON outline for interchange.

The **Cloth Pattern** menu provides commands to create a standard piece, a larger drafting example, generate a solver-ready mesh, and connect two pieces with a seam. The existing FreeCAD-independent geometry/model layers remain usable for tests and downstream simulation.

Early development. See [issue #1](https://github.com/Uhrendoktor/freecad-cloth/issues/1) for research and the implementation plan.

The repository has a single canonical GitHub Actions workflow, `canonical-execution.yml`, which runs core tests and syntax checks on pushes and pull requests. A FreeCAD smoke test runs when a `freecadcmd` executable is available.
