#!/usr/bin/env bash
# Copyright (C) 2026 FreeCAD Cloth contributors
set -euo pipefail

rebase_merge="$(git rev-parse --git-path rebase-merge)"
rebase_apply="$(git rev-parse --git-path rebase-apply)"

while [[ -d "$rebase_merge" || -d "$rebase_apply" ]]; do
  conflicts="$(git diff --name-only --diff-filter=U)"
  if [[ "$conflicts" == ".agent/PLANS.md" ]]; then
    echo "::warning::Retaining main's non-runtime .agent/PLANS.md."
    git checkout --ours -- .agent/PLANS.md
    git add .agent/PLANS.md
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tools/ci/python_validation.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "fb53561e133e531d418a61d35620c8bf9fe31ceb" ]] ||
      ! git show origin/main:tools/ci/python_validation.py | grep -Fq "tests/test_diagnostics_gui_contract.py" ||
      ! git show origin/main:tools/ci/python_validation.py | grep -Fq "tests/test_fitting_gui_status.py"; then
      echo "::error::Refusing to skip a Python test-routing conflict not proven redundant."
      exit 1
    fi
    echo "::warning::Skipping the exact GUI-routing commit because both added modules are already routed on main."
    if ! GIT_EDITOR=true git rebase --skip; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "pyrightconfig.json" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "0f8ae7645c3c2fe6491dfe9b93477d28f047563b" ]] ||
      ! git show origin/main:pyrightconfig.json | grep -Fq '"typeCheckingMode": "standard"' ||
      ! git show origin/main:pyrightconfig.json | grep -Fq '"reportMissingImports": "none"' ||
      ! git show "${rebase_commit}:pyrightconfig.json" | grep -Fq '"typeCheckingMode": "strict"' ||
      ! git show "${rebase_commit}:pyrightconfig.json" | grep -Fq '    "."' ||
      git show "${rebase_commit}:pyrightconfig.json" | grep -Fq '"exclude":'; then
      echo "::error::Refusing a Pyright config conflict outside the verified repository-wide strict-profile commit."
      exit 1
    fi
    echo "::warning::Taking the exact repository-wide strict Pyright profile while replaying its original expansion commit."
    git checkout --theirs -- pyrightconfig.json
    git add pyrightconfig.json
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tools/ci/validate_ci_structure.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "0e5acdf6bf06f40babe20a3b8afac1ac455c92be" ]] ||
      ! git show origin/main:tools/ci/validate_ci_structure.py | grep -Fq 'ROOT / "tools/ci/pbd_constraint_group_profile.py",' ||
      ! git show "${rebase_commit}:tools/ci/validate_ci_structure.py" | grep -Fq 'PYRIGHT_EXPECTED_INCLUDE = (".",)' ||
      ! git show "${rebase_commit}:tools/ci/validate_ci_structure.py" | grep -Fq 'config.get("typeCheckingMode") != "strict"'; then
      echo "::error::Refusing a CI-structure conflict outside the verified strict-Pyright migration commit and current-main PBD helper contract."
      exit 1
    fi
    echo "::warning::Preserving main's PBD diagnostic helper and transplanting only the exact strict-Pyright policy changes."
    git checkout --ours -- tools/ci/validate_ci_structure.py
    python3 - <<'PY'
from pathlib import Path

path = Path("tools/ci/validate_ci_structure.py")
source = path.read_text(encoding="utf-8")
start_marker = "# Stage semantic type checking deliberately:"
end_marker = "QUALITY_RUNNER_COMMANDS = "
if source.count(start_marker) != 1 or source.count(end_marker) != 1:
    raise SystemExit("Unexpected Pyright inventory structure; refusing manual transplant.")
start = source.index(start_marker)
end = source.index(end_marker, start)
strict_profile = (
    "# One strict Pyright profile covers the repository root; new tracked modules need no opt-in.\n"
    'PYRIGHT_EXPECTED_INCLUDE = (".",)\n'
    "PYRIGHT_EXPECTED_EXCLUDE: tuple[str, ...] = ()\n"
    "PYRIGHT_EXPECTED_STRICT: tuple[str, ...] = ()\n\n"
)
source = source[:start] + strict_profile + source[end:]

replacements = {
    '"""Require the reviewed staged Pyright inventory and prevent accidental scope drift.':
        '"""Require strict Pyright analysis to cover the repository\'s complete Python tree.',
    'added_modules: New production modules to check against the selected inventory.':
        'added_modules: New production modules to check against the repository-wide scope.',
    'Returns:\n        Contract violations describing changes to the reviewed scope or uncovered modules.':
        'Returns:\n        Contract violations describing any narrowed scope or disabled diagnostics.',
    '<Pyright include scope differs from the reviewed inventory>':
        '<Pyright include scope must cover the entire repository root>',
    '<Pyright exclude scope differs from the reviewed inventory>':
        '<Pyright must not exclude repository source paths>',
    '<Pyright strict scope differs from the reviewed simulation core>':
        '<Pyright strict mode must apply globally, not through a path subset>',
    'if config.get("typeCheckingMode") != "standard":\n        violations.append("<Pyright default mode must remain standard outside the strict core>")':
        'if config.get("typeCheckingMode") != "strict":\n        violations.append("<Pyright typeCheckingMode must be strict>")',
    'if config.get("reportMissingImports", "none") != "none":\n        violations.append("<Pyright missing-import policy differs from the reviewed host boundary>")':
        'if config.get("reportMissingImports", "error") != "error":\n        violations.append("<Pyright missing-import diagnostics must be blocking>")',
    'if config.get("reportMissingModuleSource", "none") != "none":\n        violations.append(\n            "<Pyright missing-module-source policy differs from the reviewed host boundary>"\n        )':
        'if config.get("reportMissingModuleSource", "error") != "error":\n        violations.append("<Pyright missing-module-source diagnostics must be blocking>")',
    '<new Python module is outside Pyright include/exclude scope: {path}>':
        '<new Python module is outside strict Pyright coverage: {path}>',
    '"""Require the curated ty core profile to fail on warning-level diagnostics.':
        '"""Require every ty diagnostic to be blocking for the complete tracked Python inventory.',
}
for old, new in replacements.items():
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one occurrence for transplant anchor; found {count}: {old[:90]}")
    source = source.replace(old, new)
if 'ROOT / "tools/ci/pbd_constraint_group_profile.py",' not in source:
    raise SystemExit("Mainline PBD diagnostic helper requirement was not preserved.")
if 'PYRIGHT_EXPECTED_INCLUDE = (".",)' not in source or '"typeCheckingMode") != "strict"' not in source:
    raise SystemExit("Strict Pyright profile transplant is incomplete.")
path.write_text(source, encoding="utf-8")
PY
    git add tools/ci/validate_ci_structure.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "docs/developers/UI_STYLE_GUIDE.md" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "67d656007deea6692d332e0954cb8aa1f99e92e6" ]] ||
      ! git show origin/main:docs/developers/UI_STYLE_GUIDE.md | grep -Fq 'make_scroll_area(content, QtWidgets)' ||
      ! git show origin/main:docs/developers/UI_STYLE_GUIDE.md | grep -Fq 'configure_form_layout(layout, QtWidgets)' ||
      ! git show origin/main:docs/developers/UI_STYLE_GUIDE.md | grep -Fq 'make_disclosure(title, content, QtCore, QtWidgets, expanded=False)' ||
      ! git show "${rebase_commit}:docs/developers/UI_STYLE_GUIDE.md" | grep -Fq 'make_disclosure(title, content, QtCore, QtWidgets, *, expanded=False)'; then
      echo "::error::Refusing a UI guide conflict outside the verified keyword-only disclosure documentation commit and mainline helper additions."
      exit 1
    fi
    echo "::warning::Preserving mainline UI guidance and applying only the verified keyword-only disclosure signature."
    git checkout --ours -- docs/developers/UI_STYLE_GUIDE.md
    python3 - <<'PY'
from pathlib import Path

path = Path("docs/developers/UI_STYLE_GUIDE.md")
source = path.read_text(encoding="utf-8")
old = "- make_disclosure(title, content, QtCore, QtWidgets, expanded=False) uses a checkable Qt tool button to hide/show a settings container while preserving contained widgets and values."
new = "- make_disclosure(title, content, QtCore, QtWidgets, *, expanded=False) uses a checkable Qt tool button to hide/show a settings container while preserving contained widgets and values."
if source.count(old) != 1:
    raise SystemExit("Expected exactly one old disclosure signature; refusing documentation transplant.")
if source.count("make_scroll_area(content, QtWidgets)") != 1:
    raise SystemExit("Mainline scroll-area guidance is missing or duplicated.")
if source.count("configure_form_layout(layout, QtWidgets)") != 1:
    raise SystemExit("Mainline form-layout guidance is missing or duplicated.")
source = source.replace(old, new)
path.write_text(source, encoding="utf-8")
PY
    git add docs/developers/UI_STYLE_GUIDE.md
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tests/test_tunic_audit_contract.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" == "2856b23e6fc14666c6ce36ce2f91e0b18fe95094" ]]; then
      if ! git show origin/main:tests/test_tunic_audit_contract.py | grep -Fq 'def test_realtime_benchmark_reports_cpu_and_device_fallback_metrics()' ||
        git show origin/main:tests/test_tunic_audit_contract.py | grep -Fq 'test_native_arc_evaluator_returns_validated_planar_coordinates' ||
        ! git show "$rebase_commit:tests/test_tunic_audit_contract.py" | grep -Fq 'from tests.support.freecad_arc_geometry import _native_curve_value' ||
        ! git show "$rebase_commit:tests/test_tunic_audit_contract.py" | grep -Fq 'def test_native_arc_evaluator_returns_validated_planar_coordinates()'; then
        echo "::error::Refusing native-arc test transplant outside the exact regression commit and current-main profiling contract."
        exit 1
      fi
      echo "::warning::Preserving mainline tunic profiling contracts and transplanting only the exact native-arc boundary regression."
      git checkout --ours -- tests/test_tunic_audit_contract.py
      python3 - <<'PY'
from pathlib import Path

path = Path("tests/test_tunic_audit_contract.py")
source = path.read_text(encoding="utf-8")
dataclass_import = "from dataclasses import dataclass\n"
importlib_import = "from importlib import import_module\n"
collision_import = "from freecad_cloth.shared.Collision import CollisionSurface\n"
arc_import = "from tests.support.freecad_arc_geometry import _native_curve_value\n"
if source.count(importlib_import) != 1 or source.count(collision_import) != 1:
    raise SystemExit("Unexpected tunic audit import structure; refusing test transplant.")
if "from dataclasses import dataclass" in source or arc_import.strip() in source:
    raise SystemExit("Native arc regression imports already exist; refusing duplicate transplant.")
source = source.replace(importlib_import, dataclass_import + importlib_import)
source = source.replace(collision_import, collision_import + arc_import)

regression = '''

@dataclass
class _NativeArcPoint:
    """Mutable native-point stand-in used to test the dynamic coordinate boundary."""

    x: float
    y: float


class _NativeArcCurve:
    """Expose one native-style parameter evaluator for the boundary regression."""

    def valueAt(self, parameter_value: float) -> _NativeArcPoint:
        return _NativeArcPoint(parameter_value, parameter_value + 1.0)


class _MalformedNativeArcCurve:
    """Expose malformed native coordinates without changing the declared method type."""

    def valueAt(self, parameter_value: float) -> _NativeArcPoint:
        point = _NativeArcPoint(parameter_value, parameter_value + 1.0)
        setattr(point, "x", "invalid")
        return point


def test_native_arc_evaluator_returns_validated_planar_coordinates() -> None:
    """Accept numeric FreeCAD point coordinates and reject malformed binding values."""
    point = _native_curve_value(_NativeArcCurve(), 2.5)
    assert (point.x, point.y) == (2.5, 3.5)

    for curve in (
        _MalformedNativeArcCurve(),
    ):
        try:
            _native_curve_value(curve, 2.5)
        except TypeError as error:
            assert "numeric x/y" in str(error)
        else:
            raise AssertionError("malformed native point coordinates must be rejected")
'''
if source.count("def test_realtime_benchmark_reports_cpu_and_device_fallback_metrics()") != 1:
    raise SystemExit("Mainline tunic profiling test anchor is missing or duplicated.")
