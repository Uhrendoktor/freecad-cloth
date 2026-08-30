# FreeCAD Cloth Roadmap — 2026 Supervisor Replan v2

## Decision

The roadmap is being reworked again because the project has moved from capability accumulation to release integration. M:N/free sewing, fitting arrangement, semantic export metadata, native workbench registration, deterministic CPU simulation, and a simulation-quality contract now exist. The remaining risk is no longer “missing feature count”; it is whether the three native workbenches form one reliable, manufacturable workflow.

The release criterion is therefore a **vertical slice**, not a checklist:

`Author curved parametric pieces -> mark/grain/seam allowance -> sew 1:1 and M:N -> arrange on humanoid -> choose simulation quality/material -> simulate -> inspect -> edit upstream pattern -> automatic downstream invalidation -> save/reload -> deterministic re-simulation -> production 2D export.`

No utility script, isolated model class, or green unit-test-only implementation is a milestone exit.

## Research findings that change priorities

### CLO / Marvelous Designer behavior

- Sewing is a semantic relationship, not merely two selected edges. Segment sewing, free sewing, 1:N and M:N sewing, directional correspondence and reversal are central workflows. CLO exposes these relationships in both 2D and 3D. Sources: CLO Free Sewing and M:N Sewing documentation; Marvelous Designer Sewing manual.
- Particle Distance directly controls garment mesh density, simulation speed and visual quality. Authoring commonly uses coarse values and final simulation uses finer values. This must be a behavioral control in our solver lifecycle, not a stored preference.
- The Property Editor is a major workflow surface: pattern, sewing, fabric, avatar and simulation properties are edited there. Our equivalent must expose important controls through native FreeCAD properties/task panels, not require Python commands.
- Avatar fitting is a reproducible arrangement layer: bounding volumes, arrangement points, X/Y/offset, wrap direction, symmetry and reset/save behavior matter before simulation.
- The product model separates authoritative pattern/sewing data from generated 3D simulation topology. We retain this separation.

### Open-source and FreeCAD research

- Sketcher already provides geometric/dimensional constraints, tangent/arc support, auto-constraints, snapping and symmetry. It should be used as an editing adapter instead of recreating a constraint solver.
- Part/OCCT provides robust curves and 2D offsets; MeshPart can provide conversion to simulation topology. Semantic edge IDs must remain independent of generated topology ordering.
- TechDraw/Draft provide native 2D drawing/export infrastructure and should be preferred for production output where practical.
- Tissu and PositionBasedDynamics remain optional backend candidates. The deterministic CPU backend remains the reference until an actual benchmark proves an external backend is worth its dependency/ABI cost.

## Architecture invariants

1. **PatternPiece is the semantic container; linked Sketcher geometry is authoritative when `GeometryAuthority == "Sketcher"`.** Derived outlines never become authoritative implicitly.
2. **Sketcher/Part/MeshPart are adapters.** Never make generated edge/face indices the semantic source of truth.
3. **Sewing is semantic assembly.** Ranges, reversal, correspondence, construction kind and stitch groups persist independently of simulation topology.
4. **Simulation topology is disposable.** Any change to pattern/seam/quality/material/collision inputs invalidates derived simulation state.
5. **Simulation backend is replaceable.** The deterministic CPU implementation is the reference contract; optional native solvers sit behind the same adapter.
6. **FreeCAD is the project container.** Do not introduce a mandatory second project database.

## Native workbench contracts

### Cloth Pattern — 2D authoring

**Must ship:**
- Create/Edit Pattern Piece
- native Sketcher authoring as the primary geometry editor
- point/edge selection and editing
- line, arc and curved-boundary authoring
- dimensional/geometric constraints through Sketcher
- seam allowance with robust offset behavior
- notches, grainline and internal/construction marks
- mirror/symmetry and transform/duplicate
- validation/measurement diagnostics
- simulation-resolution hint
- stable semantic IDs across recompute/save/reload

**UI:** Pattern toolbar + context menu + task panel + native property editor + 2D Sketcher adapter. Mark tools are context-sensitive. Numeric dimensions belong in properties/constraints rather than modal script dialogs.

### Cloth Sewing — semantic assembly

**Must ship:**
- Segment Sewing
- Free Sewing
- 1:N/M:N Sewing
- range editing
- sewing direction/reversal
- arc-length correspondence
- mismatch diagnostics
- stitch groups/construction kind
- validate/delete/edit/show relationships
- fitting-scene creation and arrangement controls
- simulation-scene creation

**UI:** a selection-driven task panel with 2D/3D relationship feedback. Invalid selections must be visibly rejected. Editing a sewing relationship must update every consumer through the canonical semantic object.

### Cloth Simulation — 3D fitting/draping

**Must ship:**
- generate/refresh simulation mesh
- Fast/Balanced/Final quality presets
- particle distance
- fabric density/thickness/stretch/shear/bend/friction
- solver iterations/substeps
- collision thickness and avatar skin offset
- avatar/collision selection
- arrangement placement/reset
- pin selection
- Simulate/Step/Pause/Reset
- seam/stitch visualization
- simulation status, diagnostics and reproducibility information
- saved fitting/simulation scene

