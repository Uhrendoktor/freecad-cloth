# Architecture

## Authorities

1. FreeCAD owns document persistence and host geometry.
2. Cloth domain objects own garment meaning.
3. Simulation meshes, particles, constraints, collision acceleration data and solver state are disposable derived state.
4. Each concept has one authority: no parallel JSON project database, collision-reference model, seam model, runtime solver or lifecycle state machine.

## Package boundaries

freecad_cloth/
- shared/ — host/domain-neutral immutable value contracts
- common/ — reusable infrastructure; must not import domain packages
- pattern/ — pattern domain, Sketcher adapter and UI/commands
- sewing/ — canonical sewing graph and UI/commands
- avatar/ — mannequin/provider/fitting domain and UI/commands
- simulation/ — target, preparation, runtime solver and diagnostics
- gui.py — shared FreeCAD workbench registration base

The two FreeCAD loader layouts are thin adapters into the same implementation tree.

## Dependency direction

FreeCAD loader -> workbench commands/task panels -> domain objects/value models -> derived preparation/adapters -> ClothSimulationBackend -> PositionBasedDynamics.

Application-level command modules may orchestrate multiple domains. Core domain/runtime modules must not import another domain merely to construct convenience objects.

## Pattern

PatternModel is the canonical in-memory pattern value model. PatternSketch and SketchAuthority adapt persistent PatternPiece state to native Sketcher geometry.

Semantic edge identity is owned by pattern.SeamReference. Edge references contain a semantic ID plus an exact geometry/provenance signature. Missing or changed references fail closed; repair is explicit.

PatternIR is a derived processing representation, not a persistence model.

## Sewing

The persisted FreeCAD Seam object is the document authority. PatternModel.Seam is the canonical immutable value representation. sewing.SeamGraph is the single processing graph.

M:N sewing expansion, correspondence and stitch records are derived from canonical seams. No compatibility SeamConstraint, second SewingPair model or alternate seam-reference namespace is maintained.

Persistence and domain modules do not depend on another domain's view module.

## Avatar and collision

Avatar providers produce a neutral shared.CollisionSurface plus parameters and landmarks. They do not depend on the simulation runtime.

DrapeTarget owns persistent target identity and validity. FreeCAD tessellation is isolated in common.FreeCADCollision. The result is the single neutral CollisionSurface contract.

There is no persistent AvatarCollision proxy object in the simulation model.

## Simulation lifecycle

Persistent inputs include pattern references, target reference, quality/material settings, collision settings, pins, stitches and solver controls.

The simulation proxy owns one lifecycle state:

READY_FOR_SIMULATION
 -> STALE when target/source inputs are no longer current
 -> BLOCKED when authoritative semantic inputs cannot be simulated

DrapeTarget.target_status owns target validity. The simulation proxy owns derived-scene validity. There is no second recompute guard.

SimulationQualityRuntime is the canonical quality-aware runtime and uses explicit mesh-builder composition. It never monkey-patches another module at runtime.

## Solver boundary

ClothBackend is a small solver-neutral adapter contract. PositionBasedDynamics is the only production backend.

ClothSolver contains only Particle, DistanceConstraint and ClothSystem input data. It is not a second physics engine.

CI verifies backend identity explicitly; sitecustomize does not alter production simulation classes.

## Diagnostics and persistence

Diagnostics are derived evidence and live in simulation/. FCStd is the project authority. External JSON, SVG and DXF formats are adapters, not alternate project databases.

## Non-goals

Do not replace Sketcher, add a second scene graph, add a second cloth solver, add a second persistent garment database, or restore compatibility modules only to preserve historical internal imports.


## Persisted authority and packaging metadata

The persisted FreeCAD Seam object is the document-level source of truth; PatternModel.Seam is the canonical immutable in-memory/value representation, and other headless/value forms are derived representations for computation and validation. The repository keeps `package.xml` and `pyproject.toml` as separate packaging metadata surfaces. Do not assume their version values or content entries must match.
