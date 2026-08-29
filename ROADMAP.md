# FreeCAD Cloth Roadmap — 2026 Replan

## Decision

The previous roadmap was directionally correct but too feature-list oriented. The project has crossed the prototype/integration threshold: three registered FreeCAD workbenches, native document objects, semantic seams, deterministic CPU simulation, GUI smoke coverage, and save/reload coverage already exist. The next phase therefore changes from “add more isolated capabilities” to **prove and harden a complete garment-production loop**.

The governing acceptance criterion is not the number of commands or scripts. It is this reproducible native FreeCAD workflow:

**Pattern authoring → sewing/assembly → avatar arrangement → simulation → inspect → revise pattern → recompute → simulate again → save/reload with semantics intact.**

## What research changed

CLO and Marvelous Designer make several capabilities more central than the old roadmap implied:

- Sewing is not only 1:1 segment pairing. Free sewing and M:N relationships are first-class workflows; sewing direction and reversal affect the resulting assembly. citeturn0search8turn0search10
- Simulation quality is deliberately managed through particle distance: coarse meshes are used while authoring/fitting and finer meshes for final quality. citeturn0search2turn1search0
- Avatar fitting is more than a collision mesh. Arrangement points, bounding volumes, wrap direction, symmetry, skin offset, and reset/re-drape operations form a reproducible pre-simulation arrangement layer. citeturn0search12turn0search16turn1search8turn1search9
- The surrounding product ecosystem emphasizes reusable assets, projects, avatars, fabrics and collaboration/asset sharing. For an open-source FreeCAD project, this maps better to document-native libraries and interoperable files than to a proprietary cloud service. citeturn1search2turn1search6
- Modern open-source XPBD projects demonstrate stretch, shear, bending, self-collision, pins, stitches and multiple collision models. Tissu is particularly relevant as an optional backend because it exposes these concepts through a C++/Python API, but its native dependency/ABI burden argues against making it mandatory. citeturn0search1turn0search3

## Architecture that remains valid

1. **Pattern model is authoritative.** FreeCAD document objects expose properties and persistence; a FreeCAD-independent model owns semantic IDs and pattern meaning.
2. **Sketcher, OCCT/Part and MeshPart are adapters.** They provide native editing/geometry/meshing where useful, but generated edge/face ordering is never the semantic source of truth.
3. **Sewing is semantic assembly.** Seam relationships, ranges, reversal, alignment and stitch groups are stored independently of generated simulation topology.
4. **Simulation meshes are disposable.** They are regenerated from the authoritative pattern/seam/quality inputs.
5. **The deterministic CPU solver remains the reference backend.** Optional native backends may be benchmarked but must not become a packaging requirement without evidence.
6. **FreeCAD document persistence is the project format.** Do not introduce a second mandatory project database.

## Workbench contracts

### Cloth Pattern — 2D authoring

Core tools:

- New Pattern Piece / Draft Pattern
- Select/Move point and edge
- Parametric dimensions and constraints
- Seam allowance
- Notch
- Grainline
- Internal mark / construction line
- Mirror / symmetry
- Transform / duplicate
- Mesh preview / simulation-resolution hint
- Pattern properties and measurement diagnostics

UI contract: task panel for creation/editing, property editor for numeric parameters, context-sensitive marking tools, and a native Sketcher mirror/adapter where appropriate.

### Cloth Sewing — semantic assembly

Core tools:

- Segment Sewing
- Free Sewing
- M:N Sewing
- Sewing direction/reversal
- Seam length/correspondence diagnostics
- Stitch groups and construction kinds
- Validate Seams
- Show/Hide sewing relationships
- Create/Edit Fitting Scene
- Arrangement point editor
- Reset arrangement
- Create Simulation Scene

UI contract: 2D/3D seam visualization, explicit selection state, diagnostics before simulation, editable seam relationships, and save/reload-safe task panels.

### Cloth Simulation — 3D fitting and draping

Core tools:

- Generate/refresh simulation mesh
- Fast / Preview / Final particle-distance presets
- Fabric preset and physical properties
- Solver substeps / iterations
- Collision thickness and avatar skin offset
- Avatar/collision selection
- Pin selection
- Simulate / Step / Pause / Reset
- Sewing/stitch constraint visualization
- Fit/drape diagnostics and reproducibility metrics
- Result snapshot/inspection without replacing the source pattern

