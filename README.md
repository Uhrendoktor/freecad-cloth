# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Sewing** — semantic seam operations, correspondence, fitting-scene preparation and validation.
- **Cloth Simulation** — meshing, target selection, body collision and cloth simulation.

## Python runtime

The project targets **Python 3.12 or newer**. This is the supported development, packaging, test, and canonical FreeCAD CI baseline and keeps the optional Tissu backend on a compatible interpreter. Tissu's current upstream repository requires Python >=3.12.

For local FreeCAD development, use a FreeCAD build whose embedded Python runtime is 3.12 or newer. The canonical CI image uses FreeCAD 1.1.0 from conda-forge with Python 3.12.

## Workflow

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD/Sketcher owns editable geometry and document persistence; Cloth owns garment semantics; the solver owns physics. Simulation meshes and collision data are derived and rebuildable. A native human mannequin and generic FreeCAD Shape/PartDesign/Body/Mesh are interchangeable providers of the same target-neutral `DrapeTarget` contract.

## Screenshots

The canonical FreeCAD/Xvfb workflow publishes the latest four validated 1280×720 GUI states to a stable `docs/screenshots` branch. They are refreshed on every successful `main` run.

### Pattern design

![Cloth Pattern](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png)

### Sewing

![Cloth Sewing](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png)

### Simulation arranged

![Cloth Simulation arranged](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png)

### Simulation draped

![Cloth Simulation draped](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png)

## Module architecture

The implementation is organized exclusively as a Python package tree under `freecad_cloth/`, with domain ownership split across `pattern`, `sewing`, `avatar`, `simulation`, `common`, and `shared`. Repository-root Python files are limited to the FreeCAD bootstrap files `Init.py`/`InitGui.py` and the interpreter-level `sitecustomize.py` CI hook. Domain modules are never restored as root-level compatibility shims.

Internal imports use the canonical namespace, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`.

## Current implementation

The Pattern workbench creates native, recomputable PatternPieces with semantic IDs and pattern metadata. Sewing persists seam relationships and supports direction/correspondence operations. Simulation uses a persistent DrapeTarget and exposes target status in the public task panel. The deterministic CPU solver remains the correctness reference.

## Development

There is one canonical GitHub Actions workflow: `.github/workflows/canonical-execution.yml`. It runs Python/core checks and real FreeCAD/Xvfb GUI coverage under the project-wide Python 3.12 baseline. The GUI path deliberately preserves the existing four 1280×720 PNG states and the `cloth-gui-screenshots` artifact; avatar GUI coverage is additionally validated in CI.

## Documentation

Start at [docs/README.md](docs/README.md). It links the compact user guide, architecture contract, roadmap, research summary and development/agent rules. `AGENT_STATUS.md` and `TOOL_STATE.md` remain the durable machine-readable coordination records.
