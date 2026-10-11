# Architecture decisions

This file contains durable software-architecture decisions only. Current status, experiments and agent process rules belong elsewhere.

## D-0001 — Python remains the application language

Status: accepted

The external FreeCAD workbench, document adapters, GUI, persistence model and domain orchestration remain Python. Performance work starts with profiling and algorithm/data-structure improvements.

Reference: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Workbench_creation.md

## D-0002 — PositionBasedDynamics is the sole production cloth runtime

Status: accepted

PositionBasedDynamics (pyPBD) is the only production runtime solver. There is no runtime solver registry or user-selectable fallback engine.

ClothSimulationBackend isolates solver APIs and ClothSolver remains only the deterministic input model.

## D-0003 — Rust is an optional acceleration boundary

Status: accepted

Do not add Rust until profiling identifies a bounded hotspot that remains material after Python-side optimization. A future Rust module may implement the existing backend contract, but not another document, pattern, persistence or GUI architecture.

## D-0004 — FreeCAD and Cloth have distinct single authorities

Status: accepted

FreeCAD owns document persistence and native geometry. Cloth domain objects own garment semantics. IRs, meshes, collision surfaces and solver state are derived.

## D-0005 — Collision surfaces are neutral contracts

Status: accepted

shared.CollisionSurface is the only solver-facing collision-surface value type. FreeCAD tessellation is an explicit host adapter. Avatar and Simulation exchange only the neutral contract.

## D-0006 — Validation belongs with the invariant owner

Status: accepted

Keep checks that protect a domain invariant, trust boundary or recovery condition. Fold or remove checks that merely repeat an invariant already enforced by the authoritative preparation step.

## D-0007 — Runtime composition is explicit

Status: accepted

Production code must not monkey-patch classes or replace module functions to select quality, collision or CI behavior. Composition passes explicit builders/configuration or uses a dedicated application-layer entry point.

## D-0008 — One canonical owner per tooling concern

Status: accepted

Ruff owns lint/formatting, Import Linter owns dependency contracts, Vulture is limited to high-confidence dead-code analysis, and CI verifies backend identity without mutating runtime classes.

## Historical note

Tissu was considered during an earlier solver migration. That decision was superseded by D-0002 and is not a runtime dependency.
