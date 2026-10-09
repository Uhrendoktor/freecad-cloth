# Numeric validation and mathematical contracts

## Boundary-validation policy

Pydantic v2 models in `freecad_cloth/common/ValidationModels.py` validate data where geometry and correspondence code crosses an algorithm boundary. They reject non-finite coordinates, fractional or boolean mesh indices, malformed faces, invalid sample counts, and invalid normalized ranges. The models are frozen and reject extra fields so validated snapshots cannot be mutated accidentally.

Validation is deliberately not duplicated across every internal arithmetic operation. Functions validate external inputs once, then operate on normalized immutable values. FreeCAD documents, Sketcher, OCCT, Triangle, and PositionBasedDynamics remain authoritative for their respective domains; Pydantic schemas guard boundaries rather than replacing the domain model.

## Invariants and executable evidence

| Area | Contract | Tests |
| --- | --- | --- |
| Pattern geometry | Finite 2D control points; finite non-negative seam allowance; positive finite rectangle dimensions; integral sample counts | `tests/test_validation_models.py`, `tests/test_pattern_geometry.py` |
| Mesh arrays | Every vertex is a finite 3D point; each face has exactly three integral, in-range indices | `tests/test_validation_models.py`, `tests/test_mesh_validation.py` |
| Triangulation | Validate Triangle output before indexing; preserve authored-boundary mapping; reject non-finite area limits; compare measured mesh area with polygon area | `tests/test_mesh.py`, `tests/test_pattern_geometry.py` |
| Seam correspondence | Positive finite lengths; tolerance in [0, 1); non-empty normalized ranges; mappings preserve or reverse endpoint order within the destination range | `tests/test_sewing_correspondence.py`, `tests/test_property_contracts.py` |
| Point-to-segment distance | Non-negative distance, no greater than the nearer endpoint distance, and invariant under endpoint reversal | `tools/crosshair_contracts.py`, `tests/test_mesh.py` |
| Arc-length sampling | Finite points of consistent dimension; finite positive total length; selected indices remain distinct and ordered | `tests/test_property_contracts.py` |
| Solver input | Distance symmetry and non-negativity for representable inputs; finite solver state; pins preserve zero inverse mass | `tests/test_property_contracts.py` |

Hypothesis explores generated inputs and stateful mutation sequences. CrossHair symbolically checks a deliberately small pure-math contract surface. These tools detect counterexamples but do not prove the entire FreeCAD/OCCT/native application correct.

## Geometry-library decisions

- Use Python's `math.dist` and `math.hypot` for Euclidean norms rather than hand-written square/sum/square-root formulas.
- Keep constrained triangulation and refinement in the existing Triangle binding, and validate its output before any index-based access.
- Use the required SciPy `cKDTree` path for exact nearest-target-vertex clearance on large meshes.
- Use Shapely/GEOS for the polygon simplicity predicate; do not use its buffer operation as a drop-in seam-allowance implementation because join styles, collapsed concavities, and ring ordering can alter authored topology.
- Keep native editable geometry and 2D offsets in FreeCAD Part/OCCT. A small pure-Python seam-allowance helper remains available for FreeCAD-independent use and explicitly does not resolve self-intersections.
- Keep optional diagnostic mesh libraries out of solver-critical paths when the dependency is not installed.
