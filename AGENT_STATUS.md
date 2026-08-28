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
- id: agent-supervisor-next-20260828
  agent: supervisor
  task: Native Sketcher adapter + garment XPBD constraints/self-collision
  status: implementation
  files: [PatternSketch.py, PatternCommands.py, XPBD.py, tests/test_pattern_sketch.py, tests/test_xpbd.py, AGENT_STATUS.md]
  scope: Incrementally expose PatternModel through native Sketcher and add explicit shear/bending plus deterministic particle self-collision while preserving solver-neutral APIs.
  started: 2026-08-28
  last_update: 2026-08-28T16:00:00Z
  progress: Sketcher adapter and command added; explicit shear/bending constraint factories and deterministic self-collision projection added; regression tests added. Awaiting canonical CI.
  tests: Python 3.10/3.11/3.12 plus real FreeCAD smoke
  pr: pending
  blockers: none

- id: agent-backend-audit-20260828
  agent: supervisor
  task: Audit optional Tissu and PositionBasedDynamics backends (#83)
  status: research
  files: [docs/SEWING_WORKFLOW_RESEARCH.md, AGENT_STATUS.md]
  scope: Audit APIs, Python ABI/build requirements, supported platforms, licensing, determinism and mapping to ClothSimulationBackend. No mandatory dependency adoption.
  started: 2026-08-28
  last_update: 2026-08-28T15:43:00Z
  progress: Initial audit recorded in #83 and research summary #80. Both remain optional pending adapter/build tests.
  tests: research/build audit only
  pr: null
  blockers: none

- id: agent-native-geometry-20260828
  agent: supervisor
  task: OCCT offset / MeshPart triangulation / native placement-export evaluations (#85/#86/#88)
  status: queued
  files: [PatternGeometry.py, PatternMesh.py, PatternExport.py, AGENT_STATUS.md]
  scope: Evaluate native FreeCAD geometry, meshing, placement and export adapters without losing semantic IDs or headless compatibility.
  started: 2026-08-28
  last_update: 2026-08-28T16:00:00Z
  progress: Issues #85/#86/#88 created and assigned. Implementation follows current physics/pattern branch after baseline CI.
  tests: planned differential tests + FreeCAD smoke
  pr: null
  blockers: none

- id: agent-gui-docs-20260828
  agent: supervisor
  task: Automated GUI documentation screenshots (#68)
  status: queued
  files: [tests/freecad_smoke.py, docs/, AGENT_STATUS.md]
  scope: Deterministic screenshot capture as documentation tooling only.
  started: 2026-08-28
  last_update: 2026-08-28T16:00:00Z
  progress: Issue #68 assigned; implementation follows functional GUI changes.
  tests: planned FreeCAD GUI smoke/documentation workflow
  pr: null
  blockers: none

- id: agent-sewing-command-adapter-20260828
  agent: subagent
  task: Extract shared FreeCAD command adapter for Sewing/Fitting workbenches (#98)
  status: implementation
  files: [CommandAdapter.py, SewingCommands.py, FittingCommands.py, tests/test_command_adapter.py, AGENT_STATUS.md]
  scope: Remove duplicated _FunctionCommand boilerplate from the sewing/fitting command modules without changing command behavior or introducing GUI imports into headless paths.
  started: 2026-08-28
  last_update: 2026-08-28T18:40:00+02:00
  progress: Shared adapter and regression tests implemented; PR #99 open. Awaiting canonical CI.
  tests: Python unit tests plus FreeCAD command-registration smoke if available
  pr: 99
  blockers: none
```

## Current issue map

- #43 / #80: canonical research records
- #68: GUI documentation screenshots
- #71 / #82: garment-grade XPBD
- #75: native-library architecture umbrella
- #81: Sketcher-backed pattern editing
- #83: optional solver audit
- #85: OCCT seam allowance
- #86: MeshPart/Netgen triangulation
- #87: solver authority consolidation
- #88: Placement and export adapters
- #98: sewing workbench integration and correctness

## Completed milestones

- id: agent-solver-authority-20260828
  agent: subagent
  task: Consolidate simulation solver authority behind ClothSimulationBackend (#87)
  status: completed
  files: [SimulationObjects.py, tests/test_backend_authority.py, AGENT_STATUS.md]
  scope: Keep the document-facing simulation proxy dependent on ClothSimulationBackend, with the bundled XPBD solver selected through the backend registry; preserve semantic scene behavior and avoid active XPBD implementation files.
  started: 2026-08-28
  last_update: 2026-08-28T18:15:00+02:00
  progress: Refactored SimulationProxy to construct and drive XPBDBackend through the backend registry; mesh output now consumes backend positions and reset/state reporting stays backend-owned. Canonical PR #91 and post-merge main validation passed.
  tests: Canonical PR #91 run #168 passed Python 3.10/3.11/3.12 and real FreeCAD smoke; post-merge main run #172 passed all test and FreeCAD jobs.
  pr: 91 (merged)
  blockers: none

- id: agent-meshpart-netgen-20260828
  agent: subagent
  task: Evaluate MeshPart/Netgen triangulation adapter (#86)
  status: completed
  files: [PatternMesh.py, PatternMeshFreeCAD.py, tests/test_mesh.py, tests/test_meshpart_adapter.py, tests/freecad_meshpart_smoke.py, .github/workflows/canonical-execution.yml, AGENT_STATUS.md]
  scope: Compare FreeCAD MeshPart/Netgen triangulation with the semantic TriangleMesh contract, preserving pattern-edge boundary provenance and deterministic sewing constraint generation.
  started: 2026-08-28
  last_update: 2026-08-28T18:10:00+02:00
  progress: Hardened the existing native MeshPart adapter rather than introducing a duplicate module; added canonical vertex/boundary ordering, stable pattern-segment provenance, headless regression coverage and real FreeCAD smoke coverage. The deterministic ear-clipping path remains the headless reference backend. Merged as PR #93 after canonical workflow run #170 passed.
  tests: Canonical PR #93 run #170 passed Python 3.10/3.11/3.12 and real FreeCAD smoke. Issue #86 closed as completed.
  pr: 93 (merged)
  blockers: none

- Workbench skeleton and canonical CI
- Parametric pattern model and semantic construction metadata
- Drafting UI and seam allowance/export contracts
- Sewing assembly and seam pairing
- Humanoid/body collision import and fitting-scene metadata
- Deterministic drape quality gates and benchmark contract (#84)
- Documentation/workflow refresh (#78)

## Supervisor policy

No issue is considered complete merely because code exists. Each implementation must have focused regression coverage, pass canonical Python CI, pass real FreeCAD smoke where applicable, and be reconciled with the issue registry before merge.
