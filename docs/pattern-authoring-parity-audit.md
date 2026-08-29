# Pattern authoring parity audit

Issue: #162

This audit compares the current Cloth Pattern workbench contract with the minimum
pattern-authoring capabilities needed for a production garment workflow. It is
intentionally a blocker audit, not a request to reproduce CLO's entire 2D editor.
FreeCAD Sketcher/Part/OCCT should remain the geometry and constraint implementation.

## Executive result

The current workbench has the right high-level direction—parametric pattern data,
semantic marks, seam allowance, grainline metadata, a Sketcher adapter, and a
separate sewing layer—but the authoritative geometry path is still line/sample
oriented. The main concrete P1 blocker is **native curved Sketcher geometry**:
curves can exist in the lower-level `PatternGeometry` API, but the public Pattern
command path converts boundaries to sampled points and the Sketcher adapter only
creates line segments. A curved piece therefore cannot currently be authored and
remain curved through the native Pattern → Sewing → Simulation path.

A second blocker is **semantic edge identity at the UI boundary**. `add_seam()`
currently extracts `EdgeN` selections, while the architectural target requires
stable semantic IDs that survive recompute and explicitly invalidate when topology
changes. This should be solved in the semantic sewing/reference layer rather than
by adding more topology heuristics to the Pattern UI.

## Capability matrix

| Capability | Current state | Release assessment | Recommended implementation |
|---|---|---|---|
| Non-rectangular pieces | Supported through sampled/custom outlines | Partial | Keep, but route through native Sketcher geometry for authoritative editing |
| Straight-line dimensions/constraints | Parametric width/height plus Sketcher adapter | Partial | Use native Sketcher constraints as the editable source of truth |
| Arcs / B-splines / other curves | `PatternGeometry` can represent a quadratic Bezier, but public Sketch creation samples points and creates `LineSegment`s | **Blocker** | Map supported Sketcher curves to the semantic boundary adapter without flattening them |
| Seam allowance | Pattern metadata and derived offset helper exist | Partial | Keep as derived geometry; preserve per-edge semantic ownership and refresh on outline edits |
| Grainline | Angle metadata exists | Partial | Add a persistent reference/annotation tied to Sketch geometry rather than only a scalar angle |
| Notches | Semantic mark support exists elsewhere in the model | Partial | Ensure notch position references semantic edge + normalized/arc-length parameter |
| Internal marks | Model support exists | Partial | Expose through native Sketch construction geometry plus Cloth semantic metadata |
| Mirror/transform | FreeCAD placement/geometry utilities exist | Partial | Use native transforms/Sketcher symmetry where possible; preserve semantic IDs deterministically |
| Validation | Basic geometry validation exists | Partial | Add explicit closed-profile, self-intersection and invalid-reference diagnostics in the UI |
| Stable semantic IDs | Pattern geometry has explicit IDs; seam UI still receives `EdgeN` | **Blocker** | Resolve selection to semantic edge IDs and invalidate on changed/deleted topology |
| Curved seam correspondence | Sewing layer has arc-length correspondence support | Partial | Feed it true curve geometry/parameterization from PatternIR rather than sampled-only outlines |
| M:N/free sewing | Existing sewing implementation supports it | Good | Preserve; do not regress to 1:1-only APIs |
| Save/reload | Native document objects persist metadata | Partial | Add curved-piece and invalid-reference save/reload fixtures |

## Concrete findings in mainline

### 1. Curve support is present below the workbench but not wired through it

`PatternGeometry` defines `QuadraticBezier` and a `Segment` union, and can compute
sampled outlines and approximate curve lengths. That is useful as a backend
primitive, but `PatternCommands.create_pattern_sketch()` converts the current
`SewingOutline` to `(x, y)` points before creating the Sketcher object. The
Sketcher adapter then creates one `Part.LineSegment` for each pair of points.
Consequently a curve becomes a polyline at the Pattern workbench boundary.

**Required change:** a native Sketcher curve must remain a curve in the authoritative
representation. The solver/export path may sample a curve as a derived operation,
but that sampling must not replace the source geometry.

### 2. Mesh generation is also line-only at the public command boundary

