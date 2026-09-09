# Project structure

The repository is both a normal Python project and a directly installable FreeCAD workbench. FreeCAD bootstrap files are the only Python implementation entry points kept at repository root.

```text
.
├── Init.py                         # FreeCAD Mod package marker; root by requirement
├── InitGui.py                      # FreeCAD GUI bootstrap; root by requirement
├── pyproject.toml                  # standard Python packaging metadata
├── freecad_cloth/
│   ├── __init__.py
│   ├── gui.py                      # shared workbench registration base
│   ├── common/                     # shared utilities and document adapters
│   ├── shared/                     # solver/workbench-neutral contracts
│   ├── avatar/                     # avatar model, fitting, collision, GUI
│   ├── pattern/                    # pattern geometry, objects, IR, sketch, GUI
│   ├── sewing/                     # sewing graph, references, network, GUI
│   └── simulation/                 # solver, draping, targets, diagnostics, GUI
├── tests/
├── docs/
└── .github/workflows/
    └── canonical-execution.yml     # the only CI workflow
```

## Module-tree rule

All implementation modules belong under `freecad_cloth/<domain>/`. There are no top-level `Pattern*.py`, `Sewing*.py`, `Avatar*.py`, `Drape*.py`, `Simulation*.py`, or other implementation modules.

Use fully qualified imports such as:

```python
from freecad_cloth.pattern.PatternCommands import create_pattern_piece
from freecad_cloth.sewing.SewingNetworkCommands import create_sewing_network
from freecad_cloth.simulation.DrapeTarget import create_drape_target
```

The root is reserved for FreeCAD bootstrap files (`Init.py` and `InitGui.py`) and project metadata/documentation.

## Workbench ownership

`pattern`, `sewing`, and `simulation` own their workbench registration, commands, domain objects, and GUI integration. `avatar` owns the human/avatar domain. `common` and `shared` contain only responsibility-neutral contracts/utilities and must not become alternate workbench implementations.

The target-neutral drape contract is owned by `freecad_cloth.simulation.DrapeTarget`; `freecad_cloth.shared` contains only host/solver-neutral target references and collision contracts.

## FreeCAD rule

`Init.py` and `InitGui.py` remain at the repository root because FreeCAD discovers a workbench installed directly into a `Mod` directory through those filenames. They are thin bootstrap adapters; domain behavior lives in `freecad_cloth/`.

The package must not import FreeCAD at module import time unless the module is explicitly a GUI/host integration boundary.

## Migration rule

The module-tree migration is complete. Do not reintroduce root-level implementation shims to satisfy tests or legacy imports. Tests and internal callers must migrate to the canonical package namespace instead.

When a historical import is discovered, update the caller and add/adjust a regression test at the canonical package path. Do not create a second implementation or compatibility module at repository root.
