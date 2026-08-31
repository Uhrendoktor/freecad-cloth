# Pattern workbench parity audit — 2026-08-31

Issue: #162

## Scope

Audit the current Cloth Pattern workbench against the P1 minimum described by #162 and the 2026 production plan. The target is not to clone CLO/Marvelous Designer UI; it is to provide a production-oriented FreeCAD workflow using native Sketcher for geometry and Cloth-owned semantic objects for garment meaning.

## Current baseline

Mainline already provides several important foundations:

- `PatternPiece` provides persistent semantic identity, seam allowance, grainline angle and a derived boundary.
- `PatternSketch` creates native `Sketcher::SketchObject` geometry and records semantic edge IDs.
- `SketchAuthority` can make a linked Sketcher object the geometry authority while retaining compatibility data.
- `PatternIR`/`SeamGraph` preserve curve-aware downstream representation.
- `PatternMarks` persists Notch, Grainline and InternalMark metadata.
- Seam references use semantic IDs/signatures rather than trusting raw `EdgeN` ordering.

## Findings

### P1-1 Native Sketcher entry point — BLOCKER

Creating a normal pattern piece still starts with the legacy pattern object. Native Sketcher is attached by a separate operation, while the drafting task panel remains a polygon editor.

**Required:** make **New Pattern Piece** create a Sketcher-backed piece by default and make **Edit Sketch** the primary edit action. Retain polygon drafting only as explicit legacy/migration support. Do not duplicate Sketcher constraints in Cloth.

### P1-2 Curves — BLOCKER

The initial native sketch path is line-only even though downstream `PatternIR` supports curve kinds.

**Required:** make normal Sketcher Arc/B-spline authoring the supported curved-edge path and ensure the PatternPiece/PatternIR adapter preserves curves without flattening the authoritative geometry. Add save/reload and sewing coverage for a representative curved edge.

### P1-3 Constraint editing — PARTIAL

Native Sketcher constraints are available, including generated Coincident and rectangle Horizontal/Vertical constraints, but the current Pattern workflow does not make Sketcher editing the obvious entry point.

**Required:** promote native Sketcher editing and add acceptance coverage for dimensional and geometric constraints through the native editor.

### P1-4 Seam allowance — PRESENT / NEEDS UX INTEGRATION

Persistent seam allowance and derived geometry already exist. Production-oriented visualization and validation remain limited.

**Required:** improve production-view presentation and validation without introducing another geometry kernel.

### P1-5 Notches / grainline / internal marks — PRESENT / NEEDS VISUALIZATION

Semantic mark persistence exists, but derived display geometry and universal semantic edge resolution need completion.

**Required:** resolve marks through the same stable edge identity mechanism used by seams and add deterministic derived visualization.

### P1-6 Mirror / transform — MISSING FROM PATTERN UX

No dedicated Pattern workbench production command currently exposes mirror/transform helpers.

**Required:** add thin commands over native FreeCAD/Sketcher transformation facilities, preserving semantic IDs and invalidation rules.

### P1-7 Validation — PARTIAL

Pattern/seam models perform structural validation, but there is no single Pattern workbench validation action reporting closure, self-intersection, unresolved marks and downstream readiness together.

**Required:** add deterministic, actionable Pattern validation without silent geometry repair.

### P1-8 Stable semantic IDs — PRESENT / INTEGRATION RISK

Semantic edge IDs/signatures exist, but the Sketch/PatternIR mapping needs one canonical resolver so Sketch edits cannot fall back to ordinal or flattened references.

**Required:** make the Sketch/PatternIR mapping the single authority for downstream references and cover curved-edge edit/invalidation behavior.

## Prioritized implementation slices

1. **P1-A:** Sketcher-first Pattern creation/editing.
2. **P1-B:** Curved-edge acceptance and canonical semantic mapping.
3. **P1-C:** Production marks visualization and stable references.
4. **P1-D:** Pattern validation plus mirror/transform helpers.
5. **P1-E:** Grading, production annotations and export interoperability.

## Acceptance fixture

A deterministic GUI fixture should:

1. Create a Pattern Piece and verify a linked Sketcher object exists immediately.
2. Open native Sketcher and create/edit a curved boundary.
3. Add dimensional and geometric constraints.
4. Save/reload and verify geometry, constraints and semantic IDs.
5. Add seam allowance, notch, grainline and an internal mark.
6. Create a second curved piece and sew representative edges.
7. Edit an upstream Sketch dimension/curve and recompute.
8. Verify affected seam/mesh/simulation state becomes explicitly invalid rather than silently retargeting.
9. Rebuild downstream state and continue to simulation.

Use the repository's canonical FreeCAD/Xvfb workflow; do not add another Actions workflow.

## Conclusion

The Pattern workbench is architecturally close but not yet P1-complete. The largest CLO-like workflow mismatch is that native Sketcher authority is currently an opt-in second step and the default drafting path remains custom. The next implementation should therefore be a small Sketcher-first UX slice, followed by curved semantic-reference acceptance, rather than another geometry or constraint kernel.
