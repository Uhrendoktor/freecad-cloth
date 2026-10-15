# Cloth UI style guide

## Product intent

**Cloth should feel like a focused garment workspace inside FreeCAD—not a separate application wearing a FreeCAD skin.** Keep FreeCAD's host theme, selection conventions, task-panel placement, document model, and native Sketcher workflow. Make interactions within those boundaries more intentional, readable, and feedback-rich.

The central pattern is **native shell, purpose-built interaction**: controls remain familiar Qt/FreeCAD controls; the viewport carries spatial work; panels expose only the decisions needed for the current step; model changes are visible before they become persistent.

## Evidence informing this guide

- FreeCAD's [developer design guide](https://freecad.github.io/DevelopersHandbook/designguide/elements.html) recommends the 80/20 rule for toolbars, compact panels, suitable interactive controls, and progressive disclosure for advanced settings. Its [UI zones guide](https://freecad.github.io/DevelopersHandbook/designguide/zones.html) asks workbench task panels to aim for 360 px width. Treat 360 px as a target, not a hard-coded width that breaks at different DPI or translations.
- Blender's [Human Interface Guidelines](https://developer.blender.org/docs/features/interface/human_interface_guidelines/) make consistency, language, component behavior, accessibility and feedback a shared contributor responsibility. Blender's viewport-first approach is a useful reference, not a reason to reproduce Blender's visual identity.
- CLO3D's [user-interface overview](https://support.clo3d.com/hc/en-us/articles/360001547128-User-Interface) provides a garment-specific reference for a dense production workflow with organized tools and configurable measurement/display precision. Cloth should borrow workflow ideas, not imitate proprietary screens.
- Nielsen Norman Group's [usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) prioritize visible system status, recognition over recall, consistency, user control, undo, and error prevention.
- Qt's [stylesheet guidance](https://doc.qt.io/qt-6/stylesheet.html) and [styling approaches](https://doc.qt.io/qt-6.12/qtwidgets-styling-approaches.html) support small, local adjustments while warning against uncontrolled style application. Cloth styling is deliberately scoped to an individual task panel and uses the host palette.

These sources inform the rules below; the exact spacing and component choices are Cloth conventions rather than claimed upstream requirements.

## Principles

1. **The viewport is the primary canvas.** Prefer direct manipulation, selection, handles, overlays and immediate previews when the user is working spatially. Keep numeric entry as a precision path, not the compulsory first step.
2. **One panel, one task.** Name the task in plain language. Put its primary decision first. Avoid mixing setup, spatial manipulation, expert tuning and diagnostics into one undifferentiated form.
3. **Show the common path; disclose the rest.** Defaults should cover the everyday path. Put solver internals, compatibility fields, fine-grained correspondence and rarely changed values behind a named disclosure. Never remove a supported control just because it is advanced.
4. **Use progressive, reversible change.** Stage related edits; let the viewport preview staged values; make Apply/Commit the single clear persistence step. Cancel must leave the document unchanged when a panel promises staged behavior. Use FreeCAD transactions for multi-object edits.
5. **Make state visible.** Distinguish ready, staged, picking, previewed, blocked, failed and committed states. Say what happened and what to do next. Keep feedback near the affected control. Do not rely on color, tooltips, console output, or a disabled button without an explanation.
6. **Prevent silent mistakes.** Disable actions that cannot currently succeed, validate before committing, identify invalid source objects and broken semantic references, and show a recovery path. Never silently re-map a seam or suggest derived dimensions are editable.
7. **Reuse familiar controls.** Native labels, spin boxes, combo boxes, checkboxes, tables and checkable tool buttons are preferred over bespoke widgets. Introduce a specialized control only where it materially improves interaction, such as a 3D dragger.
8. **Use one visual vocabulary.** Shared spacing, headings, status blocks, primary-action emphasis and disclosure behavior should feel consistent without forcing the whole FreeCAD application into a Cloth theme.

## Layout and typography

