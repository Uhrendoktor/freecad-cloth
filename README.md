# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Sewing** — semantic seam operations, correspondence, fitting-scene preparation and validation.
- **Cloth Simulation** — meshing, target selection, body collision and cloth simulation.

## Workflow

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD/Sketcher owns editable geometry and document persistence; Cloth owns garment semantics; the solver owns physics. Simulation meshes and collision data are derived and rebuildable. A native human mannequin and generic FreeCAD Shape/PartDesign/Body/Mesh are interchangeable providers of the same target-neutral `DrapeTarget` contract.

## Screenshots

The canonical FreeCAD/Xvfb workflow publishes the validated GUI states to a stable `docs/screenshots` branch. The avatar audit additionally captures the production mannequin from every orthographic direction so the shoulder joints and overall body silhouette can be checked visually. The avatar images below are pinned to the post-#516 screenshot publication so the README renders the corrected mannequin rather than a stale branch revision.

### Pattern design

![Cloth Pattern](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png)

### Sewing

![Cloth Sewing](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png)

### Simulation arranged

![Cloth Simulation arranged](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png)

### Simulation draped

![Cloth Simulation draped](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png)

### Avatar — front

![Cloth Avatar front](https://github.com/Uhrendoktor/freecad-cloth/raw/ddfe4cac1202bf7acc341c1f5044c42b2eed8aae/docs/images/generated/cloth-avatar-front.png)

### Avatar — rear

![Cloth Avatar rear](https://github.com/Uhrendoktor/freecad-cloth/raw/ddfe4cac1202bf7acc341c1f5044c42b2eed8aae/docs/images/generated/cloth-avatar-rear.png)

### Avatar — left

![Cloth Avatar left](https://github.com/Uhrendoktor/freecad-cloth/raw/ddfe4cac1202bf7acc341c1f5044c42b2eed8aae/docs/images/generated/cloth-avatar-left.png)

### Avatar — right

![Cloth Avatar right](https://github.com/Uhrendoktor/freecad-cloth/raw/ddfe4cac1202bf7acc341c1f5044c42b2eed8aae/docs/images/generated/cloth-avatar-right.png)

### Avatar — top

![Cloth Avatar top](https://github.com/Uhrendoktor/freecad-cloth/raw/ddfe4cac1202bf7acc341c1f5044c42b2eed8aae/docs/images/generated/cloth-avatar-top.png)

### Avatar — bottom

![Cloth Avatar bottom](https://github.com/Uhrendoktor/freecad-cloth/raw/ddfe4cac1202bf7acc341c1f5044c42b2eed8aae/docs/images/generated/cloth-avatar-bottom.png)

## Module architecture

The implementation is organized exclusively as a Python package tree under `freecad_cloth/`, with domain ownership split across `pattern`, `sewing`, `avatar`, `simulation`, `common`, and `shared`. Repository-root Python files are limited to the FreeCAD bootstrap files `Init.py`/`InitGui.py` and the interpreter-level `sitecustomize.py` CI hook. Domain modules are never restored as root-level compatibility shims.

Internal imports use the canonical namespace, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`.

## Current implementation

The Pattern workbench creates native, recomputable PatternPieces with semantic IDs and pattern metadata. Sewing persists seam relationships and supports direction/correspondence operations. Simulation uses a persistent DrapeTarget and exposes target status in the public task panel. The deterministic CPU solver remains the correctness reference.

## Development

There is one canonical GitHub Actions workflow: `.github/workflows/canonical-execution.yml`. It runs Python/core checks and real FreeCAD/Xvfb GUI coverage. The GUI path preserves the existing workflow screenshots plus a six-direction avatar audit and the `cloth-gui-screenshots` artifact.

## Documentation

Start at [docs/README.md](docs/README.md). It links the compact user guide, architecture contract, roadmap, research summary and development/agent rules. `AGENT_STATUS.md` and `TOOL_STATE.md` remain the durable machine-readable coordination records.
