# Agent Work Registry

Coordination registry for parallel work on `freecad-cloth`.

## Rules

1. Register before non-trivial implementation.
2. One scope, one owner; coordinate before touching another active scope.
3. Keep `status`, `progress`, `tests`, and `pr` current.
4. CI/review/repository state are the authority for completion.
5. Mark completed or blocked work so no stale active entries remain.

## Active work

```yaml
- id: agent-sketcher-pattern-20260828
  agent: supervisor
  task: Prototype FreeCAD Sketcher-backed parametric pattern editing (#81)
  status: queued
  files:
    - PatternSketch.py
    - PatternCommands.py
    - PatternGui.py
    - tests/test_pattern_sketch.py
    - AGENT_STATUS.md
  scope: Add a native Sketcher adapter without replacing the solver-neutral PatternModel. Preserve semantic edge IDs, dimensions and construction metadata; keep headless layers FreeCAD-independent.
  started: 2026-08-28
  last_update: 2026-08-28T15:43:00Z
  progress: Issue scoped and research baseline recorded in #80. Implementation starts after the current drape milestone is green on main.
  tests: planned Python 3.10/3.11/3.12 plus real FreeCAD smoke
  pr: null
  blockers: none

- id: agent-garment-physics-20260828
  agent: supervisor
  task: Garment-grade XPBD shear, bending and self-collision (#82 / #71)
  status: queued
  files:
    - ClothSolver.py
    - ClothBackend.py
    - ClothSimulation.py
    - tests/test_xpbd.py
    - tests/test_collisions.py
    - AGENT_STATUS.md
  scope: Add explicit shear/bending constraints, deterministic self-collision/contact fixtures, substeps/convergence reporting and garment-quality regression bounds without introducing a mandatory external solver.
  started: 2026-08-28
  last_update: 2026-08-28T15:43:00Z
  progress: Scope and acceptance criteria recorded in #71/#82. Awaiting the drape-quality baseline before changing solver behavior.
  tests: planned Python 3.10/3.11/3.12 plus real FreeCAD smoke
  pr: null
  blockers: none

- id: agent-backend-audit-20260828
  agent: supervisor
  task: Audit optional Tissu and PositionBasedDynamics backends (#83)
  status: research
  files:
    - docs/SEWING_WORKFLOW_RESEARCH.md
    - AGENT_STATUS.md
  scope: Audit APIs, Python ABI/build requirements, supported platforms, licensing, determinism and mapping to the ClothSimulationBackend contract. No mandatory dependency adoption.
  started: 2026-08-28
  last_update: 2026-08-28T15:43:00Z
  progress: Initial audit recorded in #83 and research summary #80. Tissu is Apache-2.0; PositionBasedDynamics is MIT. Both remain optional pending adapter/build tests.
  tests: research/build audit only
  pr: null
  blockers: none

- id: agent-gui-docs-20260828
  agent: supervisor
  task: Automated GUI documentation screenshots (#68)
  status: queued
  files:
    - tests/freecad_smoke.py
    - docs/
    - AGENT_STATUS.md
  scope: Add deterministic screenshot capture as documentation tooling only; do not make screenshots a production workbench dependency.
  started: 2026-08-28
  last_update: 2026-08-28T15:43:00Z
  progress: Issue remains scoped; implementation follows functional GUI work.
  tests: planned FreeCAD GUI smoke/documentation workflow
  pr: null
  blockers: none
```

## Completed milestones

