# Project structure

Implementation code lives under freecad_cloth/.

freecad_cloth/
- shared/ — neutral immutable contracts
- common/ — domain-neutral infrastructure
- pattern/ — pattern + Sketcher
- sewing/ — sewing graph + sewing UI
- avatar/ — avatar + fitting
- simulation/ — drape + solver + diagnostics
- gui.py — common FreeCAD workbench registration

Ownership rules:

shared must not import Pattern, Sewing, Avatar or Simulation.

common must not import or implement a domain.

Pattern, Sewing, Avatar and Simulation own their production domain behavior. Cross-domain orchestration belongs in command/use-case modules.

Canonical implementations:
- sewing/SeamGraph.py is the only seam graph.
- pattern/SeamReference.py is the only semantic edge-reference implementation.
- shared/collision.py is the only collision-surface value contract.
- simulation/SimulationQualityRuntime.py is the only quality-aware runtime integration.

The classic root Init.py/InitGui.py loader and the modern freecad/freecad_cloth loader register the same workbenches and contain no domain implementation.

The repository root is reserved for FreeCAD bootstrap files, sitecustomize.py, metadata, documentation and tooling.

Historical internal paths are migrated at callers. A compatibility surface requires an explicit external compatibility promise and a documented removal policy.


## Loader layouts

The repository supports both the classic root FreeCAD loader and the modern package loader layouts; both resolve the same workbench implementations.
