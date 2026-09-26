# Workbench guide

FreeCAD Cloth has three cooperating native workbenches:

- **Cloth Pattern** — author and inspect 2D pattern pieces.
- **Cloth Sewing** — create, edit and validate semantic sewing relationships.
- **Cloth Simulation** — choose a fitting target, arrange, mesh, drape and inspect results.

## Production 2D export

In the Cloth Pattern workbench, select a PatternPiece and run the public `ClothPattern_Export` command. The task panel emits deterministic SVG or DXF derived from the authoritative native Sketcher geometry and reports piece/edge/seam identities, units, scale, seam allowance and construction-mark metadata. Export is read-only: source PatternPiece/Sketch state is not mutated.

Exports fail closed when the selected piece has missing native geometry or invalid/stale semantic seam references. Re-running an export with identical document state produces byte-identical output.

## User workflow

### 1. Pattern

Create at least two PatternPieces. Use the native Sketcher representation for editable dimensions, constraints and curves. The normal Cloth Pattern authoring/editing commands are Sketcher-backed (`ClothPattern_CreatePieceWithSketch`, `ClothPattern_CreateFromSketch`, and `ClothPattern_EditSketch`); `ClothPattern_EditPiece` exposes persistent garment metadata and an explicit **Edit native Sketch…** action rather than a second geometry editor. Add seam allowance, notches, grainline and internal-mark metadata as needed. Recompute and validate before sewing.

The former `PatternDrafting` polygon editor is compatibility-only. Its parser and persisted `DraftingBoundary` data remain supported for legacy documents, but no normal Pattern workbench menu, toolbar or command registers that editor.

### 2. Sewing

Select compatible pattern edges/ranges and explicitly create a seam or M:N/free sewing relationship. Review direction, reversal, correspondence and length diagnostics before committing. Use the task panel for staged operations and the Property Editor for persistent state.

If a Sketch edit invalidates a semantic edge reference, the seam remains invalid until explicitly repaired/recreated. Never rely on generated mesh edge order. Seam objects are assigned deterministic colors. In the sewing task panel, **Focus seam in 3D** fits the assembled world-space seam; **Edit side A/B in Sketcher** opens the authoritative native Sketcher source and selects the semantic edge used by the seam.

### 3. Arrange and fit

Create or select a `DrapeTarget`: either the native human mannequin or an ordinary FreeCAD Shape/PartDesign/Body/Mesh. In **Cloth Sewing → Fitting & Avatar**, create a fitting scene, add the PatternPieces, and define the garment-local anchors used for target-aware fitting. Select one PatternPiece and run **Target-aware Arrange**. The action requires a ready DrapeTarget, uses its authoritative collision surface plus the saved garment anchor wrap directions, and applies only bounded rigid motion; failure is transactional and restores PatternPiece, linked Sketch, PiecePlacements and FitStatus. Rotation-axis data is persisted so **Reset Arrangement** restores the saved HomePlacements exactly. Target-aware fitting is solver-neutral; pinning remains an independent simulation policy.

### 4. Simulate

Generate a preview/final mesh, choose material and quality, confirm target validity, then Run. Step is for controlled/debug advancement; Reset recovers simulation state. Pinning is persistent and explicit: **Automatic** preserves the legacy behavior (use `PinSelection` when present, otherwise the existing automatic boundary pins), **Explicit** uses only `PinSelection`, and **None** runs with zero solver pins. Changing the pinning mode or selection participates in the deterministic rebuild signature. Pins/stitches and collision settings are persistent inputs. Fabric presentation properties include color, specular response, roughness and transparency and are persisted with the simulation/material state.

### 5. Iterate

After pattern, seam or target edits: recompute, inspect the stale/invalid reason, refresh/rebuild the affected derived state, then simulate again. A stale target must never be silently substituted or consumed.

## Native garment hierarchy

Use the public `ClothPattern_CreateGarment` command to create a production garment document. The FCStd document remains the only persistence authority: the native `Garment` root contains deterministic `Patterns`, `Sewing`, `Fabric`, `Avatar`, and `Simulation` groups. A persisted native `FabricMaterial` object lives in the Fabric group; pattern, sewing, fitting, avatar/target, and simulation outputs are linked into the corresponding group when the garment root exists. Existing standalone object-creation commands remain supported in documents without a Garment root.

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
