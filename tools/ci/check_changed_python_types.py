"""Enforce explicit typing on changed production Python modules."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

RULES = (
    "ANN001",
    "ANN002",
    "ANN003",
    "ANN201",
    "ANN202",
    "ANN204",
    "ANN205",
    "ANN206",
    "ANN401",
)


def _is_dynamic_surface(path: Path) -> bool:
    """Return whether a module is intentionally outside the annotation gate."""
    name = path.name
    return (
        name.endswith("Gui.py")
        or name.endswith("Commands.py")
        or name in {"gui.py", "workbench.py"}
    )


def changed_production_modules(base: str) -> tuple[str, ...]:
    """Return changed production modules, excluding deliberately dynamic GUI surfaces."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"origin/{base}...HEAD", "--", "freecad_cloth"],
        check=True,
        capture_output=True,
        text=True,
    )
    paths = []
    for raw in result.stdout.splitlines():
        path = Path(raw)
        if path.suffix == ".py" and not _is_dynamic_surface(path):
            paths.append(path.as_posix())
    return tuple(paths)


def main() -> int:
    """Check annotations on changed production modules."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default=os.environ.get("BASE_REF") or os.environ.get("GITHUB_BASE_REF") or "main",
    )
    args = parser.parse_args()
    changed = changed_production_modules(args.base)
    if not changed:
        print("changed-python-annotations=skipped modules=0", flush=True)
        return 0

    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--select",
        ",".join(RULES),
        *changed,
    ]
    subprocess.run(command, check=True)
    print(f"changed-python-annotations=passed modules={len(changed)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
