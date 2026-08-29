# AGENT STATUS

## Supervisor

- Active milestone: **P0 vertical release gates** — native end-to-end workflow plus behavioral simulation-quality controls.
- Mainline contains three registered FreeCAD workbenches: Cloth Pattern, Cloth Sewing, and Cloth Simulation.
- M:N/free sewing and fitting arrangement work are merged.
- Simulation-quality/fabric parameter contract is merged; native behavioral wiring is under P0 validation.
- Production SVG/DXF semantic metadata exists, but export validation remains a release gate.

## Current task board

- **#143** P0 end-to-end workflow audit — supervisor gate.
- **#155 / open PR #185** P0 canonical native garment fixture and GUI/Xvfb workflow — active supervisor validation; merge only after fresh terminal-green CI for the corrected head.
- **#145 / #159 / #161** P0 simulation quality — active. **PR #192** is the current #161 validation vehicle; its canonical CI must be terminal-green before merge.
- **#147 / #163** P1 production 2D export — queued behind P0; metadata is foundation, not completion.
- **#162** P1 pattern authoring parity audit — queued; focus on curved native Sketcher geometry, constraints, marks, offsets and semantic preservation discovered by the P0 audit.
- **#148** P2 optional native solver benchmark — explicitly non-blocking.
- **#165** Architecture: FreeCAD-native Sketcher pattern authoring + semantic Cloth sewing layer — architecture documented; implementation follow-up must not duplicate the P0 audit.

## Coordination protocol

- Use this file as the shared status board.
- Before editing, mark the task IN PROGRESS with agent/branch and timestamp.
- After verified completion, mark DONE with commit/PR and verification evidence.
- If blocked, record exact blocker and next action.
- Supervisor inspects PRs, CI, diffs, dependencies and integration before merge.
- Never report completion while Actions, delegated agents, or required verification are non-terminal.

## Replan v3 decision

The v2 vertical-slice roadmap remains valid but is now enforced as observable release gates:

`Pattern authoring -> 1:1 + free/M:N sewing -> avatar arrangement -> quality/material simulation -> inspect -> upstream edit -> invalidation -> save/reload -> deterministic re-simulation -> production 2D export.`

CLO research confirms that semantic sewing, avatar arrangement, simulation quality/material state, property-editor workflow, diagnostics and production output are coupled workflow concepts. FreeCAD Sketcher remains the native authoring/constraint authority; Part/OCCT remains the geometry authority; TechDraw is reused for SVG/DXF transport; a dedicated surface-cloth solver abstraction remains separate from structural FEM.

## Completed

- Three native FreeCAD workbenches and document objects.
- Parametric pattern model with semantic marks and native Sketcher adapter.
- Semantic 1:1, free and M:N sewing relationships and range editor.
- Curved/arc-length sewing correspondence and diagnostics.
- Avatar bounding volumes, arrangement points, symmetry, placement/reset.
- Deterministic CPU cloth backend with stretch/shear/bending and self-collision.
- Simulation-quality/fabric parameter contract.
- Semantic SVG/DXF export metadata.
- Canonical CI with real FreeCAD smoke and GUI/Xvfb coverage.
- #165 architecture boundary documented in `docs/architecture/freecad-sketcher-cloth-boundary.md`.
- Roadmap v2 research/replan integrated into `ROADMAP.md`.

## Release gates

1. **P0-A:** #185 proves the real public Pattern -> Sewing -> Simulation -> save/reload -> invalidation workflow on the corrected head.
2. **P0-B:** #159/#161 wire quality/material/collision properties into native simulation behavior and UI; #192 validates #161.
3. **P0-C:** audit task-panel, selection, cancellation, recompute, undo and persistence behavior across all three workbenches.
4. **P1-A:** #162 closes concrete Pattern authoring blockers discovered by the audit.
5. **P1-B:** #163/#147 validate production 2D output, units/scale and semantic round-trip.
6. **P1-C:** package/install/example/tutorial/release documentation.
7. **P2:** optional solver benchmark only after release gates are stable.

## CI discipline

- One canonical GitHub Actions workflow only.
- Never treat an in-progress workflow as success.
- Supervisor reviews diffs and tests, waits for every relevant run to become terminal, repairs failures, reruns, then verifies merged mainline.
- Persistent state changes require save/reload tests.
- Simulation changes require deterministic evidence.
- UI changes require real FreeCAD/Xvfb coverage.
- PR #160's terminal GUI failure was inspected through its uploaded diagnostic artifact; the failure occurred immediately after Simulation workbench activation. The corrected Create Drape command no longer performs an implicit 30-step simulation.

## Current state

The roadmap is now v3. **The project is not release-complete.** P0-A and P0-B remain the primary integration blockers. PR #185 is the P0-A validation vehicle; PR #192 is the P0-B/#161 validation vehicle. Neither is merge-approved until its complete canonical CI is terminal-green. P1 export and pattern-authoring gates follow P0.
