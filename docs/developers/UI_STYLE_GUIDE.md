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

## Reference study: complex EDA interfaces

Two KiCad projects provide complementary interaction references:

- [Uhrendoktor/kicad-blocks](https://github.com/Uhrendoktor/kicad-blocks) uses Tkinter for an Eeschema IPC add-on. Its [Functional Block Library screenshots](https://github.com/Uhrendoktor/kicad-blocks/blob/main/docs/visual-evidence.md#inspect-a-library-entry) show a searchable block list, selected-record summary, Facade/Schematic preview tabs, and implementation/sheet selectors. Its [UI review contract](https://github.com/Uhrendoktor/kicad-blocks/blob/main/docs/ui-review.md) specifies task-first information hierarchy, concise help, accessible text labels, shared geometry/theme/button/chooser helpers, content-measured window sizing, empty/no-result/stale-selection cases, keyboard cancellation, and parent ownership through Tk's `transient(master)`. The [browser implementation](https://github.com/Uhrendoktor/kicad-blocks/blob/main/plugin/kicad-blocks/kicad_blocks/plugin.py) lazy-loads Tk, applies desktop/KiCad light/dark appearance and uses standard file choosers. **Do not port its searchable library browser or separate top-level window into FreeCAD.** Its useful contribution here is the discipline of one clear task, selected-object context, concise recovery feedback, reusable helpers, and explicit window ownership.
- [Uhrendoktor/kicad-jlcpcb-interface](https://github.com/Uhrendoktor/kicad-jlcpcb-interface) is also a Tkinter Eeschema IPC add-on, and is the closer reference for focused editing. Its [Component Properties screen](https://github.com/Uhrendoktor/kicad-jlcpcb-interface/blob/main/docs/visual-evidence.md#component-properties) concentrates the selected symbol's identity, editable schematic fields, catalogue facts, evidence/source and related alternatives in one detail workspace. Its unified [Add or Update Component workflow](https://github.com/Uhrendoktor/kicad-jlcpcb-interface/blob/main/docs/user-guide.md#jlcpcb-add-or-update-component) reuses one review layout for different selection contexts, makes proposed changes explicit, keeps source/freshness/warnings visible, uses a scrollable content region with a persistent action footer, and asks for confirmation before writing. The [implementation](https://github.com/Uhrendoktor/kicad-jlcpcb-interface/blob/main/plugin/kicad-jlcpcb-interface/kicad_jlcpcb/plugin.py) preserves the selected component reference and sheet identity while refreshing data, gives loading and unavailable data explicit states, and returns background catalogue results to the UI thread through a queue/timer. Its [theme implementation](https://github.com/Uhrendoktor/kicad-jlcpcb-interface/blob/main/plugin/kicad-jlcpcb-interface/kicad_jlcpcb/theme.py) detects desktop appearance and supports explicit light/dark overrides; Cloth should instead let FreeCAD's own Qt palette remain authoritative.

Useful ideas to adapt:

- **Keep the current object as the context.** A focused panel should make the selected document feature, seam, pattern piece, avatar, or simulation scene unmistakable. Do not introduce a general-purpose library browser or a second navigation surface for objects that already exist in the active document.
- **Separate review from persistence.** Show what will change, keep warnings and source/state evidence visible, and make the commit boundary explicit. For document edits, preserve FreeCAD transaction/rollback semantics; for cancelable settings, stage values until the native task-panel accept action.
- **Keep the task action reachable while details scroll.** Long option groups may scroll inside the existing task-panel form, but primary actions and the current validation/status message should remain visible. Use FreeCAD's native OK/Cancel footer where it fits the panel protocol; do not add a competing footer.
- **Make state and unavailable information explicit.** Use loading, ready, warning, error, and success states. Never substitute guessed values for missing metadata or let navigation feedback obscure a validation result. Text and icon/state cues must still work without color alone.
- **Treat filtering as local to a real editing collection, not as a new product surface.** A seam filter may narrow the current network's seam rows; an advanced-parameter filter may locate a control inside an already-open editor. Do not add the KiCad Blocks library list, catalog browser, or another searchable top-level object chooser to FreeCAD.
- **Preserve identity across refresh and filtering.** Resolve document-object references or semantic IDs at selection time. Sorting, filtering, or refreshing must not redirect staged values to another seam or object. Empty results and a disappeared selected object need explicit handling.
- **Keep async work and GUI ownership explicit.** Background catalogue/analysis tasks must return through Qt signals or a queued event before changing widgets. Do not call FreeCAD document/view APIs from worker threads. Close/cancel must stop callbacks and remove transient observers.
- **Treat theme, font, and scale as runtime inputs.** Standard controls should follow FreeCAD's active Qt style/palette. Use expanding layouts and measured content rather than fixed widths; do not apply another application's full palette to FreeCAD.

Qt's [Model/View programming guide](https://doc.qt.io/qt-6/model-view-programming.html) explains how selection and data stay synchronized across sorting and filtering. Its [layout management guide](https://doc.qt.io/qt-6/layout.html) covers nested responsive layouts, and the [QScrollArea reference](https://doc.qt.io/qt-6/qscrollarea.html) documents the child-widget sizing requirements that scrolling forms must respect. FreeCAD's [Qt task-panel guide](https://freecad.github.io/Addon-Academy/Guides/Code/Qt/) describes how `Gui.Control.showDialog()` embeds the panel's `form` in the existing Combo View task area and supplies the host footer. Cloth must keep this native host model rather than copying the standalone Tk windows from the KiCad references.

The references are design inputs, not templates to copy wholesale. The useful patterns are focused selected-object context, explicit staged review, persistent actions/status, robust async/UI-thread boundaries, reusable helpers and honest empty/error states. Cloth remains a compact, viewport-first FreeCAD workbench.

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

## Complex collections and master/detail panels

- Use a searchable list with a focused detail editor when many related objects each have their own precision controls. The list answers “which item?”; the detail area answers “what can I change on this item?”
- Keep each list summary compact: identify the object and its important relationship or state. Put secondary metadata in the selected-detail summary or tooltip, not in a wide grid of tiny columns.
- Search all meaningful identifiers and both sides of a relationship, including validation state. Filtering must preserve staged edits and must not silently change the object being edited.
- Use native Qt lists/trees plus standard form controls. Reserve tables for genuinely tabular comparison or batch editing, not a narrow task panel that requires horizontal scrolling for its primary action.
- Keep one selected object explicit. Disable detail controls when no visible result is selected and say why. Preserve that record's staged values when selection or filters change.
- Prefer one selection level followed by a clear detail form over deeply nested trees or several competing splitters. Add tabs only for distinct task modes, not alternative views of the same record.
- Keep hierarchy shallow. A list, one selected-detail group, and one status area are usually enough structure for a compact workbench task.

## Scrolling and fixed task actions

- When a task contains many controls, place the long settings content inside a native QScrollArea that remains a child of the existing FreeCAD task-panel widget. Do not create a separate top-level window merely to gain space.
- Keep the title, most important actions, and current status outside the scrolling region when the task benefits from persistent access to them. This lets users scroll through details without losing the next safe action or the current result.
- Use QFormLayout.WrapLongRows and expanding field policies for compact panels so long labels and control fields adapt to available width. Apply the shared helper to grouped and nested forms as well as root forms. Avoid hard-coded widths that break under DPI scaling, font changes, or translated labels.
- Put detailed solver or compatibility settings behind a named disclosure, and make the disclosure itself scroll with the settings. Do not put the primary Run/Apply/Commit control below a long settings list.
- Add scrolling only when the content genuinely exceeds the available panel height. A short panel should remain compact and should not gain nested scroll bars.

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
- make_scroll_area(content, QtWidgets) wraps long content in a resize-aware QScrollArea that stays inside the current FreeCAD task panel.
- configure_form_layout(layout, QtWidgets) uses long-row wrapping and AllNonFixedFieldsGrow so flexible controls use the available width in narrow task panels.
- Existing domain-specific viewport tokens remain in freecad_cloth/shared/viewport_gizmo_style.py; seam identity colors stay in freecad_cloth/shared/seam_colors.py. Do not introduce another palette source.
- Styling lives on the supplied panel. The rest of FreeCAD remains the host's responsibility.

## Feature-by-feature UX audit

| Area | Current affordance and UX risk | Decision under this guide |
|---|---|---|
| Mannequin shape and measurements | 3D dimension handles provide direct manipulation; shape, measurement, display, and provider controls are grouped, and the panel has one Apply & Rebuild action. | Keep measurement handles and numeric precision; standardize feedback and spacing; remove duplicate callbacks and aliases; clearly identify derived versus editable values and provider source. |
| 3D Pose Mode | Viewport rings, presets, Mirror and snapping are aligned with a spatial task, but the joint list can exceed the compact panel height. | Keep viewport-first editing, Mirror and angle snapping; keep the title, presets and tools accessible while selected-joint details and the expandable joint list scroll together. |
| Arrange / Fit | Direct dragging and surface snap anchors avoid a wall of XYZ coordinates; anchor controls can make the panel taller than the task zone, and viewport status needs to distinguish preview, placement and failure. | Preserve direct manipulation; keep context, drag instructions, snap toggle, Reset/Fit actions and live status visible while only the longer anchor editor scrolls. Show snap/drag guidance as information, committed placements as success, and blocked placements as errors. Do not add numeric placement fields to the default flow. |
| Pattern piece | Rectangle, custom-outline, and Sketcher-authoritative modes have different dimension semantics; always showing disabled width/height fields obscures that difference. | Show editable Width/Height only for Rectangle; label and disable them as outline-derived in Custom mode and Sketch-derived when a native Sketch owns the geometry. Keep the native Sketch editor explicit and retain allowance/grainline fields with units. |
| Production export | SVG/DXF/PDF and PDF tile options are format-dependent, but status and conditional controls need coherent feedback. | Reveal PDF-only choices only for PDF; use explicit output labels and a success/error state; keep the exporter read-only with respect to source geometry. |
| 3D Pattern Pen | The viewport is the drawing surface, but its panel used a fixed maximum width and did not share the workbench's button/status styling. | Let the FreeCAD task host determine panel width; use a responsive form, palette-aware shared styling, a prominent Finish action, and secondary Clear/Cancel actions. |
| Topology repair | Explicit per-side mappings protect semantic seam references; a long invalid-edge list can overflow the task panel. | Preserve fail-closed mapping behavior, place the mapping grid inside the native task-panel scroll area, keep status visible and never repair silently. |
| Seam creation | Preview / Commit / Cancel and viewport picking are transactional, but feedback currently resets styles ad hoc. | Preserve transactional preview; style picking/preview/error statuses consistently; keep Commit disabled until the preview is safe to accept. |
| Seam / sewing network editors | A wide 10-column range table is difficult to use at the FreeCAD task-panel width and makes seam identity hard to scan; the complete master/detail body can exceed the available task height. | Use a searchable seam list summarizing both connected edges and a focused four-field normalized-range editor for the selected seam. Preserve staged ranges through filtering/selection, show an explicit no-results state, scroll the dense body inside the task panel, and keep overall network status visible. Preserve the single document transaction. |
| Sewing operation editor | Correspondence controls and repair/navigation actions exceed the useful height of the task zone; a Reverse B button duplicated the Reverse B checkbox, and navigation feedback could mask validation state. | Keep one Reverse B checkbox, keep validation and action feedback in separate persistent status labels, place longer correspondence and Sketcher actions in a native in-panel scroll area, and keep both status labels visible. |
| Seam overlay preferences | A standalone modal options dialog is inconsistent with the rest of the workbench and bypasses FreeCAD's task-panel conventions. | Present the two display preferences through Gui.Control.showDialog; use FreeCAD's native OK/Cancel footer and persist only on acceptance. |
| Drape target | Collision source, preset and settings are sensibly grouped; a separate Cancel button duplicated FreeCAD's footer, and staged feedback must distinguish Apply from closing without another apply. | Keep source selection and Preview/Normal/Final quality presets in the default view; emphasize Apply & Refresh, use the native OK/Cancel footer, and explain that Apply commits immediately while Cancel discards only later unapplied edits. |
| Simulation | Scene, fabric, solver, collision and raw pin/seam-index settings appear together, burying the normal workflow. | Put the full settings content in a resize-aware in-panel scroll area; keep Step/Run/Reset and current status outside it, and retain advanced solver/collision/pinning behind the existing disclosure. |
| Simulation quality | Presets and fitting status form a useful common workflow while low-level physics controls already have an expert disclosure. | Keep workflow readiness, target context and Arrange/Fit in the scrollable content; leave Step/Run/Reset/status visible and preserve the existing expert-settings state. |
| Diagnostics | Metric, definition, refresh/map/export actions, and runtime failures need to guide the next step. | Refresh the formula, data range and face summary when the metric changes; disable map/export while analysis is unavailable; preserve explicit refresh and export actions. |

This is a UI consistency pass, not a replacement of native FreeCAD geometry or domain semantics. A future usability study should test novice completion, recovery from invalid selections, and expert discoverability with representative garment tasks.
