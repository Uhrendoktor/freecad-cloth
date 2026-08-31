# Architecture

## Invariants

1. **FreeCAD owns geometry and document persistence.** Use Sketcher, Part/OCCT, document Links/Groups/Placement and normal recompute where they fit.
2. **Cloth owns garment meaning.** Pattern pieces, semantic edge IDs, marks, seams, sewing operations, fitting metadata and validation state live in persistent Cloth objects.
3. **The solver owns physics.** Particles, triangles, numerical constraints and solver state are derived from the Cloth model and may be rebuilt.
4. **There is one semantic authority.** Never infer persistent seam identity from generated mesh edge numbering and never create a second pattern/scene/persistence model.

## Dependency direction

```text
FreeCAD UI / commands
        ↓
Document adapters
        ↓
PatternPiece + PatternMark
        ↓
PatternIR + SewingGraph
        ↓
SimulationScene + DrapeTarget
        ↓
CPU reference solver / optional backend
        ↓
Derived diagnostics
```

## Pattern model

A PatternPiece persists a stable piece ID, authoritative 2D geometry reference, semantic edge identities, seam allowance, grainline/notches/internal marks, measurements/validation metadata and simulation-resolution hints. Native Sketcher is the interactive geometry editor; Cloth must not duplicate Sketcher's dimensional/constraint solver.

Semantic edge identity must survive recompute/save/reload and fail closed when topology is deleted, split or merged. Never silently retarget a seam to a different edge. Repair/remap is explicit.

Derived seam-allowance/offset geometry is for inspection/export and must not become the semantic authority.

## Sewing model

A seam/operation contains the participating piece/edge ranges, orientation/reversal, correspondence policy, stitch group/construction kind and validation state. The model must represent 1:1, 1:N, M:1 and M:N/free relationships without depending on particle or triangle counts.

Selection is a GUI concern; the committed sewing graph is document authority. Curved correspondence must be length-aware and report mismatch/reversal before commit.

## Fitting and DrapeTarget

A fitting scene stores garment placements, arrangement points/anchors, wrap/superimpose/reset metadata, body measurements where available and a persistent `DrapeTarget` reference.

`DrapeTarget` is target-neutral. Providers include the native human mannequin and ordinary FreeCAD Shape/PartDesign/Body/Mesh geometry. Both produce a solver-neutral `CollisionSurface`. Target edits invalidate derived collision state; stale targets must never be consumed by simulation.

## Simulation lifecycle

Persistent inputs include quality/resolution, material, collision settings, pins/stitches and solver controls. Particles/triangles/constraints/numerical state are derived. Input changes invalidate derived state.

Run/Step must check target and derived-state validity before advancing. Reset is recovery. Stale state includes an actionable reason and a rebuild/refresh path. Document recompute must remain safe when a target becomes stale.

## Diagnostics

Use structured diagnostics with severity, semantic/object ID, location/range where possible, message and remediation. At minimum cover invalid pattern topology, invalid seam ranges, correspondence mismatch, missing marks, arrangement penetration, stale target/derived state and solver instability. Future fit/stress/strain/pressure maps should consume simulation results rather than become a second simulation model.

## Persistence and interoperability

Native FCStd is the project authority. JSON-like structures may support headless tests but must not become a second project database.

Production adapters may target DXF/AAMA/ASTM-oriented pattern exchange, SVG/TechDraw/PDF sheets and standard 3D avatar formats. External formats are adapters, not authorities.

## UI consequence

Task panels use **Context → Primary action → Secondary actions → Parameters → Recovery**. Persistent data remains inspectable in the document tree/Property Editor. Transient selection/previews never replace the document model.

## Non-goals

Do not replace Sketcher, introduce a second scene graph, require an external runtime for core operation, couple Sewing/Pattern to a specific solver, or promote proprietary formats/cloud services to core dependencies.
