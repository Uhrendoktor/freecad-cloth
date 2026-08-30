# Packaging and module architecture proposal

This proposal recommends a package-oriented Python architecture while preserving FreeCAD's external-workbench discovery contract.

## Current state

The repository is a classic FreeCAD `Mod` workbench: `Init.py` and `InitGui.py` live at the workbench root, while most implementation is currently a flat collection of `Pattern*`, `Sewing*`, `Avatar*`, and cloth/simulation modules.

## Target architecture

The project has **three user-facing workbenches** and shared domain infrastructure:

```text
freecad-cloth/
├── Init.py
├── InitGui.py
├── package.xml
├── pyproject.toml
├── freecad_cloth/
│   ├── __init__.py
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── geometry.py
│   │   ├── topology.py
│   │   ├── units.py
│   │   ├── errors.py
│   │   └── freecad.py
│   │
│   ├── pattern/
│   │   ├── __init__.py
│   │   ├── workbench.py
│   │   ├── model.py
│   │   ├── geometry.py
│   │   ├── objects.py
│   │   ├── drafting.py
│   │   ├── mesh.py
│   │   ├── commands.py
│   │   └── gui/
│   │
│   ├── sewing/
│   │   ├── __init__.py
│   │   ├── workbench.py
│   │   ├── model.py
│   │   ├── assembly.py
│   │   ├── constraints.py
│   │   ├── correspondence.py
│   │   ├── network.py
│   │   ├── commands.py
│   │   └── gui/
│   │
│   ├── avatar/
│   │   ├── __init__.py
│   │   ├── workbench.py
│   │   ├── model.py
│   │   ├── fitting.py
│   │   ├── collision.py
│   │   ├── commands.py
│   │   └── gui/
│   │
│   └── simulation/
│       ├── __init__.py
│       ├── solver.py
│       ├── backend.py
│       └── drape.py
│
└── tests/
    ├── common/
    ├── pattern/
    ├── sewing/
    ├── avatar/
    └── simulation/
```

The names above are architectural targets, not a requirement to split every existing file one-for-one. Existing modules should be grouped by responsibility as they are migrated.

### Why three workbench packages?

`pattern`, `sewing`, and `avatar` represent user-facing FreeCAD workbench domains. Each owns its workbench registration, commands, domain model, and GUI integration.

The current `ClothBackend.py` and `ClothSolver.py` look primarily like simulation infrastructure rather than a separate user-facing workbench. Therefore the proposal calls that layer `simulation` for now. If product requirements establish a distinct Cloth workbench, it can become `freecad_cloth.cloth` without changing the package/bootstrap principle.

### Why a shared `common` package?

Shared functionality should have explicit responsibility-based modules rather than a catch-all `utils.py`. Examples include geometry, topology, units, errors, and small FreeCAD adapters. Workbench-specific behavior must stay in its owning package even when another package happens to call it.

Prefer this dependency direction:

```text
pattern ─┐
sewing  ─┼──> common
avatar  ──┘
simulation ──> common
```

and avoid `common -> pattern/sewing/avatar` and unnecessary cycles between workbench packages.

## FreeCAD compatibility

The root `Init.py` and `InitGui.py` remain the FreeCAD entry points. They become thin adapters that import the appropriate workbench implementation from `freecad_cloth`. `__init__.py` is a normal Python package initializer and does **not** replace FreeCAD's bootstrap files.

The installed Addon Manager/`Mod` layout therefore remains conceptually:

```text
Mod/freecad-cloth/
├── Init.py
├── InitGui.py
├── package.xml
└── freecad_cloth/
```

This permits normal Python package imports while retaining the established FreeCAD discovery mechanism. A migration should be validated with an actual FreeCAD startup and Addon Manager installation before changing any loader behavior.

## GUI and domain separation

GUI code should depend on domain code, not contain the domain implementation itself. A workbench may therefore evolve toward:

```text
pattern/
├── model.py
├── geometry.py
├── objects.py
├── commands.py
└── gui/
    ├── panels.py
    ├── views.py
    └── commands.py
```

The same principle applies to Sewing and Avatar. This enables headless unit tests for host-independent algorithms and limits FreeCAD/PySide imports to integration boundaries where practical.

## Packaging direction

Once the namespace migration exists, `pyproject.toml` should use PEP 621 metadata with setuptools package discovery for `freecad_cloth*`. FreeCAD should not be declared as a PyPI runtime dependency because it is provided by the host application.

Until the namespace migration is implemented, the current `py-modules = []` configuration is intentionally only a packaging guard. It should not be interpreted as the desired final packaging model.

## Migration sequence

1. Introduce `freecad_cloth/` and the three workbench packages without changing FreeCAD discovery.
2. Add thin compatibility imports in root `Init.py`/`InitGui.py`.
3. Move one domain at a time, preserving behavior and imports at each step.
4. Extract genuinely shared code into `common`; do not move workbench-specific code there merely for convenience.
5. Separate GUI/integration code from domain algorithms where practical.
6. Add headless tests for host-independent code and FreeCAD smoke tests for registration/loading.
7. Switch setuptools from the temporary guard to normal package discovery only after the namespace layout is working in FreeCAD.
8. Consider wheel/pip installation only after Addon Manager and `Mod` installation have been validated.

This is intentionally an architecture proposal rather than a mass file move, so it can be reviewed independently of active workbench implementation PRs.
