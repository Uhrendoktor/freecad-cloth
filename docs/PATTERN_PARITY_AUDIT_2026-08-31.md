# Pattern workbench parity audit — 2026-08-31

Issue: #162
Branch: `agent/pattern-parity-audit-20260831`

## Scope

Audit the current Cloth Pattern workbench against the P1 minimum described by #162 and the 2026 replan. The target is not to clone CLO/Marvelous Designer UI; it is to provide a production-oriented FreeCAD workflow using native Sketcher for geometry and Cloth-owned semantic objects for garment meaning.

## Current baseline

The mainline implementation already has several important foundations:

- `PatternPiece` provides persistent semantic identity, seam allowance, grainline angle and a derived boundary.
- `PatternSketch.create_sketch_for_piece()` creates a native `Sketcher::SketchObject`, adds closed-boundary Coincident constraints, and records semantic edge IDs.
- `SketchAuthority` can make a linked Sketcher object the geometry authority while retaining sampled legacy boundary data for compatibility.
- `PatternIR`/`SeamGraph` preserve curve-aware downstream representation.
- `PatternMarks` persists Notch, Grainline and InternalMark metadata.
- Seam references use semantic IDs/signatures rather than trusting raw `EdgeN` ordering.

## Findings

### P1-1 Native Sketcher entry point — BLOCKER

**Gap:** creating a normal pattern piece still starts with the legacy `Part::FeaturePython` pattern object. Native Sketcher is attached only by a separate `Create Sketch` / `Create Piece With Sketch` command. The drafting task panel remains a polygon editor and is not the native geometry authority.

**Evidence:** `PatternCommands.create_pattern_piece_from_parameters()` calls `add_pattern_piece()` directly; `_create_native_sketch_for_piece()` is a second operation. `PatternGui.PatternDraftingTaskPanel` edits only serialized point lists. `PatternSketch._add_geometry()` currently converts every boundary segment to `Part.LineSegment`.

**Required implementation:** make **New Pattern Piece** create a Sketcher-backed piece by default; make **Edit Sketch** the primary edit action; retain the polygon path only as an explicit legacy/migration tool. Do not duplicate Sketcher constraints in Cloth.

### P1-2 Curves — BLOCKER

**Gap:** the current native sketch creation path can only create line segments from the initial boundary. Although downstream `PatternIR` supports curve kinds, the Pattern creation workflow does not expose Arc/B-spline construction as a first-class path.

**Required implementation:** support native Sketcher arc/B-spline authoring by launching the normal Sketcher editor, and ensure the PatternPiece/PatternIR adapter reads those curves without flattening them into the authoritative model. A representative curved edge must survive save/reload and downstream sewing.

### P1-3 Constraint editing — PARTIAL

**Present:** Coincident plus rectangle Horizontal/Vertical constraints are created natively; Sketcher remains capable of adding normal dimensional/geometric constraints.

**Gap:** the Pattern task panel does not surface an explicit "Edit Sketch" workflow in its primary creation/edit path, so the useful constraint functionality is discoverable only after creating/attaching a sketch.

**Required implementation:** promote Sketcher editing to the default action and add acceptance coverage for dimensional and geometric constraints through the native editor.

### P1-4 Seam allowance — PRESENT / NEEDS UX INTEGRATION

`SeamAllowance` is persistent on PatternPiece and derived geometry is generated through the existing OCCT/Part path. The task panel exposes the numeric allowance.

**Gap:** allowance is not yet integrated with a richer production pattern view; corner behavior and semantic visualization are still minimal. Treat this as a P1 follow-up, not a new geometry kernel.

### P1-5 Notches / grainline / internal marks — PRESENT / NEEDS VISUALIZATION

`PatternMarks` provides persistent semantic objects for Notch, Grainline and InternalMark.

**Gap:** the mark objects store semantic data but do not themselves provide derived display geometry. The default Notch/InternalMark commands also use the literal segment ID `bottom`, which is unsuitable as a universal semantic reference for arbitrary Sketcher curves.

**Required implementation:** resolve marks through the same stable edge identity mechanism used by seams and add deterministic derived visualization without embedding competing geometry authority in the mark objects.

### P1-6 Mirror / transform — MISSING FROM PATTERN UX

No dedicated Pattern workbench command was found in the current command registration for mirror/transform helpers. FreeCAD/Sketcher can perform the underlying transformations, but the Pattern workbench has no explicit production-oriented entry point.

**Required implementation:** add thin commands that invoke native Sketcher/FreeCAD transformation capabilities, preserving semantic IDs and invalidation rules. Do not introduce a second transform model.

### P1-7 Validation — PARTIAL

Pattern and seam models perform structural validation, and semantic references fail closed when missing or changed.

**Gap:** there is no single Pattern workbench validation action that reports geometry closure, invalid/self-intersecting boundary, unresolved semantic marks and downstream readiness in one user-visible result.

**Required implementation:** add a deterministic Pattern validation command/task panel that reports actionable errors and warnings without silently repairing geometry.

### P1-8 Stable semantic IDs — PRESENT / INTEGRATION RISK

Semantic edge IDs and signatures exist and seam resolution distinguishes missing versus changed references.

**Risk:** `PatternSketch.create_sketch_for_piece()` initializes `SemanticEdgeIds` from the original point list, while `SketchAuthority` delegates curve-aware identity to `PatternIR`. The migration boundary needs one canonical resolver so a Sketch edit does not cause an ordinal/flattened fallback to silently retarget a seam or mark.

**Required implementation:** make the Sketch/PatternIR semantic-edge mapping the single authority for downstream references and add curved-edge save/reload + edit/invalidation regression coverage.

## Prioritized implementation slices

1. **P1-A: Native Sketcher-first Pattern creation/editing.** New Piece creates a linked Sketcher object; Edit Sketch launches native Sketcher; legacy polygon drafting becomes explicit migration support.
2. **P1-B: Curved-edge acceptance and semantic mapping.** Add a curved Sketcher fixture (Arc and/or B-spline), verify PatternIR preserves curve kind and seam references survive save/reload and edit invalidation.
3. **P1-C: Production marks visualization.** Add derived display geometry and stable Sketch/PatternIR references for notch/grainline/internal marks.
4. **P1-D: Pattern validation + mirror/transform helpers.** Keep these thin adapters over native FreeCAD capabilities.

## Acceptance fixture proposal

A single deterministic GUI fixture should:

1. Create a new Pattern Piece and confirm a linked `Sketcher::SketchObject` is present immediately.
2. Open the native Sketcher editor and create/edit a curved boundary.
3. Add a dimensional constraint and at least one geometric constraint.
4. Save/reload and verify the Sketcher geometry, constraint state and semantic IDs.
5. Add seam allowance, notch, grainline and an internal mark; verify persistent semantic references.
6. Create a second curved piece and sew representative edges.
7. Edit one upstream Sketch dimension/curve and recompute.
8. Verify affected seam/mesh/simulation state becomes explicitly invalid rather than silently retargeting.
9. Rebuild downstream state and continue to simulation.

This fixture should run through the repository's canonical FreeCAD/Xvfb workflow; no additional Actions workflow is required.

## Conclusion

The Pattern workbench is **architecturally close but not yet P1-complete**. The largest user-visible mismatch with a CLO-like authoring workflow is not missing primitive geometry in the backend; it is that native Sketcher authority is currently an opt-in second step and the default drafting UI remains a custom polygon editor. The next implementation should therefore be a small Sketcher-first UX slice rather than another geometry kernel or a broad UI rewrite.
