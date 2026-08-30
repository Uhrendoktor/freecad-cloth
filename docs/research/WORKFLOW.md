# Garment-CAD workflow research

Research date: 2026-08-30

This research records observable workflow behavior, not proprietary implementation details. The goal is to define interoperable semantics for FreeCAD Cloth.

## Workflow pattern seen across current tools

A common garment-CAD loop is:

1. Author or import 2D pattern pieces.
2. Refine outlines and construction geometry.
3. Add seam allowance, notches, grainlines and internal marks.
4. Establish sewing relationships between corresponding boundary ranges.
5. Arrange pieces in a reproducible 3D fitting scene around an avatar/collision body.
6. Select material and simulation quality controls.
7. Simulate/drape.
8. Inspect fit, tension/collision/seam problems and measurements.
9. Return to 2D, edit the authoritative pattern, then regenerate downstream state.
10. Save a project and export production/interchange data.

CLO documents the 2D/3D loop explicitly: simulation applies gravity and drapes pieces onto avatars/static collision objects, while configured seamlines are sewn during drape. Its current simulation UI exposes CPU and GPU quality modes. citeturn0search6

Style3D describes essentially the same authoring loop: create pattern pieces, edit curves, add darts/pleats/notches, sew, simulate, then revise in 2D. citeturn2search11

## Sewing semantics

Sewing must be modeled as a persistent relationship, not as a side effect of mesh adjacency. The semantic record should identify:

- piece A and piece B;
- source boundary/range on each piece;
- normalized range parameters rather than generated mesh indices;
- orientation/reversal;
- correspondence policy (arc-length or another explicit mapping);
- stitch group and construction kind;
- diagnostic state.

Commercial tools expose both ordinary segment sewing and more flexible sewing workflows. The project should therefore support 1:1 and M:N/free relationships as first-class semantic operations rather than baking a fixed edge-to-edge assumption into the solver.

Style3D's current documentation also treats sewing as a distinct operation between pattern pieces. citeturn2search11

## Arrangement and fitting

Arrangement is a pre-simulation layer. Pieces need stable placement relative to an avatar, collision proxy or other fitting object. Arrangement state should be reproducible and saved with the fitting scene.

The implementation should distinguish:

- garment pattern coordinates;
- fitting-scene placement (`App.Placement` or equivalent);
- avatar/collision geometry;
- solver-generated particle positions.

Changing arrangement must not mutate the authoritative 2D pattern.

## Simulation controls

Particle/mesh resolution is not merely a rendering preference: it changes simulation cost and resulting detail. CLO exposes particle distance as a garment simulation control; Style3D exposes separate simulation quality modes, including GPU accurate/normal and CPU fallback modes. citeturn0search6turn0search5

For FreeCAD Cloth, the minimum meaningful controls are:

- particle/mesh resolution;
- material density/thickness;
- stretch and shear response;
- bending response;
- friction/collision thickness;
- solver iterations/substeps;
- pins and seam/stitch constraints;
- quality presets that deterministically map to solver configuration.

Any change to these inputs invalidates derived simulation state.

## Diagnostics

The useful diagnostic categories are:

- open or self-intersecting pattern boundary;
- invalid or ambiguous seam range;
- seam length mismatch;
- reversed orientation mismatch;
- missing/notch mismatch;
- piece overlap before simulation;
- collision penetration;
- excessive stretch/tension;
- solver instability/non-convergence;
- stale simulation result after an upstream edit.

Optitex demonstrates the value of visual diagnostics with a virtual tension map showing tension, distance and stretch relative to an avatar. citeturn0search9

The MVP does not need to reproduce a proprietary tension visualization. It does need machine-readable diagnostics and a visible reason when a sewing or simulation operation is invalid.

## CLO-SET boundary

CLO-SET is not a replacement for the garment authoring/simulation kernel. It is a collaborative 3D asset-management and product-development layer around CLO assets. Current features include 3D asset management, versioning, collaboration, web tech packs, BOM/POM, measurement data and rendering. It can ingest CLO project assets such as ZPRJ/ZPAC/AVT and display common 3D interchange formats. citeturn0search0turn0search1

Therefore FreeCAD Cloth should treat asset management, collaboration and cloud rendering as external workflow concepts rather than MVP simulation requirements.

## Behavioral conclusion

The strongest cross-product architectural rule is: **2D construction semantics remain authoritative; 3D arrangement and simulation are derived state; export is an interoperability boundary.** This is consistent with the existing FreeCAD Cloth model and should remain the central invariant.
