# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Sewing** — semantic seam operations, correspondence, fitting-scene preparation and validation.
- **Cloth Simulation** — meshing, target selection, body collision and cloth simulation.

## Workflow

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD/Sketcher owns editable geometry and document persistence; Cloth owns garment semantics; the solver owns physics. Simulation meshes and collision data are derived and rebuildable. A native human mannequin and generic FreeCAD Shape/PartDesign/Body/Mesh are interchangeable providers of the same target-neutral `DrapeTarget` contract.

## Current implementation

The Pattern workbench creates native, recomputable PatternPieces with semantic IDs and pattern metadata. Sewing persists seam relationships and supports direction/correspondence operations. Simulation uses a persistent DrapeTarget and exposes target status in the public task panel. The deterministic CPU solver remains the correctness reference.

## Development

There is one canonical GitHub Actions workflow: `.github/workflows/canonical-execution.yml`. It runs Python/core checks and real FreeCAD/Xvfb GUI coverage. The GUI path deliberately preserves four 1280×720 PNG states and the `cloth-gui-screenshots` artifact; do not replace or duplicate this path.

## Documentation

Start at [docs/README.md](docs/README.md). It links the compact user guide, architecture contract, roadmap, research summary and development/agent rules. `AGENT_STATUS.md` and `TOOL_STATE.md` remain the durable machine-readable coordination records.
