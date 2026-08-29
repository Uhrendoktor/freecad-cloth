# AGENT STATUS

## Supervisor

- Active milestone: P0 end-to-end release audit and simulation-quality completion.
- Mainline contains three integrated FreeCAD workbenches: Cloth Pattern, Cloth Sewing, and Cloth Simulation.
- M1 semantic sewing core (#144) and its UI completion (#152) are merged.
- M3 avatar arrangement/fitting (#146) is already merged into mainline and must now be audited against the revised release gates.
- Latest mainline CI evidence is green on commit `672867f4b3ab1adfa0bedb03c912eba9d061c25b` (canonical workflow run `33269282697`).

## Current task board

- #143 P0 end-to-end release-blocking workflow audit — active supervisor gate.
- #145 P0 simulation quality/material controls — active supervisor implementation branch `supervisor/145-simulation-quality`; queued behind the current audit findings.
- #147 P1 production CAD export and semantic round-trip validation — queued.
- #148 P2 optional native solver benchmark — explicitly non-blocking.
- #152 P0 Free Sewing/M:N UI completion — completed and closed after PR #154.

Issues #144 and #146 are completed in mainline. New work must update this section before handoff; a branch or green CI run alone is never completion.

## Replan decision

The previous roadmap was too feature-list oriented. The release path is now governed by the native FreeCAD workflow:

`Pattern authoring -> Sewing (including M:N/free sewing) -> Avatar arrangement -> Simulation quality controls -> Save/reload -> deterministic re-simulation -> production 2D export.`

Research treats CLO and Marvelous Designer as workflow references, especially free/M:N sewing, particle-distance quality tiers, arrangement points/bounding volumes, wrap direction, skin offset, reusable assets, and property-editor-driven simulation controls. Tissu/PositionBasedDynamics remain optional backend candidates until benchmarked.

## Completed since replan

- Roadmap and research documents replaced with release-oriented milestones.
- M:N/free-sewing semantic graph merged and covered by regression tests.
- Native Sewing UI now exposes Free Sewing and a persistent M:N/free-sewing range editor.
- Avatar arrangement points, bounding volumes, symmetry and deterministic placement/reset behavior are present in mainline.
- Canonical CI remains the sole workflow and is green through real FreeCAD smoke and GUI/Xvfb.

## Remaining release gates

1. Finish #143 end-to-end audit. The audit must exercise a real multi-piece garment, curved seams, invalidation after edits, save/reload, and repeatable simulation.
2. Complete #145: particle-distance quality controls must materially and predictably affect simulation mesh/solver quality, with persisted fabric properties, collision/skin offset and GUI lifecycle.
3. Complete #147: production-oriented 2D CAD export with semantic round-trip validation.
4. Run #148 only after the release path is stable; external native solver dependencies remain optional.

## Verification gates

- Canonical GitHub Actions workflow only; no duplicate workflow files.
- Python 3.10/3.11/3.12 core, geometry, benchmark, syntax, and package checks green.
- Real FreeCAD runtime smoke must load the workbenches and exercise document operations.
- GUI Xvfb scenario must exercise Pattern, Sewing, Simulation activation, task panels, seam creation/editing, simulation controls, and screenshot artifacts.
- New persistent state requires save/reload tests.
- Simulation changes require deterministic benchmark/regression evidence.
- Supervisor inspects PR diffs/reviews, waits for every CI run to become terminal, repairs failures, verifies merged mainline, and only then closes the implementation issue.

## Final state

The roadmap replan is integrated. The project is **not yet release-complete**: #143 and #145 are the current P0 gates. Do not declare completion until those gates, #147, and the final end-to-end CI/release audit are green.
