# Project structure

The repository is both a normal Python project and a directly installable FreeCAD workbench. Those requirements are intentionally separated.

```text
.
├── Init.py                         # FreeCAD Mod package marker (keep at root)
├── InitGui.py                      # FreeCAD GUI entry point (keep at root)
├── pyproject.toml                  # standard Python packaging metadata
├── freecad_cloth/
│   ├── __init__.py
│   ├── gui.py                      # FreeCAD-independent registration shell
│   ├── shared/                     # solver/workbench-neutral contracts
│   │   └── targets.py              # target-neutral collision references
│   ├── pattern/                    # Pattern workbench boundary
│   │   └── workbench.py
│   ├── sewing/                     # Sewing workbench boundary
│   │   └── workbench.py
│   └── simulation/                 # Simulation workbench boundary
│       └── workbench.py
├── Pattern*.py / Sewing*.py / ...  # compatibility implementation modules
├── tests/
├── docs/
└── .github/workflows/
    └── canonical-execution.yml     # the only CI workflow
```

## Why the legacy modules remain at the root

FreeCAD's Mod discovery and the existing document/test ecosystem currently load
modules such as `PatternIR`, `DrapeTarget`, and `FittingCommands` by their
historical top-level names. A single large move would turn a packaging cleanup
into an API migration and would risk saved-document compatibility.

The first structure slice therefore introduces package boundaries and keeps the
old import surface intact. Future slices can move implementation modules one
workbench at a time and leave thin compatibility shims at the root until the
migration is proven by the canonical FreeCAD/Xvfb suite.

## Workbench rule

`InitGui.py` is deliberately still the root registration entry point. It imports
the three package-owned workbench classes and registers them with FreeCAD. This
keeps the repository valid when copied directly into a FreeCAD `Mod` directory
while also making the Python package importable by standard tooling.

The package must never import FreeCAD at module import time unless it is a GUI
entry point. `freecad_cloth.shared` is intentionally FreeCAD-independent.

## Migration rule

1. Introduce a package boundary.
2. Add compatibility tests.
3. Move one implementation module.
4. Leave a top-level shim when external documents/tests may import the old name.
5. Run the complete canonical workflow before deleting a shim.
6. Delete legacy paths only after the public FreeCAD workflow proves equivalent.

Do not perform a repository-wide mechanical rename of FreeCAD modules.
