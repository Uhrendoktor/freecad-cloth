# Project structure

Implementation code lives under freecad_cloth/.

freecad_cloth/
- shared/ — neutral immutable contracts
- common/ — domain-neutral infrastructure
- pattern/ — pattern + Sketcher
- sewing/ — sewing graph + sewing UI
- avatar/ — avatar + fitting
- simulation/ — drape + solver + diagnostics
- gui.py — shared FreeCAD workbench registration primitives
- bootstrap.py — idempotent startup shared by both FreeCAD loader layouts

Ownership rules:

shared must not import Pattern, Sewing, Avatar or Simulation.

common must not import or implement a domain.

Pattern, Sewing, Avatar and Simulation own their production domain behavior. Cross-domain orchestration belongs in command/use-case modules.

Canonical implementations:
- sewing/SeamGraph.py is the only seam graph.
- pattern/SeamReference.py is the only semantic edge-reference implementation.
- shared/Collision.py is the only collision-surface value contract.
- simulation/SimulationQualityRuntime.py is the only quality-aware runtime integration.

The classic root Init.py/InitGui.py loader and the modern freecad/freecad_cloth loader are thin adapters into freecad_cloth/bootstrap.py. The shared bootstrap module owns icon-path setup, command-contract validation, and idempotent registration of all three workbenches; the adapters contain no registration or domain implementation.

The repository root is reserved for FreeCAD bootstrap files, sitecustomize.py, metadata, documentation and tooling.

Historical internal paths are migrated at callers. A compatibility surface requires an explicit external compatibility promise and a documented removal policy.


## Naming and compatibility

Within `freecad_cloth/`, follow the existing module naming convention for the owning package; do not add alternate-name or `*_compat.py` modules merely to preserve pre-release internal paths. Rename an internal module and update its callers atomically. Tests and standalone tools use the conventional `test_*.py` and snake_case names, while production domain modules retain their established package naming. A compatibility layer is appropriate only for an explicitly promised external API with a documented removal policy.

## Loader layouts

The repository supports both the classic root FreeCAD loader and the modern package loader layouts. Both delegate registration to freecad_cloth.bootstrap.initialize_workbenches, which resolves icons relative to the installation root and imports the single authoritative implementation package.
