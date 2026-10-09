# External Library Evaluation

Supervisor evaluation for `freecad-cloth`. External libraries are adapters/tools, never replacements for the authoritative FreeCAD/Cloth document model.

## Python baseline

The project-wide supported Python baseline is **3.12 or newer**. This is reflected in packaging and the canonical FreeCAD CI runtime so optional PositionBasedDynamics integration can execute inside the same FreeCAD Python environment. Current upstream PositionBasedDynamics documentation requires Python >=3.12.

## Candidate matrix (research reference)

| Candidate | Capability | Proposed use | License / risk | Decision |
|---|---|---|---|---|
| PositionBasedDynamics | XPBD cloth, stitches, mesh/kinematic collision, self-collision, Python API | Production runtime solver | Apache-2.0; native dependency kept in the simulation extra | **Adopted** |
| PositionBasedDynamics | PBD/XPBD constraints, arbitrary-mesh collision, SDF collision, Python bindings, substeps | Research comparator only | C++ dependency + ABI/build burden | **Research only** |
| ezdxf | DXF read/write, broad version support | Production DXF adapter | MIT; relatively low integration risk | **Candidate / P2** |
| trimesh | Mesh processing, topology/proximity/closest-point queries | Non-authoritative diagnostics and benchmark metrics | Python dependency; keep optional | **Candidate / P2** |
| libigl | Geometry processing, remeshing, parametrization, distances; NumPy Python bindings | Derived-mesh/analysis utilities where OCCT is insufficient | Mixed optional modules/licensing; C++ dependency | **Evaluate selectively** |
| SciPy | Exact KD-tree nearest-neighbour queries | Garment-to-target vertex clearance on large meshes | NumPy-based dependency, installed with the main package | **Adopted / required** |
| Shapely / GEOS | Robust 2D polygon simplicity predicate | Pattern boundary simplicity validation | GEOS-backed dependency, installed with the main package | **Adopted / required** |
| svgpathtools | SVG paths, Bézier geometry, arc length, intersections | SVG interoperability and correspondence utilities | MIT; Python dependency | **Evaluate selectively** |
| meshio | Broad mesh import/export | Developer fixtures, benchmark interoperability | MIT; useful but not core | **Developer tooling** |
| pygalmesh / CGAL | Constrained/high-quality meshing | Derived simulation meshing experiments | GPL/CGAL dependency and packaging complexity | **Sandbox only** |
| vedo / VTK | Scientific visualization, scalar/vector fields, mesh analysis | Offline analysis and result inspection | Large dependency footprint | **Later / offline** |
| Seamly2D | Measurement-driven parametric patterns | Design/reference/interoperability research | GPL; do not embed core | **Reference only** |
| FreeSewing | Parametric pattern design and plugins | Pattern-model/workflow reference; possible import bridge | JS ecosystem; do not embed core | **Reference only** |

## PositionBasedDynamics status

The PositionBasedDynamics adapter is the production runtime boundary. PatternIR/SewingGraph/DrapeTarget remain authoritative; `ClothBackend` isolates FreeCAD document code from PositionBasedDynamics APIs.

The deterministic `ClothSystem` is input construction and validation logic, not a second physics backend. There is no XPBD fallback or runtime solver registry.

PositionBasedDynamics remains an optional **installation extra** so pattern/sewing-only installations can stay lightweight. When simulation is enabled, the workbench uses PositionBasedDynamics as the sole runtime physics implementation.

## Historical research tasks

The library investigation was tracked through issues #479–#481. Those issues are closed; the entries are retained only as historical traceability. They are not current implementation work items.

## Architecture rules

- Sketcher/Part/OCCT remain authoritative for editable pattern geometry.
- Cloth semantic IDs remain authoritative for sewing/pattern meaning.
- Generated simulation topology is disposable.
- External libraries operate on derived representations.
- No second document database, scene graph, solver contract, or drafting kernel.
- Optional dependencies must be isolated and not silently become release requirements.
- Preserve one canonical GitHub Actions workflow.

## Evidence reviewed

