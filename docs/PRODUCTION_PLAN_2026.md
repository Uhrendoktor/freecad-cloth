# Cloth Workbenches: Prototype → MVP → Production

## Product goal

Provide a FreeCAD-native garment workflow that feels like a focused CLO/Marvelous Designer workbench without replacing FreeCAD's strengths.

The primary flow is:

`Pattern → Sewing → Fitting/Arrangement → Simulation → Fit/Manufacturing output`

The document remains authoritative. Derived meshes, collision surfaces and simulation state are rebuildable.

## UI/UX principles

- **One obvious next action.** Each task panel should expose the primary workflow action first.
- **Icons for actions, text for data.** Keep standard FreeCAD OK/Cancel and native property controls.
- **2D and 3D stay synchronized.** A selected seam/pattern element should be identifiable in both views where practical.
- **Persistent state is inspectable.** Important relationships belong in the document tree and Property Editor, not only in transient task panels.
- **Fail visibly and explain why.** Stale pattern, seam, mesh or collision state must expose a reason and a recovery action.
- **Selection should be reversible.** Preview candidate seams/targets before committing; Esc/Delete should cancel staged sewing operations.
- **Quality is explicit.** Preview/Normal/Final simulation quality should change mesh density/solver cost predictably.
- **Units are visible.** Anthropometric and fabric values must use meaningful FreeCAD units.

## Prototype phase

Goal: prove the architecture and interaction model, not feature completeness.

### Pattern

- Native Sketcher-backed PatternPiece.
- Basic outline/curve editing.
- Semantic marks: grainline, notch, internal mark.
- Basic seam allowance.
- Deterministic 2D inspection.

### Sewing

- Segment sewing and free sewing.
- Explicit direction/reversal.
- Curved correspondence diagnostics.
- Persistent seam objects.
- Early M:N representation even if the UI is limited.

### Fitting / simulation

- Persistent DrapeTarget abstraction.
- Parametric mannequin provider.
- Generic Part/PartDesign/Mesh target provider.
- Deterministic arrangement via FreeCAD Placement.
- Preview mesh and deterministic CPU reference simulation.

### Prototype exit criteria

A small two-to-four-piece garment can be created, sewn, arranged on a mannequin or arbitrary FreeCAD object, simulated, saved/reloaded, edited upstream, invalidated deterministically, rebuilt and simulated again.

## MVP phase

Goal: usable for real garment experimentation and repeatable engineering workflows.

### Pattern authoring

- Robust Sketcher authority and semantic edge identity.
- Seam allowance editing and validation.
- Notches with stable references.
- Grainline and internal marks.
- Mirror/transform.
- Basic grading/size parameters.
- DXF/SVG/TechDraw-oriented export path.

CLO's current production workflow treats seam allowance, notches, grading and DXF interchange as first-class pattern concerns. citeturn0search2turn0search7turn0search9turn0search12

### Sewing

- Segment sewing.
- Free sewing.
- 1:N and M:N sewing.
- Length-aware correspondence and alignment.
- Reverse/repair diagnostics.
- Seam groups and construction kinds.
- Visual seam direction and mismatch indicators.

CLO exposes segment, free, 1:N and M:N sewing, including interactive selection and explicit direction handling. citeturn1search1turn1search5turn1search10turn1search16

### Fitting / arrangement

- Mannequin measurement presets.
- Stable arrangement points.
- Pattern placement gizmo.
- Wrap-direction control.
- Layer/sublayer and basic superimpose behavior.
- Reset-to-2D arrangement.

Arrangement points and 3D arrangement are central to the comparable workflow, while reset/superimpose operations help control layered garments. citeturn0search1turn0search5turn0search8turn0search11turn0search14

### Simulation

- Particle-distance presets.
- Fabric density/thickness/stretch/shear/bend/friction.
- Collision thickness/quality.
- Pinning.
- Deterministic step/run/reset.
- Simulation status and stale-state diagnostics.

