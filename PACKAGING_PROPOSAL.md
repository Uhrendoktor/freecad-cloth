# Packaging proposal

This proposal recommends a package-oriented Python structure while preserving FreeCAD's external-workbench discovery contract.

## Proposed architecture

```text
freecad-cloth/
├── Init.py
├── InitGui.py
├── package.xml
├── pyproject.toml
├── freecad_cloth/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── geometry.py
│   │   ├── units.py
│   │   └── utils.py
│   ├── sewing/
│   │   ├── __init__.py
│   │   ├── workbench.py
│   │   └── ...
│   ├── pattern/
│   │   ├── __init__.py
│   │   ├── workbench.py
│   │   └── ...
│   └── cloth/
│       ├── __init__.py
│       ├── workbench.py
│       └── ...
└── tests/
```

The exact three workbench names should follow the existing product/UI names in the repository. Each workbench gets its own Python module/package, while genuinely shared functionality belongs in `freecad_cloth.common` rather than being duplicated.

## FreeCAD compatibility

The root `Init.py` and `InitGui.py` remain the FreeCAD entry points. They should become thin adapters that import the appropriate workbench classes from `freecad_cloth`. The package itself does not replace FreeCAD's workbench discovery mechanism.

This is deliberately an incremental migration: introduce the namespace alongside the existing entry points, move implementation modules in small changes, and verify Addon Manager/`package.xml` installation and a real FreeCAD smoke test before changing the loader or claiming wheel/pip installation support.

## pyproject.toml direction

`pyproject.toml` should use PEP 621 metadata with setuptools as the build backend and package discovery for `freecad_cloth*`. FreeCAD should not be declared as a PyPI runtime dependency because it is supplied by the host application. The Python requirement should remain aligned with the supported FreeCAD baseline.

The earlier `py-modules = []` proposal was intentionally conservative, but it should be considered an interim packaging guard only. Once the namespace exists, normal package discovery is the cleaner long-term configuration.

## Design rules

- Keep FreeCAD-specific imports at the GUI/workbench boundary where practical.
- Keep reusable, host-independent algorithms in `common` so they can be unit-tested without launching FreeCAD.
- Do not create a generic `utils.py` dumping ground; split common functionality by responsibility as it grows.
- Avoid putting workbench-specific code in `common` merely to share it between two modules.
- Preserve the `Mod` installation layout for FreeCAD/Add-on Manager compatibility.
