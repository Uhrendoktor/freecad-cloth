# FreeCAD Cloth

Open-source FreeCAD workbenches for parametric sewing-pattern design and 3D cloth draping/simulation.

- **Cloth Pattern** — parametric 2D pattern pieces, seam allowances, notches, grainlines and sewing metadata.
- **Cloth Sewing** — semantic seam operations, correspondence, fitting-scene preparation and validation.
- **Cloth Simulation** — meshing, target selection, body collision and cloth simulation.

## Python runtime

The project targets **Python 3.12 or newer**. This is the supported development, packaging, test, and canonical FreeCAD CI baseline. PositionBasedDynamics is an optional installation extra for the simulation workbench, and it is the sole runtime physics solver. PositionBasedDynamics's current upstream repository requires Python >=3.12.

For local FreeCAD development, use a FreeCAD build whose embedded Python runtime is 3.12 or newer. The canonical CI image uses FreeCAD 1.1.0 from conda-forge with Python 3.12; the upstream FreeCAD 1.1.3 AppImage still embeds Python 3.11, so it is not the supported PositionBasedDynamics-capable CI runtime.

## Workflow

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD/Sketcher owns editable geometry and document persistence; Cloth owns garment semantics; the solver owns physics. Simulation meshes and collision data are derived and rebuildable. A native human mannequin and generic FreeCAD Shape/PartDesign/Body/Mesh are interchangeable providers of the same target-neutral `DrapeTarget` contract.

## Installation and examples

Start with [Installation](docs/INSTALLATION.md), then run the [Blanket over Cube](docs/EXAMPLES.md) example before the full tunic acceptance path. The [Release gates](docs/RELEASE_GATES.md) define what “complete” means for this repository and explicitly separate implemented behavior from the commercial-feature roadmap.

## Agent orientation

Agent-specific instructions live in [AGENTS.md](AGENTS.md). It is intentionally separate from the human README and is a current, task-scoped contract. For live repository state, use `AGENT_STATUS.md` and `TOOL_STATE.md`; do not infer current state from old issue/PR history or release-closeout prose.

## Human visual validation

The README follows the same review order as the canonical simulation checks. Review the rendered media before reading logs or numerical diagnostics.

| Stage | Human visual check | Evidence |
| --- | --- | --- |
| Pattern | Native Sketcher geometry is clean, editable, and adopted as the cloth source. | Pattern screenshot |
| Sewing | Seam identity, direction, markers, and correspondence are unambiguous. | Sewing screenshot |
| Cube collision | Cloth falls onto the rigid target without visible clipping through it. | Blanket animation |
| Mannequin contact | Cloth stays outside the body and follows the torso with believable folds. | Mannequin animation |
| Final garment | Front/back panels remain coherent after sewing and draping. | Arranged + draped turntables |
| Diagnostics | Final state is inspectable from every side and with stress visualization. | Six views + stress map |

### 1. Pattern source

![Native Sketcher pattern](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png)

### 2. Sewing

![Sewing workbench](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png)

### 3. Basic collision — blanket over cube

![Blanket collision and drape](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif)

The key contact check is the absence of visible cloth penetration into the cube. The simulation ladder applies the same rule to progressively harder cases.

### 4. Mannequin collision — sewn tunic animation

![Sewn tunic draping over mannequin](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-tunic-mannequin-motion.gif)

Inspect shoulder and side contact, body clearance, hem behavior, seam continuity, and the way folds develop from the initial state to the settled state.

### 5. Final simulation — arranged and draped 360°

![Arranged garment turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif)

![Draped garment turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif)

### 6. Six-side and diagnostic review

<details>
<summary>Final mannequin views</summary>

| Front | Rear | Left | Right | Top | Bottom |
| --- | --- | --- | --- | --- | --- |
| ![](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png) | ![](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-rear.png) | ![](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-left.png) | ![](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-right.png) | ![](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-top.png) | ![](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-bottom.png) |

</details>

![Stress diagnostic map](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-diagnostics.png)

### Simulation ladder

The collision ladder increases complexity in controlled steps and stops at the first failing rung. It is a normal simulation gate, not an after-the-fact debugging exercise.

| Rung | Scenario | Visual purpose |
| ---: | --- | --- |
| 1 | One panel on cube, pinned | Establish basic motion and contact. |
| 2 | One panel on cube, unpinned | Verify unconstrained cube contact. |
| 3 | Two panels on cube, no seam | Isolate multi-piece collision. |
| 4 | Two panels on cube, small seam | Introduce mild sewing interaction. |
| 5 | Two panels on cube, large seam | Stress seam/contact coupling. |
| 6 | One panel on mannequin, pinned | Establish body collision. |
| 7 | One panel on mannequin, unpinned | Verify unconstrained body contact. |
| 8 | Two panels on mannequin, no seam | Isolate multi-piece body collision. |
| 9 | Two panels on mannequin, small seam | Introduce garment assembly. |
| 10 | Two panels on mannequin, large seam | Stress final seam/contact coupling. |

Each rung captures steps 0, 1, 5, 15, 45, and 90. Human review should stop at the first visually or numerically failing rung rather than averaging failures across later stages.

Human visual review checks:

- no visible penetration through the cube or mannequin;
- no exploding, collapsed, detached, or self-inverted cloth;
- authored pins and seams behave as expected;
- motion progresses smoothly without sudden topology changes;
- the settled silhouette and folds read as fabric rather than a rigid sheet.

### Avatar — 360° reference turntable

![Cloth Avatar 360° turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-turntable.gif)

## Module architecture

The implementation is organized exclusively as a Python package tree under `freecad_cloth/`, with domain ownership split across `pattern`, `sewing`, `avatar`, `simulation`, `common`, and `shared`. Repository-root Python files are limited to the FreeCAD bootstrap files `Init.py`/`InitGui.py` and the interpreter-level `sitecustomize.py` CI hook. Domain modules are never restored as root-level compatibility shims.

Internal imports use the canonical namespace, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`.

## Current implementation

The Pattern workbench creates native, recomputable PatternPieces with semantic IDs and pattern metadata. Sewing persists seam relationships and supports direction/correspondence operations. Simulation uses a persistent DrapeTarget and exposes target status in the public task panel. Fabric materials now persist presentation controls in addition to physical parameters. The deterministic ClothSystem is a lightweight reference for assembling particle and constraint inputs; PositionBasedDynamics is the runtime physics authority.

The repository does not claim full commercial garment-suite parity. Advanced capabilities remain tracked in the roadmap and must pass their own executable/visual acceptance gates before being described as complete.

## License

This project is licensed under the GNU Lesser General Public License v2.1 or later; see [LICENSE](LICENSE).

## Development

Simulation changes follow a screenshot-first human-review protocol documented in [docs/SIMULATION_REVIEW.md](docs/SIMULATION_REVIEW.md). The current coordination ledger is named in `AGENT_STATUS.md` and must be used as the live issue reference.

There is one canonical GitHub Actions workflow: `.github/workflows/canonical-execution.yml`. It runs Python/core checks, real FreeCAD/Xvfb GUI coverage, the basic blanket visual fixture, semantic seam/mesh sanity checks, 360° turntables and actual step-by-step simulation motion GIFs.

## Documentation

Start at [docs/README.md](docs/README.md). It links installation, examples, the user guide, release gates, architecture, roadmap, research and development guidance. GitHub issue/PR templates and automated dependency updates are part of the repository hygiene baseline. `AGENT_STATUS.md` and `TOOL_STATE.md` remain the durable machine-readable coordination records.
