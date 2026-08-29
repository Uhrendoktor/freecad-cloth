# AGENT STATUS

## Supervisor

- Active milestone: 2026 roadmap replan and release-gate definition.
- Mainline contains three integrated FreeCAD workbenches: Cloth Pattern, Cloth Sewing, and Cloth Simulation.
- Latest mainline CI evidence is green on commit `7a6817770d7b64530d6ba7f9cb4a5a2c1036ff41` (canonical workflow run `33265788791`).
- No open pull requests or open issues existed before this replan; issues #143–#148 now define the next supervised milestones.

## Current task board

- #143 P0 end-to-end release-blocking workflow audit — supervisor-owned.
- #144 P0 M:N and free-sewing editor — supervisor-owned until implementation delegation is available.
- #145 P0 simulation quality/material controls — supervisor-owned until implementation delegation is available.
- #146 P1 avatar arrangement-point/fitting layer — queued behind P0.
- #147 P1 production CAD export and semantic round-trip validation — queued behind P0.
- #148 P2 optional native solver benchmark — explicitly non-blocking.

If delegated execution becomes available, assign independent implementation milestones to separate agents and require each agent to update this section before handoff. Do not treat an issue, task record, branch, or queued workflow as completion.

## Replan decision

The previous roadmap was too feature-list oriented. The project is no longer at the skeleton stage, so the next phase is organized around proving a complete native FreeCAD garment workflow rather than accumulating commands. The release-critical path is now:

`Pattern authoring -> Sewing (including M:N/free sewing) -> Avatar arrangement -> Simulation quality controls -> Save/reload -> deterministic re-simulation -> production 2D export.`

Research now treats CLO and Marvelous Designer as workflow references, especially free/M:N sewing, particle-distance quality tiers, arrangement points/bounding volumes, wrap direction, skin offset, reusable assets, and property-editor-driven simulation controls. The open-source solver ecosystem confirms that stretch/shear/bend/self-collision/stitch constraints are appropriate backend concepts, while native Tissu/PositionBasedDynamics integration remains optional until benchmarked.

## Architecture / data flow

- Pattern geometry and semantic sewing data are authoritative FreeCAD document objects plus FreeCAD-independent model layers.
- Pattern -> Sewing -> Simulation is the end-to-end workflow; generated simulation meshes are disposable adapters, not a second source of truth.
- Native FreeCAD Sketcher/Part/OCCT/MeshPart/Placement and document recompute/save/reopen mechanisms are reused at the boundary.
- Sewing must evolve from robust 1:1 seam pairing to a canonical graph supporting free sewing and M:N relationships without losing deterministic edge correspondence.
- Simulation must expose production quality controls while retaining the deterministic CPU reference backend.

## Verification gates

- Canonical GitHub Actions workflow only; no duplicate workflow files.
- Python 3.10/3.11/3.12 core, geometry, benchmark, syntax, and package checks are required green.
- Real FreeCAD runtime smoke must load the workbenches and exercise document operations.
- GUI Xvfb scenario must exercise Pattern, Sewing, and Simulation activation, task panels, seam creation/editing, simulation controls, and screenshot artifacts.
- New persistent state requires save/reload tests.
- Simulation changes require deterministic benchmark/regression evidence.
- Supervisor must inspect PR diffs/reviews, wait for all CI runs to become terminal, repair failures, verify the merged mainline, and only then close implementation issues.

## Final state

Replanning is documented on branch `roadmap/replan-20260829`. It is not considered integrated until the branch CI is terminal and green, the PR is reviewed/merged, post-merge main CI is terminal and green, and the source branch is removed.