UI contract: clear simulation state, quality controls visible without scripting, deterministic reset, and a fitting scene that can be saved/reloaded.

## Milestones

### M0 — Release-blocking audit (P0)

**Issue #143**

Audit the entire end-to-end workflow against real FreeCAD runtime, not mocks alone. Add regression tests for every blocker discovered. The audit must cover multiple pieces, curved edges, seam invalidation, document recompute, save/reload, UI activation, and deterministic re-simulation.

Exit gate: a clean minimal garment example can be authored and simulated entirely through the workbenches.

### M1 — Sewing completeness (P0)

**Issue #144**

Implement free sewing and M:N relationships. Keep the canonical seam model authoritative and deterministic. Add 2D/3D feedback, direction/reversal, mismatch diagnostics, edit/delete lifecycle, persistence and GUI coverage.

Exit gate: multi-segment-to-one and one-to-many seams work end-to-end.

### M2 — Simulation production controls (P0)

**Issue #145**

Add particle-distance/quality presets and material properties that map cleanly to the reference solver. Add avatar skin offset and visible solver/collision controls. Persist all settings.

Exit gate: a user can switch from fast fitting to final-quality simulation without scripting and can reproduce the same result after reload.

### M3 — Avatar fitting layer (P1)

**Issue #146**

Implement named bounding volumes and arrangement points with X/Y/offset/wrap direction, symmetry, deterministic placement, reset operations and imported-mesh compatibility. Auto-arrangement/auto-sewing is optional within this milestone.

Exit gate: the same garment can be arranged on a saved fitting scene and recreated deterministically.

### M4 — Production 2D output (P1)

**Issue #147**

Provide DXF/SVG/TechDraw-oriented export with semantic preservation and regression fixtures. Prefer FreeCAD-native export paths over custom renderers.

Exit gate: a pattern can leave the workbench as production-oriented 2D CAD output without losing the authoritative model.

### M5 — Optional solver benchmark (P2)

**Issue #148**

Benchmark Tissu and/or PositionBasedDynamics-style native backends against the reference CPU implementation. Compare performance, stability, collision behavior, determinism, dependency burden and FreeCAD ABI packaging.

Exit gate: either keep the reference backend as the default with evidence, or introduce an optional backend behind the existing adapter without making installation fragile.

### M6 — Release hardening

After M0–M4:

- package metadata and icons verified on supported FreeCAD versions;
- examples/tutorial garment committed;
- documentation contains a complete click-by-click workflow;
- CI covers Python, real FreeCAD headless runtime, GUI/Xvfb, save/reload, and representative drape benchmarks;
- no open release-blocking issues;
- no stale agent/task state;
- one canonical GitHub Actions workflow only.

## Explicitly deferred

These are valuable but are not allowed to block the first production-quality open-source release:

- topstitch rendering;
- buttons/buttonholes and trims as simulation-critical objects;
- full animation/soft-body avatar simulation;
- automated grading/nesting;
- cloud collaboration/marketplace services;
- mandatory external solver dependencies;
- photorealistic rendering.

They can be added after the core pattern/sewing/fitting/simulation loop is reliable.

## Native FreeCAD reuse policy

Prefer existing FreeCAD capabilities whenever they fit:

- **Sketcher** for constraints and familiar 2D editing affordances;
- **Part/OCCT** for robust curves, offsets and topology operations;
- **MeshPart** for deterministic conversion to simulation input;
- **App::Property*** and **App.Placement** for document-native persistence;
- **TechDraw/Draft** for 2D presentation/export;
- **Selection/task panels/view providers** for workbench UX.

Do not duplicate these with a private geometry kernel or an opaque project format.

## Verification gates

Every milestone must finish with:

1. headless unit/model tests;
2. real FreeCAD runtime smoke tests;
3. GUI/Xvfb scenario coverage where UI behavior changes;
4. save/reload coverage for new persistent state;
5. deterministic benchmark/regression evidence when simulation changes;
6. review of the diff and open issues before merge.

The canonical workflow is the only CI workflow. A non-terminal workflow run is never treated as complete; failures require diagnosis, repair, rerun and reassessment before the next dependent operation.
