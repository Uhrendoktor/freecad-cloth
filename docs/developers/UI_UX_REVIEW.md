# Cloth UI/UX review and implementation decisions

## Purpose and product model

This review audits the user-facing task panels, transient viewport controls and end-to-end garment workflow. It complements the [UI style guide](UI_STYLE_GUIDE.md): the style guide defines shared conventions; this document records the window-by-window decisions and the implementation gaps.

The guiding product rule is **FreeCAD-native task panels + purpose-built viewport interaction**. Do not introduce a second application shell, parallel object browser or modeless window for tasks that belong in the active document. Keep persistent data on document features and transient interaction geometry in the viewport.

## External reference study

| Product | Window and viewport model | Useful detail |
| --- | --- | --- |
| CLO | Avatar Size and Measure tabs plus direct 3D selection/editing | The size editor distinguishes editable from non-editable measures visually. The Measure tab lists active tapes and exposes name, Basic/Surface type, basic and surface lengths, Show and Show Length. A viewport edit tool selects a tape and highlights it; its properties remain in the editor. |
| Marvelous Designer | One Avatar Editor with Size, Measure, Arrangement, Fitting Suit and IK Joint tabs; measurement tapes are created and selected in the 3D view | Size supports presets, units, optional detail fields and linked/unlinked proportions. Measurement records can be renamed/deleted, refit to a changed pose/avatar, saved/opened, toggled in the viewport and inspected by basic/surface length. |
| Style3D Studio | Floating viewport toolbar for avatar visibility, arrangement points, skeleton, mesh/texture and measurement overlays; separate avatar/measurement tools | Scene visibility and spatial work stay near the viewport. Structured properties remain in a property editor. |
| FreeCAD | Native Combo View task panel, host palette and native dialog footer | Keep the current document/task context; use compact forms, responsive wrapping, native Qt widgets and progressive disclosure rather than a bespoke top-level window. |

