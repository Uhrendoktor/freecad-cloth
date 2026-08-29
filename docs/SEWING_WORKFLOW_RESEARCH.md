# Sewing and draping workflow research

## Reference behavior: CLO-style production loop

CLO's workflow is split between a 2D pattern window and a 3D garment window. The 2D view is used to design patterns and sewing lines; sewing operations are visible in both views. Segment Sewing and Free Sewing support one-to-one and M:N relationships, with directional orientation controlling whether a pattern is reversed during simulation. CLO also exposes notches, internal lines, folds, topstitching, buttons/buttonholes, material properties, particle distance, avatar measurements, arrangement points and collision/bounding volumes. citeturn0search1turn0search6turn0search9turn3search5turn3search8turn3search3

The open-source workbench intentionally adopts the **behavioral model**, not CLO's proprietary file formats or implementation. The core invariant is:

`Parametric pattern -> semantic seam graph -> regenerated simulation mesh -> avatar collision/drape`

### Feature matrix

| Capability | Cloth Pattern | Cloth Sewing / Fitting | Cloth Simulation | FreeCAD reuse |
| --- | --- | --- | --- | --- |
| Parametric dimensions | Width/height, expressions/properties | Reads pattern parameters | Regenerates mesh | `App::PropertyLength`, expressions |
| 2D drafting | Polygon drafting task panel + native Sketcher mirror | 2D seam display | — | Sketcher, Part/OCCT |
| Seam allowance | Pattern property + derived outline | Validation uses sewing boundary | Mesh uses sewing outline | Part geometry / optional OCCT offset |
| Notches / grainline / internal marks | Persisted semantic marks | — | — | FeaturePython properties |
| Segment sewing | Canonical `Seam` + operation | Create/edit/validate | Stitch constraints | FreeCAD links + semantic graph |
| Free sewing / M:N | Planned extension of seam selection | Planned extension | Backend accepts multiple stitch pairs | Same seam contract |
| Reversal / alignment | Canonical seam metadata | Read-only derived operation fields | Same reversal drives stitch pairs | `App::PropertyEnumeration/Bool` |
| Stitch sampling | — | User-controlled sample count | Same correspondence becomes constraints | Mesh boundary + solver adapter |
| Avatar association | — | Measurements, placement, avatar proxy | Mesh collision | FreeCAD `Part`/`Mesh` |
| Arrangement points | — | Fitting scene placement | Initial positions | `App.Placement` |
| Cloth material | — | Fitting metadata | Solver material properties | Property system |
| Particle distance | — | — | Simulation quality/performance | Solver mesh density |
| Fold / pleat / topstitch | Semantic marks/roadmap | Seam `kind` supports fold/pleat metadata | Solver hook/roadmap | Sketcher/Part-derived geometry |
| Save/reload | Native document objects | SewingOperation persisted and smoke-tested | Simulation scene persisted | FreeCAD document serialization |

### Workbench UI and interaction contract

**Cloth Pattern** toolbar/menu should contain:

1. **New Pattern Piece** — opens the parameter task panel.
2. **Edit Pattern Piece** — edits dimensions, seam allowance and grainline.
3. **Draft Pattern** — opens the sketch-like polygon editor.
4. **Create Sketch** — creates the native Sketcher adapter.
5. **2D View** — top view + fit all.
6. **Create Mesh** — generates a solver-ready mesh without replacing the pattern source.
7. **Add Seam** — uses two selected edges or a safe default and creates canonical seam metadata.
8. **Add Notch / Grainline / Internal Mark** — creates persistent semantic marks.

**Cloth Sewing** toolbar/menu should contain:

1. **Create Sewing Operation** — converts a canonical seam into a document-facing operation.
2. **Edit Sewing Operation** — opens the FreeCAD task panel.
3. **Validate Seams** — recomputes all operations and reports length mismatches.
4. **Show 2D** — focuses the flat pattern view.
5. **Create Fitting Scene** — creates measurement/avatar/placement metadata.
6. **Set Measurements** — persists deterministic body measurements.
7. **Assign Avatar** — links a selected FreeCAD body/mesh to the collision proxy.
8. **Add Pattern Pieces** — records selected pieces and their placements.
9. **Create Simulation** — hands the selected fitting scene to Cloth Simulation.

**Cloth Simulation** owns solver controls and must never become the source of truth for pattern geometry. Its scene receives pattern pieces, seam-derived stitch pairs, pins, material parameters and an optional avatar collision surface.

### Interaction rules

- Selecting a pattern edge and pressing **Add Seam** creates one canonical `PatternModel.Seam` record and a derived FreeCAD display object.
- **Create Sewing Operation** links to that seam object rather than copying orientation/alignment into independent mutable state.
- Editing a seam recomputes the operation; the operation exposes derived `LengthA`, `LengthB`, `LengthDifference`, `StitchCount` and correspondence points.
- Reversal is applied exactly once when generating correspondence: sample both ranges first, then reverse B.
- The same correspondence is used for display diagnostics and simulation stitch constraints.
- Fitting placement is persisted with `App.Placement`; simulation consumes the selected pattern objects directly.
- Save/reload reconstructs document objects and recomputes derived sewing state.

### CLO-specific behaviors worth prioritizing next

