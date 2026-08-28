# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Simulation** — meshing, sewing constraints, body collision and cloth simulation.
- **Cloth Sewing** — seam operations, piece assembly, fitting-scene metadata and validation.

## Current workflow

1. Create parametric pattern pieces and construction metadata in **Cloth Pattern**.
2. Define seam pairings and assembly operations in **Cloth Sewing**.
3. Optionally define body measurements, associate an avatar/collision proxy, and place pieces reproducibly in a fitting scene.
4. Generate simulation meshes and run the solver through the backend adapter in **Cloth Simulation**.
5. Inspect fit, revise the pattern, and repeat.

The **Cloth Pattern** workbench creates native, recomputable `Part::FeaturePython` pattern pieces. Width, height, seam allowance and grainline angle are exposed as FreeCAD properties; changing the dimensions regenerates the deterministic pattern boundary. Pattern pieces and seams carry stable semantic IDs and sewing metadata.

The FreeCAD-independent geometry/model layers remain suitable for headless tests and downstream simulation. The pattern model is authoritative; simulation meshes are regenerated from it rather than becoming a second source of truth.

Imported FreeCAD body/mesh geometry can populate a solver-neutral collision surface, with the deterministic sphere collider retained as a fallback. Fitting scenes store measurement, avatar association and piece-placement metadata without coupling the document to a particular solver.

## Development and testing

The repository has a single canonical GitHub Actions workflow, `canonical-execution.yml`. It runs the headless core test suite and Python syntax/package checks across supported Python versions. The same workflow also runs a real FreeCAD smoke test for workbench loading and GUI-layer contracts. GUI screenshot generation, when added, should remain documentation tooling rather than a production workbench dependency.

The project is early development. See [docs/SEWING_WORKFLOW_RESEARCH.md](docs/SEWING_WORKFLOW_RESEARCH.md) for the current implementation plan, architecture decisions, and external-project evaluation.
