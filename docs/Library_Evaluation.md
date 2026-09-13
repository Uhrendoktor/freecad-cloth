# Library evaluation

## Selection rules

External libraries are adapters or developer tooling unless the project explicitly promotes them after benchmarked parity. FreeCAD Sketcher/Part/OCCT remain authoritative for editable pattern geometry; Cloth semantic IDs remain authoritative; generated simulation topology remains disposable.

| Candidate | Capability | Proposed role | Compatibility / dependency posture | Decision |
|---|---|---|---|---|
| Tissu | XPBD cloth, bending, pins, stitches, mesh/kinematic collision, self-collision | Optional simulation backend | Current upstream docs require Python >=3.12; isolated/sandbox only while project supports >=3.9 | Benchmark |
| PositionBasedDynamics | XPBD/PBD, mesh/SDF collision, Python bindings | Physics comparator / optional backend | Native build and ABI review required | Benchmark later |
| libigl | geometry processing, parametrization, distances, remeshing | Analysis/mesh utilities where OCCT is insufficient | Optional/native packaging review | Evaluate |
| CGAL/pygalmesh | constrained/high-quality meshing | Derived simulation mesh generation | Higher packaging/licensing review | Sandbox |
| Shapely/GEOS | robust 2D polygon operations | Diagnostics/export preprocessing | Optional, never authoritative | Evaluate selectively |
| trimesh | mesh validation and proximity | Acceptance diagnostics and backend comparison | Current docs target Python 3.10+; use lazy optional import, no core dependency yet | Implement first |
| meshio | broad mesh I/O | Benchmark fixtures/interoperability | Development/optional only | Low priority |
| ezdxf | DXF read/write | Production DXF interoperability | Optional export dependency | Implement candidate |
| svgpathtools | SVG curve arc-length/intersections | SVG/correspondence utilities | Optional | Evaluate after export audit |
| VTK/vedo | scalar-field/mesh analysis | Offline diagnostic rendering | Heavy | Defer |
| Seamly2D / FreeSewing | garment-specific pattern workflows | Research/interoperability reference | Avoid embedding external cores | Study only |

## Architecture constraints

1. Do not introduce a second project database or scene graph.
2. Do not make external physics or geometry libraries authoritative over FreeCAD document geometry.
3. Prefer lazy/optional imports for non-core dependencies.
4. Every adopted library needs a version/license/maintenance record and a focused regression test.
5. The canonical CI workflow remains the only project workflow.
6. Dependency compatibility is an explicit gate: a library that raises the minimum supported Python/FreeCAD baseline is sandboxed until the project deliberately changes that baseline.

## Current implementation path

1. `trimesh` validation/proximity adapter (#481) provides machine-checkable mesh health and garment/target clearance metrics without becoming a mandatory dependency.
2. Tissu evaluation (#479) uses the same metrics plus constraint/collision/determinism benchmarks; no Tissu wheel is installed in the core workbench.
3. DXF export adapter (#480) consumes the authoritative export IR and keeps native TechDraw/SVG available.
4. libigl/Shapely/svgpathtools are considered only after concrete gaps are demonstrated by the Pattern/Sewing/export audits.
