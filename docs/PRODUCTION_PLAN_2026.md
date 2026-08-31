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
- **Task panels are workflow editors, not second data models.** Apply/Cancel stages edits; persistent document properties remain authoritative.
- **Common actions use common placement.** Create/Edit, Apply/Rebuild, Preview/Run, Reset and Fit View should use the same hierarchy across Pattern, Sewing, Fitting and Simulation.

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
- Transactional selection: preview candidates, Enter commits, Delete undoes the last selection, Esc cancels the operation.

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

CLO treats seam allowance, notches, grading and DXF interchange as first-class pattern-production concerns. Sources: CLO Help Center articles on 2D Pattern DXF Import/Export and Set Grading.

### Sewing

- Segment sewing.
- Free sewing.
- 1:N and M:N sewing.
- Length-aware correspondence and alignment.
- Reverse/repair diagnostics.
- Seam groups and construction kinds.
- Visual seam direction and mismatch indicators.
- Check-sewing-length validation before simulation.

Current CLO documentation exposes Segment Sewing, Free Sewing, M:N Segment Sewing and M:N Free Sewing; M:N workflows use explicit selection completion and allow Delete/Esc cancellation, while unsuitable segments are visibly rejected. citeturn0search2turn0search0turn0search8

### Fitting / arrangement

- Mannequin measurement presets.
- Stable arrangement points.
- Pattern placement gizmo.
- Wrap-direction control.
- Layer/sublayer and basic superimpose behavior.
- Reset-to-2D arrangement.

Arrangement points and 3D arrangement are central to the comparable workflow, while reset/superimpose operations help control layered garments.

### Simulation

- Particle-distance presets.
- Fabric density/thickness/stretch/shear/bend/friction.
- Collision thickness/quality.
- Pinning.
- Deterministic step/run/reset.
- Simulation status and stale-state diagnostics.

Particle distance is explicitly a quality/speed control in CLO.

### MVP exit criteria

A user can design a modest garment, use common sewing relationships, fit it to a human or arbitrary CAD target, control simulation quality/materials, diagnose fit problems, save/reload safely, and export production-oriented 2D data.

## Production phase

Goal: reliable daily-use workbench with manufacturability and fit-analysis workflows.

### Human avatar

Use a provider/fidelity ladder rather than tying the workbench to one body generator:

1. **MVP mannequin:** deterministic FreeCAD-native parametric human with measurements, landmarks, collision surface and a small set of fitting poses.
2. **Production mannequin:** improved human proportions, joint/pose controls, measurement validation and richer collision representation while preserving the same `AvatarService`/DrapeTarget contract.
3. **Optional high-fidelity provider:** replaceable body-generation service for more detailed anatomy or external model import, without changing Pattern/Sewing/Simulation APIs.

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
- Exportable diagnostic images/data.

CLO documents fit-map workflows covering stress and fit, and current documentation also exposes strain-map analysis. citeturn0search9

### Production/manufacturing

- Multi-size grading and grading review.
- DXF-AAMA/ASTM and standard DXF interoperability where licensing permits.
- Nesting/layout planning.
- Plot/print output.
- Pattern labels and annotations.
- Shrinkage/compensation metadata.
- Production validation report.

Current CLO documentation treats grading and DXF interoperability as explicit production workflows; current DXF export supports AAMA, ASTM and Standard DXF variants and size/grading options. citeturn0search3turn0search6

### Advanced garment construction

After the production baseline is stable:

- Pleats/folds and fullness.
- Topstitch visualization.
- Buttons/buttonholes and tacks.
- Linings/facings and layered garments.
- Modular blocks.
- Automatic sewing helpers.
- POM/measurement objects and reports.
- Garment fit maps and measurement reports.
- Lacing/gluing only where they map cleanly onto the existing semantic garment model.

Current CLO's manual index demonstrates that these are separate workflow families rather than reasons to couple them into the core solver: sewing, grading, POM, pleats/folds, lacing/gluing, simulation and fit maps are exposed as distinct tools. citeturn0search11

## Recommended implementation order

1. **Release gate first:** fix current simulation tessellation/quality and stale-target issues.
2. **Canonical workflow:** maintain create → sew → arrange → simulate → save/reload → edit/invalidate → rebuild.
3. **Sewing MVP:** complete 1:N/M:N/free sewing, cancellation and repair UX.
4. **Avatar MVP:** finish the parametric human mannequin and arrangement points; lock the provider contract with canonical acceptance.
5. **Generic target:** finish DrapeTarget so arbitrary FreeCAD geometry is a first-class peer to the mannequin.
6. **Simulation quality:** particle distance + physical fabric properties + fit diagnostics.
7. **Pattern production:** grading, seam allowance/notches, labels, DXF/2D export and manufacturing checks.
8. **Production avatar fidelity:** improve the body provider only after the target-neutral contract and end-to-end workflow are stable.
9. **Advanced construction:** folds, topstitch, buttons/tacks, modular blocks, POM and layered construction.
10. **Optional solver backends:** benchmark only after deterministic CPU production behavior is stable.

## Feature triage rule

A proposed feature is a **prototype** feature if it proves an architecture boundary or user interaction; an **MVP** feature if it is required for a repeatable garment workflow; and a **production** feature if it improves manufacturing, diagnostics, fidelity or advanced construction without changing the authoritative Pattern/Sewing/DrapeTarget contracts.

New features must answer four questions before implementation:

1. What persistent document object/property is authoritative?
2. Which existing boundary does it consume (`Sketcher`, `PatternPiece`, `SewingGraph`, `DrapeTarget`, `CollisionSurface`, simulation result)?
3. What invalidates it, and what visible recovery state exists?
4. What public-workbench/Xvfb acceptance scenario proves it without adding a second CI workflow?

## What not to do yet

- Do not replace native Sketcher with a custom constraint/drafting kernel.
- Do not make the mannequin the solver's special case.
- Do not add a second scene graph.
- Do not optimize CI by replacing the canonical GUI/PNG workflow without a dedicated release decision.
- Do not add every CLO feature before the end-to-end garment workflow is robust.
- Do not add GPU/native solver dependencies before the CPU reference workflow is release-stable.
- Do not pursue photorealistic/high-poly avatar work until the low-cost mannequin provider is accepted as a stable DrapeTarget provider.

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
