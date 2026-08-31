# Sewing and draping workflow research

## CLO-style behavior analysis

CLO separates garment work into a 2D pattern workflow and a 3D fitting/simulation workflow. Its production model includes segment/free sewing, sewing direction, notches, arrangement points and bounding volumes, avatar measurement, particle distance, folds, topstitching, buttons/buttonholes and material/simulation properties. The important architectural lesson is that pattern geometry and sewing semantics are edited independently from the generated 3D simulation mesh. CLO's arrangement points place patterns relative to avatar bounding volumes, while particle distance trades simulation speed against garment quality.

### Additional interaction findings

Recent CLO/Marvelous Designer documentation reinforces several UX contracts that should be treated as architectural requirements rather than cosmetic features:

- **M:N sewing is a staged operation.** Select the M side, commit it, select the N side, then commit. Invalid segments are visibly rejected; `Delete` cancels the last staged action and `Esc` cancels the complete staged operation. The FreeCAD Sewing task panel should preserve this transactional behavior instead of mutating persistent seams on every click.
- **Sewing direction must be visible in both 2D and 3D.** Directional notches and temporary highlighted sewing lines provide immediate correspondence feedback. The Cloth equivalent should make reversal, mismatch and staged selections inspectable before commit.
- **Arrangement is a first-class fitting workflow.** Arrangement points are associated with avatar/bounding-volume regions, can have offsets and wrap direction, and support preview before placement. Persistent arrangement metadata should therefore be separate from the transient 3D placement transform.
- **Reset is part of the normal workflow.** A fitting workbench needs both “Reset 2D Arrangement” and “Reset 3D Arrangement” semantics so a user can recover from a bad arrangement/simulation without reconstructing the garment.
- **Superimpose is a construction operation.** Facings, linings, cuffs and collars often need to be placed directly over/under an already draped piece. This belongs in Arrangement/Fitting as a deterministic placement operation, not in the solver.
- **Toolbars should be task-oriented and configurable.** Modern Marvelous Designer allows tool grouping/reordering and saving toolsets. FreeCAD should not copy that UI wholesale, but Cloth should keep a small stable default toolbar and use task-panel sections for less frequent commands.

These observations are supported by the official CLO and Marvelous Designer documentation: M:N sewing and staged cancellation, 1:N sewing, arrangement points/wrap direction, reset arrangement, superimpose, and configurable tool groups.

## Workbench responsibilities and UI

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
- Assign Avatar / Collision Target
- Add Pattern Pieces
- Create Simulation

**Cloth Simulation** is the 3D workbench:
- Generate/refresh simulation mesh
- Simulate / reset / step
- Pin selection
- Seam/stitch constraints
- Target-neutral collision object
- Material and particle-distance controls
- Drape/fit diagnostics

### Common UI shell

All three workbenches should use the same interaction hierarchy:

1. **Context:** selected garment/piece/target and current validity state.
2. **Primary action:** the next action needed to advance the workflow.
3. **Secondary tools:** reversible edits and inspection.
4. **Quality/material/settings:** persistent parameters, grouped and unit-aware.
5. **Recovery:** Reset/Refresh/Repair actions with explicit stale-state reasons.

Task panels should remain short enough to understand without scrolling through unrelated controls. The Property Editor remains the authoritative inspection surface for persistent values and links. Icons are reserved for actions; values, choices and dialog lifecycle use native FreeCAD controls.

Interaction is deliberately one-way at the data boundaries: Pattern -> Sewing -> Simulation. A simulation mesh is disposable and must be regenerated from the pattern/seam model. FreeCAD `App::Property*`, `App.Placement`, Part/OCCT, MeshPart, Sketcher and document recompute/save mechanisms are used instead of custom persistence or a second geometry kernel.

## Canonical seam contract

`PatternModel.Seam` is authoritative for piece references, edge references, normalized seam ranges, reversal, alignment, stitch group and construction kind. FreeCAD seam objects and SewingOperation objects are document adapters. A SewingOperation derives length diagnostics and stitch correspondence from the linked seam; it does not own a second editable copy of alignment or reversal.

