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

The important architectural split is therefore **pattern authoring -> sewing graph -> simulation mesh**. Simulation geometry must be regenerable from the pattern model instead of becoming the authoritative pattern representation.

## Existing open-source references

| Project | Useful capability | Integration assessment |
| --- | --- | --- |
| [Seamly2D](https://github.com/FashionFreedom/Seamly2D) | Measurement-driven, reusable parametric patterns and multi-size/custom measurement files | Strong reference for the pattern model and measurement UX; GPLv3+ makes direct code reuse a licensing decision. |
| [Blender seams-to-sewing-pattern](https://github.com/r0mko/blender-seams-to-sewing-pattern) | Seam markup, conversion to sewing pattern, quick cloth setup and SVG export | Useful interoperability/reference workflow; depends on Blender UV/remeshing and is not a suitable core FreeCAD dependency. |
| [Tissu](https://github.com/evanrock520-ciencias/Tissu) | Apache-2.0 C++ XPBD SDK; distance/bending/pin/stitch constraints, mesh collision and self-collision, Python API | Most attractive optional future native backend candidate; requires ABI/build integration work and independent numerical validation. |
| [PositionBasedDynamics](https://github.com/InteractiveComputerGraphics/PositionBasedDynamics) | MIT PBD library with collision handling and Python interface | Mature general-purpose reference and possible optional backend; not garment/sewing-specific. |
| [HinaCloth](https://github.com/HinaPE/HinaCloth) | Modern XPBD cloth benchmark with C++ solver and Python/Blender tooling | Useful performance/quality reference; keep optional because the repository is benchmark-oriented. |
| [XPBD-Cloth](https://github.com/steampower33/XPBD-Cloth) | GPU-oriented XPBD with stretch, shear, bend, area, self-collision and small-step techniques | Strong algorithmic reference; GPU/compute dependency is inappropriate for the first portable FreeCAD backend. |
| [ARCSim](https://github.com/zhou13/arcsim) | Adaptive remeshing and cloth/thin-shell simulation | Historically important technical reference, but its upstream README states non-commercial use, so it is not a safe dependency for an open commercial-friendly FreeCAD workbench. |
| [GarmentLab](https://github.com/GarmentLab/GarmentLab) | Garment/body interaction simulation using PBD/FEM in NVIDIA Isaac Sim | Valuable benchmark/assets reference, but Isaac Sim is far too heavyweight to make a core FreeCAD dependency. |

## Current simulation direction

The bundled CPU XPBD-style solver remains the first backend because seams, pins and distance constraints map directly to sewing semantics and it is portable and deterministic. The new avatar collision contract accepts triangulated FreeCAD body surfaces while retaining the sphere fallback. The solver now consumes a `CollisionSurface` directly and uses a deterministic triangle-surface contact approximation.

Blender 5.2 is a useful current reference: its experimental Cloth Dynamics system is also XPBD-based and exposes stretch, bend, pinning, collision radius, substeps and constraint iterations. Blender's documentation explicitly recommends closed/manifold collider meshes and notes that thin colliders can tunnel; these are useful validation rules for the FreeCAD implementation. The FreeCAD project should exchange meshes/pattern metadata with Blender rather than embed Blender as a runtime dependency.

## Planned milestones

- [x] FreeCAD workbench skeleton and canonical CI.
- [x] Parametric pattern document model and semantic marks.
- [x] Initial sewing graph and solver backend adapter.
- [x] Interactive drafting GUI and GUI smoke coverage.
- [x] Initial seam allowance geometry.
- [x] Solver-neutral avatar collision contract.
- [ ] Production seam allowance/notch/grainline geometry and deterministic SVG/DXF contracts.
- [ ] Robust imported humanoid collision mesh and fitting UI, including closed/manifold validation and collision thickness controls.
- [ ] Better piece assembly/placement and seam-edge matching diagnostics.
- [ ] XPBD quality gates: substeps, shear/bending, self-collision and convergence metrics.
- [ ] Optional Tissu/other native backend prototype behind the adapter, after license/API/ABI review.
- [ ] GUI screenshot/documentation pipeline using the single canonical workflow.
- [ ] Packaging, examples and release-quality documentation.

## Sources

- FreeCAD source and workbench examples: [FreeCAD](https://github.com/FreeCAD/FreeCAD).
- Seamly2D: [FashionFreedom/Seamly2D](https://github.com/FashionFreedom/Seamly2D).
- Blender Cloth Dynamics: [Blender 5.2 LTS manual](https://docs.blender.org/manual/en/5.2/modeling/geometry_nodes/simulation/cloth_dynamics.html).
- Blender XPBD Solver: [developer documentation](https://developer.blender.org/docs/features/nodes/xpbd_solver/).
- Tissu: [evanrock520-ciencias/Tissu](https://github.com/evanrock520-ciencias/Tissu).
- PositionBasedDynamics: [InteractiveComputerGraphics/PositionBasedDynamics](https://github.com/InteractiveComputerGraphics/PositionBasedDynamics).
- GarmentLab: [GarmentLab/GarmentLab](https://github.com/GarmentLab/GarmentLab).
