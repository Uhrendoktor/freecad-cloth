# Numeric validation and mathematical contracts

## Boundary-validation policy

Pydantic v2 models in `freecad_cloth/common/ValidationModels.py` validate data where geometry and correspondence code crosses an algorithm boundary. They reject non-finite coordinates, fractional or boolean mesh indices, malformed faces, invalid sample counts, and invalid normalized ranges. The models are frozen and reject extra fields so validated snapshots cannot be mutated accidentally.

Validation is deliberately not duplicated across every internal arithmetic operation. Functions validate external inputs once, then operate on normalized immutable values. FreeCAD documents, Sketcher, OCCT, Triangle, and PositionBasedDynamics remain authoritative for their respective domains; Pydantic schemas guard boundaries rather than replacing the domain model.

## Invariants and executable evidence

| Area | Contract | Tests |
| --- | --- | --- |
| Pattern geometry | Finite 2D control points; finite non-negative seam allowance; positive finite rectangle dimensions; integral sample counts | `tests/test_validation_models.py`, `tests/test_pattern_geometry.py` |
| Mesh arrays | Every vertex is a finite 3D point; each face has exactly three integral, in-range indices | `tests/test_validation_models.py`, `tests/test_mesh_validation.py` |
| PNG capture | Pillow verifies and decodes PNG data; NumPy derives pixel statistics; Pydantic validates policy and metric consistency | `tests/test_visual_capture_validation.py`, `tests/test_validation_models.py` |
| Triangulation | Validate Triangle output before indexing; preserve authored-boundary mapping; reject non-finite area limits; compare measured mesh area with polygon area | `tests/test_mesh.py`, `tests/test_pattern_geometry.py` |
| Seam correspondence | Positive finite lengths; tolerance in [0, 1); non-empty normalized ranges; mappings preserve or reverse endpoint order within the destination range | `tests/test_sewing_correspondence.py`, `tests/test_property_contracts.py` |
| Point-to-segment distance | GEOS computes distance to sampled line geometry; generated tests check non-negativity, endpoint bounds, and orientation invariance | `tests/test_mesh.py` |
| Arc-length sampling | Finite points of consistent dimension; finite positive total length; selected indices remain distinct and ordered | `tests/test_property_contracts.py` |
| Solver input | Distance symmetry and non-negativity for representable inputs; finite solver state; pins preserve zero inverse mass | `tests/test_property_contracts.py` |

Hypothesis explores generated inputs and stateful mutation sequences, including GEOS-backed geometry properties. CrossHair symbolically checks the pure-Python contract surface; external-library geometry is deliberately validated with property tests rather than treated as symbolically executable. These tools find counterexamples but do not prove the entire FreeCAD/OCCT/native application correct.

## Geometry-library decisions

- Use Python's `math.dist` for Euclidean point distances and Shapely/GEOS `LineString.distance` for point-to-segment queries; avoid custom projection and square/sum/square-root loops when a stable library primitive exists.
- Use NumPy vectorized cross products/norms for fallback triangle-area metrics and SciPy sparse connected-components for edge-based mesh connectivity when optional `trimesh` is absent.
- Use Pillow to verify/decode screenshot PNGs, NumPy to compute alpha/visibility/color counts, and Pydantic schemas to validate capture policy and computed image/mesh metrics.
- Use `trimesh.contains` for watertight point-in-mesh queries when its optional spatial-index backend is available; preserve the vectorized ray-parity fallback otherwise. Validate points and face indices with Pydantic before either backend.
- Keep constrained triangulation and refinement in the existing Triangle binding, and validate its output before any index-based access.
- Use the required SciPy `cKDTree` path for exact nearest-target-vertex clearance on large meshes.
- Use Shapely/GEOS for the polygon simplicity predicate; do not use its buffer operation as a drop-in seam-allowance implementation because join styles, collapsed concavities, and ring ordering can alter authored topology.
- Keep native editable geometry and 2D offsets in FreeCAD Part/OCCT. A small pure-Python seam-allowance helper remains available for FreeCAD-independent use and explicitly does not resolve self-intersections.
- Keep optional diagnostic mesh libraries out of solver-critical paths when the dependency is not installed.
