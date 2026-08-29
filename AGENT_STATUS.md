# AGENT STATUS

## Supervisor

- Active milestone: release-candidate verification for the CLO-style sewing workbench suite.
- Pattern, Sewing, and Simulation workbenches are integrated on `main`.
- Parent UI audit #119 and GUI regression #126 are completed.
- Pattern UI #121, sewing-edge regression #98, and workbench command-contract #137 are integrated.

## Architecture / data flow

- Pattern geometry and semantic sewing data are authoritative FreeCAD document objects plus FreeCAD-independent model layers.
- Pattern -> Sewing -> Simulation is the end-to-end workflow; generated simulation meshes are disposable adapters, not a second source of truth.
- Native FreeCAD Sketcher/Part/OCCT/MeshPart/Placement and document recompute/save/reopen mechanisms are reused at the boundary.
- Sewing uses canonical semantic seam metadata, deterministic arc-length edge sampling, reversal/alignment, stitch groups, and placement-aware correspondence.
- Simulation exposes fabric presets/properties, solver controls, collision thickness/deflection, avatar/collision selection, sewing pairs, pin selection, step/run/reset controls, and deterministic CPU cloth behavior.

## CLO-style research decisions

- 2D pattern authoring and 3D simulation are intentionally separated, matching CLO's workflow model.
- Important CLO concepts mapped into FreeCAD include pattern properties, seam/sewing semantics, notches/grainlines, arrangement/fitting metadata, fabric physical properties, collision thickness, simulation presets, and persistent project data.
- Optional external solver backends remain optional; the bundled deterministic CPU solver is the reference path so the workbench remains installable without proprietary or heavyweight dependencies.
- Future roadmap items such as M:N/free sewing gestures, richer arrangement-point editing, particle-distance presets, and DXF/SVG/TechDraw export remain explicitly documented rather than blocking the current usable workbench.

## Verification gates

- Canonical GitHub Actions workflow only; no duplicate workflow files.
- Python 3.10/3.11/3.12 core, geometry, benchmark, syntax, and package checks are required green.
- Real FreeCAD runtime smoke must load the workbenches and exercise document operations.
- GUI Xvfb scenario must exercise Pattern, Sewing, and Simulation workbench activation, toolbars, task panels, seam/simulation objects, and screenshot artifacts.
- Final supervisor check includes repository diff/status, open PR/issue audit, save/reload coverage, and release documentation.

## Final state

All required implementation PRs have been reviewed and integrated or explicitly superseded. Closed PRs that were stale/redundant were not merged. CI evidence is retained in the canonical workflow artifacts.
