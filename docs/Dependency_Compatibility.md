# Optional dependency compatibility matrix

Updated 2026-09-14. The project currently declares Python `>=3.9` and the canonical CI image is `freecad-1.1.0-py312-r1`. External libraries remain optional adapters or developer tooling; none is promoted to a core runtime dependency by this matrix.

## Current matrix

| Candidate | Current upstream release observed | Python floor | Wheel / packaging signal | Core dependencies | License | Import / startup risk | ABI / toolchain risk | Project gate |
|---|---:|---:|---|---|---|---|---|---|
| `trimesh` | 5.1.0 | 3.10 | `py3-none-any` wheel | `numpy` only | MIT | Low package-build risk; import cost not benchmarked in FreeCAD runtime | Low ABI risk; NumPy remains the binary dependency | Pin a 4.x release for Python 3.9, or raise the project baseline deliberately; keep lazy optional import |
| `ezdxf` | 1.4.4 | 3.10 | `py3-none-any` plus CPython platform wheels | `typing_extensions`, `pyparsing`, `numpy` | MIT | Pure-Python package plus NumPy; runtime import cost not benchmarked in FreeCAD | Low for the pure wheel; optional native extensions increase toolchain surface | Keep optional/lazy until packaging and public export fixtures pass |
| `meshio` | 5.3.5 | 3.8 | `py3-none-any` wheel | `numpy` by default; more dependencies only for selected formats / `[all]` | MIT | Low default dependency surface; import cost not benchmarked | Low ABI risk for default install; optional format stacks can add native dependencies | Suitable for benchmark/developer interchange only; do not install into core runtime |
| Tissu | Sandbox candidate | `>=3.12` per current project survey | Runtime/toolchain compatibility not established for FreeCAD image | Cloth/solver dependencies to be verified in an isolated probe | Verify before adoption | Startup cost not benchmarked | High until a FreeCAD-compatible wheel/toolchain path is proven | Sandbox only; no core dependency |
| PositionBasedDynamics | Research comparator | Probe required | Native build / Python binding path requires packaging verification | Probe required | Verify before adoption | Not benchmarked | High until ABI/toolchain path is proven | Benchmark later, never a mandatory dependency |
| libigl | Geometry adapter | Probe required | Native / compiled dependency surface | Probe required | Verify before adoption | Not benchmarked | High compared with pure-Python candidates | Evaluate only after a measured geometry gap |
| CGAL / pygalmesh | Derived meshing adapter | Probe required | Native compilation / platform packaging | Probe required | Verify exact component license before use | Not benchmarked | High | Sandbox only until concrete meshing bottleneck is measured |
| Shapely / GEOS | 2D geometry adapter | Probe required | Wheels available, GEOS is native | Probe required | Verify exact version/license pairing | Not benchmarked | Medium; GEOS ABI/platform packaging matters | Evaluate only after native OCCT/Sketcher gap is demonstrated |
| svgpathtools | SVG geometry helper | Probe required | Pure-Python oriented packaging | Probe required | Verify | Not benchmarked | Low-to-medium | Defer until export/correspondence audit demonstrates need |
| VTK / vedo | Offline diagnostic renderer | Probe required | Large compiled stack | VTK and scientific Python stack | Verify | High | High | Offline tooling only; never core runtime without measured benefit |

## Interpretation

### Project compatibility

The current project floor of Python 3.9 is the principal gate. Current `trimesh` 5.1.0 and `ezdxf` 1.4.4 both require Python 3.10 or newer, so their current releases cannot become unconditional runtime dependencies without changing the project baseline. `meshio` 5.3.5 remains compatible with Python 3.9 and ships a universal Python wheel, making it a lower-risk developer-tool candidate.

### Wheel availability

A universal `py3-none-any` wheel reduces platform-specific packaging risk but does not remove transitive binary dependencies. `trimesh` still depends on NumPy, while `ezdxf` includes NumPy among its core dependencies. `meshio` defaults to NumPy and adds additional packages only for selected formats or its `[all]` extra.

### Import/startup measurement

Import/startup time is intentionally not guessed from package metadata. A runtime probe should measure cold imports and repeated imports inside the supported FreeCAD container before any candidate is promoted. Until that measurement exists, the matrix records the dependency surface and marks startup cost as unmeasured.

### ABI/toolchain policy

Any candidate with compiled dependencies must pass an isolated packaging probe for the exact FreeCAD CI Python ABI before promotion. A successful developer workstation install is insufficient evidence. Native FreeCAD/OCCT remains authoritative regardless of adapter choice.

## Sources checked

- Project baseline: `pyproject.toml` (`requires-python = ">=3.9"`).
- Canonical CI: `.github/workflows/canonical-execution.yml` uses `ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r1`.
- `trimesh` PyPI metadata: current 5.1.0 release, Python >=3.10, MIT, `py3-none-any`, NumPy hard dependency.
- `ezdxf` PyPI metadata: current 1.4.4 release, Python >=3.10, MIT, `py3-none-any` plus platform wheels, `typing_extensions`/`pyparsing`/`numpy` core dependencies.
- `meshio` PyPI metadata: current 5.3.5 release, Python >=3.8, MIT, `py3-none-any`, NumPy default dependency.

This file is a compatibility gate, not an authorization to add any dependency to the core package.