1. M:N sewing and free sewing selection gestures. CLO explicitly supports Segment Sewing, Free Sewing, M:N Segment Sewing and M:N Free Sewing. citeturn0search3turn0search5
2. Notch-driven seam alignment and notch-aware sewing diagnostics. citeturn0search0turn3search5
3. Arrangement points/bounding volumes around the avatar, including symmetric placement and wrap direction. citeturn3search3turn3search11
4. Simulation quality controls analogous to particle distance. Lower particle distance increases garment quality at a computational cost. citeturn3search8
5. Fold/pleat metadata, topstitch visualization, and material presets. citeturn3search14turn3search15turn3search17
6. Avatar measurement tooling and editable measurement records. citeturn3search1turn3search4

## Existing open-source references

| Project | Useful capability | Integration assessment |
| --- | --- | --- |
| Seamly2D | Measurement-driven reusable parametric patterns | Strong workflow reference; GPLv3+ prevents treating it as a core embedded dependency. |
| FreeSewing | MIT parametric pattern library and reusable blocks | Good interoperability/reference target; Node/JavaScript runtime is not a core FreeCAD dependency. |
| Tissu | Apache-2.0 C++ XPBD SDK; distance/bending/pin/stitch, mesh/self collision, spatial hash, Python API | Attractive optional backend. Current README requires Python >=3.12 plus C++17/CMake/OpenMP and pybind11, so ABI/toolchain breadth makes mandatory integration inappropriate. |
| PositionBasedDynamics | MIT PBD/XPBD library, Python bindings, collision and deformable constraints | Strong optional/reference backend. Native CMake/Eigen/pybind build and Python extension ABI require packaging work; keep optional. |
| XPBD-Cloth | Stretch, shear, bend, area and self-collision reference | Useful algorithm benchmark; not the portable first backend. |
| Blender Cloth Dynamics | XPBD-style stretch/bend/pinning/collision/substeps | Useful interoperability and validation reference; Blender remains external. |
| ARCSim | Adaptive cloth/thin-shell simulation | Valuable historical algorithm reference, not a core dependency. |

## Current architecture

The bundled deterministic CPU XPBD backend remains the reference implementation. `PatternModel` is authoritative; Sketcher, native OCCT geometry and MeshPart are adapters at the FreeCAD boundary. Stable semantic edge IDs are never inferred from generated OCCT/MeshPart ordering.

The garment solver now has explicit stretch, shear and reduced-distance bending constraint families plus deterministic particle self-collision. These solver-level quality gates remain behind the backend boundary.

## Native FreeCAD replacement strategy

- OCCT `makeOffset2D` is exposed through `PatternOCCT.py` as an optional document-boundary adapter.
- MeshPart triangulation is exposed through `PatternMeshFreeCAD.py`; semantic boundary provenance remains independent from generated face ordering.
- Sketcher is exposed through `PatternSketch.py`; it mirrors the PatternPiece outline but does not become the semantic source of truth.
- `App.Placement`, TechDraw/Draft and richer export adapters remain tracked separately.

## Backend audit — 2026-08-28

### Tissu

Tissu currently advertises distance, bending, volume, pin and stitch constraints; spatial-hash broad phase; sphere/capsule/plane and mesh colliders; kinematic colliders; self-collision; gravity and aerodynamic force. Its build requires CMake >=3.20, C++17, OpenMP and Python >=3.12 with pybind11-based packaging. Linux, macOS and Windows are listed as supported. License: Apache-2.0.

Decision: **optional only**.

### PositionBasedDynamics

PositionBasedDynamics is MIT licensed and provides XPBD distance/isometric-bending/volume constraints, point-edge/point-triangle/edge-edge collision constraints, deformable-body support, signed-distance-field collision and substepping.

Decision: **optional only**.

## Planned milestones

- [x] FreeCAD workbench skeleton and canonical CI.
- [x] Parametric pattern document model and semantic marks.
- [x] Sewing graph and solver backend adapter.
- [x] Interactive drafting GUI and GUI smoke coverage.
- [x] Initial seam allowance geometry.
- [x] Humanoid/body collision contract and fitting metadata.
- [x] Deterministic drape metrics/repeatability gates.
- [x] Initial native Sketcher adapter.
- [x] Explicit shear/bending and deterministic particle self-collision implementation.
- [x] Canonical semantic seam contract with compatibility adapters.
- [x] Arc-length seam correspondence and curved-edge document adapter.
- [x] Sewing task-panel lifecycle and save/reload smoke coverage.
- [x] Pattern -> Sewing -> Simulation data-flow validation.
- [ ] M:N sewing / free sewing gesture editor.
- [ ] OCCT offset parity/regression decision.
- [ ] MeshPart/Netgen provenance/quality decision.
- [ ] Optional Tissu/PositionBasedDynamics adapter benchmark.
- [ ] Packaging, examples and release-quality documentation.

## Sources

- CLO Help Center: 2D Window, Segment Sewing, Free Sewing, Arrangement Points, Particle Distance, Notch, Avatar Measure and Topstitch documentation. citeturn0search1turn0search6turn0search11turn3search3turn3search8turn3search5turn3search1turn3search15
- FreeCAD Sketcher documentation: constraints, snapping, construction geometry and parametric sketch behavior. citeturn2search0
- Seamly2D: https://github.com/FashionFreedom/Seamly2D
- FreeSewing: https://github.com/freesewing/freesewing
- Tissu: https://github.com/evanrock520-ciencias/Tissu
- PositionBasedDynamics: https://github.com/InteractiveComputerGraphics/PositionBasedDynamics
- XPBD-Cloth: https://github.com/steampower33/XPBD-Cloth
