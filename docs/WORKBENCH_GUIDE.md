# Cloth workbench guide

FreeCAD Cloth is organized as three cooperating native workbenches:

1. **Cloth Pattern** — create and edit the 2D garment pattern.
2. **Cloth Sewing** — turn pattern boundaries into persistent sewing relationships.
3. **Cloth Simulation** — arrange, mesh, drape, and simulate the sewn garment.

The document is the source of truth. Pattern geometry is native Sketcher geometry; sewing relationships are Cloth semantic objects; simulation meshes and collision data are derived state that can be rebuilt after upstream edits.

## Recommended workflow

### 1. Create pattern pieces — Cloth Pattern

Open **Cloth Pattern** and create at least two Pattern Pieces. For production geometry, use the native Sketcher representation so dimensions, constraints, arcs and other curve geometry remain editable through FreeCAD.

Typical operations are:

- **New Pattern Piece** / pattern-piece task panel
- **Edit Pattern** and open its Sketcher representation
- **Create Sketch** or create a piece together with its Sketcher representation
- **Show 2D** for a top-down inspection view
- seam allowance, notch, grainline and internal-mark metadata
- **Validate Pattern** and **Create Simulation Mesh** where available

Pattern-piece properties remain inspectable in the Property Editor. A pattern edit should be followed by recompute before downstream sewing or simulation is rebuilt.

### 2. Create seams — Cloth Sewing

Switch to **Cloth Sewing**. Select the relevant edges on two different Pattern Pieces and create a seam. For a simple one-to-one relationship, use **Create Seam**. For multiple matching edges, use **M:N Sewing**.

The current Sewing command set provides:

| Operation | Purpose |
| --- | --- |
| Create Seam | Create a persistent seam from two selected pattern edges |
| M:N Sewing | Create 1:N, M:1 or M:N sewing relationships from selected edges |
| Create Operation | Create an editable sewing operation from a seam |
| Edit Operation | Edit alignment, orientation, tolerance and stitch samples |
| Reverse Seam | Reverse the B-side stitch correspondence |
| Toggle Alignment | Switch endpoint/uniform correspondence |
| Validate | Recompute and report sewing status/length differences |
| Show 2D | Inspect pattern, seam and stitch correspondence in top view |

Sewing is semantic document data, not a Sketcher constraint. Keep seam direction, alignment and relationship state in the Sewing workbench and Property Editor.

For curved seams, use the correspondence/validation controls and repair an invalid relationship rather than relying on raw edge insertion order. If an upstream Sketch edit invalidates a semantic seam reference, the seam should remain visibly invalid until it is repaired or recreated.

### 3. Configure fitting and target — Cloth Simulation

Switch to **Cloth Simulation** after the pattern and sewing graph are valid. The simulation side can use the parametric mannequin or another FreeCAD Shape/Mesh as the draping target.

The intended sequence is:

1. Create/select a drape target.
2. Configure mannequin measurements or target collision settings.
3. Arrange pattern pieces in the fitting scene.
4. Generate a preview or final simulation mesh.
5. Run simulation and inspect diagnostics.

Simulation consumes derived pattern/sewing data and a solver-neutral collision surface. It should not directly inspect Sketcher internals.

## Save, reload, and invalidation

Save the FreeCAD document after establishing pattern and sewing relationships. On reload, verify the PatternPiece links, semantic seam references and target links before continuing.

When a pattern dimension or curve is edited:

1. Recompute the document.
2. Validate affected seams.
3. Rebuild the simulation mesh/collision state if required.
4. Run simulation again.

Changing a seam invalidates downstream simulation state. Moving or editing a drape target invalidates its derived collision representation. Rebuilding is deterministic; do not continue with stale derived state merely because an object is still visible.

## Document model

A typical garment document follows this dependency direction:

```text
Sketcher geometry
      |
      v
PatternPiece + PatternMarks
      |
      v
PatternIR -----> SewingGraph
      |               |
      +---------------+
              |
              v
        SimulationScene
        /             \\
 PatternMesh       DrapeTarget
                     /   \\
              Mannequin   FreeCAD Shape/Mesh
```

The important boundaries are:

- **Sketcher** owns editable 2D geometry and constraints.
- **PatternPiece/PatternMark** owns garment meaning and persistent semantic metadata.
- **Sewing/SewingNetwork** owns seam relationships, correspondence and validation.
- **PatternIR** provides a solver-neutral representation of pattern curves and sewing relationships.
- **DrapeTarget** owns the selected collision source and collision settings.
- **Simulation** owns derived mesh/solver state and diagnostics.

## Workbench UI expectations

Each workbench is registered natively in FreeCAD and has its own toolbar/menu entry:

- **Cloth Pattern** — pattern construction and inspection.
- **Cloth Sewing** — seam creation, editing, validation and fitting-scene preparation.
- **Cloth Simulation** — target, arrangement, meshing, simulation and diagnostics.

Multi-step operations should use FreeCAD task panels. Persistent state should remain visible in the document tree and Property Editor so a saved document is inspectable without depending on transient GUI selection.

## Troubleshooting

### The Cloth workbench is not listed

Restart FreeCAD and confirm the Cloth module is installed as a FreeCAD `Mod` package. The GUI bootstrap registers the three workbenches as **Cloth Pattern**, **Cloth Simulation**, and **Cloth Sewing**.

### A command is disabled

Check the active document and selection. Many operations deliberately require a Pattern Piece, seam, operation, or selected pattern edges. This prevents invalid operations from creating partial document state.

### A seam becomes invalid after editing a pattern

Recompute and run Sewing validation. A changed or missing semantic edge reference must be repaired explicitly; it must not silently retarget another edge.

### Simulation appears stale after an edit

Recompute the document, inspect simulation/target diagnostics, regenerate the derived mesh or collision state, and run the solver again. Pattern, sewing, and target edits are intended to invalidate dependent derived state.

## Related architecture

See `docs/ROADMAP_2026_REPLAN.md` for the release contracts and `docs/SEWING_WORKFLOW_RESEARCH.md` for workflow research. The repository-level `AGENT_STATUS.md` records the current implementation gates and active workstreams.