if "test_native_arc_evaluator_returns_validated_planar_coordinates" in source:
    raise SystemExit("Native arc regression already present; refusing duplicate append.")
source = source.rstrip() + regression + "\n"
path.write_text(source, encoding="utf-8")
PY
    elif [[ "$rebase_commit" == "ba252a0a385e61f6fb7d0e2a2321e073d3d874a5" ]]; then
      if ! git show origin/main:tests/test_tunic_audit_contract.py | grep -Fq 'def test_realtime_benchmark_reports_cpu_and_device_fallback_metrics()' ||
        ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'def test_native_arc_evaluator_returns_validated_planar_coordinates()' ||
        ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'setattr(point, "x", "invalid")' ||
        git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'def value(self, parameter_value: float)' ||
        ! git show "$rebase_commit:tests/test_tunic_audit_contract.py" | grep -Fq 'def value(self, parameter_value: float)' ||
        ! git show "$rebase_commit:tests/test_tunic_audit_contract.py" | grep -Fq 'try:'; then
        echo "::error::Refusing native-curve protocol refinement outside the exact follow-up commit and expected pre-protocol test state."
        exit 1
      fi
      echo "::warning::Preserving mainline tunic audits and applying only the native-curve protocol test refinements."
      git checkout --ours -- tests/test_tunic_audit_contract.py
      python3 - <<'PY'
from pathlib import Path

path = Path("tests/test_tunic_audit_contract.py")
source = path.read_text(encoding="utf-8")
curve_old = (
    "    def valueAt(self, parameter_value: float) -> _NativeArcPoint:\n"
    "        return _NativeArcPoint(parameter_value, parameter_value + 1.0)\n"
    "\n"
    "\n"
    "class _MalformedNativeArcCurve:"
)
curve_new = (
    "    def valueAt(self, parameter_value: float) -> _NativeArcPoint:\n"
    "        return _NativeArcPoint(parameter_value, parameter_value + 1.0)\n"
    "\n"
    "    def value(self, parameter_value: float) -> _NativeArcPoint:\n"
    "        return self.valueAt(parameter_value)\n"
    "\n"
    "\n"
    "class _MalformedNativeArcCurve:"
)
malformed_old = (
    "    def valueAt(self, parameter_value: float) -> _NativeArcPoint:\n"
    "        point = _NativeArcPoint(parameter_value, parameter_value + 1.0)\n"
    '        setattr(point, "x", "invalid")\n'
    "        return point\n"
    "\n"
    "\n"
    "def test_native_arc_evaluator_returns_validated_planar_coordinates() -> None:"
)
malformed_new = (
    "    def valueAt(self, parameter_value: float) -> _NativeArcPoint:\n"
    "        point = _NativeArcPoint(parameter_value, parameter_value + 1.0)\n"
    '        setattr(point, "x", "invalid")\n'
    "        return point\n"
    "\n"
    "    def value(self, parameter_value: float) -> _NativeArcPoint:\n"
    "        return self.valueAt(parameter_value)\n"
    "\n"
    "\n"
    "def test_native_arc_evaluator_returns_validated_planar_coordinates() -> None:"
)
old_loop = (
    "    for curve in (\n"
    "        _MalformedNativeArcCurve(),\n"
    "    ):\n"
    "        try:\n"
    "            _native_curve_value(curve, 2.5)\n"
    "        except TypeError as error:\n"
    '            assert "numeric x/y" in str(error)\n'
    "        else:\n"
    '            raise AssertionError("malformed native point coordinates must be rejected")'
)
new_direct = (
    "    try:\n"
    "        _native_curve_value(_MalformedNativeArcCurve(), 2.5)\n"
    "    except TypeError as error:\n"
    '        assert "numeric x/y" in str(error)\n'
    "    else:\n"
    '        raise AssertionError("malformed native point coordinates must be rejected")'
)
for old, new, label in (
    (curve_old, curve_new, "native curve value fallback"),
    (malformed_old, malformed_new, "malformed curve value fallback"),
    (old_loop, new_direct, "single malformed curve assertion"),
):
    if source.count(old) != 1:
        raise SystemExit(f"Expected exactly one {label} anchor; refusing protocol transplant.")
    source = source.replace(old, new)
if source.count("def value(self, parameter_value: float)") != 2:
    raise SystemExit("Expected exactly two native curve value fallbacks after transplant.")
if "for curve in (\n        _MalformedNativeArcCurve()," in source:
    raise SystemExit("Singleton loop remains after protocol transplant.")
path.write_text(source, encoding="utf-8")
PY
    else
      echo "::error::Unsupported commit for tests/test_tunic_audit_contract.py conflict: $rebase_commit"
      exit 1
    fi
    git add tests/test_tunic_audit_contract.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tests/test_simulation_gui.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" == "ffd9acf1e6e06794ded282037216e1db0449775c" ]]; then
      if ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'from pathlib import Path' ||
        ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))' ||
        ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'def test_simulation_scene_selectors_highlight_the_selected_objects_in_3d()' ||
        ! git show "$rebase_commit:tests/test_simulation_gui.py" | grep -Fq 'from freecad_cloth.simulation.SimulationGui import SimulationTaskPanel' ||
        git show "$rebase_commit:tests/test_simulation_gui.py" | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))'; then
        echo "::error::Refusing the bootstrap-removal conflict outside the exact cleanup commit and expected mainline viewport-test state."
        exit 1
      fi
      echo "::warning::Preserving mainline simulation viewport tests and removing only the bootstrap for pytest execution."
      git checkout --ours -- tests/test_simulation_gui.py
      python3 - <<'PY'
from pathlib import Path

path = Path("tests/test_simulation_gui.py")
source = path.read_text(encoding="utf-8")
path_import = "from pathlib import Path\n"
bootstrap = "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
if source.count(path_import) != 1 or source.count(bootstrap) != 1:
    raise SystemExit("Expected exactly one pathlib import and pytest bootstrap.")
if "def test_simulation_scene_selectors_highlight_the_selected_objects_in_3d() -> None:" not in source:
    raise SystemExit("Mainline simulation viewport tests are missing.")
if "sys.stdout.write(" not in source or "import sys\n" not in source:
    raise SystemExit("The sys import is still required by the script entry point.")
source = source.replace(path_import, "")
source = source.replace(bootstrap, "")
source = source.replace(
    "from unittest.mock import patch\n\n\nfrom freecad_cloth.simulation.SimulationGui import SimulationTaskPanel",
    "from unittest.mock import patch\n\nfrom freecad_cloth.simulation.SimulationGui import SimulationTaskPanel",
    1,
)
if "from pathlib import Path" in source or "sys.path.insert(" in source:
    raise SystemExit("The pytest bootstrap was not completely removed.")
path.write_text(source, encoding="utf-8")
PY
    elif [[ "$rebase_commit" == "d94c75f1fe15f978a3c5be15d3068ac46e59e96a" ]]; then
      if ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'def test_simulation_scene_selectors_highlight_the_selected_objects_in_3d()' ||
        ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'sys.stdout.write("simulation GUI tests passed\n")' ||
        git show HEAD:tests/test_simulation_gui.py | grep -Fq 'from pathlib import Path' ||
        git show HEAD:tests/test_simulation_gui.py | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))' ||
        ! git show "$rebase_commit:tests/test_simulation_gui.py" | grep -Fq 'from pathlib import Path' ||
        ! git show "$rebase_commit:tests/test_simulation_gui.py" | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))'; then
        echo "::error::Refusing bootstrap-restoration conflict outside the exact standalone-runner commit and expected cleaned mainline state."
        exit 1
      fi
      echo "::warning::Preserving mainline viewport regressions and restoring the exact standalone-script root bootstrap."
      git checkout --ours -- tests/test_simulation_gui.py
      python3 - <<'PY'
from pathlib import Path

path = Path("tests/test_simulation_gui.py")
source = path.read_text(encoding="utf-8")
path_import = "from pathlib import Path\n"
bootstrap = "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
if source.count("import sys\n") != 1:
    raise SystemExit("Expected one sys import before restoring standalone bootstrap.")
if path_import in source or bootstrap in source:
    raise SystemExit("Expected already-cleaned test bootstrap state before restoration.")
if "from types import SimpleNamespace" not in source or "from unittest.mock import patch" not in source:
    raise SystemExit("Mainline simulation GUI fixture imports are missing.")
if "def test_simulation_scene_selectors_highlight_the_selected_objects_in_3d() -> None:" not in source:
    raise SystemExit("Mainline viewport-selection regressions are missing.")
if 'sys.stdout.write("simulation GUI tests passed\\n")' not in source:
    raise SystemExit("Standalone test runner entry point is missing.")
source = source.replace(
    "import sys\nfrom types import SimpleNamespace",
    "import sys\nfrom pathlib import Path\nfrom types import SimpleNamespace",
    1,
)
anchor = "from unittest.mock import patch\n\nfrom freecad_cloth.simulation.SimulationGui import SimulationTaskPanel"
replacement = (
    "from unittest.mock import patch\n\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\n"
    "from freecad_cloth.simulation.SimulationGui import SimulationTaskPanel"
)
if source.count(anchor) != 1:
    raise SystemExit("Expected exactly one package-import insertion anchor.")
source = source.replace(anchor, replacement, 1)
if source.count(path_import) != 1 or source.count(bootstrap) != 1:
    raise SystemExit("Standalone path bootstrap restoration did not produce exact single occurrences.")
path.write_text(source, encoding="utf-8")
PY
    else
      echo "::error::Unsupported commit for tests/test_simulation_gui.py conflict: $rebase_commit"
      exit 1
    fi
    git add tests/test_simulation_gui.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "freecad_cloth/simulation/SimulationQualityRuntime.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "897bfa8e14095ccfbb402b76e78a74378ccb3d72" ]] ||
      ! git show origin/main:freecad_cloth/simulation/SimulationQualityRuntime.py | grep -Fq 'self._preview_mesh_publisher = None' ||
      ! git show origin/main:freecad_cloth/simulation/SimulationQualityRuntime.py | grep -Fq 'obj: Persisted simulation-quality feature restored by the FreeCAD document loader."""' ||
      ! git show "$rebase_commit:freecad_cloth/simulation/SimulationQualityRuntime.py" | grep -Fq 'obj: Persisted simulation-quality feature restored by the FreeCAD document loader.'; then
      echo "::error::Refusing SimulationQualityRuntime conflict outside the exact Ruff docstring-format commit and current-main preview-publisher implementation."
      exit 1
    fi
    echo "::warning::Preserving mainline preview-publisher behavior and applying only the exact Ruff docstring-close formatting."
    git checkout --ours -- freecad_cloth/simulation/SimulationQualityRuntime.py
    python3 - <<'PY'
from pathlib import Path

path = Path("freecad_cloth/simulation/SimulationQualityRuntime.py")
source = path.read_text(encoding="utf-8")
old = '            obj: Persisted simulation-quality feature restored by the FreeCAD document loader."""\n'
new = (
    "            obj: Persisted simulation-quality feature restored by the FreeCAD document loader.\n"
    '        """\n'
)
if source.count(old) != 1:
    raise SystemExit("Expected exactly one unformatted restore docstring line; refusing transform.")
if "self._preview_mesh_publisher = None" not in source:
    raise SystemExit("Mainline preview-publisher reset was not preserved.")
source = source.replace(old, new)
if old in source or source.count(new) != 1:
    raise SystemExit("Ruff docstring formatting transform did not produce one exact formatted block.")
path.write_text(source, encoding="utf-8")
PY
    git add freecad_cloth/simulation/SimulationQualityRuntime.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "freecad_cloth/pattern/PatternTopologyRepair.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "c8588e857cb46cd2e7e5f8eee829518a2cbffee0" ]] ||
      ! git show origin/main:freecad_cloth/pattern/PatternTopologyRepair.py | grep -Fq 'def current_edge_candidate_for_sketch_index(' ||
      ! git show origin/main:freecad_cloth/pattern/PatternTopologyRepair.py | grep -Fq 'from freecad_cloth.common.JsonTypes import JsonObject' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/SeamReference.py" | grep -Fq 'class EdgeRecord(TypedDict):' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/SeamReference.py" | grep -Fq 'provenance: _ProvenanceValue'; then
      echo "::error::Refusing a topology-repair conflict outside the exact protocol migration commit, current-main viewport helper, and required EdgeRecord contract."
      exit 1
    fi
    echo "::warning::Preserving mainline Sketcher viewport-edge resolution and transplanting only the exact typed topology-repair contracts."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepair.py
    python3 - <<'PY'
