# Sewing and draping workflow research

## CLO-style behavior analysis

CLO separates garment work into a 2D pattern workflow and a 3D fitting/simulation workflow. Its production model includes segment/free sewing, sewing direction, notches, arrangement points and bounding volumes, avatar measurement, particle distance, folds, topstitching, buttons/buttonholes and material/simulation properties. The important architectural lesson is that pattern geometry and sewing semantics are edited independently from the generated 3D simulation mesh. CLO's arrangement points place patterns relative to avatar bounding volumes, while particle distance trades simulation speed against garment quality. citeturn0search3turn0search5turn3search3turn3search8turn3search5turn3search14

### Workbench responsibilities and UI

**Cloth Pattern** is the 2D authoring workbench:
- New/Edit Pattern Piece
- Draft Pattern (sketch-like polygon editor)
- Native Sketcher mirror
- 2D view
- Seam Allowance
- Add Seam
- Add Notch / Grainline / Internal Mark
- Create Mesh

**Cloth Sewing** is the semantic assembly workbench:
- Create/Edit Sewing Operation
- Validate Seams
- Show 2D
- Create Fitting Scene
- Set Body Measurements
- Assign Avatar
- Add Pattern Pieces
- Create Simulation

**Cloth Simulation** is the 3D workbench:
- Generate/refresh simulation mesh
- Simulate / reset / step
- Pin selection
- Seam/stitch constraints
- Avatar collision proxy
- Material and particle-distance controls
- Drape/fit diagnostics

Interaction is deliberately one-way at the data boundaries: Pattern -> Sewing -> Simulation. A simulation mesh is disposable and must be regenerated from the pattern/seam model. FreeCAD `App::Property*`, `App.Placement`, Part/OCCT, MeshPart, Sketcher and document recompute/save mechanisms are used instead of custom persistence or a second geometry kernel.

### Canonical seam contract

`PatternModel.Seam` is authoritative for piece references, edge references, normalized seam ranges, reversal, alignment, stitch group and construction kind. FreeCAD seam objects and SewingOperation objects are document adapters. A SewingOperation derives length diagnostics and stitch correspondence from the linked seam; it does not own a second editable copy of alignment or reversal.

### CLO-to-FreeCAD mapping

| CLO behavior | Workbench implementation / next step |
| --- | --- |
| 2D pattern drafting | Cloth Pattern drafting panel + native Sketcher adapter |
| Seam allowance | Pattern property + derived Part/OCCT outline |
| Segment/free sewing | Canonical `Seam`; M:N selection remains a roadmap item |
| Sewing direction/reversal | Canonical seam `reversed_b`, one-time reversal during correspondence |
| Notches | Persisted semantic PatternMark objects |
| Grainline/internal marks | Persisted semantic PatternMark objects |
| Arrangement points | FittingScene + deterministic `App.Placement`; richer avatar points are next |
| Avatar measurements | BodyMeasurements/FittingScene |
| Collision/bounding volumes | Solver-neutral avatar collision proxy + humanoid fallback |
| Particle distance | Solver mesh density/performance control; UI exposure is next |
| Fold/pleat | Seam `kind` metadata + future 3D fold adapter |
| Topstitch/buttons | Pattern semantic marks/material adapters; not simulation-critical |
| Save/reload | Native FreeCAD document objects and smoke coverage |

### Prioritized next capabilities

1. M:N and free-sewing gestures.
2. Notch-aware seam alignment and diagnostics.
3. Rich avatar arrangement points and wrap direction.
4. Particle-distance presets and simulation quality controls.
5. Fold/pleat and topstitch visualization.
6. Print/CAD export (DXF/SVG/TechDraw) while preserving semantic IDs.

## Existing open-source references

| Project | Useful capability | Integration assessment |
| --- | --- | --- |
| Seamly2D | Measurement-driven reusable parametric patterns | Strong workflow reference; GPLv3+ prevents treating it as a core embedded dependency. |
| FreeSewing | MIT parametric pattern library and reusable blocks | Good interoperability/reference target; Node/JavaScript runtime is not a core FreeCAD dependency. |
| Tissu | Apache-2.0 C++ XPBD SDK; distance/bending/pin/stitch, mesh/self collision, spatial hash, Python API | Attractive optional backend; native toolchain/ABI breadth makes it unsuitable as a mandatory dependency. |
| PositionBasedDynamics | MIT PBD/XPBD library, collision and deformable constraints | Strong optional backend/reference; compiled Python bindings require ABI packaging work. |
| XPBD-Cloth | Stretch/shear/bend/self-collision reference | Useful algorithm benchmark. |
| Blender Cloth | Deformable cloth/pinning/collision/substeps | Useful external interoperability/reference target. |
| ARCSim | Adaptive cloth/thin-shell simulation | Valuable algorithm reference, not a core dependency. |

## Current architecture

The bundled deterministic CPU XPBD backend remains the reference implementation. `PatternModel` is authoritative; Sketcher, native OCCT geometry and MeshPart are adapters at the FreeCAD boundary. Stable semantic edge IDs are not inferred from generated OCCT/MeshPart ordering.

The solver has explicit stretch, shear and reduced-distance bending families plus deterministic particle self-collision. Future native backends remain optional behind the backend adapter.

## Native FreeCAD replacement strategy

- OCCT `makeOffset2D` is an optional document-boundary adapter.
- MeshPart triangulation is an adapter; semantic boundary provenance stays independent from generated face ordering.
- Sketcher mirrors the PatternPiece outline but does not become the semantic source of truth.
- `App.Placement` stores reproducible fitting arrangement.
- TechDraw/Draft and richer CAD export remain planned.

## Planned milestones

- [x] FreeCAD workbench skeleton and canonical CI.
- [x] Parametric pattern document model and semantic marks.
- [x] Sewing graph and solver backend adapter.
- [x] Interactive drafting GUI and GUI smoke coverage.
- [x] Initial seam allowance geometry.
- [x] Humanoid/body collision contract and fitting metadata.
- [x] Deterministic drape metrics/repeatability gates.
- [x] Native Sketcher adapter.
- [x] Explicit shear/bending and deterministic particle self-collision.
- [x] Canonical seam metadata for alignment/stitch grouping/construction kind.
- [x] Curved/native-edge arc-length sewing correspondence.
- [x] Sewing task-panel lifecycle and save/reload smoke coverage.
- [x] Pattern -> Sewing -> Simulation invalidation and integration audit.
- [ ] M:N/free sewing editor.
- [ ] Particle-distance/material UI presets.
- [ ] Avatar arrangement-point editor.
- [ ] OCCT offset parity and export regression suite.
- [ ] Optional Tissu/PositionBasedDynamics benchmark.
- [ ] Packaging, examples and release-quality documentation.

## Sources

- CLO Help Center: 2D/sewing, Notch, Particle Distance, Avatar Measurement, Arrangement Points, Fold and Topstitch documentation. https://support.clo3d.com/
- FreeCAD: https://github.com/FreeCAD/FreeCAD
- Seamly2D: https://github.com/FashionFreedom/Seamly2D
- FreeSewing: https://github.com/freesewing/freesewing
- Tissu: https://github.com/evanrock520-ciencias/Tissu
- PositionBasedDynamics: https://github.com/InteractiveComputerGraphics/PositionBasedDynamics
- XPBD-Cloth: https://github.com/steampower33/XPBD-Cloth
