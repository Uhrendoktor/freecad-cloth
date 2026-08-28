# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Simulation** — meshing, sewing constraints, body collision and cloth simulation.

The **Cloth Pattern** workbench creates native, recomputable `Part::FeaturePython` pattern pieces. Width, height, seam allowance and grainline angle are exposed as FreeCAD properties; changing the dimensions regenerates the deterministic pattern boundary. Pattern pieces and seams carry stable semantic IDs and sewing metadata.

The workbench menu provides commands to create a standard piece, create a larger drafting piece, generate a solver-ready mesh, and connect the first two pattern pieces with a seam. The FreeCAD-independent geometry/model layers remain suitable for headless tests and downstream simulation.

The current architecture keeps the pattern model authoritative and regenerates simulation meshes from it. Imported FreeCAD body/mesh geometry can now populate a solver-neutral `CollisionSurface`, with the sphere collider retained as a fallback.

Early development. See the [workflow and backend research](docs/SEWING_WORKFLOW_RESEARCH.md) for the current implementation plan and external-project evaluation.

The repository has a single canonical GitHub Actions workflow, `canonical-execution.yml`, which runs core tests and syntax checks on pushes and pull requests. A FreeCAD smoke test runs in a Debian container with `freecadcmd`.