References:
- [CLO: Edit Measurement](https://support.clo3d.com/hc/en-us/articles/360000013828-Edit-Measurement)
- [CLO: Adjust Avatar Size](https://support.clo3d.com/hc/en-us/articles/360013257553-Adjust-Avatar-Size)
- [Marvelous Designer: Avatar Editor (2025.0)](https://www.marvelousdesigner.com/en-gb/manuals/articles/47358128221337)
- [Style3D Studio: Avatar viewport tools](https://help.style3d.com/studio/en/c4905/c74f/0716/1baf/391f)
- [FreeCAD Developer Handbook: UI elements and task panels](https://freecad.github.io/DevelopersHandbook/designguide/elements.html)

The references converge on a hybrid workflow. A viewport-only measurement tool is quick but poor for a complete measurement specification; a property-only editor is precise but weak for spatial understanding. Cloth should keep both, linked to one canonical value.

### Findings applied across the window audit

- **Avatar Size and Measure:** Marvelous Designer separates size presets, editable/hidden measurement selection, width/height key measures, linked proportions and optional detail measurements. Its Measure tab lists tapes and exposes name, Basic/Surface type, basic/surface lengths, fit-to-avatar, visibility and label visibility. This supports keeping Cloth's canonical measurement fields in the task panel and its handles in the viewport, while reserving custom/free tape creation and tape management for a future separate workflow rather than mixing those concepts into body-size editing. Style3D similarly splits avatar properties from viewport toggles for avatar, arrangement points, skeleton, mesh and measurement lines.
- **Pattern and sewing:** CLO uses separate 2D pattern and 3D garment windows, with a selection-driven Property Editor. Sewing Lines are selected, moved and resized in the 2D window; precise length entry is available while dragging, while fold/tension/reversal and presentation settings live in the selected seam's property list. Marvelous Designer's Property Editor changes its property set based on the selected object and has distinct Pattern, Sewing, Stitch, Fabric, Avatar and Simulation properties. This supports Cloth's native Sketcher authority, viewport edge picks and one selected seam detail panel. It does not support a separate floating dialog for every selected seam.
- **Arrangement and fitting:** CLO's Auto 3D Arrangement is a short reviewable wizard with Proceed, stepwise Back/Next inspection and OK, while Smart Arrangement runs from the 3D garment context. Style3D places arrangement handles on the avatar and lets users drag them while exposing joint binding and dimensions in the property editor. Cloth's direct viewport drag is the right default for continuous placement; the task panel should handle target selection, snap state and recovery, and any future multi-piece solver should have a reviewable staged result rather than silently moving the garment.
- **Simulation:** Style3D starts simulation from its 3D window and distinguishes accurate, normal and CPU simulation modes, with visible simulation status. Marvelous Designer exposes simulation properties through a selection/context-driven property panel. Cloth should put a simple quality preset and target/readiness first, put solver detail behind Expert, and keep Run / Step / Reset close to the viewport rather than requiring users to navigate to a separate configuration window mid-run.
- **Export:** CLO starts PDF export from File → Export, then shows a format-specific options pop-up; its published AI/PDF import/export guide exposes scale and rotation for PDF. Cloth should keep the destination path beside Browse and show page size/overlap only for PDF; hidden units and low-frequency curve sampling should not consume prominent rows.
- **Diagnostics and viewport review:** CLO's interface overview separates 3D and 2D working windows, selected-object properties, vertical view toggles and fit-map tools. Style3D exposes simulation status and avatar/mesh overlays from the 3D context. These patterns support explicit orientation/view toggles when the task is a repeatable inspection, while keeping the generic CAD camera controls for normal navigation.

Additional official references:
- [Marvelous Designer: Avatar Editor, Size/Measure/Arrangement tabs](https://www.marvelousdesigner.com/en-gb/manuals/articles/47358128221337)
- [Marvelous Designer: Edit Avatar Measurement properties](https://www.marvelousdesigner.com/en-sg/manuals/articles/47358335488537)
- [Marvelous Designer: Property Editor by selected asset type](https://support.marvelousdesigner.com/hc/en-us/articles/47358318005913-Property-Editor)
- [CLO: Edit Sewing in the 2D window and property panel](https://support.clo3d.com/hc/en-us/articles/115012380148-Edit-Sewing)
- [CLO: Edit Sewing property options](https://support.clo3d.com/hc/en-us/articles/115002324608-Edit-Sewing)
- [CLO: Auto 3D Arrangement review flow](https://support.clo3d.com/hc/en-us/articles/13200837772185-Auto-3D-Arrangement-ver-7-1)
- [Style3D: Avatar property and 3D viewport controls](https://help.style3d.com/studio/en/c4905/d2d78/313d5)
- [Style3D: 3D Simulation and Adjustment](https://help.style3d.com/studio/en/c4905/d2d78/19ef3)
- [CLO: PDF pattern export flow](https://support.clo3d.com/hc/en-us/articles/115004273427-2D-Pattern-AI-PDF-Import-Export)
- [CLO: interface overview](https://support.clo3d.com/hc/en-us/article_attachments/48293801440281)

## Global decisions

### Information hierarchy

Every task panel should present information in this order:

1. **Context and validity** — selected object/feature, target identity, current or stale state.
2. **Next action** — the one action that advances the current task.
3. **Spatial interaction and preview** — pick, drag, inspect, focus, preview or reset.
4. **Common editable values** — only the few settings needed for the normal workflow.
5. **Advanced / recovery controls** — expert settings, correspondence, repair, solver detail, provider-specific controls.

A status/readiness message should describe what blocks the next action and how to recover. Do not make users infer validity from button enablement or console output.

### Layout grammar

- Aim for the FreeCAD task-panel width (~360 px), but let it expand with font scale, DPI and translations. Use configure_form_layout and native expanding fields.
- Use a grid for repeated peer measurements (avatar values), two columns for a few independent values (width/height, start/end), and a single-column form for long semantic labels or a small number of dissimilar settings.
- Pair controls that form one concept: start/end for range A; start/end for range B; horizontal/vertical dimensions; paper size/overlap; mirror/snap; focus/export. Do not put unrelated actions into a dense toolbar merely to save vertical space.
- Put text/path fields and Browse on one row. Put units in the spin box suffix rather than a separate read-only row when units are fixed.
- Keep one primary button per panel. Put reversible/secondary actions beside one another when their labels fit; otherwise keep only the primary action full width and move secondary actions into a compact utility row.
- Long content scrolls inside the current FreeCAD task panel. The native task footer remains the only accept/cancel location.
- Prefer one selected-object list plus one detail area for many related objects. Do not use tables with tiny columns in a narrow task panel.
- Use the shared UiDesign helpers. Avoid panel-specific styles, repeated title bars, duplicate Apply actions and separate top-level utility windows.

### Viewport interaction grammar

- Pick and drag spatial geometry in the viewport. Keep an exact numeric field in the panel when a user must specify a measurement or transformation accurately.
- Make selected/hovered/active states differ in size and shape as well as color.
- Occlusion must not erase the affordance. Keep hidden measurement guides as a readable dashed X-ray underlay, keep visible front segments solid and depth-tested, and render rounded 3D grips in a Coin annotation layer above the mannequin. Avoid square point sprites for body handles or skeleton joints.
- Expose high-frequency scene controls close to the viewport: avatar show/hide, measurement visibility, skeleton/landmark visibility, arrangement points, seam highlights and orthographic inspection views.
- Use the host's standard camera/navigation controls for general navigation. Add explicit view buttons where a task requires a repeatable audit, such as diagnostics six-side review.

## Window-by-window decisions

### 1. Pattern Piece editor

**Current model:** one native task panel edits the selected PatternPiece. When a Sketch is authoritative, width/height are derived and read-only, with an explicit Edit native Sketch action. This preserves Sketcher as the geometry authority.

**Keep in the panel:** piece name; geometry source only when it is genuinely selectable; derived width/height; seam allowance; grainline angle; Edit Sketch; Focus in 3D.

**Layout decision:** keep name and geometry source as full-width rows. Pair width and height in one Dimensions row, and seam allowance with grainline angle in one Construction row; keep labels attached to the individual fields so compactness does not cost clarity. Keep derived fields visibly identified as “from Sketch” or “from outline”. Never make a greyed-out field look like a broken editable control.

**Viewport:** the panel is appropriate; geometry editing belongs in native Sketcher. Focus should frame the piece without changing orientation where possible. Do not add a custom 3D dimension gizmo for values already owned by Sketcher constraints.

### 2. Surface Pen / 3D Pattern Pen

**Current model:** viewport-first authoring with a compact task panel for placement mode, curve/freehand mode, snap/closure and extraction tolerance.

**Keep in the panel:** current mode, surface target, closure/deviation thresholds, finish/clear/cancel. Keep cursor-dependent geometry and feedback in the viewport.

**Layout decision:** pair related mode choices, put numeric tolerances on compact form rows, and keep Finish Stroke / Create Pattern as the single primary action. Clear and Cancel are secondary. Only show extraction tolerance when it applies to the current extraction path.

**Workflow:** select/confirm the surface target → draw in viewport → close/validate the loop → review deviation → create a normal Sketcher-backed PatternPiece. Do not turn the pen into a second pattern editor.

### 3. Pattern Export

**Current model:** selected-piece context plus format, PDF page options, fixed millimetres, curve sampling and output path.

**Keep in the panel:** source piece identity/status, format, output path, PDF paper size and overlap when PDF is selected. Keep export read-only with respect to the source document.

**Layout decision:** source identity + Focus Source share one row; output path + Browse share one row; PDF-only paper size and overlap are paired and only shown for PDF. Curve sampling is behind Advanced. Show fixed units as static “Units: mm” text, not a read-only input row.

**Viewport:** Focus Source is a convenience, not the core export interaction. Keep it secondary.

### 4. Topology Repair

**Current model:** a master/detail repair task with affected seams and explicit viewport edge replacement.

**Keep in the panel:** affected seam ID and side, current broken reference/status, replacement source piece, Pick replacement edge, preview mapping, apply/repair and cancel.

**Layout decision:** list multiple invalid seams in a selectable list; selected seam details appear underneath. Use one row per A/B side with the Pick action beside its target field. Put verbose topology diagnostics behind a disclosure, but keep the actual invalid-reference reason visible. Do not present generated mesh edge numbers as durable identity.

**Viewport:** viewport edge picking is required and correctly paired with a structured panel. Highlight the broken side and candidate replacement distinctly; cancel must remove temporary overlays and restore prior selection.

### 5. Sewing creation

**Current model:** staged viewport edge-picking plus one Preview/Commit/Cancel panel. This is the right pattern for spatial pairing.

**Keep in the panel:** task name, selection count/current side, short instruction, edge focus/selection helpers, Preview, Commit and Cancel.

**Layout decision:** show current A/B selection state before controls. Put Pick / Focus as compact secondary actions; Preview and Commit remain prominent, with Commit disabled until validation passes. Do not add a full form for values derived from selected semantic edges.

**Viewport:** show both selected sides with paired IDs and direction marks; keep hover preview local to the edge under the pointer. The sequence should be “pick A → pick B → preview → commit”, with explicit recovery if either reference is stale or incompatible.

### 6. Sewing Operation editor

**Current model:** one selected operation and its semantic seam. Fields cover alignment, side-B reversal, normalized A/B ranges, tolerance, stitch samples, lengths/correspondence status, repair and Sketcher navigation.

**Keep in the panel:** seam ID and piece A/B identity; alignment; orientation; A start/end; B start/end; length/correspondence validation; stitch sample count. Preserve repair and Sketcher actions.

**Layout decision:** put normalized range fields into two paired rows (A: Start / End; B: Start / End), matching the Sewing Network editor. Alignment and Reverse B share one row. Tolerance and stitch samples are behind an Advanced correspondence disclosure. Keep measured lengths and validation message visible without expansion. Group Edit side A and Edit side B together. Repair must remain a clear recovery action, not a second competing primary action.

**Viewport:** Focus seam in 3D and side-specific highlights are useful. The viewport is for selection/review; precision correspondence remains in the panel. Do not add numeric handles for normalized seam parameters until they can map to stable Sketcher-edge semantics.

### 7. Sewing Network editor

**Current model:** searchable seam list plus selected-seam details. This is the right master/detail structure for a larger collection.

**Keep in the panel:** filter text, compact seam identity/relationship/validation state, one selected seam, correspondence settings, selected-range editor and Focus Seam.

**Layout decision:** use the list first, selected detail below. Keep the selected seam explicit when filtering; never redirect staged values after sorting/filtering. Do not replace the list with a wide table. Detail controls reuse the same A/B range row layout as Sewing Operation.

**Viewport:** focus/highlight the selected seam. Maintain seam identity and occlusion settings consistently across Pattern, Sewing and Simulation.

### 8. Seam Overlay Options

**Current model:** two staged Boolean preferences: seam identity highlights and depth/occlusion.

**Keep in the panel:** the two checkboxes and a concise explanation. No extra tabs, groups or viewport preview buttons are needed.

**Layout decision:** one compact preferences panel with a single explanation and native OK/Cancel footer. Both options are independent and do not need full-width group boxes.

### 9. Avatar Shape & Measurements

**Current model:** a grouped shape editor with canonical numeric fields in two-up measurement grids, continuous shape controls, linked viewport handles, a provider choice and disclosed scene/advanced settings.

**Keep in the panel:** body profile/preset + continuous control; all canonical body measurements and proportions; provider identity/source; collision skin offset; Apply & Rebuild; Pose entry. Do not remove uncommon measurements just to reduce height—keep them in the existing measurement groups or a discoverable disclosure.

**Priority order:** (1) body profile and preset; (2) common body measurements; (3) less-common proportions; (4) Apply & Rebuild; (5) Pose; (6) provider/source; (7) collision/display/landmark options; (8) provider-specific advanced morph values.

**Layout decision:** maintain the two-up measurement grid, with consistent field widths and visible units. Keep measurement names as labels; short two-up display abbreviations are acceptable only when the full measurement name is available on hover and in accessible text. Keep numeric precision fields visible—the viewport is not a substitute. Keep provider-specific morph lists under a single searchable Advanced disclosure.

**Viewport:** each canonical dimension is linked to one rig-aligned spherical 3D grip and field. Hidden guide paths use a clearer dashed X-ray underlay; solid front segments still depth-test against the mannequin. The grips use nested halo/rim/semantic spheres in a Coin annotation layer above the mesh. Hovering a handle highlights its field; focusing a field emphasizes its grip; a click transfers focus and starts a drag. Use the same semantic state on both surfaces.

**Do not:** put every measurement name permanently in the viewport; label only the hovered/active measurement. Avoid a second full measurement table floating over the model.

### 10. Avatar Pose

**Current model:** viewport skeleton selection and native rotation gizmo, with exact XYZ spinboxes, presets, Mirror and Snap in the task panel. A collapsible joint list is a fallback for crowded views.

**Keep in the panel:** preset row; selected joint; Mirror and 5° Snap; XYZ precision values; exact-joint list disclosure; Reset Pose; Apply & Rebuild status/action.

**Layout decision:** retain the three axis fields together as one XYZ row. Mirror and Snap share one tool row. Keep presets together. The selected joint and current action/status come before the optional joint list. Do not merge pose editing into the anthropometric editor: they are distinct tasks and already have a clear handoff.

**Viewport:** the gizmo is primary. Keep standard X/Y/Z rotation rings, capsule-like bone shafts, spherical joints and selected-bone/pivot emphasis. Render the skeleton in a Coin annotation layer so the mannequin cannot occlude it; keep screen-space hit testing for bone selection and native dragger interaction for rotation. A visible selected-joint label in the task panel must update from either viewport or list selection.

### 11. Interactive Arrange / Fitting

**Current model:** direct viewport drag of pattern pieces to persistent arrangement points, with snap indication and a task panel for picking a surface, reset, fit and status.

**Keep in the panel:** current fitting scene/target validity; viewport-pick mode; snap enable/disable; reset arrangement; fit/snap-to-target recovery.

**Layout decision:** make Pick Surface / Snap compact toggles; keep Reset secondary. Do not require numeric placement fields in the normal path. Exact placements can remain in the native property editor until a clear, stable transform gizmo is available.

**Viewport:** preview the nearest arrangement point and show a clear cyan snap marker; distinguish stale target points from live candidates. Add an obvious “snap enabled” state near the viewport action. Preserve the current drag workflow and cancel/transaction behavior.

### 12. Drape Target editor

**Current model:** provider + source object, viewport pick/show helpers, quality preset and collision state.

**Keep in the panel:** target provider, target source, Pick in viewport / Show source, collision preset, tessellation/deflection, thickness, Enabled state, current validation status and Apply.

**Layout decision:** provider/source at top; place Pick and Show beside the source selector; keep common collision quality as one preset row. Defer fine tessellation/thickness to Advanced unless the user is explicitly in custom-quality mode. Keep target state near source selection so simulation readiness is easy to understand.

**Viewport:** Pick source is essential; Show source/Focus source is secondary. Keep selected source clearly highlighted. Never permit a stale/disabled target to look ready.

### 13. Simulation Quality / Run

**Current model:** workflow readiness, target context, Arrange/Fit, quality preset, pinning mode and an Expert physics disclosure. Advanced values include particle distance, solver iterations/substeps, fabric, collision and run settings. Step/Run/Reset are persistent panel actions.

**Keep in the panel:** readiness of pieces/sewing/target/arrangement; target identity/state; quality preset; pinning mode; Arrange/Fit handoff; Step, Run and Reset. Expose particle distance and solver iteration/substep controls only in Expert.

**Layout decision:** place readiness first, target and fitting recovery second, quality preset and pin mode third, then the primary Run action. Put expert particle/solver settings and detailed material/collision values behind one stable disclosure. Avoid two different visible simulation panels with overlapping quality/solver fields. The public Simulation Controls command currently opens the quality task panel; treat the older SimulationGui form as legacy/unregistered until it is intentionally reintroduced or removed.

**Viewport:** garment arrangement and simulation are viewport-first. Show current target, garment state and stale-reason feedback. Keep the panel visible during run; Step and Reset remain available for deterministic inspection/recovery. Do not invent a second in-viewport physics inspector.

### 14. Diagnostics

**Current model:** select stress/strain/fit/pressure metric, inspect formula/units/range, create a derived map, focus source panels and export data.

**Keep in the panel:** metric, formula/units, data readiness, Create Map, Focus Panels and Export. Keep the status/readiness statement close to the primary action.

**Layout decision:** put metric and Refresh on one row; Create Map gets the primary full-width action; put secondary Focus and Export controls together. The implementation adds six standard orthographic view controls in a 3×2 grid so a user can run the same front/rear/left/right/top/bottom audit without manually navigating the camera.

**Viewport:** six-side inspection is a real diagnostic requirement, not decoration. The explicit view actions change orientation only; Focus Panels remains separate and does not silently rotate the camera. The map is derived/read-only and must be rejected when upstream simulation data is stale.

## Workflow audit

### Recommended path

1. **Author pattern** — create/edit native Sketcher pieces; verify outline, seam allowance and grainline.
2. **Create sewing relationships** — pick authored edges in the viewport; review direction and correspondence; commit.
3. **Create or edit avatar** — enter size/measurements and optionally pose the mannequin.
4. **Arrange / fit** — place garment pieces with viewport anchors and snap feedback; recover/reset explicitly.
5. **Configure simulation** — verify target and readiness; select a quality preset and pin mode; use expert parameters only when necessary.
6. **Run and inspect** — Step/Run/Reset, then inspect diagnostics across six orthographic views.
7. **Export** — export the authoritative pattern or diagnostic data only after state validity is confirmed.

The current workbench model mostly supports these stages. Keep cross-workbench entry points (Avatar & Fitting, target editing and Simulation Controls) accessible from the current task. Do not require users to remember which workbench owns a recovery action.

### Accessibility and recovery checks

- No task should depend only on hover or color; visible labels and state text remain.
- A viewport picker must provide an explicit active/cancel state and restore prior selection/visibility when cancelled.
- A disabled action must explain its missing prerequisite.
- A failed/stale semantic reference must show the source identity and recovery route.
- Staged editing must preserve Cancel semantics and FreeCAD transaction behavior.
- A list filter must preserve the selected semantic object and staged values.
- Advanced disclosure must be keyboard-operable and preserve values when collapsed.
- Each active tool must remove callbacks and transient scene graph geometry when closed.

## Implemented in this pass

- Measurement guides render a subdued dashed X-ray underlay through occluding avatar geometry, then redraw visible guide segments solid with depth testing.
- Measurement handles use a three-layer screen-sized marker (light halo, dark rim, semantic centre) so the pick target remains legible on both light and dark mannequin surfaces.
- Diagnostics provides explicit front/rear/left/right/top/bottom viewport actions, with orientation changes separate from Focus Panels.
- Diagnostics packs metric + Refresh together and places its two secondary actions on one row rather than spending one full row per button.
- Sewing Operation and Sewing Network now use matching paired A/B start–end rows; the precision validation/stitch count fields are disclosed as Advanced.
- Pattern Piece pairs width/height and allowance/grainline fields. Pattern Export pairs its source context and PDF options and keeps advanced curve sampling out of the default form.

## Validation still required in the host application

Headless tests can verify line-style tokens, marker layering, command callbacks and layout contracts. Final review should open Avatar Shape and Diagnostics in a real FreeCAD GUI at normal and high-DPI scale, rotate the mannequin through front/back/oblique views, confirm hidden ring segments appear dashed, confirm front segments remain solid, and verify all six camera actions. The repository's FreeCAD GUI acceptance/screenshot suite remains the required visual gate.
