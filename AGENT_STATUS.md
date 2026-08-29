# AGENT STATUS

## Supervisor

- Active milestone: **P0 vertical release gates** — native end-to-end workflow plus behavioral simulation-quality controls.
- Mainline contains three registered FreeCAD workbenches: Cloth Pattern, Cloth Sewing, and Cloth Simulation.
- M:N/free sewing and fitting arrangement work are merged.
- Simulation-quality/fabric parameter contract is merged, but native behavioral wiring is not yet release-complete.
- Production SVG/DXF semantic metadata exists, but export validation is still a release gate.

## Current task board

- **#143** P0 end-to-end workflow audit — supervisor gate.
- **#155 / closed PR #160 / open PR #185** P0 canonical native garment fixture and GUI/Xvfb workflow — active supervisor validation. PR #160 exposed real GUI failures; PR #185 contains the corrected E2E bootstrap and non-blocking Create Drape command fix. Merge only after a fresh terminal-green CI run for the corrected head.
- **#145 / #159 / #161** P0 simulation quality — active; #159 is claimed by Uhrendoktor in `agent/159-simulation-quality`.
- **#147 / #163** P1 production 2D export — queued behind P0; current metadata work is a foundation, not completion.
- **#162** P1 pattern authoring parity audit — queued; research-driven audit of curved authoring, constraints, marks, offsets and semantic preservation.
- **#148** P2 optional native solver benchmark — explicitly non-blocking.
- **#165** Architecture: FreeCAD-native Sketcher pattern authoring + semantic Cloth sewing layer — architecture documented; implementation follow-up must not duplicate the P0 audit.
- **#174** P1 PatternIR curved Sketcher adapter — claimed by Uhrendoktor in `agent/issue-174-pattern-ir-curves-standalone-20260829`; preserves native line/arc/BSpline/Bezier curve kind at the solver-neutral boundary and adds real FreeCAD smoke coverage.

Issues #144 and #146 are completed. Do not close parent issues merely because a branch, PR, or unit test is green.

## Replan v2 decision

The roadmap is organized around a native FreeCAD **vertical release slice** rather than a feature list:

`Pattern authoring -> 1:1 + free/M:N sewing -> avatar arrangement -> quality/material simulation -> inspect -> upstream edit -> invalidation -> save/reload -> deterministic re-simulation -> production 2D export.`

Research confirms that CLO/Marvelous Designer make semantic sewing, particle-distance quality control, Property Editor-driven simulation/material settings, and reproducible avatar arrangement first-class workflow concepts. FreeCAD Sketcher/Part/TechDraw should be reused instead of duplicating constraint, geometry and drawing systems.

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

1. **P0-A:** PR #185 proves the real public Pattern -> Sewing -> Simulation -> save/reload -> invalidation workflow on the corrected head.
2. **P0-B:** #161/#159 wire quality/material/collision properties into native simulation behavior and UI.
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

The roadmap replan is integrated. **The project is not release-complete.** P0-A remains the primary integration blocker, followed by P0-B/P0-C. PR #185 is the current validation vehicle; its CI has not yet been emitted by the GitHub connector after branch creation, so it must not be merged or declared green without an actual run. P1 export and pattern-authoring gates follow P0.