- Task panels target the FreeCAD-recommended compact width (~360 px), but must flex with window size, high-DPI scaling, font metrics and translated labels. Do not set fixed control widths unless data entry requires them.
- Use one clear panel title; section labels are short, sentence case, and stable across workbenches. Do not use multiple bold title treatments in one panel.
- Align labels and fields consistently. For a form, put a concise visible label beside or above each control. A placeholder is not a label.
- Use sentence case and action-oriented words: “Pick edges in viewport”, “Preview seam”, “Apply changes”, “Reset pose”. Avoid vague verbs such as “Do” or engine jargon on the default path.
- Keep instructions to one short, actionable sentence when possible. Put longer explanation in help text or documentation.
- Establish hierarchy through order, grouping and spacing before adding decoration. Avoid nested group boxes solely to create visual cards.
- Normalize root panel margins and inter-control spacing via shared helpers. Do not force a custom font family, global font size, shadow system, animated transitions or application-wide stylesheet.

## Inputs and units

- Numeric fields use spin boxes with a sensible range, step, precision and explicit unit suffix (mm, degrees, percent) where appropriate.
- Distinguish **measured/derived** data from **editable** values. If Sketcher or another authoritative source owns a dimension, show it read-only and explain the source rather than presenting a disabled field with no reason.
- Do not make users remember codes or separators without help. If legacy text-list input remains necessary, show a format hint and validate it before applying. Replace text lists with viewport selection when the task is inherently spatial and a clear selection UI is practical.
- Use preset names that communicate quality/time trade-offs (for example Fast / Balanced / Final); changing the preset should update visible values without making hidden changes seem mysterious.
- Respect Qt/FreeCAD locale and unit behavior. Do not parse number strings manually when a typed numeric control can express the same constraint.

## Buttons and actions

- Each panel should have one visually primary task action. Emphasize it with the current FreeCAD palette's highlight roles; all other actions remain native, visually secondary controls.
- Use action labels with outcomes: “Apply changes & rebuild”, “Create diagnostic map”, “Commit”, “Cancel”. Keep destructive/reset operations explicit and separate from the primary action.
- Do not show two controls that run the same callback with the same effect. When an internal attribute must remain for compatibility, alias it to the single visible action rather than creating a second button.
- Preserve FreeCAD's standard task-dialog accept/cancel conventions where supported. Do not add a second independent Apply/Cancel bar that competes with the host controls.
- Disable impossible actions until their prerequisites are met, and explain missing prerequisites in the status area.

## Disclosure and advanced controls

- Use a compact checkable disclosure with a clear title and arrow; expose its expanded/collapsed state to assistive technology through a real Qt checkable control.
- The default view should answer “What do I select, what do I change, and how do I run it?” before showing solver coefficients and compatibility fields.
- Keep expert controls discoverable and persistent; do not bury common fabric values or essential error recovery.
- Prefer a small number of meaningful disclosures over dozens of unrelated accordion rows.
- Keep current selection and staged values when expanding or collapsing advanced settings.

## Viewport interaction and semantic color

- Keep the viewport visually quiet until an action needs feedback. Show hovered, selected, active, editable and invalid states with clear differences in size/weight as well as color.
- Retain the established X/Y/Z axis convention (red/green/blue). Amber signals the active pose control; cyan signals a live snap target; the existing seam-identity palette remains owned by the seam-color definitions.
- Do not reuse a semantic viewport color to decorate an unrelated panel. Do not hard-code a full application palette: use Qt palette roles for panel styling, and reserve fixed RGB values for spatial semantics that have a stable meaning.
- Viewport gizmos remain transient UI overlays, not document objects. Mouse handlers and scene-graph nodes must be removed when their interaction ends.
- Show the result of direct manipulation quickly and preserve a numeric precision path for users who need exact values. Avoid auto-changing the camera unless the user explicitly requests fit-view.

## Feedback, validation and accessibility

- Give status feedback close to the task controls. Recommended vocabulary: **Ready**, **Changes staged**, **Picking**, **Preview ready**, **Action required**, **Failed**, **Applied**.
- Errors state both cause and next step, e.g. “No pattern edges selected. Select two authored edges, then Preview.”
- Use a visible state label or text as well as semantic styling. Color alone is not sufficient to distinguish success, warning and failure.
- Keep tooltips supplementary: they explain non-obvious behavior, not the only place a field's purpose or unit appears.
- Preserve keyboard tab order, focus visibility and native widget accessibility. Checkable controls must expose their checked state; label every field; avoid tiny hit targets. Do not remove precision controls to make a screen appear simpler.
- For long calculations, expose progress and allow cancellation where the underlying operation supports it. Do not add fake progress bars to synchronous work.

## Shared implementation contract

