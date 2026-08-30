# FreeCAD Cloth Roadmap — 2026 Supervisor Replan v3

## Decision

The roadmap remains a vertical-slice release plan. The PR/issue audit on 2026-08-30 showed that capability accumulation is no longer the correct ordering principle: the current release risk is integration of the three native workbenches under real FreeCAD. A new P0-0 gate is therefore inserted before DrapeTarget and end-to-end garment work.

Release criterion:

`Author curved parametric pieces -> mark/grain/seam allowance -> sew 1:1 and M:N -> arrange on humanoid -> choose simulation quality/material -> simulate -> inspect -> edit upstream pattern -> automatic downstream invalidation -> save/reload -> deterministic re-simulation -> production 2D export.`

No utility script, isolated model class, or unit-test-only implementation is a milestone exit.

## Research-driven product model

CLO and Marvelous Designer make several behaviors release-critical rather than optional UI polish:

- Sewing is a persistent semantic relationship. Segment, Free, 1:N and M:N sewing are normal workflows; directional correspondence, reversal and mismatch feedback are visible during authoring. citeturn1search0turn1search1turn1search2turn1search5
- Arrangement points/bounding volumes provide reproducible pre-simulation placement, with explicit position, offset, rotation and wrap-direction controls. citeturn1search8turn1search12
- Particle Distance changes garment quality and simulation speed and therefore must affect actual generated topology/solver behavior, not merely persist as a preference. citeturn1search10
- Property/task-panel editing is a major workflow surface for sewing, arrangement, fabric and simulation controls. citeturn1search8turn1search3

FreeCAD already provides the complementary engineering kernels: Sketcher supplies geometric/dimensional constraints and expressions; external geometry remains parametric reference geometry; TechDraw can export SVG/DXF. Cloth should own garment semantics and lifecycle state rather than duplicate these kernels. citeturn0search1turn0search2turn0search15turn0search10

Seamly2D demonstrates the value of reusable, scalable, measurement-driven pattern documents, while FreeSewing demonstrates a modular parametric pattern library. These are design references, not runtime dependencies. citeturn2search0turn2search6

## Architecture invariants

1. **Pattern geometry is authoritative.** Prefer native Sketcher/Part geometry; Cloth stores semantic IDs and manufacturing metadata.
2. **Sketcher/Part/MeshPart are adapters.** Generated Edge/Face ordering is never the semantic source of truth.
3. **Sewing is semantic assembly.** Ranges, direction, correspondence, stitch groups and construction kind persist independently of simulation topology.
4. **Simulation topology is disposable.** Pattern, seam, quality, material or collision changes invalidate derived simulation state.
5. **Collision target is target-neutral.** Mannequin and arbitrary FreeCAD Shape/Mesh objects feed the same collision interface.
6. **Simulation backend is replaceable.** The deterministic CPU implementation defines the reference behavior; optional native backends remain behind an adapter.
7. **FreeCAD is the project container.** Do not introduce a mandatory second project database.

## Native workbench contracts

### Cloth Pattern — 2D authoring

Must ship:
- Create/Edit Pattern Piece
- point/edge selection and editing
- line, arc and curved-boundary authoring
- native Sketcher constraints/dimensions/expressions or a thin Sketcher-backed adapter
- robust seam allowance/offset
- notches, grainline and internal/construction marks
- mirror/symmetry and transform/duplicate
- validation/measurement diagnostics
- simulation-resolution hint
- stable semantic IDs across recompute/save/reload

UI: Pattern toolbar + context menu + task panel + native property editor + Sketcher adapter. Mark tools are context-sensitive. Dimensions belong in properties/constraints rather than modal script dialogs.

### Cloth Sewing — semantic assembly

Must ship:
- Segment Sewing
- Free Sewing
- 1:N/M:N Sewing
- range editing
- direction/reversal
- arc-length correspondence
- mismatch diagnostics
- stitch groups/construction kind
- validate/delete/edit/show relationships
- fitting-scene creation and arrangement controls
- simulation-scene creation

UI: selection-driven task panel with 2D/3D relationship feedback. Invalid selections are visibly rejected. Editing a sewing relationship updates every consumer through the canonical semantic object.

### Cloth Simulation — 3D fitting/draping

