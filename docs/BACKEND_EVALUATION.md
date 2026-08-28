# Cloth solver backend evaluation

The adapter is intentionally solver-neutral. Candidate families were assessed against the required capabilities: PBD/XPBD is the best first fit for interactive garment draping because constraints map naturally to seams/pins and it can remain CPU-first; FEM is attractive for physically based material response but adds more demanding meshing/material infrastructure; hybrid approaches can be considered after the adapter stabilizes.

Selection criteria are stretch, shear, bending, sewing, pinning, body/self collision, friction, stable stepping, CPU/GPU portability, Python/C++ integration, build complexity, maintenance, and license compatibility. No third-party dependency is made mandatory by this task because those properties must be audited against the exact version adopted.

First production adapter target: an XPBD/PBD-style constraint backend behind `ClothSolver`, with seam constraints generated from stable pattern edge ranges and collision surfaces supplied by `AvatarCollision`. Deterministic CI uses fixed meshes, fixed constraints, fixed timestep/count, and tolerance-based position comparisons.

Initially approximate/defer: sophisticated anisotropic fabric, advanced friction, GPU-only acceleration, self-collision tuning, and sewing-order optimization. These remain backend capabilities rather than pattern-model requirements.
