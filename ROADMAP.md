# FreeCAD Cloth Roadmap — 2026 Supervisor Replan v3

## Supervisor decision

The project is now in **release integration mode**. The next unit of progress is a trustworthy vertical slice, not another collection of isolated capabilities.

The target workflow remains:

`Author pattern → sew semantically → arrange/fit → choose simulation quality/material → simulate → inspect → edit upstream → invalidate downstream → save/reload → deterministic re-simulation → production output`

CLO is used as a workflow benchmark, not as a cloning target. Public CLO documentation confirms several high-value concepts that should guide our UX: explicit Free/1:N/M:N sewing, property-editor simulation controls, particle distance as a mesh-quality/performance control, persistent arrangement points/bounding volumes for fitting, and fit/stress/strain/pressure diagnostics. See the existing research summary and the primary vendor references below.

## Current repository state

- Supervisor issue #1017 remains the complete-project criterion.
- Current main is `8cee5774c25110448675e7b45d651869f3921692`, merged from PR #1059 at 2026-09-23T10:09:55Z.
- Active release-closeout PR is #1066, head `af1e98d12a2287e9042aebb3ef9cb163bf97354c`, which aligns the basic Blanket-over-Cube and README blanket fixtures with the validated 200 mm geometry.
- The canonical workflow remains exactly one workflow: `.github/workflows/canonical-execution.yml`.
- Supporting canonical run #35845226384 validated the 200 mm basic blanket fixture successfully (mesh, drape, motion, material presentation and 16 motion frames), while the same run still exposed unrelated README-turntable and Native Sketcher failures.
- Current branch/PR push runs #3394 (merged main) and #3397 (PR #1066 head) both terminate immediately with failure and zero jobs. The connector currently exposes no corresponding pull_request execution for #1066.
- Issue #1053 records the reproducible Actions event-delivery/orchestration blocker and the administrator-side restoration path. No workflow duplication, threshold relaxation, or timeout weakening has been introduced.

## Supervisor milestone ladder

### M0 — Baseline / unblock visual truth — COMPLETE
**Historical scope: Epic #471 / task #472**

Prove avatar topology, scale/orientation, arrangement and collision targeting are sane enough that the canonical garment is visibly worn rather than merely simulated.

**Exit:** canonical FreeCAD/Xvfb evidence shows a sane target and a convincing multi-piece drape; structural assertions reject edge-on/detached outcomes where feasible.

### M1 — Release vertical slice — COMPLETE
**Historical scope: tasks #473 + #474**

Lock one public-workbench scenario covering native Pattern → Sewing → Arrange → Simulation → Save/Reload → Upstream invalidation → deterministic re-simulation.

Simulation quality/material controls become lifecycle controls, not passive properties: quality changes alter mesh/solver configuration, material/collision values invalidate appropriate derived state, and stale/ready reasons are visible.

**Exit:** a clean run completes the full vertical slice without private helper APIs.

### M2 — Production parity foundations — COMPLETE
**Historical scope: tasks #475 + #476**

Bring sewing correspondence and diagnostics to a robust semantic baseline, with explicit ranges, orientation/reversal, curved arc-length mapping, mismatch diagnostics and staged commit/cancel behavior.

Complete a production-oriented 2D export contract using authoritative Pattern/Sewing data and native FreeCAD output paths where practical. Preserve units, scale, piece identity, seam allowance, notches, grainlines, internal marks and sewing metadata.

**Exit:** canonical garment sewing and export are machine-checkable and survive save/reload/invalidation.

### M3 — Fit/analysis layer — COMPLETE FOR CURRENT RELEASE SLICE
**Historical scope: task #477**

Add result-consuming stress/strain/fit/contact-style diagnostics as a read-only layer over the existing solver output. No second solver and no second scene graph.

**Exit:** at least two deterministic analysis quantities have numerical regression coverage and a useful GUI presentation on the canonical drape.

### M4 — Evidence-led scale/performance — FUTURE
**Historical scope: task #478**

Use the existing benchmark artifact to derive at least three measured improvements, prioritizing thin test coverage and disproportionate command surfaces before speculative micro-optimization.

**Exit:** every adopted performance/UX improvement has before/after measurements and a clear regression boundary.
This is intentionally outside the completed release-closeout scope and remains future optimization work.

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
