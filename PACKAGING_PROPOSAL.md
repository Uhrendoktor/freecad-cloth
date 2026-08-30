# Packaging proposal

This branch proposes adopting `pyproject.toml` as the repository's packaging and
Python-tool configuration entry point without changing how FreeCAD discovers
the workbench today.

## Compatibility assessment

FreeCAD external Python workbenches are currently discovered from the user's
`Mod` directory. The existing repository deliberately keeps the classic
`Init.py`/`InitGui.py` entry points for compatibility. A `pyproject.toml` file is
passive metadata from FreeCAD's point of view, so adding it does not change
startup or workbench discovery.

FreeCAD's documented **namespaced workbench** layout is the better long-term
match for pip/standard-Python packaging. It moves runtime code under a
`freecad/<workbench>/` namespace and keeps FreeCAD initialization entry points
inside that namespace. That migration should be a separate, deliberately
tested compatibility change rather than being hidden inside this packaging
proposal.

## Why this proposal is intentionally conservative

- `pyproject.toml` uses standard PEP 621 metadata and setuptools as the build
  backend.
- No FreeCAD dependency is declared for pip resolution: FreeCAD is an
  application/runtime dependency, not a normal PyPI dependency.
- The current classic Mod layout is not claimed to be pip-installable yet.
- `requires-python = ">=3.8"` preserves the Python baseline documented for
  FreeCAD 1.0. A newer minimum should be adopted only when the workbench's
  supported FreeCAD runtime matrix is intentionally raised.
- `py-modules = []` prevents setuptools from accidentally treating the current
  collection of top-level FreeCAD scripts as an installable package.

## Recommended next step

If this proposal is accepted, migrate the runtime into a namespaced layout in a
separate PR, for example:

```text
freecad/
└── cloth/
    ├── __init__.py
    ├── init_gui.py
    └── ...runtime modules...
```

The migration should preserve the existing `Mod`-directory installation path,
exercise the Addon Manager/package metadata and a real FreeCAD smoke test, and
only then enable setuptools package discovery for an actual wheel installation.

This keeps packaging modernization independent from the sewing, avatar, and
simulation implementation work currently in progress.