Particle distance is explicitly a quality/speed control in CLO-style workflows. citeturn1search15

### MVP exit criteria

A user can design a modest garment, use common sewing relationships, fit it to a human or arbitrary CAD target, control simulation quality/materials, diagnose fit problems, save/reload safely, and export production-oriented 2D data.

## Production phase

Goal: reliable daily-use workbench with manufacturability and fit-analysis workflows.

### Human avatar

- Measurement-driven parametric body.
- Named anthropometric landmarks.
- Pose presets and controlled joint parameters.
- Visual mesh separate from collision mesh.
- Measurement validation and presets.
- Replaceable body-generation service so higher-fidelity models can be added without changing Sewing/Simulation APIs.

Do not make Blender, MakeHuman or another external runtime a hard dependency.

### Generic drape targets

- Any usable FreeCAD Shape/Mesh as a target.
- Persistent target link and tessellation settings.
- Deterministic invalidation on geometry/Placement changes.
- Optional face/subelement selection later.
- Target groups later (mannequin + chair + floor, etc.).

The mannequin and arbitrary CAD object should be two providers of the same target-neutral collision contract, not two solver implementations.

### Fit analysis

- Stress map.
- Strain map.
- Fit/tightness map.
- Pressure map.
- Point inspection with numerical values.

CLO's fit-map workflow exposes stress, strain, fit and pressure views; its newer strain map also relates results to fabric stretch limits. citeturn1search0turn1search14

### Production/manufacturing

- Multi-size grading and grading review.
- DXF-AAMA/ASTM and standard DXF interoperability where licensing permits.
- Nesting/layout planning.
- Plot/print output.
- Pattern labels and annotations.
- Shrinkage/compensation metadata.
- Production validation report.

Current CLO documentation treats grading, DXF export and nesting as manufacturing workflows rather than simulation-only features. citeturn0search2turn0search7turn0search19

### Advanced garment construction

After the production baseline is stable:

- Pleats/folds.
- Topstitch visualization.
- Buttons/buttonholes and tacks.
- Linings/facings and layered garments.
- Modular blocks.
- Automatic sewing helpers.
- Garment fit maps and measurement reports.

These should remain layered features over the stable Pattern/Sewing/Simulation contracts rather than changing those contracts.

## Recommended implementation order

1. **Release gate first:** fix current simulation tessellation/quality and stale-target issues.
2. **Canonical workflow:** maintain create → sew → arrange → simulate → save/reload → edit/invalidate → rebuild.
3. **Sewing MVP:** complete 1:N/M:N/free sewing and repair UX.
4. **Avatar MVP:** finish the parametric human mannequin and arrangement points.
5. **Generic target:** finish DrapeTarget so arbitrary FreeCAD geometry is a first-class peer to the mannequin.
6. **Simulation quality:** particle distance + physical fabric properties + fit diagnostics.
7. **Pattern production:** grading, export, labels, manufacturing checks.
8. **Advanced construction:** folds, topstitch, buttons/tacks, modular blocks.
9. **Optional solver backends:** benchmark only after deterministic CPU production behavior is stable.

## What not to do yet

- Do not replace native Sketcher with a custom constraint/drafting kernel.
- Do not make the mannequin the solver's special case.
- Do not add a second scene graph.
- Do not optimize CI by replacing the canonical GUI/PNG workflow without a dedicated release decision.
- Do not add every CLO feature before the end-to-end garment workflow is robust.
- Do not add GPU/native solver dependencies before the CPU reference workflow is release-stable.

## Agent handoff contract

Every implementation issue should state:

- authoritative data model/API;
- files allowed to change;
- dependencies on other issues;
- required unit tests;
- required real-FreeCAD/Xvfb acceptance;
- screenshot/artifact expectations;
- explicit non-goals;
- whether canonical CI must remain byte-for-byte unchanged.

The supervisor merges only after those acceptance conditions are evidenced.
