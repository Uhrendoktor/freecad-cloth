# AGENT STATUS

## Supervisor

- Active milestone: P0 end-to-end release audit and simulation-quality completion.
- Mainline contains three integrated FreeCAD workbenches: Cloth Pattern, Cloth Sewing, and Cloth Simulation.
- M1 semantic sewing core (#144) and its UI completion (#152) are merged.
- M3 avatar arrangement/fitting (#146) is merged and remains under end-to-end audit.
- Simulation-quality parameter contract (#156) is merged; native workbench wiring is now #159.

## Current task board

- #143 P0 end-to-end release-blocking workflow audit — active supervisor gate.
- #145 P0 simulation quality/material controls — parent gate; implementation split into #156 and #159.
- #155 P0 canonical end-to-end garment fixture and FreeCAD GUI workflow test — active execution task under #143.
- #156 P0 simulation quality/fabric parameter model — first slice merged; keep parent #145 open until native behavior is complete.
- #159 P0 wire SimulationQuality into native Simulation object/task panel/meshing/solver lifecycle — next active implementation task.
- #147 P1 production CAD export and semantic round-trip validation — queued behind P0.
- #148 P2 optional native solver benchmark — explicitly non-blocking.

Issues #144 and #146 are completed in mainline. New work must update this section before handoff; a branch, PR, or green CI run alone is never completion.

## Replan decision

The previous roadmap was too feature-list oriented. The release path is governed by the native FreeCAD workflow:

`Pattern authoring -> Sewing (including M:N/free sewing) -> Avatar arrangement -> Simulation quality controls -> Save/reload -> deterministic re-simulation -> production 2D export.`

Research treats CLO and Marvelous Designer as workflow references, especially free/M:N sewing, particle-distance quality tiers, arrangement points/bounding volumes, wrap direction, skin offset, reusable assets, and property-editor-driven simulation controls. Tissu/PositionBasedDynamics remain optional backend candidates until benchmarked.

## Completed since replan

- Roadmap and research documents replaced with release-oriented milestones.
- M:N/free-sewing semantic graph merged and covered by regression tests.
- Native Sewing UI exposes Free Sewing and a persistent M:N/free-sewing range editor.
- Avatar arrangement points, bounding volumes, symmetry and deterministic placement/reset behavior are present in mainline.
- A stable, validated Fast/Balanced/Final simulation-quality and fabric-parameter contract is now in mainline.
- Canonical CI remains the sole workflow and covers real FreeCAD smoke and GUI/Xvfb.

## Remaining release gates

1. Finish #143 using #155: real multi-piece garment, curved seams, invalidation, save/reload and repeatable simulation.
2. Complete #145 through #159: quality presets must materially change discretization/solver behavior; fabric/collision controls must persist and invalidate cached simulation state; GUI must expose the lifecycle.
3. Complete #147: production-oriented 2D CAD export with semantic round-trip validation.
4. Run #148 only after the release path is stable; external solver dependencies remain optional.

## Verification gates

- Canonical GitHub Actions workflow only; no duplicate workflow files.
- Python 3.10/3.11/3.12 core, geometry, benchmark, syntax, and package checks green.
- Real FreeCAD runtime smoke must load the workbenches and exercise document operations.
- GUI Xvfb scenario must exercise Pattern, Sewing, Simulation activation, task panels, seam creation/editing, simulation controls, and screenshot artifacts.
- New persistent state requires save/reload tests.
- Simulation changes require deterministic benchmark/regression evidence.
- Supervisor inspects PR diffs/reviews, waits for every CI run to become terminal, repairs failures, verifies merged mainline, and only then closes implementation issues.

## Final state

The roadmap replan is integrated. The project is **not yet release-complete**: #143, #145, and #159 remain P0 gates, with #147 required before release. Do not declare completion until the full end-to-end and export gates are green.