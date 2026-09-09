# Packaging and module architecture

The repository uses a package-oriented Python architecture with a thin FreeCAD bootstrap at the repository root. The package tree is the canonical home of implementation code.

## Current architecture

```text
freecad-cloth/
├── Init.py
├── InitGui.py
├── pyproject.toml
├── freecad_cloth/
│   ├── __init__.py
│   ├── gui.py
│   ├── common/
│   ├── shared/
│   ├── pattern/
│   ├── sewing/
│   ├── avatar/
│   └── simulation/
└── tests/
```

`Init.py` and `InitGui.py` are the only Python files intentionally kept at the workbench root because FreeCAD discovers them when the repository is installed directly into a `Mod` directory. Every command, model, adapter, solver, target, GUI module, and other implementation belongs under `freecad_cloth/`.

## Package responsibilities

`freecad_cloth.pattern` owns pattern geometry, PatternPiece/PatternIR, Sketcher integration, pattern objects, drafting, derived geometry, export, commands, and pattern GUI.

`freecad_cloth.sewing` owns sewing semantics, references, graph/network data, assembly/constraints/correspondence, commands, views, and sewing GUI.

`freecad_cloth.avatar` owns mannequin/avatar models, providers, collision and fitting behavior, commands, and avatar GUI.

`freecad_cloth.simulation` owns cloth simulation, solver state, draping, the target-neutral `DrapeTarget`, stale-state guards, diagnostics, quality/material lifecycle, commands, and simulation GUI.

`freecad_cloth.common` and `freecad_cloth.shared` contain only genuinely shared contracts/utilities. They must not become alternate homes for workbench-specific behavior.

## Dependency direction

```text
Pattern ───┐
Sewing ────┼──> common/shared
Avatar ────┤
Simulation ┘

PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state
```

Do not create reciprocal imports between unrelated workbench packages, and do not duplicate a shared module in another workbench package.

## FreeCAD bootstrap

The installed `Mod/freecad-cloth/` layout remains:

```text
Mod/freecad-cloth/
├── Init.py
├── InitGui.py
├── package.xml
└── freecad_cloth/
```

`InitGui.py` imports the package-owned workbench registration classes. It does not own Pattern, Sewing, Avatar, or Simulation implementation logic.

## Import policy

Internal code and tests use fully qualified package imports:

```python
from freecad_cloth.pattern.PatternCommands import create_pattern_piece
from freecad_cloth.sewing.SewingNetworkCommands import create_sewing_network
from freecad_cloth.simulation.DrapeTarget import target_status
```

Do not add top-level compatibility modules such as `PatternCommands.py` or `SewingNetworkCommands.py`. A historical import is migrated at its call site rather than restored as a second import surface.

## Packaging direction

`pyproject.toml` should discover `freecad_cloth*` packages with setuptools. FreeCAD remains a host-provided runtime and is not a PyPI dependency.

The canonical CI workflow validates both the Python package namespace and real FreeCAD/Xvfb startup. Do not add a second workflow or weaken the existing acceptance path.