from pathlib import Path

path = Path("freecad_cloth/pattern/PatternTopologyRepair.py")
source = path.read_text(encoding="utf-8")

import_anchor = "from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol\n"
imports = (
    "from collections.abc import Iterable, Sequence\n"
    "from typing import Protocol, TypeVar, cast\n\n"
)
if source.count(import_anchor) != 1:
    raise SystemExit("Expected one mainline FreeCAD protocol import anchor.")
if "from collections.abc import Iterable, Sequence" in source:
    raise SystemExit("Topology typing imports already exist; refusing duplicate transplant.")
source = source.replace(import_anchor, imports + import_anchor, 1)

seam_import_anchor = (
    "from freecad_cloth.pattern.SeamReference import (\n"
    "    ChangedEdgeReference,\n"
)
seam_import_replacement = (
    "from freecad_cloth.pattern.SeamReference import (\n"
    "    ChangedEdgeReference,\n"
    "    EdgeRecord,\n"
)
if source.count(seam_import_anchor) != 1:
    raise SystemExit("Expected exact SeamReference import anchor.")
source = source.replace(seam_import_anchor, seam_import_replacement, 1)

class_anchor = (
    'class InvalidRepairTarget(TopologyRepairError):\n'
    '    """The selected replacement edge cannot be resolved on the seam piece."""\n'
)
protocols = '''

class PatternPieceFeatureProtocol(Protocol):
    """Minimal native pattern-piece identity required by seam repair."""

    PieceId: str


class SeamFeatureProtocol(Protocol):
    """Native seam properties updated by an explicit topology repair."""

    PatternA: PatternPieceFeatureProtocol
    PatternB: PatternPieceFeatureProtocol
    EdgeAId: str
    EdgeASignature: str
    EdgeA: int
    EdgeBId: str
    EdgeBSignature: str
    EdgeB: int

    def touch(self) -> None: ...


class DocumentTransactionProtocol(Protocol):
    """FreeCAD document transaction surface used by the repair operation."""

    Objects: Sequence[object]

    def openTransaction(self, label: str) -> None: ...

    def recompute(self) -> None: ...

    def commitTransaction(self) -> None: ...

    def abortTransaction(self) -> None: ...


_RepairSeam = TypeVar("_RepairSeam")
'''
if source.count(class_anchor) != 1 or "class PatternPieceFeatureProtocol" in source:
    raise SystemExit("Expected unique insertion point for topology protocols.")
source = source.replace(class_anchor, class_anchor + protocols, 1)

signature_replacements = (
    ("def seam_reference_status(seam, side):",
     "def seam_reference_status(seam: object, side: str) -> tuple[bool, str]:"),
    ("def invalid_seam_sides(doc):",
     "def invalid_seam_sides(\n    doc: DocumentTransactionProtocol,\n) -> list[tuple[SeamFeatureProtocol, str, str]]:"),
    ("def current_edge_candidates(seam, side):",
     "def current_edge_candidates(seam: object, side: str) -> list[EdgeRecord]:"),
    ("def validate_repair_target(seam, side, edge_id):",
     "def validate_repair_target(seam: object, side: str, edge_id: str) -> EdgeRecord:"),
    ("def build_repair_plan(repairs):",
     "def build_repair_plan(\n    repairs: Iterable[tuple[_RepairSeam, str, str]],\n) -> list[tuple[_RepairSeam, str, EdgeRecord]]:"),
    ("def apply_repair_plan(doc, repairs):",
     "def apply_repair_plan(\n    doc: DocumentTransactionProtocol,\n    repairs: Iterable[tuple[SeamFeatureProtocol, str, str]],\n) -> list[tuple[SeamFeatureProtocol, str, EdgeRecord]]:"),
)
for old, new in signature_replacements:
    if source.count(old) != 1:
        raise SystemExit(f"Expected one topology signature anchor: {old}")
    source = source.replace(old, new, 1)

invalid_old = (
    "    result = []\n"
    '    for obj in getattr(doc, "Objects", ()):\n'
    '        if getattr(obj, "SeamId", None) is None:\n'
    "            continue\n"
    '        for side in ("A", "B"):\n'
    "            valid, reason = seam_reference_status(obj, side)\n"
    "            if not valid:\n"
    "                result.append((obj, side, reason))\n"
)
invalid_new = (
    "    result: list[tuple[SeamFeatureProtocol, str, str]] = []\n"
    "    for obj in doc.Objects:\n"
    '        if getattr(obj, "SeamId", None) is None:\n'
    "            continue\n"
    '        for side in ("A", "B"):\n'
    "            valid, reason = seam_reference_status(obj, side)\n"
    "            if not valid:\n"
    "                # SeamId marks a native seam feature with the properties in this protocol.\n"
    "                result.append((cast(SeamFeatureProtocol, obj), side, reason))\n"
)
if source.count(invalid_old) != 1:
    raise SystemExit("Expected one current-main invalid_seam_sides body.")
source = source.replace(invalid_old, invalid_new, 1)

plan_old = "    plan = []\n    seen = set()\n"
plan_new = (
    "    plan: list[tuple[_RepairSeam, str, EdgeRecord]] = []\n"
    "    seen: set[tuple[int, str]] = set()\n"
)
if source.count(plan_old) != 1:
    raise SystemExit("Expected one current-main repair-plan local initializer.")
source = source.replace(plan_old, plan_new, 1)

if source.count('record.get("provenance")') != 2:
    raise SystemExit("Expected exactly two optional provenance lookups in repair application.")
source = source.replace('record.get("provenance")', 'record["provenance"]')

# Keep the mainline viewport picker and its JsonObject return contract intact.
for required in (
    "from freecad_cloth.common.JsonTypes import JsonObject",
    "from freecad_cloth.pattern.PatternObjects import _edge_records, _native_edge_record_for_sketch_index",
    "def current_edge_candidate_for_sketch_index(",
    "record = _native_edge_record_for_sketch_index(piece, int(edge_index))",
    "def seam_reference_status(seam: object, side: str) -> tuple[bool, str]:",
    "def invalid_seam_sides(",
    "def current_edge_candidates(seam: object, side: str) -> list[EdgeRecord]:",
    "def validate_repair_target(seam: object, side: str, edge_id: str) -> EdgeRecord:",
    "def build_repair_plan(",
    "def apply_repair_plan(",
    "class DocumentTransactionProtocol(Protocol):",
):
    if required not in source:
        raise SystemExit(f"Transplanted topology contract missing: {required}")
if source.count("record[\"provenance\"]") != 2:
    raise SystemExit("Required provenance access was not applied exactly twice.")
path.write_text(source, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepair.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "freecad_cloth/pattern/PatternTopologyRepairGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "bfe0121970b5eae29bfd16be705cfae86c27d636" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "bfe0121970b5eae29bfd16be705cfae86c27d636" ]] ||
      ! git show origin/main:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _TopologyRepairViewportPicker:' ||
      ! git show origin/main:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'def _begin_viewport_pick(' ||
      ! git show origin/main:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'self.rows.append((seam, side, combo, pick_button))' ||
      ! git show "$rebase_commit:pyproject.toml" | grep -Fq '"currentData",' ||
      ! git show "$rebase_commit:tests/support/ruff_contract.py" | grep -Fq '"currentData",'; then
      echo "::error::Refusing topology GUI conflict outside the exact task-panel typing commit and current-main viewport-picker contract."
      exit 1
    fi
    echo "::warning::Preserving mainline viewport picker lifecycle and typing the expanded repair-panel row contract."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepairGui.py
    python3 - <<'PY'
from pathlib import Path

path = Path("freecad_cloth/pattern/PatternTopologyRepairGui.py")
source = path.read_text(encoding="utf-8")

typing_import = "from typing import TYPE_CHECKING\n"
if source.count(typing_import) != 1:
    raise SystemExit("Expected one TYPE_CHECKING import anchor.")
source = source.replace(typing_import, "from typing import TYPE_CHECKING, Protocol\n", 1)

typing_block = (
    "if TYPE_CHECKING:\n"
    "    from types import ModuleType\n\n"
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n"
)
typed_block = (
    "if TYPE_CHECKING:\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
    "    from types import ModuleType\n\n"
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n"
)
if source.count(typing_block) != 1:
    raise SystemExit("Expected exact current-main TYPE_CHECKING import block.")
source = source.replace(typing_block, typed_block, 1)

protocol_anchor = (
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n\n"
    "def _gui_modules()"
)
protocol_block = (
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n\n"
    "class _ComboBoxProtocol(Protocol):\n"
    "    def addItem(self, text: str, userData: object | None = None) -> None: ...\n\n"
    "    def currentData(self) -> object: ...\n\n"
    "def _gui_modules()"
)
if source.count(protocol_anchor) != 1 or "class _ComboBoxProtocol(Protocol)" in source:
    raise SystemExit("Expected unique combo-box protocol insertion point.")
source = source.replace(protocol_anchor, protocol_block, 1)

signature_replacements = (
    ("    def __init__(self, doc):", "    def __init__(self, doc: object) -> None:"),
    ("    def accept(self):", "    def accept(self) -> bool:"),
    ("    def reject(self):", "    def reject(self) -> bool:"),
    ("    def getStandardButtons(self):", "    def getStandardButtons(self) -> int:"),
    ("def show_topology_repair_task(doc):",
     "def show_topology_repair_task(doc: object) -> PatternTopologyRepairTaskPanel:"),
)
for old, new in signature_replacements:
    if source.count(old) != 1:
        raise SystemExit(f"Expected one topology GUI signature anchor: {old}")
    source = source.replace(old, new, 1)

rows_old = "        self.rows = []\n"
rows_new = (
    "        self.rows: list[\n"
    "            tuple[\n"
    "                SeamFeatureProtocol,\n"
    "                str,\n"
    "                _ComboBoxProtocol,\n"
    "                _QT_TYPE_QtWidgets.QPushButton,\n"
    "            ]\n"
    "        ] = []\n"
)
if source.count(rows_old) != 1:
    raise SystemExit("Expected one mainline four-column repair-row initializer.")
source = source.replace(rows_old, rows_new, 1)

repairs_old = (
    "        repairs = [\n"
    "            (seam, side, combo.currentData())\n"
    "            for seam, side, combo, _pick_button in self.rows\n"
    "            if combo.currentData()\n"
    "        ]\n"
)
repairs_new = (
    "        repairs: list[tuple[SeamFeatureProtocol, str, str]] = [\n"
    "            (seam, side, str(combo.currentData()))\n"
    "            for seam, side, combo, _pick_button in self.rows\n"
    "            if combo.currentData()\n"
    "        ]\n"
)
if source.count(repairs_old) != 1:
    raise SystemExit("Expected one current-main four-field repair selection comprehension.")
source = source.replace(repairs_old, repairs_new, 1)

# The latest viewport-picker behavior must remain present and the row remains four fields.
for required in (
    "from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol",
    "class _ComboBoxProtocol(Protocol):",
    "def currentData(self) -> object: ...",
    "class _TopologyRepairViewportPicker:",
    "def _begin_viewport_pick(",
    "def _cancel_viewport_pick(",
    "self.rows.append((seam, side, combo, pick_button))",
    "for seam, side, combo, _pick_button in self.rows",
    "repairs: list[tuple[SeamFeatureProtocol, str, str]] = [",
    "def show_topology_repair_task(doc: object) -> PatternTopologyRepairTaskPanel:",
):
    if required not in source:
        raise SystemExit(f"Topology GUI protocol transplant incomplete: {required}")
path.write_text(source, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepairGui.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == ".github/workflows/canonical-execution.yml" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "bbd581e2df7ed83509755ef7a32850edd3441f49" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "bbd581e2df7ed83509755ef7a32850edd3441f49" ]] ||
      ! git show "$rebase_commit:.github/workflows/canonical-execution.yml" | grep -Fq 'name: Strict checks and guarded safe Ruff batch' ||
      ! git show "$rebase_commit:.github/workflows/canonical-execution.yml" | grep -Fq 'bash tools/ci/run_safe_ruff_batch.sh "$QUALITY_IMAGE"' ||
      ! git show "$rebase_commit:tools/ci/run_safe_ruff_batch.sh" | grep -Fq -- '--ruff-autofix' ||
      ! git show "$rebase_commit^:.github/workflows/canonical-execution.yml" | grep -Fq 'name: Apply safe Ruff batch and dispatch exact-head validation' ||
      ! git show HEAD:.github/workflows/canonical-execution.yml | grep -Fq 'name: Run strict repository checks in the pinned FreeCAD runtime' ||
      ! git show HEAD:.github/workflows/canonical-execution.yml | grep -Fq 'name: Apply safe Ruff batch and dispatch exact-head validation' ||
      ! git show HEAD:.github/workflows/canonical-execution.yml | grep -Fq 'actions: write' ||
      ! git show HEAD:.github/workflows/canonical-execution.yml | grep -Fq 'contents: write' ||
      [[ ! -f tools/ci/run_safe_ruff_batch.sh ]]; then
      echo "::error::Refusing canonical-workflow conflict outside the exact guarded safe-Ruff activation and expected two-step pre-replay job."
      exit 1
    fi
    echo "::warning::Preserving replayed workflow changes and mainline job context; folding only the strict/safe-Ruff steps into the exact guarded path."
    git checkout --ours -- .github/workflows/canonical-execution.yml
    python3 - <<'PY'
