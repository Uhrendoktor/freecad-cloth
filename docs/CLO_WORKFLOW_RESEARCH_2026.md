# CLO-like cloth workflow research — 2026-08-31

## Purpose

This document translates common CLO/Marvelous Designer garment-workflow capabilities into FreeCAD-native product requirements. It is a workflow reference, not a feature checklist to implement wholesale.

The architectural rule remains:

> FreeCAD owns geometry and document state; Cloth owns garment semantics; the solver owns physics.

## Research observations

### Pattern production

A production garment workflow needs more than closed outlines:

- curved editable geometry;
- dimensional/geometric constraints;
- seam allowance;
- notches and directional marks;
- grainline/internal marks;
- mirror/transform;
- grading/size sets;
- validation before simulation/export;
- industrial interchange such as Standard DXF, DXF-AAMA and DXF-ASTM where licensing and implementation permit.

CLO's current DXF documentation explicitly covers AAMA/ASTM/Standard DXF, grading, annotations, notches, seam allowance, curve optimization and selected-pattern export. This supports treating pattern production as a first-class workbench concern rather than a simulation afterthought.

Reference: https://support.clo3d.com/hc/en-us/articles/115000493067-2D-Pattern-DXF-Import-Export

### Sewing

A useful sewing workbench should support a progression from simple to complex relationships:

1. segment-to-segment;
2. free sewing along partial edges;
3. 1:N;
4. M:N;
5. explicit direction/reversal;
6. length-aware correspondence and mismatch diagnostics;
7. persistent seam groups/construction semantics.

CLO documents Segment Sewing, Free Sewing, M:N Segment Sewing and M:N Free Sewing as separate workflows. Its M:N workflow also makes cancellation and invalid selection explicit during staged selection.

References:
- https://support.clo3d.com/hc/en-us/articles/360007863993-3D-Sewing
- https://support.clo3d.com/hc/en-us/articles/360001754668--3D-Tool-M-N-Free-Sewing
- https://support.clo3d.com/hc/en-us/articles/115000497727--2D-Tool-M-N-Segment-Sewing

### Fitting and arrangement

The user needs a clear distinction between:

- 2D pattern state;
- 3D arrangement state;
- collision target;
- simulated garment state.

The mannequin is important for garment fitting, but it should be a provider of a target-neutral collision interface rather than a solver special case. The same interface should accept a Part/PartDesign/Mesh object for non-human draping.

CLO's fitting guidance explicitly separates creating/draping the garment from fit inspection and uses alignment aids plus fit, stress and strain views. This suggests that arrangement and fit diagnostics should be first-class workflow stages rather than hidden solver options.

Reference: https://support.clo3d.com/hc/en-us/articles/115013660447-How-do-you-fit-3D-Garments-in-CLO

### Simulation and fit analysis

Simulation controls should expose meaningful physical and quality parameters rather than arbitrary solver knobs:

- particle/mesh distance;
- fabric density and thickness;
- stretch, shear and bending behavior;
- friction;
- collision thickness/quality;
- substeps/iterations;
- pinning;
- deterministic Step / Run / Reset;
- visible stale/invalid state.

Fit analysis should eventually provide at least:

- stress;
- strain;
- fit/tightness;
- pressure;
- point inspection with numerical values;
- fabric-specific stretch limits where the material model supports them.

CLO documents four garment fit maps: Stress, Strain, Fit and Pressure. Its 2026 strain-map documentation also distinguishes a global scale from a fabric-specific stretch limit and supports point inspection of actual stretch/force values. These are strong arguments for a later solver-neutral diagnostic layer consuming simulation results instead of embedding visualization logic in the solver.

References:
- https://support.clo3d.com/hc/en-us/articles/360000436368-Garment-Fit-Maps
- https://support.clo3d.com/hc/en-us/articles/56500755006617--Fit-Map-Strain-Map

## UI/UX model

### Workbench shell

Keep the three native workbenches, but make their task panels read as one product:

