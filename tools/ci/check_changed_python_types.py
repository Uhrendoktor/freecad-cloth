# Copyright (C) 2026 FreeCAD Cloth contributors
"""Block increases in missing-annotation and generic-object debt in changed Python files.

The repository has existing annotation debt. This gate compares Ruff annotation diagnostics
and generic-object type annotations against the merge base, so changed code cannot add debt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from tools.ci.command_runner import CommandOptions, run_command

if TYPE_CHECKING:
    from collections.abc import Mapping

from tools.check_documentation_contract import object_annotation_violations

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


def changed_python_sources(base: str) -> dict[str, str | None]:
    """Map each changed Python path to its base path, or None for newly added files.

    Args:
        base: Target branch name used as the merge-base comparison reference.

    Returns:
        Changed Python paths mapped to their previous path, or None when newly added.
    """
    base_ref = f"origin/{base}"
    result = run_command(
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            "-z",
            f"{base_ref}...HEAD",
            "--",
            "*.py",
            "*.pyi",
        ],
        options=CommandOptions(check=True, capture_output=True, timeout=30),
    )
    fields = (result.stdout or "").split("\0")
    changed: dict[str, str | None] = {}
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not status:
            continue
        if status.startswith(("R", "C")):
            old_path, new_path = fields[index : index + 2]
            index += 2
            if new_path:
                changed[new_path] = old_path
            continue
        current_path = fields[index]
        index += 1
        if not current_path or status == "D":
            continue
        changed[current_path] = None if status == "A" else current_path
    return changed


def annotation_regressions(
    current: Mapping[str, int],
    baseline: Mapping[str, int],
) -> tuple[tuple[str, int, int], ...]:
    """Return rules whose current violation count exceeds the base count.

    Args:
        current: Current diagnostic totals by Ruff rule code.
        baseline: Diagnostic totals measured at the target branch base.

    Returns:
        Rule codes whose current total exceeds the baseline, with both counts.
    """
    return tuple(
        (rule, baseline.get(rule, 0), current.get(rule, 0))
        for rule in RULES
        if current.get(rule, 0) > baseline.get(rule, 0)
    )


def _ruff_annotation_counts(source: str, filename: str) -> dict[str, int]:
    """Count selected annotation diagnostics in source using an isolated Ruff run.

    Args:
        source: Python source text analyzed through standard input.
        filename: Original filename used to label diagnostics and config matching.

    Returns:
        Ruff annotation diagnostic totals by rule code.

    Raises:
        RuntimeError: If Ruff cannot analyze the source or returns invalid JSON.
    """
    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--isolated",
        "--target-version",
        "py312",
        "--select",
        ",".join(RULES),
        "--output-format",
        "json",
        "--stdin-filename",
        filename,
        "-",
    ]
    result = run_command(
        command,
        options=CommandOptions(
            check=False,
            capture_output=True,
            input_text=source,
            timeout=30,
        ),
    )
    if result.returncode not in {0, 1}:
        detail = (result.stderr or "").strip() or (result.stdout or "").strip()
        msg = f"Ruff could not analyze {filename}: {detail}"
        raise RuntimeError(msg)
    try:
        diagnostics = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        msg = f"Ruff returned invalid JSON for {filename}"
        raise RuntimeError(msg) from exc
    counts: Counter[str] = Counter()
    for diagnostic in diagnostics:
        code = diagnostic.get("code")
        if code in RULES:
            counts[code] += 1
    return dict(counts)


def object_annotation_regression(current: int, baseline: int) -> tuple[int, int] | None:
    """Return baseline/current counts when changed code adds generic object annotations.

    Args:
        current: Number of generic object annotations in the changed source.
        baseline: Number of generic object annotations in its base version.

    Returns:
        Baseline and current totals when debt increased, otherwise None.
    """
    return (baseline, current) if current > baseline else None


def _base_source(base: str, path: str) -> str | None:
    """Read a file from the target branch; return None when it did not exist there.

    Args:
        base: Target branch name containing the previous source version.
        path: Repository-relative path read from that branch.

    Returns:
        Source text from the target branch, or None when the path is absent.
    """
    result = run_command(
        ["git", "show", f"origin/{base}:{path}"],
        options=CommandOptions(check=False, capture_output=True, timeout=15),
    )
    if result.returncode != 0:
        return None
    return result.stdout or ""


def main() -> int:
    """Fail when a changed Python file adds missing-annotation violations.

    Returns:
        Zero when changed Python sources add no annotation or generic-object debt.

    Raises:
        SystemExit: If command-line arguments are invalid.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default=os.environ.get("BASE_REF") or os.environ.get("GITHUB_BASE_REF") or "main",
    )
    args = parser.parse_args()
    changed = changed_python_sources(args.base)
    if not changed:
        print("changed-python-types=skipped files=0", flush=True)
        return 0

    regressions: list[str] = []
    for path, base_path in sorted(changed.items()):
        current_path = Path(path)
        if not current_path.is_file():
            continue
        try:
            current_source = current_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            msg = f"unable to read changed Python source {path}: {exc}"
            raise SystemExit(msg) from exc

        current_counts = _ruff_annotation_counts(current_source, path)
        previous_source = _base_source(args.base, base_path) if base_path is not None else None
        previous_counts = (
            _ruff_annotation_counts(previous_source, path) if previous_source is not None else {}
        )
        for rule, previous_count, current_count in annotation_regressions(
            current_counts, previous_counts
        ):
            regressions.append(f"{path}: {rule} increased from {previous_count} to {current_count}")

        current_object_count = len(object_annotation_violations(current_source, path))
        previous_object_count = (
            len(object_annotation_violations(previous_source, base_path))
            if previous_source is not None and base_path is not None
            else 0
        )
        object_delta = object_annotation_regression(current_object_count, previous_object_count)
        if object_delta is not None:
            previous_count, current_count = object_delta
            regressions.append(
                f"{path}: generic object annotations increased from "
                f"{previous_count} to {current_count}"
            )

    if regressions:
        print("changed-python-types=failed", file=sys.stderr)
        print("\n".join(regressions), file=sys.stderr)
        return 1

    print(
        f"changed-python-types=passed files={len(changed)} "
        "policy=no annotation or generic-object debt increase",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