from pathlib import Path

path = Path(".github/workflows/canonical-execution.yml")
source = path.read_text(encoding="utf-8")
job_start = source.index("  agent-quality:\n")
job_end = source.index("  local_runner_readiness:\n", job_start)
job = source[job_start:job_end]

permissions_old = (
    "    permissions:\n"
    "      actions: read\n"
    "      contents: read\n"
    "      packages: read\n"
)
permissions_new = (
    "    permissions:\n"
    "      actions: write\n"
    "      contents: write\n"
    "      packages: read\n"
)
if job.count(permissions_old) == 1:
    job = job.replace(permissions_old, permissions_new, 1)
elif job.count(permissions_new) != 1:
    raise SystemExit("Expected the exact agent-quality permission block before safe Ruff activation.")

strict_name = "      - name: Run strict repository checks in the pinned FreeCAD runtime\n"
safe_name = "      - name: Apply safe Ruff batch and dispatch exact-head validation\n"
combined_name = "      - name: Strict checks and guarded safe Ruff batch\n"
path_name = "      - name: Add persistent user binary directory to PATH\n"

if job.count(combined_name) == 1:
    strict_start = job.index(combined_name)
    path_start = job.index(path_name, strict_start)
    combined = job[strict_start:path_start]
    if 'bash tools/ci/run_safe_ruff_batch.sh "$QUALITY_IMAGE"' not in combined:
        raise SystemExit("Existing combined safe Ruff step does not invoke the reviewed batch script.")
    if 'bash tools/ci/run_strict_quality.sh "$QUALITY_IMAGE"' not in combined:
        raise SystemExit("Existing combined step lost strict validation.")
elif job.count(strict_name) == 1 and job.count(safe_name) == 1:
    strict_start = job.index(strict_name)
    safe_start = job.index(safe_name, strict_start)
    path_start = job.index(path_name, safe_start)
    strict_block = job[strict_start:safe_start]
    safe_block = job[safe_start:path_start]
    if 'bash tools/ci/run_strict_quality.sh "$QUALITY_IMAGE"' not in strict_block:
        raise SystemExit("Strict validation step is not the expected pinned-image invocation.")
    if 'bash tools/ci/run_safe_ruff_batch.sh "$QUALITY_IMAGE"' not in safe_block:
        raise SystemExit("Safe Ruff step is not the expected reviewed batch invocation.")
    has_actor = (
        "GITHUB_ACTOR: ${{ github.actor }}" in strict_block
        or "GITHUB_ACTOR: ${{ github.actor }}" in safe_block
    )
    actor_line = "          GITHUB_ACTOR: ${{ github.actor }}\n" if has_actor else ""
    combined = (
        combined_name
        + "        shell: bash\n"
        + "        env:\n"
        + "          QUALITY_IMAGE: ${{ needs.pbd_validation_image.outputs.image }}\n"
        + "          GH_TOKEN: ${{ github.token }}\n"
        + actor_line
        + "          RUNNER_TOOL_CACHE: ${{ runner.tool_cache }}\n"
        + "          PR_TITLE: ${{ github.event.pull_request.title || '' }}\n"
        + "        run: |\n"
        + '          if [[ "$GITHUB_EVENT_NAME" == "pull_request" && "$PR_TITLE" == *"[apply-safe-ruff]"* ]]; then\n'
        + '            bash tools/ci/run_safe_ruff_batch.sh "$QUALITY_IMAGE"\n'
        + "          else\n"
        + '            bash tools/ci/run_strict_quality.sh "$QUALITY_IMAGE"\n'
        + "          fi\n"
    )
    job = job[:strict_start] + combined + job[path_start:]
else:
    raise SystemExit("Expected the reviewed strict and safe-Ruff sibling steps or the final combined step.")

for required in (
    "      actions: write\n",
    "      contents: write\n",
    "      packages: read\n",
    "      - name: Strict checks and guarded safe Ruff batch\n",
    "          PR_TITLE: ${{ github.event.pull_request.title || '' }}\n",
    'if [[ "$GITHUB_EVENT_NAME" == "pull_request" && "$PR_TITLE" == *"[apply-safe-ruff]"* ]]; then',
    'bash tools/ci/run_safe_ruff_batch.sh "$QUALITY_IMAGE"',
    'bash tools/ci/run_strict_quality.sh "$QUALITY_IMAGE"',
):
    if required not in job:
        raise SystemExit(f"Guarded safe-Ruff workflow transplant incomplete: {required}")
if "GITHUB_ACTOR: ${{ github.actor }}" in source and "GITHUB_ACTOR: ${{ github.actor }}" not in job:
    raise SystemExit("Mainline GITHUB_ACTOR context was dropped by the safe-Ruff workflow transplant.")

source = source[:job_start] + job + source[job_end:]
path.write_text(source, encoding="utf-8")
PY
    git add .github/workflows/canonical-execution.yml
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "freecad_cloth/sewing/SewingNetworkGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "5d84563005f984dec139794200ad57a77d29ca26" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "5d84563005f984dec139794200ad57a77d29ca26" ]] ||
      ! git show "$rebase_commit:freecad_cloth/sewing/SewingNetworkGui.py" | grep -Fq 'field = cast("_RangeEditor", qt_widgets.QDoubleSpinBox())' ||
      ! git show "$rebase_commit^:freecad_cloth/sewing/SewingNetworkGui.py" | grep -Fq 'field = cast(_RangeEditor, qt_widgets.QDoubleSpinBox())' ||
      ! git show HEAD:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'field = cast(_RangeEditor, qt_widgets.QDoubleSpinBox())' ||
      ! git show HEAD:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'class _NetworkEditorSnapshot(TypedDict):' ||
      ! git show HEAD:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'self._range_fields: tuple[_RangeEditor, ...] = (' ||
      ! git show HEAD:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'ranges = getattr(self, "_range_values", ())' ||
      ! git show HEAD:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'self.table.item(row, column).text()' ||
      ! git show HEAD:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'if getattr(self, "_loading_range", False)'; then
      echo "::error::Refusing SewingNetworkGui Ruff replay outside the exact 5d845630 safe-format commit and validated typed/fallback state."
      exit 1
    fi
    echo "::warning::Preserving the replayed typed seam editor and current-main defensive fallbacks; applying only the exact Ruff formatting changes."
    git checkout --ours -- freecad_cloth/sewing/SewingNetworkGui.py
    python3 - <<'PY'
from pathlib import Path

path = Path("freecad_cloth/sewing/SewingNetworkGui.py")
source = path.read_text(encoding="utf-8")

old_cast = 'field = cast(_RangeEditor, qt_widgets.QDoubleSpinBox())'
new_cast = 'field = cast("_RangeEditor", qt_widgets.QDoubleSpinBox())'
if source.count(old_cast) == 1 and source.count(new_cast) == 0:
    source = source.replace(old_cast, new_cast, 1)
elif source.count(old_cast) == 0 and source.count(new_cast) == 1:
    pass
else:
    raise SystemExit("Expected exactly one current Ruff cast expression.")

import_line = "from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol\n"
if source.count(import_line) != 1:
    raise SystemExit("Expected exactly one FreeCAD document Protocol import.")
import_end = source.index(import_line) + len(import_line)
module_start = source.find("def _modules():\n", import_end)
if module_start < 0:
    raise SystemExit("Expected _modules() immediately after the FreeCAD document Protocol import.")
gap = source[import_end:module_start]
if gap.strip():
    raise SystemExit("Unexpected code between the FreeCAD document Protocol import and _modules().")
# Normalize to Ruff two-empty-line separation; accept any whitespace-only prior gap.
source = source[:import_end] + "\n\n" + source[module_start:]
required = (
    'field = cast("_RangeEditor", qt_widgets.QDoubleSpinBox())',
    "class _NetworkEditorSnapshot(TypedDict):",
    "self._range_fields: tuple[_RangeEditor, ...] = (",
    'ranges = getattr(self, "_range_values", ())',
    "self.table.item(row, column).text()",
    'if getattr(self, "_loading_range", False)',
)
for marker in required:
    if marker not in source:
        raise SystemExit(f"Safe Ruff replay removed required seam editor contract: {marker}")

