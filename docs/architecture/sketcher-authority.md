# Sketcher authority contract

## Decision

Pattern editing uses a **one-way authority model**:

```text
Sketcher::SketchObject  --recompute-->  PatternPiece derived state  --> PatternIR --> Sewing / Mesh / Simulation
          ^
          |
     normal FreeCAD
     Sketcher editing
```

**Sketcher geometry is authoritative.** `PatternPiece` remains authoritative for garment meaning (piece identity, seam allowance, grainline and future annotations). `PatternIR` is an immutable solver-facing snapshot, not a second editable geometry model.

There is deliberately **no normal two-way geometry synchronization**. Recompute reads the Sketcher and updates compatibility/derived properties only. The legacy `sync_sketch_from_piece()` operation is migration/repair tooling and is never part of the recompute path.

This avoids circular updates, solver-vs-Sketcher conflicts, and loss of native Sketcher constraints.

## What stays native

The Pattern workbench does not implement replacements for these Sketcher capabilities:

| Capability | Authority | Cloth behavior |
|---|---|---|
| Lines, arcs, B-splines, Beziers | Sketcher | Read through PatternIR; preserve curve kind and parameter range |
| Coincident / horizontal / vertical | Sketcher | Native constraint solver |
| Tangent | Sketcher | Native constraint solver |
| Symmetry / equality | Sketcher | Native constraint solver |
| Point-on-object | Sketcher | Native constraint solver |
| Dimensional constraints | Sketcher | Native datum/constraint values |
| Expressions / named dimensions | Sketcher / FreeCAD ExpressionEngine | Read after recompute; no duplicate Cloth solver |
| Driven/reference dimensions | Sketcher | Remain reference/read-only dimensions in the sketch |
| Construction geometry | Sketcher | Ignored as pattern boundary; available for drafting/reference use |
| External geometry | Sketcher | Reference-only; never becomes a Cloth boundary automatically |
| Physical sewing constraints | Cloth Sewing | Never encoded as Sketcher constraints |

This means a user can stay in the normal FreeCAD Sketcher environment for parametric editing. Cloth only consumes the solved result.

## Stable IDs and invalidation

Each pattern sketch persists `SemanticEdgeIds`, aligned with native `Geometry` indices. Existing IDs are retained. Appended geometry receives a new deterministic ID. If geometry cardinality shrinks, the adapter fails closed because it cannot safely determine whether a deleted item was a construction element or a sewn boundary; seams must not silently retarget by ordinal.

Sewing references therefore use:

```text
(piece_id, semantic_edge_id, geometry_signature)
```

rather than treating `EdgeN` as permanent identity. A changed signature is reported as changed geometry; a missing semantic ID is reported as missing geometry.

## Persistence

The FreeCAD document is the persistence boundary. The PatternPiece stores a persistent `Sketch` link and `GeometryAuthority=Sketcher`; the sketch stores its piece ID, semantic edge IDs and contract version. Constraints, expressions, construction geometry and external references stay in the native Sketcher object and therefore use FreeCAD's normal save/reload mechanism.

## Recompute contract

On recompute:

1. FreeCAD solves the Sketcher constraints/expressions.
2. Cloth resolves the solved non-construction boundary through `PatternIR.from_sketches()`.
3. PatternPiece compatibility values are regenerated from that result.
4. Downstream sewing/mesh/simulation consumers observe the resulting document dependency/invalidation state.

Cloth never writes geometry or constraints back into the Sketcher during this path.

## Production slice in this change

The production minimum is:

- native Sketcher remains the editable authority;
- explicit authority metadata and versioned semantic-ID contract;
- fail-closed topology deletion handling;
- stable IDs through appended geometry;
- existing PatternIR support for line/arc/BSpline/Bezier boundaries;
- native Sketcher constraints, dimensions and expressions remain untouched;
- headless contract regression tests;
- existing real-FreeCAD smoke coverage remains the GUI/runtime acceptance path.

## Follow-up work

The remaining parity work should be incremental rather than another geometry kernel:

1. **Sketch authoring UX parity:** expose a small Pattern toolbar/task panel that opens native Sketcher with garment-specific setup without replacing Sketcher commands.
2. **Curved sewing end-to-end:** consume the full sampled/parametric PatternIR boundary in all sewing visualization and mesh paths, not only the adapter.
3. **Semantic marks:** add persistent Cloth metadata for grainlines, notches, darts and folds referencing Sketch geometry without taking geometry authority.
4. **Topology repair UI:** provide an explicit command for repairing semantic IDs after intentional deletion/split/merge, with previewed seam impact.
5. **Canonical GUI regression:** extend the existing FreeCAD/Xvfb garment scenario to exercise a constraint/expression edit, save/reload, seam validation and downstream invalidation.

Do not add a bidirectional synchronization layer unless a concrete workflow demonstrates a requirement that cannot be satisfied by native Sketcher plus derived Cloth state.
