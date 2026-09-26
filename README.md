# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Sewing** — semantic seam operations, correspondence, fitting-scene preparation and validation.
- **Cloth Simulation** — meshing, target selection, body collision and cloth simulation.

## Python runtime

The project targets **Python 3.12 or newer**. This is the supported development, packaging, test, and canonical FreeCAD CI baseline and keeps the optional Tissu backend on a compatible interpreter. Tissu's current upstream repository requires Python >=3.12.

For local FreeCAD development, use a FreeCAD build whose embedded Python runtime is 3.12 or newer. The canonical CI image uses FreeCAD 1.1.0 from conda-forge with Python 3.12; the upstream FreeCAD 1.1.3 AppImage still embeds Python 3.11, so it is not the supported Tissu-capable CI runtime.

## Workflow

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD/Sketcher owns editable geometry and document persistence; Cloth owns garment semantics; the solver owns physics. Simulation meshes and collision data are derived and rebuildable. A native human mannequin and generic FreeCAD Shape/PartDesign/Body/Mesh are interchangeable providers of the same target-neutral `DrapeTarget` contract.

## Installation and examples

Start with the human-first [Getting started](docs/GETTING_STARTED.md), then use [Installation](docs/INSTALLATION.md) for environment details and [Examples](docs/EXAMPLES.md) for the executable blanket and tunic paths. The [Release gates](docs/RELEASE_GATES.md) define what “complete” means for this repository and explicitly separate implemented behavior from the commercial-feature roadmap.

## Screenshots and simulation media

The canonical FreeCAD/Xvfb workflow publishes validated GUI states to a stable `docs/screenshots` branch. The basic example proves real cloth motion; the advanced tunic example is published from the authoritative tunic visual audit.

### Pattern design

The Pattern workbench is documented in [Examples](docs/EXAMPLES.md) and covered by the native-Sketcher and production-export acceptance jobs.

### Sewing

The Sewing workbench is documented in [Examples](docs/EXAMPLES.md) and covered by staged creation, correspondence, validation, persistence, and world-space seam checks.

### Basic example — blanket over cube

![Blanket over cube motion](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif)

### Advanced example — tunic

![Advanced tunic validation](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png)

### Simulation — arranged and draped 360° turntables

![Arranged cloth turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif)

![Draped cloth turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif)

### Avatar — 360° turntable

![Cloth Avatar 360° turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-turntable.gif)

## Module architecture

The implementation is organized exclusively as a Python package tree under `freecad_cloth/`, with domain ownership split across `pattern`, `sewing`, `avatar`, `simulation`, `common`, and `shared`. Repository-root Python files are limited to the FreeCAD bootstrap files `Init.py`/`InitGui.py` and the interpreter-level `sitecustomize.py` CI hook. Domain modules are never restored as root-level compatibility shims.

Internal imports use the canonical namespace, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`.

## Current implementation

The Pattern workbench creates native, recomputable PatternPieces with semantic IDs and pattern metadata. Sewing persists seam relationships and supports direction/correspondence operations. Simulation uses a persistent DrapeTarget and exposes target status in the public task panel. Fabric materials now persist presentation controls in addition to physical parameters. The deterministic CPU solver remains the correctness reference.

The repository does not claim full commercial garment-suite parity. Advanced capabilities remain tracked in the roadmap and must pass their own executable/visual acceptance gates before being described as complete.

## License

This project is licensed under the GNU Lesser General Public License v2.1 or later; see [LICENSE](LICENSE).

## Development

There is one canonical GitHub Actions workflow: `.github/workflows/canonical-execution.yml`. It runs Python/core checks, real FreeCAD/Xvfb GUI coverage, the basic blanket visual fixture, semantic seam/mesh sanity checks, 360° turntables and actual step-by-step simulation motion GIFs.

## Documentation

Start at [docs/README.md](docs/README.md). It links installation, examples, the user guide, release gates, architecture, roadmap, research and development guidance. GitHub issue/PR templates and automated dependency updates are part of the repository hygiene baseline. `AGENT_STATUS.md` and `TOOL_STATE.md` remain the durable machine-readable coordination records.
