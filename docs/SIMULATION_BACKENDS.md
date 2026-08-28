# Cloth simulation backend evaluation

## Recommendation

Keep the solver dependency optional and target a small adapter API first. The current `ClothSolver.step(state, dt)` contract is intentionally minimal. A production adapter should additionally expose mesh constraints, pin constraints, sewing constraints, collision bodies, material parameters, and deterministic stepping without leaking solver-specific types into the pattern model.

## Evaluation criteria

Candidate backends should be scored on stretch/shear/bending, sewing constraints, pinning, body and self collision, friction, stable time stepping, CPU/GPU portability, Python/C++ integration, build complexity, maintenance activity, and license compatibility. The project should not make a large third-party solver mandatory until these criteria are verified against the candidate's current release.

## Constraint mapping

Pattern edges become mesh boundary ranges. A seam pairs two ranges by stable edge ID plus normalized parameters; the solver adapter converts those pairs into positional/coincident constraints. Notches remain semantic matching marks and can assist correspondence but should not become solver-specific objects. Pinning is represented as vertex/parameter constraints. Collision geometry is supplied independently by the avatar/collision pipeline.

## Determinism strategy

Core tests should construct a tiny generated mesh, apply a fixed constraint set, run a fixed number of steps, and compare positions within a documented tolerance. Solver-specific floating-point tolerances belong in the adapter tests; the pattern/data layers must remain exact and solver-independent.

## Deferred functionality

Initially defer sophisticated friction models, self-collision tuning, GPU-only features, sewing-order optimization, and complex material anisotropy. They should be adapter capabilities rather than requirements of the core model.

This document is an adapter specification, not a claim that any candidate is currently selected without a fresh license/build/maintenance audit.