```text
Pattern
  Create / Edit / Validate
        ↓
Sewing
  Select A → Select B → Confirm / Repair
        ↓
Fitting
  Arrange → Choose Drape Target → Preview
        ↓
Simulation
  Quality / Fabric / Collision → Run
        ↓
Analysis / Production
  Fit maps / Measurements / Validation / Export
```

### Primary interaction rules

- One obvious next action in each task panel.
- Use icons for frequent actions; keep labels and tooltips for clarity.
- Keep standard FreeCAD OK/Cancel semantics.
- Show staged sewing/target selection before committing it.
- Esc cancels the staged operation; Delete removes the last staged selection where appropriate.
- Selected semantic objects should be identifiable in both 2D and 3D when practical.
- Important state must be visible in the document tree and Property Editor, not only in a transient task panel.
- Invalid derived state must show the reason and recovery action.
- Never silently retarget a seam or collision source after topology/geometry changes.
- Numeric controls must expose units.
- Preview/Normal/Final should communicate cost and quality rather than hiding them behind solver terminology.

## Feature inventory by maturity

### Prototype

- native Sketcher-backed pattern pieces;
- line + curve authoring through Sketcher;
- semantic seam objects;
- segment/free sewing;
- persistent DrapeTarget;
- parametric mannequin provider;
- arbitrary FreeCAD geometry target;
- deterministic arrangement;
- preview mesh;
- deterministic CPU simulation;
- save/reload and explicit invalidation.

### MVP

- 1:N and M:N sewing;
- curved seam correspondence diagnostics;
- seam allowance/notch/grainline/internal-mark visualization;
- Pattern validation;
- mirror/transform;
- basic grading;
- DXF/SVG/TechDraw output;
- arrangement points and placement gizmo;
- simulation quality/material presets;
- pinning and collision controls;
- simulation status diagnostics.

### Production

- measurement-driven human avatar with named landmarks and pose presets;
- replaceable avatar surface/collision generator;
- fit maps and numerical inspection;
- fabric-specific strain limits;
- grading review and manufacturing validation;
- industrial DXF interoperability where permitted;
- nesting/plot output;
- labels and annotations;
- shrinkage/compensation metadata;
- advanced construction such as pleats, folds, topstitching, buttons/tacks and layered garments.

## Correct implementation order

1. **Protect the release gate.** Fix simulation tessellation/quality and stale-target safety first.
2. **Prove one canonical garment.** Pattern → Sewing → Arrangement → Simulation → Save/Reload → Edit → Invalidate → Rebuild.
3. **Finish sewing MVP.** Especially 1:N/M:N, curved correspondence, direction and repair UX.
4. **Make the human avatar useful.** Measurements, landmarks, basic poses, visual/collision separation.
5. **Make arbitrary CAD targets first-class.** Mannequin and generic FreeCAD geometry share one DrapeTarget contract.
6. **Make simulation controllable.** Quality and material properties must have predictable effects and persistence.
7. **Add fit analysis.** Consume simulation results without creating a second solver or scene graph.
8. **Add manufacturing.** Grading, export, validation, nesting/plotting.
9. **Add advanced construction.** Only after the base contracts are stable.
10. **Benchmark optional native/GPU backends last.** The deterministic CPU reference path remains the production oracle until evidence proves otherwise.

## CI and release discipline

The canonical workflow is part of the product contract. Do not create parallel workflows and do not replace the GUI/Xvfb screenshot/export path with a lighter substitute.

The canonical workflow currently validates real FreeCAD GUI execution and exports 1280×720 PNG artifacts for Pattern, Sewing and Simulation states. Any future CI change must be narrowly scoped, preserve those artifacts, and be validated against the release gate.

## Agent handoff contract

Every implementation issue should identify:

- authoritative object/data model;
- exact files allowed to change;
- dependencies and sequencing;
- unit tests;
- real FreeCAD/Xvfb acceptance;
- screenshot/diagnostic artifacts;
- explicit non-goals;
- whether canonical CI must remain unchanged.

Do not implement a feature by adding a parallel geometry kernel, constraint solver, scene graph, or solver-specific avatar abstraction.
