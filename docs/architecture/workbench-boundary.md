# Cloth workbench boundaries

The GUI is split into three FreeCAD-native workbenches. They are separate entry points over one document model, not three independent application layers.

## Workbench responsibilities

| Workbench | Primary responsibility | Representative commands |
| --- | --- | --- |
| **Cloth Pattern** | Author and inspect pattern geometry and pattern semantics | create/edit piece, sketch, marks, 2D view |
| **Cloth Sewing** | Define and validate semantic sewing relationships and fitting/arrangement inputs | create seam, M:N sewing, edit/reverse/alignment, validate |
| **Cloth Simulation** | Configure, run and inspect cloth simulation | create/edit scene, explicit simulation steps, quality/material controls |

The intended dependency direction is:

`Sketcher/Part geometry -> PatternPiece -> Seam/SewingNetwork -> Mesh/PatternIR -> Simulation`

A workbench may expose commands for another object's properties only when that operation is explicitly part of its user workflow. Persistent meaning belongs to document objects; task panels are editors, not alternate sources of truth.

## Registration contract

`InitGui.py` owns only FreeCAD GUI registration. Each workbench provides:

- `MenuText`
- `ToolTip`
- `Icon`
- `GetResources()` returning those three fields
- `Initialize()` that registers its command list once per workbench instance
- `Activated()` / `Deactivated()` lifecycle hooks
- optional context-menu exposure

The common registration shell deliberately owns `commands` per instance. A class-level mutable command list is unsafe because FreeCAD tests, reloads, or multiple workbench instances can otherwise share and overwrite command state.

Command registration is deduplicated while preserving declared order. This keeps the toolbar/menu contract deterministic without changing the command modules that implement behavior.

## Sewing workbench boundary

The Sewing workbench is the semantic layer between authored pattern geometry and simulation. A seam stores piece/geometry references, direction, correspondence/alignment, and validation state. A sewing operation derives display/validation information from that seam. M:N sewing is represented by a sewing network rather than by inventing multiple unrelated UI concepts.

The Sewing task panel edits persistent seam settings and operation parameters. It must not become a second model of seam direction or correspondence.

## UI versus document state

- **Document objects are authoritative.** Save/reload must preserve their properties and links.
- **Task panels are transient editors.** Accept commits changes; reject restores the captured edit state.
- **Commands should be explicit.** Simulation commands must not silently run solver steps merely because a workbench is activated or a task panel is opened.
- **FreeCAD recompute remains the invalidation mechanism.** Do not introduce a parallel GUI-only dirty-state system.

## Compatibility rule

New workbench features should extend the existing Pattern/Sewing/Simulation command modules and document-object APIs. Do not create a second workbench registration path or an additional GitHub Actions workflow for GUI changes. The canonical workflow already runs Python, real-FreeCAD, and GUI/Xvfb coverage.
