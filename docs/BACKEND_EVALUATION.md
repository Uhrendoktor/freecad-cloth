# Simulation backend evaluation

## Python runtime baseline

`freecad-cloth` targets **Python >=3.12** across packaging, development, and the canonical FreeCAD CI runtime. This matches the current PositionBasedDynamics build requirement and keeps the workbench and its native solver adapter in one supported interpreter family.

## Backend contract

`ClothSimulationBackend` is the single application boundary for runtime simulation. PatternIR, SewingGraph, ClothSystem and DrapeTarget remain authoritative. Runtime solver code must consume those inputs without mutating authoritative FreeCAD geometry.

## Runtime policy

PositionBasedDynamics is the **sole runtime cloth solver**. The simulation package may keep PositionBasedDynamics as an installation extra so non-simulation users do not pay the native dependency cost, but there is no second runtime physics implementation or user-selectable fallback.

`ClothBackend.py` contains only the small application-facing adapter contract. `ClothSolver.py` is a headless input model containing particles, constraints, stitches and pins; it deliberately contains no integration, collision projection or constraint solving.

## Research candidates

1. **PositionBasedDynamics** — adopted production solver. The upstream project is a C++ XPBD cloth SDK with distance, bending, volume, pin, stitch, mesh/kinematic collision and self-collision support, exposed through a Python package. Its current README requires Python >=3.12. See https://github.com/evanrock520-ciencias/PositionBasedDynamics
2. **PositionBasedDynamics** — research comparator for future collision/solver investigations. It is not a runtime dependency and does not justify retaining a second in-tree solver.
3. **GPU XPBD references** — useful for later performance research, but not runtime dependencies. A replacement must still implement the existing application boundary and prove a material end-to-end benefit.

## Future replacement gate

A new native or GPU backend may become a replacement candidate only after profiling identifies a concrete limitation in PositionBasedDynamics and the candidate proves, against the same contract:

- stretch, bending, stitches, pinning and collision semantics;
- deterministic or explicitly documented repeatability;
- canonical garment visual parity;
- performance and memory measurements at the repository's defined quality levels;
- safe synchronization back into FreeCAD without backend-specific document state.

Rust is therefore an **acceleration boundary**, not a second application architecture. It should only be introduced after profiling identifies a bounded hotspot that cannot be addressed adequately in Python-side algorithms or by the current PositionBasedDynamics path.
