# Sewing and draping workflow research

## CLO-style behavior analysis

CLO separates garment production into a 2D pattern workflow and a 3D fitting/simulation workflow. Current CLO documentation confirms that the important user-facing model is not simply “draw a polygon and simulate”: users establish segment/free sewing lines, control sewing direction with directional notches, support 1:N and M:N sewing, arrange patterns around avatar bounding volumes/arrangement points, and trade simulation quality against speed with particle distance. Avatar skin offset and collision/friction settings are separate physical controls.

### Workbench responsibilities

**Cloth Pattern — authoritative 2D authoring**
- Create/Edit Pattern Piece
- Native Sketcher editing and constraints
- Pattern dimensions/expressions
- Seam allowance
- Notch, grainline, internal mark, fold/dart metadata
- Mirror/transform/validation
- Preview/mesh-density preparation
- 2D inspection and production/export preparation

**Cloth Sewing — semantic assembly and fitting setup**
- Segment Sewing
- Free Sewing
- 1:N and M:N sewing
- Direction/reversal/alignment diagnostics
- Length mismatch/easing diagnostics
- Transactional seam editor
- 2D/3D paired seam visualization
- Arrangement points / reproducible placement
- Avatar/drape-target selection
- Create/refresh simulation scene

**Cloth Simulation — 3D physical workflow**
- Generate/refresh simulation mesh
- Particle-distance / quality presets
- Fabric density, thickness, stretch, shear, bend and friction
- Collision target, skin offset/thickness and tessellation
- Pinning and seam/stitch constraints
- Step / Run / Reset
- Explicit stale/invalid status and rebuild actions
- Fit/drape diagnostics

### UI action hierarchy

Use native FreeCAD task panels and standard property editors as the primary interaction surface. The custom action hierarchy should be:

**Pattern:** New Piece → Edit Sketch → Draft/Marks → Seam Allowance → Validate → Mesh.

**Sewing:** Segment/Free/M:N Sewing → Edit/Repair → Validate → Arrange → Drape Target → Create Simulation.

**Simulation:** Refresh Mesh/Target → Run (primary) → Step (secondary/debug) → Reset (separate state action). Status and stale reasons remain visible above lifecycle controls.

Icons are for frequent actions; labels/tooltips remain explicit. Numeric controls use FreeCAD units and expose the physical meaning of values. This follows the project UX issue #267 rather than adding decorative icons.

### CLO-to-FreeCAD mapping

| CLO behavior | FreeCAD Cloth design |
| --- | --- |
| 2D pattern drafting | Native `Sketcher::SketchObject` owned/referenced by PatternPiece |
| Parametric dimensions | Sketcher constraints + FreeCAD Expressions/Property system |
| Seam allowance | Pattern semantic property + OCCT/Part derived geometry |
| Segment/free sewing | Persistent Cloth seam objects and Sewing task panel |
| Sewing direction | Explicit reversal/alignment and correspondence metadata |
| M:N sewing | SewingGroup/operation model with transactional editing |
| Directional notches | Semantic marks plus seam correspondence diagnostics |
| Arrangement points | Persistent fitting arrangement objects and `App.Placement`; future avatar-bound points |
| Avatar measurements | Parametric FreeCAD mannequin properties/landmarks |
| Arbitrary collision target | Persistent target-neutral `DrapeTarget` linking any supported Shape/Mesh |
| Particle distance | Simulation mesh density/quality property and presets |
| Skin/collision offset | Target/Simulation collision thickness and skin offset properties |
| Save/reload | Native document Links/Properties + FreeCAD recompute and E2E smoke |

FreeCAD Sketcher already provides geometric/dimensional constraints, expressions and scripting APIs, so a second constraint kernel is not justified. The official documentation also recommends using native constraints and expressions for parametric CAD data.

### Revised release priorities

1. **Target-authoritative simulation lifecycle:** stale target is safe during recompute, visible in status, and blocks Step/Run until Refresh.
2. **Canonical public-workbench E2E:** native Pattern → Sewing → Simulation, save/reload, upstream edit, invalidation, refresh and successful re-simulation.
3. **Curved/M:N sewing UX:** complete repairable correspondence and transactional editing in the task panel.
4. **Pattern production minimum:** stable semantic references, native Sketcher authority, marks, seam allowances, validation and export-safe IDs.
5. **Fitting UX:** avatar arrangement points, target selection and reproducible 3D placements.
6. **Simulation quality:** particle-distance presets, fabric/collision controls and diagnostics.
7. **Export/package/release documentation.**
8. **Optional solver benchmarks only after release gates are green.**