Must ship:
- generate/refresh simulation mesh
- Fast/Balanced/Final quality presets
- particle distance
- fabric density/thickness/stretch/shear/bend/friction
- solver iterations/substeps
- collision thickness and avatar skin offset
- mannequin or arbitrary FreeCAD collision target selection
- arrangement placement/reset
- pin selection
- Simulate/Step/Pause/Reset
- seam/stitch visualization
- simulation status, diagnostics and reproducibility information
- saved fitting/simulation scene

UI: native task panel + property editor exposing the complete lifecycle without scripting.

## Revised milestones and gates

### P0-0 — Sewing workbench GUI registration gate

**Issue #308**

Resolve the discovered real-FreeCAD initialization failure before any dependent release gate. Registration must be deterministic and idempotent; every command in SewingCommands, SewingNetworkCommands, FittingCommands and AvatarCommands must appear in exactly one declared group; workbench icons must resolve from the installed workbench; activation must be proven by the real FreeCAD/Xvfb scenario.

**Exit:** canonical GUI job reaches Pattern, Sewing and Simulation without workbench initialization exceptions and the Sewing smoke assertion sees the complete public command set.

### P0-1 — DrapeTarget authority and safe lifecycle

**Issues #276, #289, #284**

Make target-neutral collision state authoritative and recompute-safe. A changed target must produce explicit stale status/reason; document recompute must not crash; Run/Step must refuse while stale; Refresh rebuilds the target and returns the simulation to ready state. Verify mannequin and arbitrary FreeCAD geometry through public commands and save/reload.

**Exit:** canonical FreeCAD/Xvfb scenario proves target edit -> stale -> refresh -> simulate for both target classes.

### P0-2 — Canonical garment end-to-end gate

**Issues #278, #155, #143**

Prove one four-piece garment through public Pattern -> Sewing -> fitting/arrangement -> Simulation commands/task panels, including a curved seam, M:N sewing, save/reload, upstream edit, downstream invalidation and deterministic re-simulation.

**Exit:** real FreeCAD/Xvfb scenario passes and leaves diagnostics/screenshots on failure.

### P0-3 — Simulation behavior gate

**Issues #145, #159, #161**

Fast/Balanced/Final must change particle density and solver settings; fabric/collision values must affect the backend; all derived state changes invalidate caches; values survive save/reload.

**Exit:** GUI test demonstrates quality switch -> changed particle count/configuration -> simulation -> save/reload -> repeatable result.

### P0-4 — Release UX/persistence audit

Audit all three workbenches as a user would: toolbar/menu registration, selection state, task-panel lifecycle, undo/recompute behavior, save/reload, errors and cancellation. Remove paths that require internal helper imports or scripts.

**Exit:** the canonical tutorial can be executed by clicking the workbench UI alone.

### P1-A — Pattern authoring parity

**Issue #162**

Implement only concrete authoring blockers found by audit: curved edges, native constraints, robust offsets, marks, symmetry, diagnostics and semantic preservation. Use Sketcher/Part/OCCT rather than a private drafting kernel.

### P1-B — Production 2D export

**Issues #147, #163**

Complete DXF/SVG/TechDraw-oriented export and validate scale/units, piece identity, seam allowance, notches, grainlines, internal marks and sewing metadata. FreeCAD model remains authoritative. TechDraw supports SVG/DXF export; the release adapter must add garment-specific semantic grouping and validation. citeturn0search0turn0search12

### P1-C — Packaging, examples and documentation

Provide an example garment, installation instructions, click-by-click workflow, supported FreeCAD/Python matrix, troubleshooting and CI-generated screenshots. Verify icons, registration and clean installation.

### P2 — Optional solver benchmark

**Issue #148**

Benchmark optional native backends only after P0/P1 are green. Compare speed, stability, collision quality, determinism, dependency burden and ABI compatibility.

## Explicitly deferred

- photorealistic fabric rendering
- topstitch/puckering as simulation-critical behavior
- buttons/buttonholes/trims as simulation-critical objects
- full avatar soft-body/animation simulation
- automated grading/nesting
- cloud collaboration/marketplace services
- mandatory external solver dependencies

## Verification policy

Every implementation task requires headless tests, real FreeCAD runtime smoke, GUI/Xvfb coverage for UI changes, save/reload coverage, deterministic simulation evidence for solver changes, supervisor review, terminal green CI before merge, and merged-main verification.

There is one canonical GitHub Actions workflow. Never create a second workflow to bypass a failing gate. If CI fails, diagnose, repair, rerun and wait for terminal results before progressing dependent work.
