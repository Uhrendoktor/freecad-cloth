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
    fi  elif [[ "$conflicts" == "freecad_cloth/pattern/PatternTopologyRepairGui.py" ]]; then
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
    "    def addItem(self, text: str, userData: object = None) -> None: ...\n\n"
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
  elif [[ "$conflicts" == $'freecad_cloth/pattern/PatternTopologyRepairGui.py\ntests/test_simulation_gui.py\ntests/test_tunic_audit_contract.py' ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "99b9aa0e93e1a5e071a989c9b0a751dc2d8d6bbd" ]] ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _ComboBoxProtocol(Protocol):' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'self.rows: list[tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, _QT_TYPE_QtWidgets.QPushButton]] = []' ||
      ! git show HEAD:tests/test_simulation_gui.py | grep -Fq 'test_simulation_scene_selectors_highlight_the_selected_objects_in_3d' ||
      ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))' ||
      ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'def test_native_arc_evaluator_returns_validated_planar_coordinates()' ||
      ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"'; then
      echo "::error::Refusing the Ruff bulk conflict outside the exact commit and its three verified file states."
      exit 1
    fi
    echo "::warning::Applying the exact Ruff formatting to topology GUI and tunic tests while restoring the valid mainline simulation test source."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepairGui.py tests/test_tunic_audit_contract.py
    git checkout origin/main -- tests/test_simulation_gui.py
    python3 - <<'PY'
from pathlib import Path

gui_path = Path("freecad_cloth/pattern/PatternTopologyRepairGui.py")
gui = gui_path.read_text(encoding="utf-8")
old_imports = (
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
)
new_imports = (
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
)
if gui.count(old_imports) != 1:
    raise SystemExit("Expected exactly one topology GUI TYPE_CHECKING import pair for Ruff formatting.")
gui = gui.replace(old_imports, new_imports, 1)

old_rows = (
    "        self.rows: list[tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, "
    "_QT_TYPE_QtWidgets.QPushButton]] = []\n"
)
new_rows = (
    "        self.rows: list[\n"
    "            tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, _QT_TYPE_QtWidgets.QPushButton]\n"
    "        ] = []\n"
)
if gui.count(old_rows) != 1:
    raise SystemExit("Expected exactly one long four-column repair-row annotation for Ruff formatting.")
gui = gui.replace(old_rows, new_rows, 1)
if old_imports in gui or old_rows in gui or "class _TopologyRepairViewportPicker:" not in gui:
    raise SystemExit("Topology GUI Ruff transform did not preserve the viewport picker.")
if "self.rows.append((seam, side, combo, pick_button))" not in gui:
    raise SystemExit("Four-field mainline repair rows were lost.")
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
old_boundary = (
    '    assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"\n'
    "@dataclass\n"
)
new_boundary = (
    '    assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"\n'
    "\n\n"
    "@dataclass\n"
)
if tunic.count(old_boundary) != 1:
    raise SystemExit("Expected exactly one native-arc dataclass boundary for Ruff blank-line formatting.")
tunic = tunic.replace(old_boundary, new_boundary, 1)
if old_boundary in tunic or tunic.count("@dataclass\nclass _NativeArcPoint") != 1:
    raise SystemExit("Tunic native-arc Ruff formatting did not preserve one dataclass declaration.")
if "test_native_arc_evaluator_returns_validated_planar_coordinates" not in tunic:
    raise SystemExit("The previously transplanted native-arc regression test was lost.")