- freecad_cloth/common/UiDesign.py owns lightweight Qt panel conventions only. It must not import feature packages or alter document/domain state.
- apply_panel_style(panel) styles one form and normalizes basic spacing. It must never call QApplication.setStyleSheet, change the global palette, or hard-code a light/dark theme.
- mark_button(button, emphasis) gives a QPushButton a semantic role (primary, secondary, or danger).
- set_status(label, text, state) sets text and the info, warning, error or success role. Callers are responsible for wording that communicates state independently of color.
- make_disclosure(title, content, QtCore, QtWidgets, expanded=False) uses a checkable Qt tool button to hide/show a settings container while preserving contained widgets and values.
- Existing domain-specific viewport tokens remain in freecad_cloth/shared/viewport_gizmo_style.py; seam identity colors stay in freecad_cloth/shared/seam_colors.py. Do not introduce another palette source.
- Styling lives on the supplied panel. The rest of FreeCAD remains the host's responsibility.

## Feature-by-feature UX audit

| Area | Current affordance and UX risk | Decision under this guide |
|---|---|---|
| Mannequin shape and measurements | 3D dimension handles are a good direct-manipulation path, but the panel mixes provider, shape, measurements, display and legacy hidden pose widgets; two visible controls invoke the same rebuild callback. | Keep measurement handles and numeric precision; standardize feedback and spacing; show one Apply & Rebuild action (retain the old rebuild attribute as an alias); clearly identify derived versus editable values and provider source. |
| 3D Pose Mode | Viewport rings, presets, mirror and snap are aligned with a spatial task, but heading/status styles and disclosure controls vary. | Keep viewport-first editing, Mirror and angle snapping; standardize title/status styling; retain Exact angles and Joint list as disclosures, since they are precision aids rather than the normal interaction. |
| Arrange / Fit | Dragging garment pieces and snapping to arrangement points avoids a wall of XYZ coordinates. | Preserve direct manipulation; standardize the active-pick state, status copy and secondary reset/fit actions. Do not add numeric placement fields to the default flow. |
| Pattern piece | Native Sketcher authority is respected, but disabled derived dimensions can be misread as editable fields. | Keep Sketcher authoritative; style derived/read-only values consistently and explain why they are not editable; retain explicit seam-allowance and grainline fields with units. |
| Production export | SVG/DXF/PDF and PDF tile options are format-dependent, but status and conditional controls need coherent feedback. | Reveal PDF-only choices only for PDF; use explicit output labels and a success/error state; keep the exporter read-only with respect to source geometry. |
| Topology repair | The explicit mapping workflow protects semantic seam references; generic status text can hide whether mappings remain unresolved. | Preserve explicit per-side mapping and fail-closed behavior; show actionable status/error roles and never repair silently. |
| Seam creation | Preview / Commit / Cancel and viewport picking are transactional, but feedback currently resets styles ad hoc. | Preserve transactional preview; style picking/preview/error statuses consistently; keep Commit disabled until the preview is safe to accept. |
| Seam / sewing network editors | Orientation, normalized-range, alignment, length and correspondence values can be confusing without context; errors vary by label. | Keep valid semantic data visible, group related orientation/range fields, standardize warning/status roles, and surface recovery guidance from the correspondence report. |
| Drape target | Collision source, preset and settings are sensibly grouped; title/status styling differs from other panels. | Keep source selection and Preview/Normal/Final quality presets in the default view; emphasize Apply & Refresh, use consistent status and palette-aware control styling. |
| Simulation | Scene, fabric, solver, collision and raw pin/seam-index settings appear together, burying the normal workflow. | Keep scene/fabric, Step/Run/Reset and status visible; put solver, collision and manual sewing/pinning fields in one collapsed “Advanced solver, collision & sewing settings” disclosure. |
| Simulation quality | Presets and fitting status form a useful common workflow while low-level physics controls already have an expert disclosure. | Keep existing expert-settings behavior and use the same panel and status vocabulary; do not introduce a second competing disclosure layer. |
| Diagnostics | Metric, definition, refresh/map/export actions, and runtime failures need to guide the next step. | Preserve a short workflow; emphasize the main map action and standardize analysis/error status while keeping data export explicit. |

This is a UI consistency pass, not a replacement of native FreeCAD geometry or domain semantics. A future usability study should test novice completion, recovery from invalid selections, and expert discoverability with representative garment tasks.
