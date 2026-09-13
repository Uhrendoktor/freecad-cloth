# Simulation backend evaluation

## Backend contract

`ClothSimulationBackend` is the only solver boundary. PatternIR/SewingGraph/SimulationScene/DrapeTarget remain authoritative. Backend implementations may be optional and must not mutate authoritative FreeCAD geometry.

## Candidate ladder

1. **CPU XPBD reference** — release correctness baseline and deterministic comparison target.
2. **Tissu** — serious cloth-specific optional backend. Upstream currently exposes XPBD distance/bending/pin/stitch constraints, mesh/kinematic colliders and self-collision, plus a Python package, but current upstream requirements are Python >=3.12. Keep sandboxed until compatibility and parity are demonstrated. citeturn449272search0
3. **PositionBasedDynamics** — research-grade PBD/XPBD comparator for collision and solver experiments; native build/ABI burden means later evaluation.
4. **GPU XPBD research candidates** — ClothDD is MIT-licensed and demonstrates XPBD with CPU domain decomposition plus OpenGL 4.3 graph-colored GPU compute; this is a performance research reference, not a runtime dependency. citeturn309432search0 XPBD-Cloth demonstrates a Vulkan 1.4/C++20 GPU path and is useful as a second research reference, but its platform/toolchain requirements make direct reuse inappropriate for the FreeCAD Python workbench. citeturn309432search3

## Decision gates

A backend must pass constraint mapping, DrapeTarget collision, self-collision, determinism, canonical garment visual parity, and Fast/Balanced/Final performance measurements before it can become user-selectable.

A GPU backend must additionally prove that data transfer does not dominate simulation time and that the result can be synchronized back into FreeCAD without making the document state backend-specific.