- PositionBasedDynamics documents distance, bending, pin, stitch, mesh/kinematic collision, self-collision, spatial-hash broad phase, and a Python API; its current upstream README requires Python >=3.12 and Apache-2.0 licensing.
- PositionBasedDynamics documents Python bindings, XPBD constraints, arbitrary-mesh and SDF collision, substepping, and parallelized solving.
- libigl provides NumPy-native geometry processing and optional Triangle/CGAL-related modules.
- pygalmesh provides a Python frontend to CGAL mesh generation.
- ezdxf provides DXF creation/read/modify/write and current documentation lists MIT licensing.
- Shapely provides robust GEOS-backed polygon buffer and geometry operations.
- trimesh provides mesh processing and closest-point/proximity utilities.
- svgpathtools provides Bézier/SVG path operations including arc length and intersections.
- meshio provides broad mesh-format conversion and point/cell data handling.
- vedo provides VTK/NumPy mesh analysis and scalar-field visualization.
- Seamly2D and FreeSewing are useful references for measurement-driven and parametric pattern workflows but should not become core runtime dependencies.


## Numerical validation and complexity audit

### Boundary validation

Pydantic v2 is adopted for **external and cross-module numerical input boundaries** through `freecad_cloth.common.ValidationModels`. Schemas reject NaN/infinity, booleans masquerading as numbers, fractional/string mesh indices, invalid sample counts, and out-of-range connectivity before geometry algorithms run. Models are immutable and reject unknown fields. Integer coordinates normalize to floats; mesh indices and sample counts remain exact integers.

Pydantic is not used for each arithmetic operation or inside per-particle solver loops: model construction in hot loops adds overhead without stronger invariants. Core math remains testable by Hypothesis and CrossHair. Property-based tests explore broad input spaces; they are regression evidence, not a proof of correctness.

### Delegation choices

- **Triangle** remains responsible for constrained Delaunay triangulation and mesh refinement. The adapter retains checks needed for authored-boundary provenance, face orientation, and area preservation. Boundary-vertex reconciliation now builds one quantized-coordinate index instead of rescanning all output vertices for every boundary point.
- **trimesh** remains an optional diagnostics library for point-to-triangle-surface queries and mesh metrics. The dependency-free component-count fallback stays because it preserves optional-install behavior.
- **`math.dist`** replaces hand-rolled Euclidean norm loops for vertex clearance. It prevents non-strict `zip` from silently ignoring mismatched dimensions and delegates norm arithmetic to the standard library.
- **FreeCAD Part/OCCT** remains authoritative for native editable geometry and offsets. Shapely is required for the polygon simplicity predicate, but is not used as a drop-in seam-allowance buffer: buffer join styles, collapsed concavities and ring ordering can alter authored topology.
- **svgpathtools**, **libigl**, and other optional geometry tools remain candidates until a concrete production path and FreeCAD packaging/runtime compatibility are demonstrated. Do not duplicate a geometry kernel simply to remove loops that preserve semantic identities a library does not know about.

Research references:
- [Pydantic strict mode](https://pydantic.dev/docs/validation/2.12/concepts/strict_mode/)
- [Hypothesis quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html)
- [trimesh proximity queries](https://trimesh.org/trimesh.proximity.html)

## Implemented geometry-library accelerations

SciPy and Shapely are required runtime dependencies declared in `pyproject.toml` and installed
by the same package setup and pinned FreeCAD CI image. The production geometry paths do not branch
between optimized and scalar fallback implementations.

- `nearest_target_clearance` uses one exact `scipy.spatial.cKDTree` nearest-neighbour query for
  all non-empty vertex sets. Non-finite or unrepresentable results fail closed; there is no scalar
  production fallback.
- `PatternMesh._self_intersects` uses GEOS/Shapely's simplicity predicate on the closed polygon
  boundary for all input sizes. `SurfacePen.polygon_self_intersects` retains its tolerance-aware
  predicate because near-coincident touch handling is part of that authoring contract.
- Seam-allowance buffering was **not** replaced by Shapely `buffer`: its join styles, handling of
  collapsed concavities/self-intersections, and ring ordering can alter generated outline topology.
  FreeCAD Part/OCCT also remains authoritative for native editable geometry.
- Run `python tools/benchmarks/benchmark_geometry_libraries.py --sizes 128 512 1024` after
  `python -m pip install -e .` to compare result equivalence and timings on the local
  machine. Timings are informative only; no hardware-sensitive threshold is used as a CI assertion.

## Python symbolic contract checking

The canonical static gate runs CrossHair against `tools/crosshair_contracts.py`. The contracts call
the **production implementations** for particle distance, seam-parameter mapping, interpolation,
and line intersection; the file is not a duplicate implementation of those formulas. CrossHair
symbolically explores the supported paths and reports counterexamples to the assertions. This is
stronger than testing a few concrete examples, but it is not a complete proof of arbitrary Python,
IEEE-754 behaviour, FreeCAD/OCCT, or native PositionBasedDynamics code. Hypothesis tests and native
integration/visual acceptance remain separate validation layers.
