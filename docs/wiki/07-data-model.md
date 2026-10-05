# 07 · Data model, persistence and architecture

## The authority rule

FreeCAD Cloth uses one saved FreeCAD document as the persistence authority.

The system can have in-memory value objects, derived meshes and runtime solver state, but they must not become competing databases.

<pre>
Native Sketcher geometry
        │
        ▼
  PatternPiece + marks
        │
        ▼
 PatternIR / seam graph
        │
        ├──────────────► fitting scene
        │                     │
        │                     ▼
        │                DrapeTarget
        │                     │
        ▼                     ▼
 semantic sewing ───────► simulation inputs
                                │
                                ▼
                         PBD derived state
                                │
                                ▼
                           diagnostics</pre>

## What is authoritative

| Domain | Persistent authority | Derived |
| --- | --- | --- |
| Pattern | Native Sketcher + PatternPiece semantics | Preview/offset/mesh geometry |
| Sewing | Persisted semantic seam objects | Stitch samples / solver constraints |
| Fitting | Persisted placements and arrangement points | Viewport drag preview |
| Pose | Persisted skeleton joint rotations | Deformed mannequin mesh |
| Collision | Persisted DrapeTarget reference | Collision surface representation |
| Simulation | Persistent material/quality/pin/solver inputs | Particles, triangles, numerical state |
| Diagnostics | Interpretation of valid simulation state | Rendered maps/inspection views |

## Dependency direction

The architecture should read in one direction:

<strong>FreeCAD UI / commands → document adapters → semantic garment model → DrapeTarget / simulation inputs → PBD runtime → diagnostics</strong>

The solver does not define garment semantics. The GUI does not define persistence. Generated images do not define product truth.

## Why this matters

This split provides explicit answers to common audit questions.

### What changed?

Look at the saved Sketcher geometry, PatternPiece metadata, seam objects, fitting state, pose state or simulation inputs.

### What must be rebuilt?

Look at the dependency boundary. Derived simulation state becomes stale when authoritative inputs change.

### Can the state survive reopening the FCStd?

Persistent data should round-trip through the FreeCAD document. GUI-only previews do not count.

### Can another solver be substituted later?

The solver sits behind <code>ClothBackend</code>. A future backend must consume the same semantic inputs and preserve reference behavior.

## Avatar architecture

The mannequin is a provider behind the target-neutral fitting/collision boundary, not a separate simulation architecture.

The provider exposes authored pose and collision data. Visual geometry and collision geometry may differ.

The fitting layer therefore does not need to know whether a target is the native mannequin, generic FreeCAD geometry or a future high-fidelity avatar provider.

## Simulation boundary

PositionBasedDynamics is the production physics runtime.

<code>freecad_cloth.simulation.ClothSolver</code> is an input/model assembly layer, not a second user-selectable solver. It must not become a competing integration or time-integration engine.

## Package map

| Area | Main code |
| --- | --- |
| Pattern | <code>freecad_cloth/pattern/</code> |
| Sewing | <code>freecad_cloth/sewing/</code> |
| Avatar/fitting | <code>freecad_cloth/avatar/</code> |
| Simulation | <code>freecad_cloth/simulation/</code> |
| Shared diagnostics / document adapters | <code>freecad_cloth/common/</code> and <code>freecad_cloth/shared/</code> |

For the full engineering contract, see [docs/ARCHITECTURE.md](../ARCHITECTURE.md) and [docs/PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md).
