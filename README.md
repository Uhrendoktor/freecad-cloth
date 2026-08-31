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

The **Cloth Pattern** workbench creates native, recomputable `Part::FeaturePython` pattern pieces. Width, height, seam allowance and grainline angle are exposed as FreeCAD properties; changing the dimensions regenerates the deterministic pattern boundary. Pattern pieces and seams carry stable semantic IDs and sewing metadata. A native Sketcher representation is available through the Cloth Pattern command while the semantic pattern model remains authoritative. Context-sensitive mark commands (Notch, Grainline and Internal Mark) are enabled when a pattern piece is selected.

The FreeCAD-independent geometry/model layers remain suitable for headless tests and downstream simulation. The pattern model is authoritative; simulation meshes are regenerated from it rather than becoming a second source of truth.

Imported FreeCAD body/mesh geometry can populate a solver-neutral collision surface, with the deterministic sphere collider retained as a fallback. Fitting scenes store measurement, avatar association and piece-placement metadata without coupling the document to a particular solver.

The reference CPU solver now includes explicit stretch/shear/bending constraint families and deterministic particle self-collision. External native XPBD/PBD engines remain optional backend candidates.

## Development and testing

The repository has a single canonical GitHub Actions workflow, `canonical-execution.yml`. It runs the headless core test suite and Python syntax/package checks across supported Python versions, a real FreeCAD smoke test, and a GUI screenshot scenario under Xvfb. Screenshot PNGs are uploaded as the `cloth-gui-screenshots` CI artifact so documentation captures remain reproducible without making image files a production runtime dependency.

See [docs/SEWING_WORKFLOW_RESEARCH.md](docs/SEWING_WORKFLOW_RESEARCH.md) for workflow research, architecture decisions, and external-project evaluation.
