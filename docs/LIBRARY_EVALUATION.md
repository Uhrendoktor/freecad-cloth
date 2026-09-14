# External Library Evaluation

Supervisor evaluation for `freecad-cloth`. External libraries are adapters/tools, never replacements for the authoritative FreeCAD/Cloth document model.

## Python baseline

The project-wide supported Python baseline is **3.12 or newer**. This is reflected in packaging and the canonical FreeCAD CI runtime so optional Tissu integration can execute inside the same FreeCAD Python environment. Current upstream Tissu documentation requires Python >=3.12.

## Ranked candidates

| Candidate | Capability | Proposed use | License / risk | Decision |
|---|---|---|---|---|
| Tissu | XPBD cloth, stitches, mesh/kinematic collision, self-collision, Python API | Optional simulation backend | Apache-2.0; Python >=3.12; backend parity and packaging risk remain high | **Benchmark / P2** |
| PositionBasedDynamics | PBD/XPBD constraints, arbitrary-mesh collision, SDF collision, Python bindings, substeps | Backend comparator / research | C++ dependency + ABI/build burden | **Benchmark / P2** |
| ezdxf | DXF read/write, broad version support | Production DXF adapter | MIT; relatively low integration risk | **Candidate / P2** |
| trimesh | Mesh processing, topology/proximity/closest-point queries | Non-authoritative diagnostics and benchmark metrics | Python dependency; keep optional | **Candidate / P2** |
| libigl | Geometry processing, remeshing, parametrization, distances; NumPy Python bindings | Derived-mesh/analysis utilities where OCCT is insufficient | Mixed optional modules/licensing; C++ dependency | **Evaluate selectively** |
| Shapely / GEOS | Robust 2D polygon predicates/buffer/overlay | Export/preflight/diagnostic preprocessing | Low integration risk; not authoritative geometry | **Evaluate selectively** |
| svgpathtools | SVG paths, Bézier geometry, arc length, intersections | SVG interoperability and correspondence utilities | MIT; Python dependency | **Evaluate selectively** |
| meshio | Broad mesh import/export | Developer fixtures, benchmark interoperability | MIT; useful but not core | **Developer tooling** |
| pygalmesh / CGAL | Constrained/high-quality meshing | Derived simulation meshing experiments | GPL/CGAL dependency and packaging complexity | **Sandbox only** |
| vedo / VTK | Scientific visualization, scalar/vector fields, mesh analysis | Offline analysis and result inspection | Large dependency footprint | **Later / offline** |
| Seamly2D | Measurement-driven parametric patterns | Design/reference/interoperability research | GPL; do not embed core | **Reference only** |
| FreeSewing | Parametric pattern design and plugins | Pattern-model/workflow reference; possible import bridge | JS ecosystem; do not embed core | **Reference only** |

## Tissu implementation plan

1. Create a `TissuBackend` adapter behind `ClothSimulationBackend`.
2. Map `PatternIR` mesh + `SewingGraph` into Tissu cloth/stitch constraints.
3. Map pins/material/quality/collision settings without changing public UI contracts.
4. Adapt `DrapeTarget` to Tissu mesh/kinematic collision.
5. Compare stretch, bend, stitches, collision and self-collision against the deterministic CPU backend.
6. Compare repeatability for identical inputs.
7. Compare simulation time and memory at Fast/Balanced/Final resolutions.
8. Compare canonical garment visual output.
9. Run the backend inside the same Python 3.12 FreeCAD runtime used by CI before calling it runtime-compatible.
10. Keep Tissu optional until parity and packaging are demonstrated.

## First low-risk implementation targets

- **#480**: DXF export adapter using `ezdxf` behind the canonical export IR.
- **#481**: `trimesh` validation/proximity adapter for mesh sanity and CPU-vs-Tissu metrics.
- **#479**: umbrella research/benchmark task for Tissu and the broader library matrix.

## Architecture rules

- Sketcher/Part/OCCT remain authoritative for editable pattern geometry.
- Cloth semantic IDs remain authoritative for sewing/pattern meaning.
- Generated simulation topology is disposable.
- External libraries operate on derived representations.
- No second document database, scene graph, solver contract, or drafting kernel.
- Optional dependencies must be isolated and not silently become release requirements.
- Preserve one canonical GitHub Actions workflow.

## Evidence reviewed

- Tissu documents distance, bending, pin, stitch, mesh/kinematic collision, self-collision, spatial-hash broad phase, and a Python API; its current upstream README requires Python >=3.12 and Apache-2.0 licensing.
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
