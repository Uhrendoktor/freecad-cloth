# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The initial PR/issue backlog was audited before new implementation work. Obsolete stacked branches were closed; validated work was rebased onto current `main` instead of merging stale bases.

### Current architecture gates

- **P0-A Pattern authoring:** native `Sketcher::SketchObject` is now the intended geometry authority for linked PatternPieces. `PatternIR` preserves curve kind and endpoint connectivity. Remaining work: native authoring toolbar/task flow, curved seam editing, seam allowance/marks as derived features, and real multi-piece GUI acceptance.
- **P0-B Sewing:** semantic seam references are merged; Show 2D now focuses authoritative PatternPieces. Remaining work: curved/M:N sewing, seam editing UI, length validation, invalid-reference UX, and sewing dependency invalidation.
- **P0-C Simulation:** native FreeCAD simulation scene and humanoid collision source exist. Remaining work: particle-distance quality presets, fabric/collision material presets, robust drape transfer from authored PatternPieces, and final deterministic simulation acceptance.
- **P0-D Acceptance:** canonical FreeCAD/Xvfb smoke exists, but its garment fixture still uses direct PatternPiece construction. It must be upgraded to create/edit real Sketcher-backed pieces and prove save/reload plus edit→seam→mesh→simulation invalidation.

## Active workstreams

| Workstream | Issue/PR | Status | Owner role |
|---|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged PR #206 | done | supervisor |
| Semantic seam references | #169, merged PR #200 | done | supervisor |
| Export validation | #163, merged PR #209 | done | supervisor |
| Sketcher authority | #165/#170, PR #213 | CI/review | supervisor |
| Sewing Show 2D focus | #207, merged before current main | done | supervisor |
| Sewing task invalid-reference acceptance | #165, branch `agent/sewing-task-invalid-ref-20260830` | active | subagent |
| Canonical GUI acceptance | #155 | queued P0 | supervisor |
| Simulation quality/material controls | #145 | queued P0 |
| Architecture roadmap | #162/#165 | active planning | supervisor |

## Rules for new work

1. Sketcher geometry is editable/source geometry; PatternPiece is the semantic garment object.
2. PatternIR is the solver-neutral boundary and must preserve native curve identity and connectivity.
3. Sewing references use semantic IDs/signatures, not raw insertion-order edge numbers.
4. Simulation consumes derived geometry and must invalidate/rebuild deterministically after source edits.
5. Native FreeCAD behavior is preferred over parallel custom CAD infrastructure.
6. Every P0 feature requires headless tests plus real FreeCAD smoke/Xvfb coverage before merge.
7. One canonical CI workflow is used; do not add push-triggered workflow variants.

## Next supervisor sequence

1. Merge the validated Sketcher-authority gate after terminal-green CI.
2. Rework #155 into a real Sketcher-backed 3+ piece garment fixture with curved seam, save/reload, edit propagation, and deterministic re-simulation.
3. Complete P0 sewing UI: semantic edge selection, M:N/curved sewing, reverse/alignment, length check, and invalid-reference task-panel states.
4. Complete P0 simulation quality/material presets and authored-pattern drape transfer.
5. Replace legacy drafting as the default Pattern UI with native Sketcher commands while retaining it only as a migration utility.
6. Add production export/round-trip acceptance and package/install validation.
7. Re-audit the full issue list and update this file before release.