path.write_text(source, encoding="utf-8")
PY
    git add freecad_cloth/sewing/SewingNetworkGui.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "freecad_cloth/sewing/SewingNetworkGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "f62b45d70533341c14e6f9909c233498c7d5ef01" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "f62b45d70533341c14e6f9909c233498c7d5ef01" ]] ||
      ! git show "$rebase_commit:freecad_cloth/sewing/SewingNetworkGui.py" | grep -Fq 'class _NetworkReferenceCollection(Protocol):' ||
      ! git show "$rebase_commit:freecad_cloth/sewing/SewingNetworkGui.py" | grep -Fq 'class _NetworkEditorSnapshot(TypedDict):' ||
      ! git show "$rebase_commit:freecad_cloth/sewing/SewingNetworkGui.py" | grep -Fq 'valueChanged: _FloatChangedSignal' ||
      ! git show origin/main:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'make_paired_range_row(self.start_a, self.end_a, QtWidgets)' ||
      ! git show origin/main:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'ranges = getattr(self, "_range_values", ())' ||
      ! git show origin/main:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'self.table.item(row, column).text()' ||
      git show origin/main:freecad_cloth/sewing/SewingNetworkGui.py | grep -Fq 'class _NetworkEditorSnapshot(TypedDict):' ||
      [[ "$(git rev-parse origin/main:freecad_cloth/sewing/SewingNetworkGui.py)" != "3c68946244ace48f3e96bb356b33422b55a49cdb" ]] ||
      [[ ! -f .agent/rebase-patches/PR-2842-f62b45-sewing-network-gui.patch ]]; then
      echo "::error::Refusing SewingNetworkGui replay outside exact f62b typing commit or expected current-main editor contract."
      exit 1
    fi
    echo "::warning::Restoring the exact current-main SewingNetworkGui blob, preserving paired A/B rows and defensive fallbacks, then applying the reviewed typing patch."
    git checkout origin/main -- freecad_cloth/sewing/SewingNetworkGui.py
    git apply --check .agent/rebase-patches/PR-2842-f62b45-sewing-network-gui.patch
    git apply .agent/rebase-patches/PR-2842-f62b45-sewing-network-gui.patch
    if ! grep -Fq 'class _NetworkEditorSnapshot(TypedDict):' freecad_cloth/sewing/SewingNetworkGui.py ||
      ! grep -Fq 'self._range_fields: tuple[_RangeEditor, ...] = (' freecad_cloth/sewing/SewingNetworkGui.py ||
      ! grep -Fq 'ranges = getattr(self, "_range_values", ())' freecad_cloth/sewing/SewingNetworkGui.py ||
      ! grep -Fq 'self.table.item(row, column).text()' freecad_cloth/sewing/SewingNetworkGui.py; then
      echo "::error::Static sewing GUI patch lost typed state or current-main defensive fallbacks."
      exit 1
    fi
    git add freecad_cloth/sewing/SewingNetworkGui.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "freecad_cloth/avatar/AvatarPoseGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "561071281bb387794029dbbfda720a581b028d04" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    avatar_path="freecad_cloth/avatar/AvatarPoseGui.py"
    changed_paths="$(git diff-tree --no-commit-id --name-only -r "$rebase_commit")"
    if [[ "$rebase_commit" != "561071281bb387794029dbbfda720a581b028d04" ]] ||
      [[ "$changed_paths" != "$avatar_path" ]] ||
      ! git show "$rebase_commit^:$avatar_path" | grep -Fq 'class _PoseVector(Protocol):' ||
      ! git show "$rebase_commit:$avatar_path" | grep -Fq 'class _PoseVector(Protocol):' ||
      ! git show "$rebase_commit:$avatar_path" | grep -Fq 'from freecad_cloth.avatar.avatar_protocols import AvatarTaskPanelProtocol' ||
      ! git show "$rebase_commit:$avatar_path" | grep -Fq 'def _gizmo_finish(' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'class _PoseVector(Protocol):' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'class _PosePanel(Protocol):' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'def _set_rotation_axis_highlight(self, axis: str | None) -> None:' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'GIZMO_SIZE = 88.0' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'BONE_PICK_RADIUS = 16.0' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'JOINT_PICK_RADIUS = 24.0' ||
      ! git show HEAD:"$avatar_path" | grep -Fq 'class _PoseAxisFocusFilter' ||
      ! git show HEAD:freecad_cloth/avatar/coin_protocols.py | grep -Fq 'class _CoinModule(Protocol):' ||
      ! git show HEAD:pyproject.toml | grep -Fq '"ruff==0.17.2"'; then
      echo "::error::Refusing AvatarPoseGui safe-Ruff replay outside the exact one-file 56107128 commit and verified post-Pivy current-main GUI."
      exit 1
    fi
    echo "::warning::Keeping the current-main pose UI and Pivy transplant; replaying only pinned Ruff formatting and safe autofixes on AvatarPoseGui.py."
    git checkout --ours -- "$avatar_path"
    ruff_venv="$(mktemp -d "\${RUNNER_TEMP:-/tmp}/ruff-56107128.XXXXXX")"
    python3 -m venv "$ruff_venv"
    "$ruff_venv/bin/python" -m pip install --disable-pip-version-check --no-input "ruff==0.17.2"
    "$ruff_venv/bin/ruff" format --config pyproject.toml "$avatar_path"
    "$ruff_venv/bin/ruff" check --config pyproject.toml --fix "$avatar_path"
    "$ruff_venv/bin/ruff" format --config pyproject.toml --check "$avatar_path"
    "$ruff_venv/bin/ruff" check --config pyproject.toml "$avatar_path"
    rm -rf "$ruff_venv"
    changed_after_ruff="$(git diff --name-only)"
    if [[ "$changed_after_ruff" != "$avatar_path" ]]; then
      echo "::error::Pinned safe Ruff pass changed files outside AvatarPoseGui.py: \${changed_after_ruff:-none}"
      exit 1
    fi
    git add "$avatar_path"
    if git diff --cached --quiet; then
      echo "::notice::Current-main AvatarPoseGui was already at the exact Ruff-clean result; skipping this now-empty historical formatter commit."
      if ! git rebase --skip; then
        rebase_merge="$(git rev-parse --git-path rebase-merge)"
        rebase_apply="$(git rev-parse --git-path rebase-apply)"
        if [[ -d "$rebase_merge" || -d "$rebase_apply" ]]; then
          bash tools/ci/guarded_rebase_conflict_entrypoint.sh
        else
          exit 1
        fi
      fi
    elif ! GIT_EDITOR=true git rebase --continue; then
      rebase_merge="$(git rev-parse --git-path rebase-merge)"
      rebase_apply="$(git rev-parse --git-path rebase-apply)"
      if [[ -d "$rebase_merge" || -d "$rebase_apply" ]]; then
        bash tools/ci/guarded_rebase_conflict_entrypoint.sh
      else
        exit 1
      fi
    fi
  elif [[ "$conflicts" == "freecad_cloth/avatar/AvatarPoseGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "69999107b2e8888a5d179835b8297b21fef19d74" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "69999107b2e8888a5d179835b8297b21fef19d74" ]] ||
      ! git show "$rebase_commit:freecad_cloth/avatar/AvatarPoseGui.py" | grep -Fq 'class _PoseVector(Protocol):' ||
      ! git show "$rebase_commit:freecad_cloth/avatar/AvatarPoseGui.py" | grep -Fq 'class _PosePanel(Protocol):' ||
      ! git show "$rebase_commit:freecad_cloth/avatar/AvatarPoseGui.py" | grep -Fq 'def _coin(self) -> _CoinModule:' ||
      ! git show "$rebase_commit:freecad_cloth/avatar/coin_protocols.py" | grep -Fq 'class _CoinModule(Protocol):' ||
      git cat-file -e origin/main:freecad_cloth/avatar/coin_protocols.py 2>/dev/null ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'GIZMO_SIZE = 88.0' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'BONE_PICK_RADIUS = 16.0' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'JOINT_PICK_RADIUS = 24.0' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'self._axis_draggers = {}' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'def highlight_axis(self, axis: str | None) -> None:' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'def _set_rotation_axis_highlight(self, axis: str | None) -> None:' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'class _PoseAxisFocusFilter' ||
      ! git show origin/main:freecad_cloth/avatar/AvatarPoseGui.py | grep -Fq 'axis_branch = coin.SoSeparator()'; then
      echo "::error::Refusing AvatarPoseGui typing replay outside the exact 69999107 protocol commit and verified current three-axis pose UI."
      exit 1
    fi
    echo "::warning::Preserving current-main three-axis draggers and focus highlight; transplanting only Pivy/FreeCAD protocols and compatible type annotations."
    git checkout --ours -- freecad_cloth/avatar/AvatarPoseGui.py
    git checkout "$rebase_commit" -- freecad_cloth/avatar/coin_protocols.py
    python3 - <<'PY'
from __future__ import annotations

import ast
import io
import subprocess
import tokenize
from collections import defaultdict
from pathlib import Path

path = Path("freecad_cloth/avatar/AvatarPoseGui.py")
source = path.read_text(encoding="utf-8")
typed_source = subprocess.check_output(
    ["git", "show", "69999107b2e8888a5d179835b8297b21fef19d74:freecad_cloth/avatar/AvatarPoseGui.py"],
    text=True,
    encoding="utf-8",
)

def replace_once(old: str, new: str, label: str) -> None:
    global source
    if source.count(old) != 1:
        raise SystemExit(f"Expected one exact {label} anchor in current-main AvatarPoseGui.")
    source = source.replace(old, new, 1)

collection_import_options = (
    "from collections.abc import Sequence\n",
    "from collections.abc import Callable, Sequence\n",
)
collection_matches = [line for line in collection_import_options if source.count(line) == 1]
if len(collection_matches) != 1:
    raise SystemExit("Expected one exact supported collections.abc import anchor in current-main AvatarPoseGui.")
if collection_matches[0] == "from collections.abc import Sequence\n":
    source = source.replace(
        collection_matches[0],
        "from collections.abc import Callable, Sequence\n",
        1,
    )
typing_import_options = (
    "from typing import TYPE_CHECKING\n",
    "from typing import TYPE_CHECKING, Protocol\n",
)
typing_matches = [line for line in typing_import_options if source.count(line) == 1]
if len(typing_matches) != 1:
    raise SystemExit("Expected one exact supported typing import anchor in current-main AvatarPoseGui.")
source = source.replace(
    typing_matches[0],
    "from typing import TYPE_CHECKING, Protocol, cast\n",
    1,
)
replace_once(
    "from typing import TYPE_CHECKING, Protocol, cast\n",
    "from typing import TYPE_CHECKING, Protocol, cast\n\n"
    "from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol\n",
    "runtime FreeCAD object protocol import",
)
replace_once(
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n",
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n"
    "    from freecad_cloth.avatar.AvatarModel import AvatarParameters\n"
    "    from freecad_cloth.avatar.SkeletonPose import AffineTransform, JointRotation\n"
    "    from freecad_cloth.avatar.SkeletonTypes import SkeletonData\n"
    "    from freecad_cloth.avatar.coin_protocols import (\n"
    "        _CoinDynamicDragger,\n"
    "        _CoinEventCallback,\n"
    "        _CoinModule,\n"
    "        _CoinNode,\n"
    "        _CoinRotationField,\n"
    "        _CoinSeparator,\n"
    "        _CoinTransform,\n"
    "        _CoinType,\n"
    "    )\n\n",
    "typed GUI protocol imports",
)

protocol_start = typed_source.index("type PosePoint =")
protocol_end = typed_source.index("\ndef _modules()", protocol_start)
protocol_block = typed_source[protocol_start:protocol_end].rstrip() + "\n"

vector_anchor = (
    "    z: float\n"
)
vector_extension = (
    vector_anchor
    + "\n"
    + "    def __add__(self, other: _PoseVector) -> _PoseVector:\n"
    + "        \"\"\"Add two native FreeCAD vectors component by component.\"\"\"\n"
    + "        ...\n"
)
if protocol_block.count(vector_anchor) != 1:
    raise SystemExit("Expected one exact _PoseVector coordinate block.")
protocol_block = protocol_block.replace(vector_anchor, vector_extension, 1)

rotation_anchor = (
    "    def getEulerAngles(self, mode: int) -> Sequence[float]:\n"
    "        \"\"\"Return Euler components in the requested FreeCAD convention.\"\"\"\n"
    "        ...\n"
)
rotation_extension = (
    rotation_anchor
    + "\n"
    + "    def setYawPitchRoll(self, yaw: float, pitch: float, roll: float) -> None:\n"
    + "        \"\"\"Set the rotation using FreeCAD's yaw-pitch-roll convention.\"\"\"\n"
    + "        ...\n"
    + "\n"
    + "    def getYawPitchRoll(self) -> Sequence[float]:\n"
    + "        \"\"\"Return yaw, pitch and roll components in degrees.\"\"\"\n"
    + "        ...\n"
    + "\n"
    + "    def multVec(self, vector: _PoseVector) -> _PoseVector:\n"
    + "        \"\"\"Transform a vector using this rotation.\"\"\"\n"
    + "        ...\n"
)
if protocol_block.count(rotation_anchor) != 1:
    raise SystemExit("Expected one exact _PoseRotation method block.")
protocol_block = protocol_block.replace(rotation_anchor, rotation_extension, 1)

view_size_anchor = (
    "    def getSize(self) -> tuple[int, int]:\n"
    "        \"\"\"Return viewport dimensions in pixels.\"\"\"\n"
    "        ...\n"
)
view_size_extension = (
    view_size_anchor
    + "\n"
    + "    def getCameraOrientation(self) -> _PoseRotation:\n"
    + "        \"\"\"Return the viewport camera's world-space orientation.\"\"\"\n"
    + "        ...\n"
)
if protocol_block.count(view_size_anchor) != 1:
    raise SystemExit("Expected one exact _PoseView size method.")
protocol_block = protocol_block.replace(view_size_anchor, view_size_extension, 1)

qt_protocol_block = (
    "class _PoseQtMouseButtons(Protocol):\n"
    "    \"\"\"Minimal Qt mouse-button flags supporting a left-button test.\"\"\"\n"
    "\n"
    "    def __and__(self, other: object) -> object:\n"
    "        \"\"\"Return the flags selected by a Qt button mask.\"\"\"\n"
    "        ...\n"
    "\n"
    "\n"
    "class _PoseQtApplication(Protocol):\n"
    "    \"\"\"Application input-state API used by the pose release watchdog.\"\"\"\n"
    "\n"
    "    def mouseButtons(self) -> _PoseQtMouseButtons:\n"
    "        \"\"\"Return the currently held mouse-button flags.\"\"\"\n"
    "        ...\n"
    "\n"
    "\n"
    "class _PoseQtApplicationFactory(Protocol):\n"
    "    \"\"\"Static QApplication factory surface used by the controller.\"\"\"\n"
    "\n"
    "    def instance(self) -> _PoseQtApplication | None:\n"
    "        \"\"\"Return the active Qt application, when available.\"\"\"\n"
    "        ...\n"
    "\n"
    "\n"
    "class _PoseQtWidgets(Protocol):\n"
    "    \"\"\"Qt widget module surface used by viewport input handling.\"\"\"\n"
    "\n"
    "    QApplication: _PoseQtApplicationFactory\n"
    "\n"
    "\n"
    "class _PoseQtNamespace(Protocol):\n"
    "    \"\"\"Qt enum namespace exposing the mouse-button flag used by Pose Mode.\"\"\"\n"
    "\n"
    "    LeftButton: object\n"
    "\n"
    "\n"
    "class _PoseQtTimerFactory(Protocol):\n"
    "    \"\"\"Constructors and one-shot scheduling operations for Qt timers.\"\"\"\n"
    "\n"
    "    def __call__(self, parent: _QT_TYPE_QtWidgets.QWidget) -> _QtTimerProtocol:\n"
    "        \"\"\"Create a timer with the supplied QObject parent.\"\"\"\n"
    "        ...\n"
    "\n"
    "    def singleShot(self, milliseconds: int, callback: Callable[[], None]) -> None:\n"
    "        \"\"\"Schedule a no-argument callback after a delay in milliseconds.\"\"\"\n"
    "        ...\n"
    "\n"
    "\n"
    "class _PoseQtCore(Protocol):\n"
    "    \"\"\"Qt core module surface used by the pose release watchdog.\"\"\"\n"
    "\n"
    "    QTimer: _PoseQtTimerFactory\n"
    "    Qt: _PoseQtNamespace\n"
    "\n"
    "\n"
)
pose_panel_anchor = "class _PosePanel(Protocol):\n"
if protocol_block.count(pose_panel_anchor) != 1:
    raise SystemExit("Expected one exact _PosePanel protocol insertion point.")
protocol_block = protocol_block.replace(pose_panel_anchor, qt_protocol_block + pose_panel_anchor, 1)

panel_fields_anchor = (
    "    App: _PoseApplication\n"
    "    Gui: _PoseGui\n"
)
panel_fields = (
    "    App: _PoseApplication\n"
    "    Gui: _PoseGui\n"
    "    QtCore: _PoseQtCore\n"
    "    QtWidgets: _PoseQtWidgets\n"
    "    form: _QT_TYPE_QtWidgets.QWidget\n"
)
if protocol_block.count(panel_fields_anchor) != 1:
    raise SystemExit("Expected one exact _PosePanel application/gui field block.")
protocol_block = protocol_block.replace(panel_fields_anchor, panel_fields, 1)

panel_status_anchor = (
    "    def _set_status(self, message: str) -> None:\n"
    "        \"\"\"Update the task panel status.\"\"\"\n"
    "        ...\n"
)
panel_status_extension = (
    panel_status_anchor
    + "\n"
    + "    def _preview_rebuild(self) -> None:\n"
    + "        \"\"\"Regenerate the visible mannequin preview from staged pose data.\"\"\"\n"
    + "        ...\n"
)
if protocol_block.count(panel_status_anchor) != 1:
    raise SystemExit("Expected one exact _PosePanel status method.")
protocol_block = protocol_block.replace(panel_status_anchor, panel_status_extension, 1)
panel_method_original = (
    "    def _stage_joint_rotation(\n"
    "        self, bone: str, x: float, y: float, z: float, *, preview: bool\n"
    "    ) -> None:\n"
    "        \"\"\"Stage one joint rotation from an interactive viewport drag.\"\"\"\n"
    "        ...\n"
)
panel_method = (
    "    def _stage_joint_rotation(\n"
    "        self, bone: str, x: float, y: float, z: float, *, preview: bool, "
    "snap: bool | None = None\n"
    "    ) -> None:\n"
    "        \"\"\"Stage one joint rotation from an interactive viewport drag.\"\"\"\n"
    "        ...\n"
)
if protocol_block.count(panel_method_original) != 1:
    raise SystemExit("Expected one exact historical _PosePanel staged-rotation protocol declaration.")
protocol_block = protocol_block.replace(panel_method_original, panel_method, 1)
if protocol_block.count(panel_method) != 1:
    raise SystemExit("Expected one updated _PosePanel staged-rotation protocol declaration.")
protocol_block = protocol_block.replace(
    panel_method,
    panel_method
    + "\n"
    + "    def _set_rotation_axis_highlight(self, axis: str | None) -> None:\n"
    + '        """Highlight the matching numeric editor and viewport rotation ring."""\n'
    + "        ...\n",
    1,
)
anchor = "\n_VIEW_POSITION_METHOD = \"getPointOnScreen\"\n"
if source.count(anchor) != 1:
    raise SystemExit("Expected one insertion point before current-main viewport API constants.")
source = source.replace(anchor, "\n\n" + protocol_block + anchor, 1)

coin_old = "        from pivy import coin\n\n        return coin\n"
coin_new = "        from pivy import coin\n\n        return cast(\"_CoinModule\", coin)\n"
if source.count(coin_old) != 1:
    raise SystemExit("Expected one lazy Pivy import in SkeletonPoseController._coin.")
source = source.replace(coin_old, coin_new, 1)

screen_old = (
    "        project_on_screen = getattr(view, _VIEW_POSITION_METHOD)\n"
    "        get_size = getattr(view, _VIEW_SIZE_METHOD)\n"
    "        projected = project_on_screen(self.App.Vector(*point))\n"
    "        size = get_size()\n"
)
screen_new = (
    "        projected = view.getPointOnScreen(self.App.Vector(*point))\n"
    "        size = view.getSize()\n"
)
if source.count(screen_old) != 1:
    raise SystemExit("Expected one current-main screen projection block.")
source = source.replace(screen_old, screen_new, 1)
size_old = "        size = getattr(view, _VIEW_SIZE_METHOD)()\n"
if source.count(size_old) != 2:
    raise SystemExit("Expected two current-main pointer handlers using the documented view size API.")
source = source.replace(size_old, "        size = view.getSize()\n")

def collect_definitions(tree: ast.AST):
    found = {}
    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, scope + (child.name,))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = ".".join(scope + (child.name,))
                if key in found:
                    raise SystemExit(f"Ambiguous function scope while transplanting types: {key}")
                found[key] = child
                visit(child, scope + (child.name,))
            else:
                visit(child, scope)
    visit(tree, ())
    return found

def iter_arguments(args: ast.arguments) -> list[ast.arg]:
    values = [*args.posonlyargs, *args.args]
    if args.vararg is not None:
        values.append(args.vararg)
    values.extend(args.kwonlyargs)
    if args.kwarg is not None:
        values.append(args.kwarg)
    return values

def byte_column_to_char_offset(lines, line_offsets, line_number, byte_column):
    encoded = lines[line_number - 1].encode("utf-8")
    return line_offsets[line_number - 1] + len(encoded[:byte_column].decode("utf-8"))

def function_colon_offset(text, node, line_offsets):
    started = False
    paren_depth = 0
    closed_signature = False
    for item in tokenize.generate_tokens(io.StringIO(text).readline):
        if item.start[0] < node.lineno:
            continue
        if not started:
            if item.type == tokenize.NAME and item.string == "def" and item.start[0] == node.lineno:
                started = True
            continue
        if item.type != tokenize.OP:
            continue
        if item.string == "(":
            paren_depth += 1
        elif item.string == ")":
            paren_depth -= 1
            if paren_depth == 0:
                closed_signature = True
        elif item.string == ":" and closed_signature and paren_depth == 0:
            return line_offsets[item.start[0] - 1] + item.start[1]
    raise SystemExit(f"Could not locate a function header colon at line {node.lineno}.")

def walk_function_body(node):
    def walk(value):
        for child in ast.iter_child_nodes(value):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            yield child
            yield from walk(child)
    yield from walk(node)

main_tree = ast.parse(source)
typed_tree = ast.parse(typed_source)
main_defs = collect_definitions(main_tree)
typed_defs = collect_definitions(typed_tree)
main_lines = source.splitlines(keepends=True)
line_offsets = []
running = 0
for line in main_lines:
    line_offsets.append(running)
    running += len(line)

patches = defaultdict(list)
matched_functions = 0
added_parameters = 0
added_returns = 0
added_assignments = 0
for key, typed_node in typed_defs.items():
    main_node = main_defs.get(key)
    if main_node is None:
        continue
    matched_functions += 1
    typed_args = {arg.arg: arg for arg in iter_arguments(typed_node.args)}
    main_args = {arg.arg: arg for arg in iter_arguments(main_node.args)}
    if set(typed_args) != set(main_args):
        # Current main has newer methods in a few shared scopes. Do not graft
        # annotations onto a semantically different call signature.
        continue
    for name, main_arg in main_args.items():
        typed_arg = typed_args[name]
        if typed_arg.annotation is None or main_arg.annotation is not None:
            continue
        annotation = ast.get_source_segment(typed_source, typed_arg.annotation)
        if not annotation:
            raise SystemExit(f"Missing source text for parameter annotation {key}.{name}.")
        offset = byte_column_to_char_offset(main_lines, line_offsets, main_arg.end_lineno, main_arg.end_col_offset)
        patches[offset].append(": " + annotation)
        added_parameters += 1
    if typed_node.returns is not None and main_node.returns is None:
        annotation = ast.get_source_segment(typed_source, typed_node.returns)
        if not annotation:
            raise SystemExit(f"Missing source text for return annotation {key}.")
        patches[function_colon_offset(source, main_node, line_offsets)].append(" -> " + annotation)
        added_returns += 1

    typed_assignments = [x for x in walk_function_body(typed_node) if isinstance(x, ast.AnnAssign) and x.value is not None]
    main_assignments = [x for x in walk_function_body(main_node) if isinstance(x, ast.Assign) and len(x.targets) == 1]
    used = set()
    for typed_assignment in typed_assignments:
        target_key = ast.dump(typed_assignment.target, include_attributes=False)
        value_key = ast.dump(typed_assignment.value, include_attributes=False)
        candidates = [
            x for x in main_assignments
            if id(x) not in used
            and ast.dump(x.targets[0], include_attributes=False) == target_key
            and ast.dump(x.value, include_attributes=False) == value_key
            and isinstance(x.targets[0], (ast.Name, ast.Attribute))
        ]
        if len(candidates) != 1:
            continue
        assignment = candidates[0]
        used.add(id(assignment))
        annotation = ast.get_source_segment(typed_source, typed_assignment.annotation)
        if not annotation:
            raise SystemExit(f"Missing source text for assignment annotation {key}.")
        target = assignment.targets[0]
        offset = byte_column_to_char_offset(main_lines, line_offsets, target.end_lineno, target.end_col_offset)
        patches[offset].append(": " + annotation)
        added_assignments += 1

if matched_functions < 55:
    raise SystemExit(f"Too few matching typed functions; found {matched_functions}.")
for offset in sorted(patches, reverse=True):
    fragments = patches[offset]
    if len(fragments) != 1:
        raise SystemExit(f"Overlapping annotation insertions at source offset {offset}.")
    source = source[:offset] + fragments[0] + source[offset:]

old_axes = "        self._axis_draggers = {}\n"
axis_assignment_count = source.count(old_axes)
if axis_assignment_count != 3:
    raise SystemExit(
        f"Expected three current-main axis-dragger map assignments, found {axis_assignment_count}."
    )
source = source.replace(old_axes, "        self._axis_draggers: dict[str, _CoinDynamicDragger] = {}\n")

for required in (
    "from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol",
    "class _PoseAvatarFeature(FreeCADDocumentObjectProtocol, Protocol):",
    "class _PoseView(Protocol):",
    "class _PosePanel(Protocol):",
    "def _set_rotation_axis_highlight(self, axis: str | None) -> None:",
    "def _coin(self) -> _CoinModule:",
    "return cast(\"_CoinModule\", coin)",
    "GIZMO_SIZE = 88.0",
    "BONE_PICK_RADIUS = 16.0",
    "JOINT_PICK_RADIUS = 24.0",
    "self._axis_draggers: dict[str, _CoinDynamicDragger] = {}",
    "def highlight_axis(self, axis: str | None) -> None:",
    "class _PoseAxisFocusFilter",
    "axis_branch = coin.SoSeparator()",
    "self.panel.QtCore.QTimer.singleShot(0, self.panel._preview_rebuild)",
    "self.panel.QtWidgets.QApplication.instance()",
    "self._pointer_release_timer: _QtTimerProtocol | None = None",
    "def _poll_qt_pointer_release_state(self) -> None:",
    "camera_rotation = self.view.getCameraOrientation()",
    "def setYawPitchRoll(self, yaw: float, pitch: float, roll: float) -> None:",
    "def getYawPitchRoll(self) -> Sequence[float]:",
    "def multVec(self, vector: _PoseVector) -> _PoseVector:",
    "class _PoseQtCore(Protocol):",
    "class _PoseQtWidgets(Protocol):",
    "QtCore: _PoseQtCore",
    "form: _QT_TYPE_QtWidgets.QWidget",
    "def _preview_rebuild(self) -> None:",
):
    if required not in source:
        raise SystemExit(f"AvatarPoseGui typed-boundary transplant lost required state: {required}")
ast.parse(source)
path.write_text(source, encoding="utf-8")
print(
    "Transplanted Pivy boundary: "
    f"{matched_functions} function scopes, {added_parameters} parameters, "
    f"{added_returns} returns, {added_assignments} matching assignments."
)
PY
    git add freecad_cloth/avatar/AvatarPoseGui.py freecad_cloth/avatar/coin_protocols.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi

  elif [[ "$conflicts" == $'tests/test_build_visual_gifs.py\ntools/ci/build_visual_gifs.py' ]] && [[ "$(git rev-parse REBASE_HEAD)" == "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ]] ||
      ! git show origin/main:tools/ci/build_visual_gifs.py | grep -Fq 'options=CommandOptions(check=True, timeout=timeout)' ||
      ! git show origin/main:tests/test_build_visual_gifs.py | grep -Fq 'def test_build_visual_gif_passes_checked_command_options(' ||
      ! git show "$rebase_commit:tools/ci/build_visual_gifs.py" | grep -Fq 'from concurrent.futures import Future, ThreadPoolExecutor, as_completed' ||
      ! git show "$rebase_commit:tools/ci/build_visual_gifs.py" | grep -Fq 'if __package__ is not None and __package__ != ""' ||
      ! git show "$rebase_commit:tools/ci/build_visual_gifs.py" | grep -Fq '    if tool is None:' ||
      ! git show "$rebase_commit:tools/ci/build_visual_gifs.py" | grep -Fq 'jobs: list[Future[None]] = []' ||
      ! git show "$rebase_commit:tests/test_build_visual_gifs.py" | grep -Fq 'CommandOptions(check=True, timeout=17)'; then
      echo "::error::Refusing GIF-builder conflict outside the exact 9a43 typing cleanup and verified mainline CommandOptions contract."
      exit 1
    fi
    echo "::warning::Preserving mainline GIF command-runner API and stronger regression test; transplanting only exact typing refinements."
    git checkout --ours -- tests/test_build_visual_gifs.py tools/ci/build_visual_gifs.py
    python3 - <<'PY'
from pathlib import Path

path = Path("tools/ci/build_visual_gifs.py")
source = path.read_text(encoding="utf-8")

def replace_exact(old: str, new: str, label: str) -> None:
    global source
    old_count = source.count(old)
    new_count = source.count(new)
    if old_count == 1 and new_count == 0:
        source = source.replace(old, new, 1)
        return
    if old_count == 0 and new_count == 1:
        return
    raise SystemExit(f"Expected exactly one old or final {label} expression.")

replace_exact(
    "from concurrent.futures import ThreadPoolExecutor, as_completed",
    "from concurrent.futures import Future, ThreadPoolExecutor, as_completed",
    "concurrent future import",
)
replace_exact(
    "if __package__:",
    'if __package__ is not None and __package__ != ""',
    "package-context guard",
)
replace_exact(
    "    if not tool:",
    "    if tool is None:",
    "ImageMagick lookup guard",
)
replace_exact(
    "        jobs = []",
    "        jobs: list[Future[None]] = []",
    "turntable future list annotation",
)

for required in (
    "from concurrent.futures import Future, ThreadPoolExecutor, as_completed",
    'if __package__ is not None and __package__ != ""',
    "    if tool is None:",
    "options=CommandOptions(check=True, timeout=timeout)",
    "jobs: list[Future[None]] = []",
):
    if required not in source:
        raise SystemExit(f"GIF builder typing transplant incomplete: {required}")
path.write_text(source, encoding="utf-8")
PY
    git add tests/test_build_visual_gifs.py tools/ci/build_visual_gifs.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi

    elif [[ "$conflicts" == "freecad_cloth/pattern/PatternTopologyRepairGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "a59f58d25537de846677f89a7858562cfcfc9672" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "a59f58d25537de846677f89a7858562cfcfc9672" ]] ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _ComboBoxProtocol(Protocol):' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'def addItem(self, text: str, userData: object | None = None) -> None: ...' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'def currentData(self) -> object: ...' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _TopologyRepairViewportPicker:' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'self.rows.append((seam, side, combo, pick_button))' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/PatternTopologyRepairGui.py" | grep -Fq '"""Minimal Qt combo-box interface used by the topology repair panel."""' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/PatternTopologyRepairGui.py" | grep -Fq 'def addItem(self, text: str, userData: object | None = None) -> None: ...' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/PatternTopologyRepairGui.py" | grep -Fq 'def currentData(self) -> object: ...'; then
      echo "::error::Refusing combo protocol conflict outside the exact a59f docstring/optional-data commit and validated mainline viewport-picker state."
      exit 1
    fi
    echo "::warning::Preserving the already-typed combo-box protocol and applying only the exact a59f docstring."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepairGui.py
    python3 - <<'PY'
from pathlib import Path

path = Path("freecad_cloth/pattern/PatternTopologyRepairGui.py")
source = path.read_text(encoding="utf-8")
class_anchor = "class _ComboBoxProtocol(Protocol):\n"
docstring = '    """Minimal Qt combo-box interface used by the topology repair panel."""\n'
if source.count(class_anchor) != 1:
    raise SystemExit("Expected exactly one combo-box protocol declaration.")
if source.count(docstring) == 0:
    source = source.replace(class_anchor, class_anchor + docstring + "\n", 1)
elif source.count(docstring) != 1:
    raise SystemExit("Duplicate combo-box protocol docstrings are not a supported state.")
for required in (
    class_anchor,
    docstring,
    "def addItem(self, text: str, userData: object | None = None) -> None: ...",
    "def currentData(self) -> object: ...",
    "class _TopologyRepairViewportPicker:",
    "def _begin_viewport_pick(",
    "def _cancel_viewport_pick(",
    "self.rows.append((seam, side, combo, pick_button))",
    "for seam, side, combo, _pick_button in self.rows",
):
    if required not in source:
        raise SystemExit(f"Combo-box protocol replay incomplete: {required}")
path.write_text(source, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepairGui.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
elif [[ "$conflicts" == "freecad_cloth/pattern/PatternTopologyRepairGui.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "f7cc118eb4aafafbaf1e5bcc7526140ad2e6f28e" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "f7cc118eb4aafafbaf1e5bcc7526140ad2e6f28e" ]] ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _ComboBoxProtocol(Protocol):' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _TopologyRepairViewportPicker:' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'self.rows.append((seam, side, combo, pick_button))' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepair.py | grep -Fq 'class DocumentTransactionProtocol(Protocol):' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/PatternTopologyRepairGui.py" | grep -Fq 'def currentData(self) -> str | None: ...' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/PatternTopologyRepairGui.py" | grep -Fq 'def findData(self, value: str) -> int: ...' ||
      ! git show "$rebase_commit:freecad_cloth/pattern/PatternTopologyRepairGui.py" | grep -Fq 'def addItem(self, text: str, userData: str | None = None) -> None: ...'; then
      echo "::error::Refusing structural GUI typing outside the exact f7cc protocol commit and verified post-Ruff task-panel state."
      exit 1
    fi
    echo "::warning::Applying exact structural seam/document and string-valued combo protocols across the post-Ruff import layout; preserving viewport-picker behavior."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepairGui.py
    python3 - <<'PY'
from pathlib import Path

path = Path("freecad_cloth/pattern/PatternTopologyRepairGui.py")
source = path.read_text(encoding="utf-8")

legacy_import = "from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol\n"
if source.count(legacy_import) > 1:
    raise SystemExit("Duplicate legacy document-object imports are not a supported GUI state.")

protocol_import = (
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
)
combined_protocol_import = (
    "    from freecad_cloth.pattern.PatternTopologyRepair import "
    "DocumentTransactionProtocol, SeamFeatureProtocol\n"
)
if source.count(combined_protocol_import) == 0:
    if source.count(protocol_import) != 1:
        raise SystemExit("Expected exactly one SeamFeatureProtocol import in the TYPE_CHECKING block.")
    source = source.replace(protocol_import, combined_protocol_import, 1)
elif source.count(combined_protocol_import) != 1:
    raise SystemExit("Duplicate structural protocol imports are not a supported GUI state.")

def replace_type(old: str, new: str, *, label: str, expected: int = 1) -> None:
    global source
    count = source.count(old)
    if count == expected:
        source = source.replace(old, new)
        return
    if count == 0 and source.count(new) == expected:
        return
    raise SystemExit(f"Expected {expected} occurrence(s) of either old or final {label} annotation.")

replace_type(
    "    def addItem(self, text: str, userData: object | None = None) -> None: ...",
    "    def addItem(self, text: str, userData: str | None = None) -> None: ...",
    label="combo addItem",
)
replace_type(
    "    def currentData(self) -> object: ...",
    "    def currentData(self) -> str | None: ...",
    label="combo currentData",
)
def ensure_combo_method(old: str, new: str, *, label: str, after: str) -> None:
    global source
    old_count = source.count(old)
    new_count = source.count(new)
    if old == new:
        if old_count == 1:
            return
        if old_count > 1:
            raise SystemExit(f"Expected at most one final combo {label} method.")
        if source.count(after) != 1:
            raise SystemExit(f"Expected one insertion anchor for combo {label}.")
        source = source.replace(after, after + "\n" + new, 1)
        return
    if old_count == 1 and new_count == 0:
        source = source.replace(old, new, 1)
        return
    if old_count == 0 and new_count == 1:
        return
    if old_count == 0 and new_count == 0:
        if source.count(after) != 1:
            raise SystemExit(f"Expected one insertion anchor for combo {label}.")
        source = source.replace(after, after + "\n" + new, 1)
        return
    raise SystemExit(f"Expected one old or final combo {label} method.")

ensure_combo_method(
    "    def findData(self, value: object) -> int: ...",
    "    def findData(self, value: str) -> int: ...",
    label="findData",
    after="    def currentData(self) -> str | None: ...",
)
ensure_combo_method(
    "    def setCurrentIndex(self, index: int) -> None: ...",
    "    def setCurrentIndex(self, index: int) -> None: ...",
    label="setCurrentIndex",
    after="    def findData(self, value: str) -> int: ...",
)
ensure_combo_method(
    "    def count(self) -> int: ...",
    "    def count(self) -> int: ...",
    label="count",
    after="    def setCurrentIndex(self, index: int) -> None: ...",
)
replace_type(
    "        seam: FreeCADDocumentObjectProtocol,",
    "        seam: SeamFeatureProtocol,",
    label="seam feature",
    expected=2,
)
replace_type(
    "    def __init__(self, doc: object) -> None:",
    "    def __init__(self, doc: DocumentTransactionProtocol) -> None:",
    label="task-panel document",
)
replace_type(
    "def show_topology_repair_task(doc: object) -> PatternTopologyRepairTaskPanel:",
    "def show_topology_repair_task(doc: DocumentTransactionProtocol) -> PatternTopologyRepairTaskPanel:",
    label="task-panel factory document",
)

if legacy_import in source:
    source = source.replace(legacy_import, "", 1)
if "FreeCADDocumentObjectProtocol" in source:
    raise SystemExit("Legacy document-object protocol remains after seam/document typing.")
for required in (
    "from freecad_cloth.pattern.PatternTopologyRepair import DocumentTransactionProtocol, SeamFeatureProtocol",
    "def addItem(self, text: str, userData: str | None = None) -> None: ...",
    "def currentData(self) -> str | None: ...",
    "def findData(self, value: str) -> int: ...",
    "def setCurrentIndex(self, index: int) -> None: ...",
    "def count(self) -> int: ...",
    "seam: SeamFeatureProtocol,",
    "def __init__(self, doc: DocumentTransactionProtocol) -> None:",
    "def show_topology_repair_task(doc: DocumentTransactionProtocol) -> PatternTopologyRepairTaskPanel:",
    "class _TopologyRepairViewportPicker:",
    "def _begin_viewport_pick(",
    "def _cancel_viewport_pick(",
    "self.rows.append((seam, side, combo, pick_button))",
    "for seam, side, combo, _pick_button in self.rows",
):
    if required not in source:
        raise SystemExit(f"Structural topology GUI postcondition missing: {required}")
path.write_text(source, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepairGui.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == $'freecad_cloth/pattern/PatternTopologyRepairGui.py\ntests/test_simulation_gui.py\ntests/test_tunic_audit_contract.py' ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "99b9aa0e93e1a5e071a989c9b0a751dc2d8d6bbd" ]] ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _ComboBoxProtocol(Protocol):' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _TopologyRepairViewportPicker:' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'self.rows: list[' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'SeamFeatureProtocol' ||
      ! git show HEAD:tests/test_simulation_gui.py | grep -Fq 'test_simulation_scene_selectors_highlight_the_selected_objects_in_3d' ||
      ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))' ||
      ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'def test_native_arc_evaluator_returns_validated_planar_coordinates()' ||
      ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"'; then
      echo "::error::Refusing Ruff bulk conflict outside exact commit and verified post-typing source states."
      exit 1
    fi
    echo "::warning::Normalizing the already-typed topology GUI to the exact Ruff output, restoring valid mainline simulation tests, and retaining the native-arc regression."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepairGui.py tests/test_tunic_audit_contract.py
    git checkout origin/main -- tests/test_simulation_gui.py
    python3 - <<'PY'
from pathlib import Path

gui_path = Path("freecad_cloth/pattern/PatternTopologyRepairGui.py")
gui = gui_path.read_text(encoding="utf-8")

old_typechecking = (
    "if TYPE_CHECKING:\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
    "    from types import ModuleType\n\n"
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n"
)
formatted_typechecking = (
    "if TYPE_CHECKING:\n"
    "    from types import ModuleType\n\n"
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
)
if gui.count(old_typechecking) == 1:
    gui = gui.replace(old_typechecking, formatted_typechecking, 1)
elif gui.count(formatted_typechecking) != 1:
    raise SystemExit("Expected one supported topology GUI TYPE_CHECKING block.")

nested_rows = (
    "        self.rows: list[\n"
    "            tuple[\n"
    "                SeamFeatureProtocol,\n"
    "                str,\n"
    "                _ComboBoxProtocol,\n"
    "                _QT_TYPE_QtWidgets.QPushButton,\n"
    "            ]\n"
    "        ] = []\n"
)
flat_rows = (
    "        self.rows: list[tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, "
    "_QT_TYPE_QtWidgets.QPushButton]] = []\n"
)
formatted_rows = (
    "        self.rows: list[\n"
    "            tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, _QT_TYPE_QtWidgets.QPushButton]\n"
    "        ] = []\n"
)
if gui.count(nested_rows) == 1:
    gui = gui.replace(nested_rows, formatted_rows, 1)
elif gui.count(flat_rows) == 1:
    gui = gui.replace(flat_rows, formatted_rows, 1)
elif gui.count(formatted_rows) != 1:
    raise SystemExit("Expected one supported typed four-column topology GUI row annotation.")

if gui.count(formatted_typechecking) != 1 or gui.count(formatted_rows) != 1:
    raise SystemExit("Topology GUI Ruff normalization did not produce the exact expected imports/rows.")
for marker in (
    "class _ComboBoxProtocol(Protocol):",
    "class _TopologyRepairViewportPicker:",
    "self.rows.append((seam, side, combo, pick_button))",
    "def _begin_viewport_pick(",
    "def _cancel_viewport_pick(",
):
    if marker not in gui:
        raise SystemExit(f"Mainline topology GUI behavior was lost: {marker}")
gui_path.write_text(gui, encoding="utf-8")

sim_path = Path("tests/test_simulation_gui.py")
sim = sim_path.read_text(encoding="utf-8")
if len(sim.splitlines()) < 150:
    raise SystemExit("The simulation GUI test source was not restored as a real Python module.")
if "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))" not in sim:
    raise SystemExit("The valid mainline standalone test bootstrap was not restored.")
if "test_simulation_scene_selectors_highlight_the_selected_objects_in_3d" not in sim:
    raise SystemExit("The mainline viewport-selection test was not preserved.")

tunic_path = Path("tests/test_tunic_audit_contract.py")
tunic = tunic_path.read_text(encoding="utf-8")
arc_dataclass = "@dataclass\nclass _NativeArcPoint:"
if tunic.count(arc_dataclass) != 1:
    raise SystemExit("Expected exactly one native-arc point dataclass.")
marker_index = tunic.index(arc_dataclass)
prefix_start = marker_index
while prefix_start > 0 and tunic[prefix_start - 1] == "\n":
    prefix_start -= 1
blank_line_count = marker_index - prefix_start - 1
if blank_line_count == 1:
    tunic = tunic[:prefix_start] + "\n\n\n" + tunic[marker_index:]
elif blank_line_count != 2:
    raise SystemExit("Unexpected blank-line structure before the native-arc point dataclass.")
if tunic.count("@dataclass\nclass _NativeArcPoint") != 1:
    raise SystemExit("Tunic native-arc formatting must retain exactly one dataclass.")
if "test_native_arc_evaluator_returns_validated_planar_coordinates" not in tunic:
    raise SystemExit("The previously transplanted native-arc regression test was lost.")
tunic_path.write_text(tunic, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepairGui.py tests/test_simulation_gui.py tests/test_tunic_audit_contract.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tests/test_runner_routing_contract.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "50ede88397daff95154ba5e3386f4914b08ee3e9" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    test_path="tests/test_runner_routing_contract.py"
    benchmark_path="tests/freecad_realtime_benchmark.py"
    changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}")"
    changed_path_count="$(printf '%s\n' "$changed_paths" | grep -c .)"
    test_numstat="$(git diff --numstat "${rebase_commit}^" "${rebase_commit}" -- "${test_path}")"
    test_additions="$(printf '%s' "$test_numstat" | cut -f1)"
    test_deletions="$(printf '%s' "$test_numstat" | cut -f2)"
    helper_references="$(git show "${rebase_commit}:${benchmark_path}" | grep -Fc '_avatar_preview_dimensions(' || true)"
    if [[ "$rebase_commit" != "50ede88397daff95154ba5e3386f4914b08ee3e9" ]] ||
      [[ "$changed_path_count" != "2" ]] ||
      ! printf '%s\n' "$changed_paths" | grep -Fxq "$benchmark_path" ||
      ! printf '%s\n' "$changed_paths" | grep -Fxq "$test_path" ||
      [[ "$test_additions" != "1" ]] ||
      [[ "$test_deletions" != "3" ]] ||
      ! git show "${rebase_commit}:${benchmark_path}" | grep -Fq "def _avatar_preview_dimensions(" ||
      [[ "$helper_references" != "3" ]] ||
      git show "${rebase_commit}^:${benchmark_path}" | grep -Fq "def _avatar_preview_dimensions(" ||
      git show "origin/main:${benchmark_path}" | grep -Fq "def _avatar_preview_dimensions(" ||
      ! git show "origin/main:${test_path}" | grep -Fq "loop_done = resolver.index" ||
      ! git show "origin/main:${test_path}" | grep -Fq "for handler in (" ||
      ! git show "origin/main:${test_path}" | grep -Fq "tests/test_build_visual_gifs.py" ||
      ! git show "origin/main:${test_path}" | grep -Fq "tools/ci/build_visual_gifs.py" ||
      ! git show "origin/main:${test_path}" | grep -Fq "assert loop_start < position < fail_closed"; then
      echo "::error::Refusing 50ede883 conflict outside the exact test-format hunk and expected new avatar-bounds helper."
      exit 1
    fi
    echo "::warning::Keeping main current routing contracts and retaining the exact shared avatar-bounds helper."
    git checkout --ours -- "${test_path}"
    git add "${test_path}" "${benchmark_path}"
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "${conflicts}" == "tests/test_runner_routing_contract.py" ]] && [[ "$(git rev-parse REBASE_HEAD)" == "876177f738e9b2d44add162e589027f5fb68338c" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    test_path="tests/test_runner_routing_contract.py"
    benchmark_path="tests/freecad_realtime_benchmark.py"
    expected_paths="$(printf '%s\n' "${benchmark_path}" "${test_path}" | LC_ALL=C sort)"
    changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}" | LC_ALL=C sort)"
    benchmark_numstat="$(git diff --numstat "${rebase_commit}^" "${rebase_commit}" -- "${benchmark_path}")"
    benchmark_additions="$(printf '%s' "${benchmark_numstat}" | cut -f1)"
    benchmark_deletions="$(printf '%s' "${benchmark_numstat}" | cut -f2)"
    helper_references="$(git show "${rebase_commit}:${benchmark_path}" | grep -Fc '_avatar_preview_dimensions(' || true)"
    formatted_calls="$(git show "${rebase_commit}:${benchmark_path}" | grep -Fc 'body_width, body_depth, body_height, center_x, center_y, z_min = _avatar_preview_dimensions(' || true)"
    parent_wrapped_calls="$(git show "${rebase_commit}^:${benchmark_path}" | grep -Fc 'body_width, body_depth, body_height, center_x, center_y, z_min = (' || true)"
    if [[ "${rebase_commit}" != "876177f738e9b2d44add162e589027f5fb68338c" ]] ||
      [[ "${conflicts}" != "${test_path}" ]] ||
      [[ "${changed_paths}" != "${expected_paths}" ]] ||
      [[ "${benchmark_additions}" != "4" ]] ||
      [[ "${benchmark_deletions}" != "4" ]] ||
      [[ "${helper_references}" != "3" ]] ||
      [[ "${formatted_calls}" != "2" ]] ||
      [[ "${parent_wrapped_calls}" != "2" ]] ||
      ! git show "${rebase_commit}^:${benchmark_path}" | grep -Fq "def _avatar_preview_dimensions(" ||
      ! git show "${rebase_commit}:${benchmark_path}" | grep -Fq "def _avatar_preview_dimensions("; then
      echo "::error::Refusing 876177f7 conflict outside the exact duplicate-test plus two-call Ruff formatting change."
      exit 1
    fi
    if ! python3 - "${rebase_commit}" "${test_path}" <<'PY'
import re
import subprocess
import sys

commit, path = sys.argv[1:]
def show(revision: str) -> str:
    return subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

historical = show(commit)
mainline = show("origin/main")
pattern = re.compile(r"^def (test_[A-Za-z0-9_]+)\(", re.MULTILINE)
historical_names = pattern.findall(historical)
mainline_names = pattern.findall(mainline)
historical_set = set(historical_names)
mainline_set = set(mainline_names)
missing = sorted(historical_set - mainline_set)
if missing:
    raise SystemExit(f"Historical test functions absent from current main: {missing!r}")
if len(historical_names) <= len(historical_set):
    raise SystemExit("Expected the historical duplicate test-function tail in 876177f7.")
if len(mainline_names) != len(mainline_set):
    raise SystemExit("Current main routing contract unexpectedly contains duplicate test functions.")
for marker in (
    "syntax_check.returncode == 0, syntax_check.stderr",
    "loop_done = resolver.index",
    "for handler in (",
    "tests/test_build_visual_gifs.py",
    "tools/ci/build_visual_gifs.py",
    "assert loop_start < position < fail_closed",
):
    if marker not in mainline:
        raise SystemExit(f"Current-main routing contract is missing required marker: {marker}")
PY
    then
      echo "::error::Current-main routing contract does not fully cover the historical test functions from 876177f7."
      exit 1
    fi
    echo "::notice::Retaining the two exact Ruff-formatted avatar helper calls and keeping current main's single canonical routing contract."
    git checkout origin/main -- "${test_path}"
    git checkout "${rebase_commit}" -- "${benchmark_path}"
    git add "${test_path}" "${benchmark_path}"
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
      bash tools/ci/guarded_rebase_conflict_entrypoint.sh
    fi
  else
    echo "::error::Unsupported rebase conflict; refusing automatic resolution: ${conflicts:-(none)}"
    exit 1
  fi
done