`ClothPattern_CreateMesh` reconstructs a `ParametricPattern` from `SewingOutline`
points and wraps every boundary interval in `LineSegment`. This is acceptable as
a temporary derived meshing fallback, but it must consume a solver-neutral resolved
curve representation once PatternIR is introduced.

**Required change:** move curve-to-sampling policy into the derived mesh/PatternIR
layer. Do not encode sampling in the Pattern authoring command.

### 3. Seam selection is still topology-number based

The Pattern command currently converts selected subelements such as `Edge1` into
zero-based edge indices. This is fragile under Sketch edits that split, merge or
reorder geometry.

**Required change:** the Pattern/Sewing boundary should resolve selection to a
semantic edge identity plus parameter range. If the semantic edge no longer
resolves exactly, mark the seam invalid and require user repair; never silently
retarget to another `EdgeN`.

### 4. Existing semantic marks need curve-relative positions

Notches and other edge annotations cannot rely only on a point index when curves
are edited. The stable representation should be:

- pattern-piece ID;
- semantic edge ID;
- normalized parameter or arc-length position;
- optional orientation/direction;
- annotation-specific properties.

This also gives sewing and production export a common reference model.

## Minimum UI acceptance scenario

The next implementation PR should exercise the following public workflow:

1. Create a Pattern Piece through the native Pattern workbench.
2. Open/create its linked native Sketcher object.
3. Add an arc or B-spline using normal Sketcher tools.
4. Close the outline and recompute.
5. Verify the Pattern Piece reports the curve as authoritative geometry; no sampled
   polyline is written back as the source outline.
6. Add a notch and grainline/reference mark associated with semantic geometry.
7. Create a seam to the curved edge using the Sewing workbench.
8. Verify the seam stores semantic edge identity and a direction/parameter mapping.
9. Save/reload and verify all references resolve identically.
10. Change a Sketch constraint so the curve topology remains valid and verify
    downstream geometry updates.
11. Delete/split the referenced geometry and verify the seam/mark becomes explicitly
    invalid rather than attaching to a different edge.
12. Rebuild the derived mesh and verify simulation still consumes the resolved
    geometry.

## Scope for follow-up implementation PRs

Split implementation into small, independently reviewable changes:

1. **Sketch authority + curve adapter:** preserve native Sketcher curves and expose
   a resolved boundary representation without flattening the source.
2. **Semantic edge/mark references:** replace UI `EdgeN` persistence with stable IDs,
   parameter ranges and explicit invalidation.
3. **PatternIR adapter:** resolve Sketcher/Cloth objects into solver-neutral curves,
   local coordinates, materials and sewing relationships.
4. **Native GUI regression:** add the curved-piece workflow above to the canonical
   FreeCAD/Xvfb fixture.

Do not duplicate the active P0 workbench audit or simulation-quality branch.

## External parity evidence

CLO's current documentation treats seam allowance as editable pattern-edge data,
including automatic following of edited pattern outlines and per-edge properties.
Its current pattern tool set also exposes curve editing, free sewing, M:N sewing,
notches and pattern annotations as first-class 2D operations. DXF import/export
preserves units, notches, annotations and curve information. These are useful
parity targets, but Cloth should implement them with FreeCAD-native geometry and
semantic document objects rather than copying CLO's UI architecture.

References:
- CLO, Edit Seam Allowance Properties (updated 2026-07-15): https://support.clo3d.com/hc/en-us/articles/115013370408-Edit-Seam-Allowance-Properties
- CLO, 2D Pattern (DXF) Import/Export (updated 2026-07-15): https://support.clo3d.com/hc/en-us/articles/115000493067-2D-Pattern-DXF-Import-Export
- CLO, Notch (updated 2019-01-16): https://support.clo3d.com/hc/en-us/articles/115015735467-Notch
- CLO, Free Sewing (updated 2024-05-29): https://support.clo3d.com/hc/en-us/articles/115000531308--2D-Tool-Free-Sewing

## Conclusion

#162 should not be closed merely because the current Pattern workbench can create
rectangular or sampled custom pieces. The release-blocking parity gap is the loss
of native curve semantics at the workbench boundary, followed by fragile `EdgeN`
references. Those two issues are concrete, testable, and can be fixed without
creating a second drafting/constraint engine.
