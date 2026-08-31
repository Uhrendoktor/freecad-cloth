# Workbench guide

FreeCAD Cloth has three cooperating native workbenches:

- **Cloth Pattern** — author and inspect 2D pattern pieces.
- **Cloth Sewing** — create, edit and validate semantic sewing relationships.
- **Cloth Simulation** — choose a fitting target, arrange, mesh, drape and inspect results.

## User workflow

### 1. Pattern

Create at least two PatternPieces. Use the native Sketcher representation for editable dimensions, constraints and curves. Add seam allowance, notches, grainline and internal-mark metadata as needed. Recompute and validate before sewing.

### 2. Sewing

Select compatible pattern edges/ranges and explicitly create a seam or M:N/free sewing relationship. Review direction, reversal, correspondence and length diagnostics before committing. Use the task panel for staged operations and the Property Editor for persistent state.

If a Sketch edit invalidates a semantic edge reference, the seam remains invalid until explicitly repaired/recreated. Never rely on generated mesh edge order.

### 3. Arrange and fit

Create/select a `DrapeTarget`: either the native human mannequin or an ordinary FreeCAD Shape/PartDesign/Body/Mesh. Arrange pieces using persistent placements/arrangement metadata. Reset and superimpose are deterministic fitting operations, not solver state.

### 4. Simulate

Generate a preview/final mesh, choose material and quality, confirm target validity, then Run. Step is for controlled/debug advancement; Reset recovers simulation state. Pins/stitches and collision settings are persistent inputs.

### 5. Iterate

After pattern, seam or target edits: recompute, inspect the stale/invalid reason, refresh/rebuild the affected derived state, then simulate again. A stale target must never be silently substituted or consumed.

## Document authority

```text
Sketcher geometry
      ↓
PatternPiece / PatternMark
      ↓
PatternIR + SewingGraph
      ↓
SimulationScene + DrapeTarget
      ↓
Derived mesh / solver state
```

The saved FreeCAD document is authoritative. Transient GUI selection and previews are not.

## UI/UX rules

Task panels read **Context → Primary action → Secondary actions → Parameters → Recovery**.

Important state is visible in the document tree/Property Editor. Multi-step sewing stages selection before commit: `Enter` completes the stage, `Delete` undoes the latest stage, `Esc` cancels. Invalid selections are visibly rejected.

Simulation shows target identity/validity before Run/Step. Quality/material controls are separate from target selection. Stale state always has an actionable recovery path.

## Troubleshooting

**Workbench missing:** restart FreeCAD and verify the Cloth module is installed as a FreeCAD `Mod` package.

**Command disabled:** check the active document and selection; commands intentionally reject incomplete inputs.

**Seam invalid after editing:** recompute and validate; repair semantic references explicitly.

**Simulation stale:** inspect target/scene status, refresh the target or regenerate the derived mesh, then run again.