```yaml
- id: agent-meshpart-netgen-20260828
  agent: subagent
  task: Evaluate MeshPart/Netgen triangulation adapter (#86)
  status: completed
  files:
    - PatternMesh.py
    - PatternMeshFreeCAD.py
    - tests/test_mesh.py
    - tests/test_meshpart_adapter.py
    - tests/freecad_meshpart_smoke.py
    - .github/workflows/canonical-execution.yml
    - AGENT_STATUS.md
  scope: Compare FreeCAD MeshPart/Netgen triangulation with the semantic TriangleMesh contract, preserving pattern-edge boundary provenance and deterministic sewing constraint generation. Avoid changes to active Sketcher, sewing assembly, or XPBD solver scopes.
  started: 2026-08-28
  last_update: 2026-08-28T17:55:00+02:00
  progress: Added optional MeshPart tessellation adapter, canonical vertex/boundary ordering, stable pattern-segment provenance, headless regression coverage and real FreeCAD smoke coverage. The existing deterministic ear-clipping backend remains the reference path.
  tests: Canonical workflow run #166 passed Python 3.10/3.11/3.12 and real FreeCAD smoke.
  pr: 90 (open, ready to merge)
  blockers: none

- id: agent-supervisor-drape-quality-20260828
  agent: supervisor
  task: Deterministic drape quality gates (#70)
  status: completed
  progress: Added DrapeMetrics, bounded residual/displacement/finite-state assertions, deterministic repeat benchmark and canonical CI coverage. Rebased stale PR #79 as #84 and merged it after Python 3.10/3.11/3.12 and real FreeCAD smoke passed.
  tests: Canonical PR #84 run #154 green; post-merge main run #155 in progress at registry update.
  pr: 84 (merged)
  blockers: none

- id: agent-docs-quality-20260828
  agent: supervisor
  task: Documentation and workflow refresh (#63)
  status: completed
  progress: README now documents Cloth Pattern, Cloth Sewing, Cloth Simulation, fitting workflow, semantic source-of-truth architecture and canonical CI. Research summary is tracked in #80.
  tests: Documentation-only; canonical PR run #147 green before merge.
  pr: 78 (merged)
  blockers: none

- id: agent-avatar-fitting-20260828
  agent: subagent
  task: Body measurement/avatar fitting workflow (#69)
  status: completed
  progress: Added solver-neutral BodyMeasurements, PiecePlacement and FittingScene contracts, persistent fitting metadata and FreeCAD-facing fitting commands.
  tests: Canonical CI and FreeCAD smoke passed for PR #73.
  pr: 73 (merged)
  blockers: none

- id: agent-sewing-assembly-20260828
  agent: subagent
  task: Sewing-piece assembly and seam pairing UI (#67)
  status: completed
  progress: Added validated SewingAssembly, seam pairing metadata, stitch groups, alignment/reversal and deterministic piece transforms.
  tests: Canonical CI passed for PR #72.
  pr: 72 (merged)
  blockers: none

- id: agent-supervisor-humanoid-collision-20260828
  agent: supervisor
  task: Replace sphere-only avatar proxy with imported humanoid collision mesh (#59)
  status: completed
  progress: Imported FreeCAD body/mesh geometry now populates solver-neutral CollisionSurface data while retaining the sphere fallback and collision thickness metadata.
  tests: Canonical PR #64 and post-merge main validation passed.
  pr: 64 (merged)
  blockers: none

- id: agent-subagent-sewing-workbench-20260828
  agent: subagent
  task: Harden sewing workbench registration/load smoke coverage (#27)
  status: completed
  progress: Static GUI checks cover all three workbench registrations and sewing commands; FreeCAD smoke imports InitGui and validates all three workbench contracts.
  tests: Canonical PR #58 and post-merge main validation passed.
  pr: 58 (merged)
  blockers: none

- id: agent-avatar-contract-20260828
  agent: subagent
  task: Avatar collision contract and fitting-scene proxy (#54)
  status: completed
  progress: Solver-neutral AvatarSpec/CollisionSurface, deterministic sphere fallback and FreeCAD AvatarCollision proxy are integrated.
  tests: Avatar contract tests plus canonical FreeCAD smoke.
  pr: null
  blockers: none

- id: agent-seam-backend-20260828
  agent: subagent
  task: Robust seam graph and solver backend adapter (#46)
  status: completed
  progress: SeamGraph.py and ClothBackend.py provide stable semantic seams, stitch-pair generation, transforms, reset/replay and backend registry.
  tests: Canonical PR #50 passed all Python versions and FreeCAD smoke.
  pr: 50 (merged)
  blockers: none

- id: agent-supervisor-seam-allowance-20260828
  agent: supervisor
  task: Generic parametric seam allowance geometry (#48)
  status: completed
  progress: Deterministic convex/concave offset outline helper and regression coverage merged.
  tests: Canonical PR #49 passed all Python versions and FreeCAD smoke.
  pr: 49 (merged)
  blockers: none

- id: agent-pattern-drafting-canvas-20260828
  agent: subagent
  task: Interactive 2D drafting canvas (#39)
  status: completed
  progress: Editable drafting boundary, semantic marks, seam allowance preview and recompute-safe edits are on main.
  tests: Canonical main validation passed.
  pr: 41 (closed as superseded)
  blockers: none
```

## Superseded PR audit

- PR #65 closed: implementation already present on main.
- PR #74 closed: stale-base duplicate; functionality carried into #84.
- PR #76 closed: DXF/export implementation already present on main.
- PR #79 closed: stale-base quality implementation rebased as #84.
- PR #78 merged after documentation-only review.
- PRs #72 and #73 were already merged and are recorded above.
