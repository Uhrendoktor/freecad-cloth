# Simulation backend

Cloth dynamics are delegated to the upstream [PositionBasedDynamics](https://github.com/InteractiveComputerGraphics/PositionBasedDynamics) project through its `pyPBD` Python bindings. `XPBD.py` is only an adapter between FreeCAD/garment state and the library; it must not contain a second XPBD integrator or hand-written constraint projection.

## Dependency

The supported binding is `pypbd==2.2.2`, which provides native XPBD distance and isometric-bending constraints and the PositionBasedDynamics time-step controller. Install it into the same Python environment used by FreeCAD:

```text
python3 -m pip install pypbd==2.2.2
```

The repository CI image installs the same pinned package. The dependency is also declared in `requirements-simulation.txt`.

## Architecture

`ClothSystem` remains as a compatibility/domain facade for existing workbench code. It converts particle state and garment constraints into `XPBDClothSolver`; `XPBDClothSolver` creates and updates a `pypbd.Simulation`/`SimulationModel` and delegates the actual integration and constraint projection to PositionBasedDynamics.

Collision geometry should be registered as PBD collision objects at the simulation-scene layer. Primitive Python projection helpers are intentionally not retained in the solver adapter.
