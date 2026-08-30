# 2026 CLO / FreeCAD Cloth Research Notes

Date: 2026-08-30

## Research scope

The release target is not feature-count parity with CLO. The useful target is the smallest open-source workflow that preserves the behaviors users depend on when drafting, sewing, fitting, and manufacturing garments.

### CLO behaviors confirmed from current official help

- **2D and 3D sewing are coupled.** Segment Sewing creates paired sewing lines from pattern segments and reflects them in both 2D and 3D. Free Sewing allows arbitrary start/end ranges on outlines and internal lines. M:N Segment and M:N Free Sewing explicitly support multiple-to-multiple relationships. Direction/notch orientation matters because crossing directions can reverse a pattern during simulation.
- **Particle Distance is a first-class quality control.** CLO describes it as the average mesh-point distance; larger values speed garment construction/simulation, while values below roughly 5 mm are used for higher final quality. The setting lives with simulation properties rather than being an implementation-only solver parameter.
- **Arrangement is part of the fitting workflow.** CLO uses avatar Arrangement Points to place pattern pieces in repeatable 3D starting positions and uses them for automatic sewing workflows. This is stronger than a one-off transform because placement has semantic meaning.
- **Avatar fitting is measurement-driven.** Current CLO documentation exposes avatar sizing/fitting and supports fitting workflows after avatar-size changes. This reinforces the decision that the FreeCAD mannequin's saved anthropometric properties must be authoritative, with the collision/visual mesh derived from them.
- **Grading is a production feature, not just scaling.** Current CLO grading exposes per-size distance/offset values, grade points, notch grading, reverse direction, copy/paste, alignment and irregular grading. This belongs after the core P0 garment loop but must be represented in the document model so later implementation does not require redesigning PatternPiece semantics.
- **The broader product separates drafting, sewing, simulation, avatar, grading and production tooling.** The FreeCAD design should therefore use three workbenches with explicit boundaries rather than a single monolithic task panel.

Primary CLO references:
- https://support.clo3d.com/hc/en-us/articles/360007863993-3D-Sewing
- https://support.clo3d.com/hc/en-us/articles/360001771047--3D-Tool-Segment-Sewing
- https://support.clo3d.com/hc/en-us/articles/360001754628--3D-Tool-Free-Sewing
- https://support.clo3d.com/hc/en-us/articles/360001754668--3D-Tool-M-N-Free-Sewing
- https://support.clo3d.com/hc/en-us/articles/115000414447-Particle-Distance-Setting
- https://support.clo3d.com/hc/en-us/articles/360053353574-Auto-Sewing-ver-6-0
- https://support.clo3d.com/hc/en-us/articles/360034333053-Auto-Fitting
- https://support.clo3d.com/hc/en-us/articles/115015798567-Set-Grading

## FreeCAD capability mapping

FreeCAD already supplies the appropriate foundations:

| Garment requirement | Native FreeCAD facility | Cloth responsibility |
| --- | --- | --- |
| Parametric 2D geometry | Sketcher::SketchObject | PatternPiece identity/semantics |
| Constraints/dimensions | Sketcher constraints + expressions | Measurement-driven pattern helpers |
| CAD curves/offsets/intersections | Part / OpenCascade | Seam allowance and derived inspection geometry |
| Persistent object graph | DocumentObject, Links, Groups, Placement, recompute | Semantic references/invalidation policy |
| Solver mesh | Mesh / MeshPart | PatternIR -> mesh adapter |
| 3D target geometry | Part/PartDesign/Mesh | DrapeTarget abstraction |
| Human fitting target | Native Cloth mannequin | Anthropometric model and derived collision surface |
| Production drawings | TechDraw | Garment-specific export orchestration/metadata |
| DXF/SVG | TechDraw APIs | Correct garment layers/marks and round-trip tests |

A native Sketcher SketchObject is already a Part2DObject with geometry, constraints and external geometry. It should remain the authoritative pattern source rather than being mirrored by a custom sketch kernel.

TechDraw can project geometry and export DXF/SVG, so production output should build on it where practical instead of implementing a second exporter.

Primary FreeCAD references:
- https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Sketcher_SketchObject.md
- https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Sketcher/App/SketchObject.cpp
- https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/TechDraw_Workbench.md
- https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/TechDraw_API.md

## Replan decisions

1. **Keep three native workbenches.** Pattern owns construction, Sewing owns assembly semantics, Simulation owns fitting/physics.
2. **Do not build a CLO-style duplicate 2D CAD editor.** Native Sketcher remains the editor; Cloth adds pattern-specific semantic commands and overlays.
3. **Promote arrangement points to a P0 simulation concept.** They are the bridge between 2D pieces and a deterministic 3D initial state.
4. **Treat seam allowance, notches, grainline and internal marks as persistent semantic derived objects.** They are required for a useful pattern workbench even before full grading/export parity.
5. **Make DrapeTarget solver-authoritative.** The mannequin is one provider; arbitrary FreeCAD geometry is another. Simulation must not depend on an AvatarProxy implementation detail.
6. **Make lifecycle/status explicit.** Run/Step/Reset, invalidation reasons, mesh quality and collision state must be visible and deterministic.
7. **Defer optional solver backends.** The CPU reference path is the correctness oracle until all P0/P1 acceptance is green.
8. **Use one canonical CI workflow.** Any CI repair must be validated through a PR-triggered canonical run; bot-created commits do not provide adequate execution evidence.

## Release sequence

### P0-1: Integration foundation
- canonical create -> edit -> sew -> arrange -> drape fixture
- native Sketcher authority and stable semantic references
- explicit invalidation chain
- save/reload continuation

### P0-2: Sewing completion
- curved correspondence in task panel
- 1:1, 1:N and M:N editing
- reverse/alignment controls
- actionable invalid-reference repair

### P0-3: Simulation completion
- DrapeTarget as authoritative input
- mannequin and arbitrary FreeCAD geometry targets
- arrangement points
- preview/final particle-distance presets
- lifecycle/status/pinning/diagnostics

### P0-4: Pattern production minimum
- seam allowance
- notches
- grainline
- internal marks/fold/dart metadata
- validation and derived inspection geometry

### P1: Manufacturing parity
- grading/size groups
- measurement-driven helpers
- richer seam allowance corner handling
- production TechDraw/DXF/SVG export and round-trip tests

### P2: Performance and advanced features
- optional native solver benchmarks
- advanced avatar/pose features
- multiple collision targets
- advanced modular/auto-sewing workflows

## Acceptance rule

A feature is not complete merely because a Python module or utility script exists. Every P0 feature must be reachable through a registered FreeCAD workbench command/task-panel/document-object workflow and covered by both headless tests and a real FreeCAD/Xvfb scenario where the feature affects the user-visible workflow.
