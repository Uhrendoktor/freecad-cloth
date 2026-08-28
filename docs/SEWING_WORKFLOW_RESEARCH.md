# Sewing and draping workflow research

## Common production workflow

1. Capture body measurements or select a body/avatar specification.
2. Draft reusable 2D pattern pieces from measurements and construction rules.
3. Keep the **seam line** as the design/source boundary and derive a separate cut boundary for seam allowance.
4. Add construction metadata: grainline/fold line, notches, labels, dart/fold information, piece quantity and cut instructions.
5. Define seam pairings and alignment information before meshing.
6. Validate the flat pattern and export a print/CAD interchange representation.
7. Triangulate/mesh each piece for simulation while retaining the parametric pattern as the source of truth.
8. Place or pin pieces around the avatar, assemble paired seam edges, and simulate drape.
9. Inspect fit, collision/interpenetration and seam stress; revise parameters and repeat.

The important architectural split is **pattern authoring -> sewing graph -> simulation mesh**. Simulation geometry must be regenerable from the pattern model instead of becoming the authoritative pattern representation.

## Existing open-source references

| Project | Useful capability | Integration assessment |
| --- | --- | --- |
| Seamly2D | Measurement-driven reusable parametric patterns | Strong workflow reference; GPLv3+ prevents treating it as a core embedded dependency. |
| FreeSewing | MIT parametric pattern library and reusable blocks | Good interoperability/reference target; Node/JavaScript runtime is not a core FreeCAD dependency. |
| Tissu | Apache-2.0 C++ XPBD SDK; distance/bending/pin/stitch, mesh/self collision, spatial hash, Python API | Attractive optional backend. Current README requires Python >=3.12 plus C++17/CMake/OpenMP and pybind11, so ABI/toolchain breadth makes mandatory integration inappropriate. |
| PositionBasedDynamics | MIT PBD/XPBD library, Python bindings, collision and deformable constraints | Strong optional/reference backend. Native CMake/Eigen/pybind build and Python extension ABI require packaging work; keep optional. |
| XPBD-Cloth | Stretch, shear, bend, area and self-collision reference | Useful algorithm benchmark; not the portable first backend. |
| Blender Cloth Dynamics | XPBD-style stretch/bend/pinning/collision/substeps | Useful interoperability and validation reference; Blender remains external. |
| ARCSim | Adaptive cloth/thin-shell simulation | Valuable historical algorithm reference, not a core dependency. |

## Current architecture

The bundled deterministic CPU XPBD backend remains the reference implementation. `PatternModel` is authoritative; Sketcher, native OCCT geometry and MeshPart are adapters at the FreeCAD boundary. Stable semantic edge IDs are never inferred from generated OCCT/MeshPart ordering.

The garment solver now has explicit stretch, shear and reduced-distance bending constraint families plus deterministic particle self-collision. These are solver-level quality gates; a future backend may provide more sophisticated dihedral bending or continuous collision detection behind the same interface.

## Native FreeCAD replacement strategy

- OCCT `makeOffset2D` is exposed through `PatternOCCT.py` as an optional document-boundary adapter.
- MeshPart triangulation is exposed through `PatternMeshFreeCAD.py`; semantic boundary provenance remains independent from generated face ordering.
- Sketcher is exposed through `PatternSketch.py`; it mirrors the PatternPiece outline but does not become the semantic source of truth.
- `App.Placement`, TechDraw/Draft and richer export adapters remain tracked separately in #88.

## Backend audit — 2026-08-28

### Tissu

Tissu currently advertises distance, bending, volume, pin and stitch constraints; spatial-hash broad phase; sphere/capsule/plane and mesh colliders; kinematic colliders; self-collision; gravity and aerodynamic force. Its build requires CMake >=3.20, C++17, OpenMP and Python >=3.12 with pybind11-based packaging. Linux, macOS and Windows are listed as supported. License: Apache-2.0.

Decision: **optional only**. The Python >=3.12 requirement and native build chain make it unsuitable as a mandatory runtime dependency for a FreeCAD workbench that should remain portable across supported FreeCAD Python environments.

### PositionBasedDynamics

PositionBasedDynamics is MIT licensed and provides XPBD distance/isometric-bending/volume constraints, point-edge/point-triangle/edge-edge collision constraints, deformable-body support, signed-distance-field collision and substepping. The repository supplies Python bindings through a CMake/pybind build and documents platform-specific compiled extension wheels/builds.

Decision: **optional only**. It is technically mature and maps well to the simulation contract, but compiled Python extensions remain sensitive to the FreeCAD Python ABI and packaging environment. Benchmark it behind the backend adapter before any adoption.

## Planned milestones

- [x] FreeCAD workbench skeleton and canonical CI.
- [x] Parametric pattern document model and semantic marks.
- [x] Sewing graph and solver backend adapter.
- [x] Interactive drafting GUI and GUI smoke coverage.
- [x] Initial seam allowance geometry.
- [x] Humanoid/body collision contract and fitting metadata.
- [x] Deterministic drape metrics/repeatability gates.
- [x] Initial native Sketcher adapter.
- [x] Explicit shear/bending and deterministic particle self-collision implementation.
- [ ] OCCT offset parity/regression decision (#85).
- [ ] MeshPart/Netgen provenance/quality decision (#86).
- [ ] Consolidate solver authority behind ClothSimulationBackend (#87).
- [ ] Native Placement/export decision (#88).
- [ ] Optional Tissu/PositionBasedDynamics adapter benchmark (#83).
- [ ] GUI screenshot/documentation pipeline (#68).
- [ ] Packaging, examples and release-quality documentation.

## Sources

- FreeCAD: https://github.com/FreeCAD/FreeCAD
- Seamly2D: https://github.com/FashionFreedom/Seamly2D
- FreeSewing: https://github.com/freesewing/freesewing
- Tissu: https://github.com/evanrock520-ciencias/Tissu
- PositionBasedDynamics: https://github.com/InteractiveComputerGraphics/PositionBasedDynamics
- XPBD-Cloth: https://github.com/steampower33/XPBD-Cloth