**UI:** a native task panel and property editor that expose the lifecycle without scripting. Quality/material changes must visibly invalidate the derived result and trigger deterministic regeneration.

## Revised milestones and gates

### P0-A — Native end-to-end workflow gate

**Issues #143 + #155 / PR #160**

Prove one canonical four-piece garment entirely through public FreeCAD workbench commands and task panels. It must include a curved contour, real sewing relationships, simulation, save/reload, upstream edit, downstream invalidation and repeatable re-simulation.

**Exit:** the GUI scenario passes on a real FreeCAD runtime under Xvfb and leaves diagnostics on failure.

### P0-B — Simulation behavior gate

**Issues #145 + #159 + #161**

Turn the existing simulation-quality/fabric contract into native behavior. Fast/Balanced/Final must change particle density and solver settings; fabric/collision values must affect the backend; all changes must invalidate caches; values must survive save/reload.

**Exit:** a GUI test demonstrates quality switch -> different particle count/solver configuration -> simulation -> save/reload -> identical repeatable result.

### P0-C — Release UX and persistence audit

After P0-A/P0-B, audit all three workbenches as a user would: toolbar/menu registration, selection state, task-panel lifecycle, undo/recompute behavior, save/reload, errors and cancellation. Remove any path that requires internal helper imports or scripting.

**Exit:** the canonical tutorial can be executed by clicking the workbench UI alone.

### P1-A — Pattern authoring parity audit

**Issue #162**

The audit identified one immediate production blocker and several follow-on parity tasks. The immediate blocker is now addressed: native Sketcher editing is an explicit workbench command and closed-boundary validation has a persistent diagnostic/task-panel surface. Do not expand the custom drafting canvas as a second authoring system.

Next implement only the remaining concrete authoring blockers: dedicated arc/Bezier/BSpline creation, robust offset self-intersection handling, richer marks/measurements, symmetry, transform/duplicate and semantic preservation. Reuse Sketcher/Part/OCCT.

**Exit:** a non-rectangular curved garment piece can be authored and edited natively and still drives sewing/simulation correctly.

### P1-B — Production 2D export contract

**Issues #147 + #163**

Complete DXF/SVG/TechDraw-oriented export and validate units/scale, piece identity, seam allowance, notches, grainlines, internal marks and sewing metadata. Export is never authoritative over the FreeCAD model.

**Exit:** canonical garment export passes machine-checkable geometry/metadata regression tests.

### P1-C — Packaging, examples and documentation

Provide an example garment, installation instructions, click-by-click workflow, supported FreeCAD/Python matrix, troubleshooting and screenshots generated by CI. Verify icons, workbench registration and clean installation from the packaged repository.

**Exit:** a fresh FreeCAD installation can open the example and reproduce the complete workflow without developer-only setup.

### P2 — Optional native solver benchmark

**Issue #148**

Benchmark Tissu/PositionBasedDynamics-style backends only after P0/P1 release gates are stable. Compare speed, stability, collision quality, determinism, dependency burden and ABI compatibility. Do not replace the reference backend on speculation.

**Exit:** evidence-based decision: keep CPU reference or add an optional backend behind the existing adapter.

## Explicitly deferred from the first release

- photorealistic fabric rendering
- topstitch/puckering as simulation-critical behavior
- buttons/buttonholes/trims as simulation-critical objects
- full avatar soft-body/animation simulation
- automated grading/nesting
- cloud collaboration/marketplace services
- mandatory external solver dependencies

These are post-release enhancements unless the end-to-end audit unexpectedly makes one a hard correctness dependency.

## Verification policy

Every implementation task requires:

1. headless model/unit tests;
2. real FreeCAD runtime smoke coverage;
3. GUI/Xvfb coverage for UI changes;
4. save/reload coverage for persistent properties;
5. deterministic simulation evidence for solver changes;
6. supervisor review of the PR diff and issue state;
7. a terminal green CI run before merge;
8. merged-main verification after merge.

There is one canonical GitHub Actions workflow. Never create a second workflow to bypass a failing gate. If CI fails, diagnose, repair, rerun and wait for terminal results before progressing dependent work.

## Research sources

- CLO Help Center: https://support.clo3d.com/
- Marvelous Designer Manual: https://support.marvelousdesigner.com/hc/en-us/categories/51985515993625-Manual
- FreeCAD Sketcher documentation: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Sketcher_Workbench.md
- FreeCAD Sketcher scripting: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Sketcher_scripting.md
- FreeCAD TechDraw documentation: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/TechDraw_Workbench.md
- FreeCAD source: https://github.com/FreeCAD/FreeCAD
- Seamly2D: https://github.com/FashionFreedom/Seamly2D
- FreeSewing: https://github.com/freesewing/freesewing
- Tissu: https://github.com/evanrock520-ciencias/Tissu
- PositionBasedDynamics: https://github.com/InteractiveComputerGraphics/PositionBasedDynamics
