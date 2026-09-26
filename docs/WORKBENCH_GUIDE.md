# Workbench guide

FreeCAD Cloth has three cooperating native workbenches:

- **Cloth Pattern** — author and inspect 2D pattern pieces.
- **Cloth Sewing** — create, edit and validate semantic sewing relationships.
- **Cloth Simulation** — choose a fitting target, arrange, mesh, drape and inspect results.

## User workflow

### 1. Pattern

Create at least two PatternPieces for a sewn garment. Use the native Sketcher representation for editable dimensions, constraints and curves. Normal Cloth Pattern authoring is Sketcher-backed; the legacy `PatternDrafting` polygon editor is compatibility-only.

Useful public UI actions include:

- **Create Garment** for the native garment hierarchy.
- **Create Pattern Piece** / **Create Pattern Piece With Sketch** for native pieces.
- **Edit Sketch** to return to the authoritative Sketcher geometry.
- **Add Seam** for a simple seam relationship.
- **Repair Topology** for the explicit semantic-edge repair path after upstream Sketch edits.
- **Export Pattern** for deterministic SVG/DXF production output.

Recompute and validate before sewing. Generated mesh edge order is not semantic identity.

### 2. Sewing

Select compatible pattern edges/ranges and explicitly create a seam or M:N/free sewing relationship. Review direction, reversal, correspondence and length diagnostics before committing.

The sewing inspection surface includes:

- **Create Seam**
- **Create M:N Sewing**
- **Validate Sewing**
- **Repair Seam**
- **Focus Seam in 3D**
- **Edit Seam Side A in Sketcher**
- **Edit Seam Side B in Sketcher**
- **Show Sewing 2D**

Seam objects use deterministic colors. These colors are a presentation aid; semantic identity remains the persisted seam relationship.

### 3. Arrange and fit

Create/select a persistent `DrapeTarget`: either the native human mannequin or an ordinary FreeCAD Shape/PartDesign/Body/Mesh.

For a mannequin workflow, the public target surface provides **Create Mannequin Drape Target**, **Edit Drape Target**, and **Refresh Drape Target**. Fitting metadata stores persistent piece placement/arrangement state and can be reset without treating the action as a solver step.

The important boundary is that fitting state is stored separately from solver state. Do not use simulation pins to conceal a bad target or stale fitting state.

### 4. Simulate

Open **Simulation Controls** and verify the target status before running.

The task panel exposes:

- **Simulation quality**: **Fast**, **Balanced**, **Final**, particle distance, solver iterations, and substeps.
- **Fabric**: density, thickness, stretch, shear, bend, friction, color, specular response, roughness, transparency.
- **Collision**: avatar skin offset and fallback sphere radius.
- **Run**: simulation steps, **Step**, **Run 30**, and **Reset**.

Use **Step** for controlled/debug advancement, **Run 30** for the normal short run, and **Reset** to clear numerical progress while retaining authored settings.

### 5. Iterate

After a pattern, seam, target, quality, material, or collision edit:

1. recompute the document;
2. inspect the visible state/reason for stale or invalid derived data;
3. refresh or rebuild the affected target/derived mesh;
4. confirm the target is ready;
5. simulate again.

Cloth intentionally fails closed rather than silently consuming stale target/collision state.

## Native garment hierarchy

Use **Create Garment** to create a production garment document. The FCStd document remains the persistence authority: the native `Garment` root contains deterministic `Patterns`, `Sewing`, `Fabric`, `Avatar`, and `Simulation` groups. A persisted native `FabricMaterial` object lives in the Fabric group, and linked pattern, sewing, fitting, target, and simulation state remains in the document.

## Seam visualization and inspection

In 2D, use **Show Sewing 2D** to inspect pattern/seam/stitch correspondence. In 3D, **Focus Seam in 3D** fits the selected semantic seam. The **Edit Seam Side A in Sketcher** and **Edit Seam Side B in Sketcher** actions return to the authoritative source geometry.

## Public target commands

The target commands are deliberately explicit:

- **Create Drape Target** — use selected FreeCAD shape/mesh as the persistent target.
- **Create Mannequin Drape Target** — create/select the Cloth mannequin as the persistent target.
- **Edit Drape Target** — edit target and collision quality settings.
- **Refresh Drape Target** — rebuild collision geometry from the current target source.
- **Enable/Disable Drape Target** — change target participation without deleting its source.
- **Cloth Diagnostics** — inspect stress, strain, fit, and pressure-style diagnostics on simulated results.

## Troubleshooting

**Workbench missing:** restart FreeCAD and verify the Cloth module is installed directly as a FreeCAD `Mod` package.

**Command disabled:** check the active document and the current selection; public commands intentionally reject incomplete inputs.

**Seam invalid after editing:** recompute, inspect the invalid relationship, then use **Repair Seam** or recreate the affected seam.

**Target stale:** use **Refresh Drape Target** after the target source changes.

**Simulation stale or blocked:** inspect the target/scene status, refresh the target or regenerate the derived mesh, then run again.

**Simulation result is non-finite:** press **Reset**, inspect the target and authored simulation inputs, and re-run only after the dependency state is ready.

## Production 2D export

In **Cloth Pattern**, select a PatternPiece and run **Export Pattern**. The task panel emits deterministic SVG or DXF derived from authoritative native Sketcher geometry and reports piece/edge/seam identities, units, scale, seam allowance, and construction-mark metadata. Export is read-only: source PatternPiece/Sketch state is not mutated.

Exports fail closed when the selected piece has missing native geometry or invalid/stale semantic seam references. Re-running an export with identical document state produces byte-identical output.

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