## CLO-to-FreeCAD mapping

| CLO/MD behavior | Workbench implementation / next step |
| --- | --- |
| 2D pattern drafting | Cloth Pattern drafting panel + native Sketcher adapter |
| Seam allowance | Pattern property + derived Part/OCCT outline |
| Segment/free sewing | Canonical `Seam`; M:N selection remains a roadmap item |
| 1:N / M:N sewing | Transactional staged Sewing UI with explicit commit/cancel |
| Sewing direction/reversal | Canonical seam `reversed_b`, one-time reversal during correspondence |
| Notches | Persisted semantic PatternMark objects |
| Grainline/internal marks | Persisted semantic PatternMark objects |
| Arrangement points | FittingScene + deterministic `App.Placement`; richer avatar points are next |
| Wrap direction / arrangement preview | Persistent arrangement metadata + preview placement |
| Reset 2D/3D arrangement | Explicit reversible fitting commands |
| Superimpose | Deterministic over/under/side placement for sewn pieces |
| Avatar measurements | BodyMeasurements/FittingScene |
| Collision/bounding volumes | Solver-neutral avatar collision proxy + humanoid fallback |
| Arbitrary FreeCAD target | Target-neutral `DrapeTarget` provider |
| Particle distance | Solver mesh density/performance control; UI exposure is next |
| Fold/pleat | Seam `kind` metadata + future 3D fold adapter |
| Topstitch/buttons | Pattern semantic marks/material adapters; not simulation-critical |
| Save/reload | Native FreeCAD document objects and smoke coverage |

## Feature taxonomy

### Prototype — prove contracts

- Native Sketcher-backed PatternPiece.
- Persistent semantic Seam and PatternMark objects.
- Segment/free sewing with explicit direction and transactional cancellation.
- Early 1:N/M:N representation.
- Persistent DrapeTarget with mannequin and generic FreeCAD Shape/Mesh providers.
- Deterministic arrangement and reset.
- Preview mesh and deterministic CPU reference simulation.
- Save/reload and explicit stale-state diagnostics.

### MVP — make the workflow useful

- Complete 1:N/M:N/free sewing UX with length-aware correspondence and repair.
- Arrangement points, wrap direction, preview placement, superimpose and reset operations.
- Parametric mannequin measurements and basic pose presets.
- Generic FreeCAD-object draping with persistent target quality settings.
- Particle-distance and fabric presets.
- Pinning and reproducible run/step/reset controls.
- Pattern production basics: seam allowance validation, notches, grading and DXF/SVG/TechDraw-oriented export.

### Production — broaden construction and manufacturing

- Higher-fidelity replaceable human body provider while retaining the Cloth avatar API.
- Multiple collision targets and optional face/subelement selection.
- Stress/strain/fit/pressure maps and measurement reports.
- Multi-size grading review, nesting, plotting and manufacturing validation.
- Pleats/folds, topstitch visualization, buttons/buttonholes/tacks, linings/facings and modular garment blocks.
- Optional solver backends only after the deterministic CPU reference path is release-stable.

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
- [ ] P0 simulation-ready tessellation/quality integration.
- [ ] M:N/free sewing editor.
- [ ] Particle-distance/material UI presets.
- [ ] Avatar arrangement-point editor.
- [ ] Generic DrapeTarget production path.
- [ ] OCCT offset parity and export regression suite.
- [ ] Optional Tissu/PositionBasedDynamics benchmark.
- [ ] Packaging, examples and release-quality documentation.

## Sources

- CLO Help Center: https://support.clo3d.com/
- Marvelous Designer Help Center: https://support.marvelousdesigner.com/
- FreeCAD: https://github.com/FreeCAD/FreeCAD
- Seamly2D: https://github.com/FashionFreedom/Seamly2D
- FreeSewing: https://github.com/freesewing/freesewing
- Tissu: https://github.com/evanrock520-ciencias/Tissu
- PositionBasedDynamics: https://github.com/InteractiveComputerGraphics/PositionBasedDynamics
- XPBD-Cloth: https://github.com/steampower33/XPBD-Cloth
