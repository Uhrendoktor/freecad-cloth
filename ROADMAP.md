# FreeCAD Cloth Roadmap — 2026 Supervisor Replan v3

## Supervisor decision

The project is now in **release integration mode**. The next unit of progress is a trustworthy vertical slice, not another collection of isolated capabilities.

The target workflow remains:

`Author pattern → sew semantically → arrange/fit → choose simulation quality/material → simulate → inspect → edit upstream → invalidate downstream → save/reload → deterministic re-simulation → production output`

CLO is used as a workflow benchmark, not as a cloning target. Public CLO documentation confirms several high-value concepts that should guide our UX: explicit Free/1:N/M:N sewing, property-editor simulation controls, particle distance as a mesh-quality/performance control, persistent arrangement points/bounding volumes for fitting, and fit/stress/strain/pressure diagnostics. See the existing research summary and the primary vendor references below.

## Current repository state

- `main` is at `12bcede65c2f5f3d6e414ab8d01d10e23cd357dc` after the README/GUI screenshot publication work.
- Open PR #469 addresses unreferenced HM08 avatar vertices that distort bounds and visual acceptance.
- Open PR #453 improves collision preprocessing but must not be treated as release-complete until the drape is visually trustworthy.
- PR #438 remains diagnostic-only.
- Benchmark issue #454 provides reproducible workbench measurements and should drive measured improvements rather than more benchmark infrastructure.

## New supervisor milestone ladder

### M0 — Baseline / unblock visual truth
**Epic #471 / task #472**

Prove avatar topology, scale/orientation, arrangement and collision targeting are sane enough that the canonical garment is visibly worn rather than merely simulated.

**Exit:** canonical FreeCAD/Xvfb evidence shows a sane target and a convincing multi-piece drape; structural assertions reject edge-on/detached outcomes where feasible.

### M1 — Release vertical slice
**Tasks #473 + #474**

Lock one public-workbench scenario covering native Pattern → Sewing → Arrange → Simulation → Save/Reload → Upstream invalidation → deterministic re-simulation.

Simulation quality/material controls become lifecycle controls, not passive properties: quality changes alter mesh/solver configuration, material/collision values invalidate appropriate derived state, and stale/ready reasons are visible.

**Exit:** a clean run completes the full vertical slice without private helper APIs.

### M2 — Production parity foundations
**Tasks #475 + #476**

Bring sewing correspondence and diagnostics to a robust semantic baseline, with explicit ranges, orientation/reversal, curved arc-length mapping, mismatch diagnostics and staged commit/cancel behavior.

Complete a production-oriented 2D export contract using authoritative Pattern/Sewing data and native FreeCAD output paths where practical. Preserve units, scale, piece identity, seam allowance, notches, grainlines, internal marks and sewing metadata.

**Exit:** canonical garment sewing and export are machine-checkable and survive save/reload/invalidation.

### M3 — Fit/analysis layer
**Task #477**

Add result-consuming stress/strain/fit/contact-style diagnostics as a read-only layer over the existing solver output. No second solver and no second scene graph.

**Exit:** at least two deterministic analysis quantities have numerical regression coverage and a useful GUI presentation on the canonical drape.

### M4 — Evidence-led scale/performance
**Task #478**

Use the existing benchmark artifact to derive at least three measured improvements, prioritizing thin test coverage and disproportionate command surfaces before speculative micro-optimization.

**Exit:** every adopted performance/UX improvement has before/after measurements and a clear regression boundary.

## Parallel work policy

Agents may work in parallel on M1/M2 once M0's visual-truth contract is stable enough for their fixture inputs, but no task may invent a competing canonical garment scenario. The same canonical fixture, target-neutral DrapeTarget contract, and canonical CI workflow remain authoritative.

## Deferred

Keep production avatar fidelity (#374), advanced manufacturing/diagnostics (#362), and optional native solver evaluation (#148/#404) behind the M0–M3 gates. Do not make an external solver, second project database, second drafting engine, or second scene graph a release dependency.

## Architecture invariants

1. Pattern model is authoritative.
2. Sketcher/Part/MeshPart are adapters; generated edge/face ordering is not semantic identity.
3. Sewing is semantic assembly independent of simulation topology.
4. Simulation topology and numerical state are derived/rebuildable.
5. Solver backends sit behind one stable adapter; deterministic CPU remains the reference.
6. FreeCAD remains the project container.
7. There is one canonical GitHub Actions workflow.

## Verification policy

Every implementation task requires the appropriate combination of headless model tests, real FreeCAD runtime coverage, GUI/Xvfb coverage, save/reload persistence checks and deterministic simulation evidence. PRs must be inspected, CI must become terminal-green, and merged-main behavior must be verified before dependent work proceeds.

## Existing research basis

The earlier roadmap and `docs/RESEARCH.md` remain the detailed architecture reference. Current CLO sources consulted for this replan include the public Free Sewing, 1:N/M:N Sewing, Particle Distance, Property Editor, Avatar/Arrangement and Garment Fit Maps documentation.

## Research references

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
