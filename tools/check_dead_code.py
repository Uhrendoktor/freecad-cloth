#!/usr/bin/env python3
# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run Vulture only on high-confidence dead code in selected core surfaces."""

from __future__ import annotations

import sys
from pathlib import Path

from vulture.core import main as vulture_main

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = (
    ROOT / "freecad_cloth" / "common",
    ROOT / "freecad_cloth" / "shared",
    ROOT / "freecad_cloth" / "pattern",
    ROOT / "freecad_cloth" / "sewing",
    ROOT / "freecad_cloth" / "avatar",
    ROOT / "freecad_cloth" / "simulation",
    ROOT / "tools",
)


def allowed(path: Path) -> bool:
    """Return whether a path is in a statically analyzable core surface.

    Args:
        path: Candidate source path to classify.

    Returns:
        Whether the resolved path belongs to an eligible core directory and file type.
    """
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT)
    except ValueError:
        return False
    return any(
        resolved.is_relative_to(root) for root in ALLOWED_ROOTS
    ) and not relative.name.endswith(("Gui.py", "Commands.py", "workbench.py"))


def _run_vulture(paths: tuple[str, ...]) -> int:
    """Run Vulture's CLI entrypoint without spawning a separate process.

    Args:
        paths: Eligible source paths passed to Vulture's command-line interface.

    Returns:
        The same integer exit status Vulture would return to the calling shell.
    """
    previous_argv = sys.argv
    try:
        sys.argv = ["vulture", "--min-confidence", "100", *paths]
        try:
            vulture_main()
        except SystemExit as error:
            if error.code is None:
                return 0
            return error.code if isinstance(error.code, int) else 1
    finally:
        sys.argv = previous_argv
    return 0


def main() -> int:
    """Run Vulture at 100% confidence for selected files.

    Returns:
        Vulture's exit status, or zero when no eligible paths remain.
    """
    candidates = [Path(value) for value in sys.argv[1:]]
    if not candidates:
        candidates = [
            path for root in ALLOWED_ROOTS if root.exists() for path in root.rglob("*.py")
        ]
    paths = tuple(str(path) for path in candidates if path.is_file() and allowed(path))
    if not paths:
        return 0
    return _run_vulture(paths)


if __name__ == "__main__":
    raise SystemExit(main())
