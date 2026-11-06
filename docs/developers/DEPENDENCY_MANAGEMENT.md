# Dependency management

`pyproject.toml` is the source of truth for Python runtime and development dependencies. Runtime requirements belong in `[project].dependencies`; tools used only for development, tests, or static analysis belong in the appropriate optional extra. Keep version ranges and exact pins intentional, and review upstream compatibility notes before accepting a dependency change.

## Updating dependencies

Dependabot pull requests are reviewed individually. For each update:

1. Confirm the package or action is used and that its proposed version matches the intended compatibility range or pin.
2. Review upstream release notes for Python-version, API, binary, native-extension, and security changes relevant to FreeCAD's Python 3.12 runtime.
3. Keep GitHub Actions pinned to immutable commit SHAs, with the release tag retained as a comment for review.
4. Run the canonical validation path. Static checks, focused tests, and the full FreeCAD/GUI/simulation acceptance matrix remain blocking where the change affects those surfaces.
5. Update developer documentation when a tool's role, version policy, or execution contract changes.

A green dependency-update check does not authorize changes to lint scope, type-checking mode, test assertions, artifact validation, geometry/collision criteria, solver settings, performance limits, or GUI acceptance thresholds. Repair compatibility in the implementation or the dependency declaration; do not reduce the acceptance contract to accommodate an update.

## Current maintained toolchain pins

The following versions are the repository's declared baseline on 6 November 2026. The exact dependency declarations remain authoritative in `pyproject.toml` and the immutable action references in `.github/workflows/`.

| Component | Declared version or range | Source |
| --- | --- | --- |
| Ruff | `0.17.2` | `pyproject.toml`, pre-commit Ruff hook |
| Pyright | `1.1.414` | `pyproject.toml` |
| pre-commit | `4.7.0` | `pyproject.toml`, `.pre-commit-config.yaml` |
| CrossHair | `0.0.112` | `pyproject.toml` |
| ty | `0.0.91` | `pyproject.toml` |
| Pillow | `>=11,<14` | `pyproject.toml` |
| actions/setup-python | `7.1.0` | Immutable workflow action reference |
| jscpd | `5.4.2` | Immutable workflow action reference |

Update this table in the same reviewed change as any corresponding declaration or action pin. It is a human-readable index, not an alternative dependency lockfile.