### Existing open-source references

| Project | Useful capability | Integration assessment |
| --- | --- | --- |
| Seamly2D | Measurement-driven reusable parametric patterns | Strong workflow reference; GPLv3+ prevents treating it as a core embedded dependency. |
| FreeSewing | MIT parametric pattern library and reusable blocks | Good interoperability/reference target; Node/JavaScript runtime is not a core FreeCAD dependency. |
| Tissu | Apache-2.0 C++ XPBD SDK; distance/bending/pin/stitch, mesh/self collision | Attractive optional backend; native toolchain/ABI breadth makes it unsuitable as a mandatory dependency. |
| PositionBasedDynamics | MIT PBD/XPBD library, collision and deformable constraints | Strong optional backend/reference; compiled Python bindings require ABI packaging work. |
| XPBD-Cloth | Stretch/shear/bend/self-collision reference | Useful algorithm benchmark. |
| Blender Cloth | Deformable cloth/pinning/collision/substeps | Useful external interoperability/reference target. |
| ARCSim | Adaptive cloth/thin-shell simulation | Valuable algorithm reference, not a core dependency. |

### Current architecture

The bundled deterministic CPU XPBD backend remains the reference implementation. `PatternModel` is authoritative; Sketcher, native OCCT geometry and MeshPart are adapters at the FreeCAD boundary. Stable semantic edge IDs are not inferred from generated OCCT/MeshPart ordering.

The solver has explicit stretch, shear and reduced-distance bending families plus deterministic particle self-collision. Future native backends remain optional behind the backend adapter.

### Native FreeCAD replacement strategy

- Sketcher owns parametric geometry and constraint solving.
- FreeCAD Expressions bind garment measurements and dimensions without another expression engine.
- OCCT/Part supplies offsets, intersections and derived geometry.
- MeshPart/FreeCAD Mesh supplies triangulation/visualization adapters.
- `App::PropertyLink`, Groups and `App.Placement` persist semantic relationships and fitting arrangement.
- TechDraw/Draft remain the preferred future production-output path.

### Planned milestones

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
- [ ] Safe stale-DrapeTarget lifecycle and canonical target-authority E2E.
- [ ] Public curved/M:N sewing repair acceptance.
- [ ] Canonical multi-piece garment release fixture.
- [ ] Particle-distance/material/collision quality presets.
- [ ] Avatar arrangement-point editor.
- [ ] OCCT offset parity and export regression suite.
- [ ] Packaging, examples and release-quality documentation.
- [ ] Optional Tissu/PositionBasedDynamics benchmark.

## Sources

- CLO Help Center: Segment Sewing, Free Sewing, M:N Free Sewing, 1:N Sewing, Check Sewing Length, Particle Distance, Avatar Properties, Arrangement Points, Hi/Low-Resolution Garment.
  - https://support.clo3d.com/hc/en-us/articles/115012381248--3D-Tool-Segment-Sewing
  - https://support.clo3d.com/hc/en-us/articles/360001754628--3D-Tool-Free-Sewing
  - https://support.clo3d.com/hc/en-us/articles/360001754668--3D-Tool-M-N-Free-Sewing
  - https://support.clo3d.com/hc/en-us/articles/360001771407--3D-Tool-1-N-Segment-Sewing
  - https://support.clo3d.com/hc/en-us/articles/115000495467--2D-Tool-Check-Sewing-Length
  - https://support.clo3d.com/hc/en-us/articles/115000414447-Particle-Distance-Setting
  - https://support.clo3d.com/hc/en-us/articles/115002227327-Avatar-Properties
  - https://support.clo3d.com/hc/en-us/articles/115000430768-Add-Arrangement-Point
  - https://support.clo3d.com/hc/en-us/articles/115000430668-Hi-Low-Resolution-Garment
- FreeCAD Sketcher documentation and scripting examples.
  - https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Sketcher_Workbench.md
  - https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Sketcher_scripting.md
  - https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Expressions.md
- FreeCAD: https://github.com/FreeCAD/FreeCAD
- Seamly2D: https://github.com/FashionFreedom/Seamly2D
- FreeSewing: https://github.com/freesewing/freesewing
- Tissu: https://github.com/evanrock520-ciencias/Tissu
- PositionBasedDynamics: https://github.com/InteractiveComputerGraphics/PositionBasedDynamics
- XPBD-Cloth: https://github.com/steampower33/XPBD-Cloth