tunic_path.write_text(tunic, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepairGui.py tests/test_simulation_gui.py tests/test_tunic_audit_contract.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  else
    echo "::error::Unsupported rebase conflict; refusing automatic resolution: ${conflicts:-(none)}"
    exit 1
  fi
done
freecad_cloth/pattern/PatternTopologyRepairGui.py\ntests/test_simulation_gui.py\ntests/test_tunic_audit_contract.py' ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "99b9aa0e93e1a5e071a989c9b0a751dc2d8d6bbd" ]] ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'class _ComboBoxProtocol(Protocol):' ||
      ! git show HEAD:freecad_cloth/pattern/PatternTopologyRepairGui.py | grep -Fq 'self.rows: list[tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, _QT_TYPE_QtWidgets.QPushButton]] = []' ||
      ! git show HEAD:tests/test_simulation_gui.py | grep -Fq 'test_simulation_scene_selectors_highlight_the_selected_objects_in_3d' ||
      ! git show origin/main:tests/test_simulation_gui.py | grep -Fq 'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))' ||
      ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'def test_native_arc_evaluator_returns_validated_planar_coordinates()' ||
      ! git show HEAD:tests/test_tunic_audit_contract.py | grep -Fq 'assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"'; then
      echo "::error::Refusing the Ruff bulk conflict outside the exact commit and its three verified file states."
      exit 1
    fi
    echo "::warning::Applying the exact Ruff formatting to topology GUI and tunic tests while restoring the valid mainline simulation test source."
    git checkout --ours -- freecad_cloth/pattern/PatternTopologyRepairGui.py tests/test_tunic_audit_contract.py
    git checkout origin/main -- tests/test_simulation_gui.py
    python3 - <<'PY'
from pathlib import Path

gui_path = Path("freecad_cloth/pattern/PatternTopologyRepairGui.py")
gui = gui_path.read_text(encoding="utf-8")
old_imports = (
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
)
new_imports = (
    "    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets\n\n"
    "    from freecad_cloth.pattern.PatternTopologyRepair import SeamFeatureProtocol\n"
)
if gui.count(old_imports) != 1:
    raise SystemExit("Expected exactly one topology GUI TYPE_CHECKING import pair for Ruff formatting.")
gui = gui.replace(old_imports, new_imports, 1)

old_rows = (
    "        self.rows: list[tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, "
    "_QT_TYPE_QtWidgets.QPushButton]] = []\n"
)
new_rows = (
    "        self.rows: list[\n"
    "            tuple[SeamFeatureProtocol, str, _ComboBoxProtocol, _QT_TYPE_QtWidgets.QPushButton]\n"
    "        ] = []\n"
)
if gui.count(old_rows) != 1:
    raise SystemExit("Expected exactly one long four-column repair-row annotation for Ruff formatting.")
gui = gui.replace(old_rows, new_rows, 1)
if old_imports in gui or old_rows in gui or "class _TopologyRepairViewportPicker:" not in gui:
    raise SystemExit("Topology GUI Ruff transform did not preserve the viewport picker.")
if "self.rows.append((seam, side, combo, pick_button))" not in gui:
    raise SystemExit("Four-field mainline repair rows were lost.")
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
old_boundary = (
    '    assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"\n'
    "@dataclass\n"
)
new_boundary = (
    '    assert not missing, f"Realtime CPU/CUDA fallback measurements are missing: {missing!r}"\n'
    "\n\n"
    "@dataclass\n"
)
if tunic.count(old_boundary) != 1:
    raise SystemExit("Expected exactly one native-arc dataclass boundary for Ruff blank-line formatting.")
tunic = tunic.replace(old_boundary, new_boundary, 1)
if old_boundary in tunic or tunic.count("@dataclass\nclass _NativeArcPoint") != 1:
    raise SystemExit("Tunic native-arc Ruff formatting did not preserve one dataclass declaration.")
if "test_native_arc_evaluator_returns_validated_planar_coordinates" not in tunic:
    raise SystemExit("The previously transplanted native-arc regression test was lost.")
tunic_path.write_text(tunic, encoding="utf-8")
PY
    git add freecad_cloth/pattern/PatternTopologyRepairGui.py tests/test_simulation_gui.py tests/test_tunic_audit_contract.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  else
    echo "::error::Unsupported rebase conflict; refusing automatic resolution: ${conflicts:-(none)}"
    exit 1
  fi
done
