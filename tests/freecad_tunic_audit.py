# Copyright (C) 2026 FreeCAD Cloth contributors
"""Production tunic visual/simulation audit entry point.

The shared FreeCAD screenshot fixture owns all executable behavior. This module
selects its explicit production audit profile and runs the checked-in fixture
without generating or modifying Python source.
"""

import ast
import importlib.util
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "freecad_screenshot_source.py"


def _load_openmp_experiment_binding() -> None:
    """Load the pinned source-built pyPBD extension before the workbench imports it.

    The FreeCAD launcher can reorder Python search paths after process startup.
    Loading the extension by its absolute path makes the A/B binary selection
    explicit and prevents accidentally timing the installed wheel in both arms.
    """
    mode = os.environ.get("CLOTH_PBD_OPENMP_TEAM_REUSE")
    if mode not in {"0", "1"}:
        return

    extension_root = Path("/opt/pypbd-openmp-experiment")
    extension_paths = sorted(extension_root.glob("pypbd*.so"))
    if len(extension_paths) != 1:
        raise RuntimeError(
            "expected exactly one source-built pyPBD extension in "
            f"{extension_root}, found {len(extension_paths)}"
        )
    module_path = extension_paths[0].resolve()
    existing_module = sys.modules.get("pypbd")
    if existing_module is not None:
        existing_path = getattr(existing_module, "__file__", None)
        if isinstance(existing_path, str) and Path(existing_path).resolve() == module_path:
            return
        raise RuntimeError(
            f"pyPBD was imported before the native experiment loader: {existing_path!r}"
        )

    spec = importlib.util.spec_from_file_location("pypbd", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create the source-built pyPBD module spec: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pypbd"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("pypbd", None)
        raise

    loaded_path = getattr(module, "__file__", None)
    if not isinstance(loaded_path, str) or Path(loaded_path).resolve() != module_path:
        sys.modules.pop("pypbd", None)
        raise RuntimeError(
            f"source-built pyPBD import resolved to an unexpected module: {loaded_path!r}"
        )
    print(
        f"pypbd-openmp-experiment=loaded mode={mode} module={loaded_path}",
        flush=True,
    )


def main() -> int:
    """Run the checked-in screenshot fixture with production tunic acceptance.

    Returns:
        Zero after the fixture passes or after a requested syntax-only check succeeds.
    """
    os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
    os.environ["CLOTH_TUNIC_AUDIT_PROFILE"] = "production"
    os.environ["CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"] = "1"
    if "--syntax-check" in sys.argv:
        ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
        print("tunic-audit-source-syntax=passed", flush=True)
        return 0
    _load_openmp_experiment_binding()
    runpy.run_path(str(SOURCE), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
