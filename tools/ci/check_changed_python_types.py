"""Block increases in missing-annotation debt for every changed Python file.

The repository has existing annotation debt. This gate compares Ruff's annotation
diagnostics per file and rule against the merge base, so new or changed code must
not add debt while unrelated historical debt can be retired incrementally.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
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


def changed_python_sources(base: str) -> dict[str, str | None]:
    """Map each changed Python path to its base path, or None for newly added files."""
    base_ref = f"origin/{base}"
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            "-z",
            f"{base_ref}...HEAD",
            "--",
            "*.py",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.split("\0")
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
    """Return rules whose current violation count exceeds the base count."""
    return tuple(
        (rule, baseline.get(rule, 0), current.get(rule, 0))
        for rule in RULES
        if current.get(rule, 0) > baseline.get(rule, 0)
    )


def _ruff_annotation_counts(source: str, filename: str) -> dict[str, int]:
    """Count selected annotation diagnostics in source using a stable isolated Ruff run."""
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
    result = subprocess.run(command, input=source, check=False, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Ruff could not analyze {filename}: {detail}")
    try:
        diagnostics = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff returned invalid JSON for {filename}") from exc
    counts: Counter[str] = Counter()
    for diagnostic in diagnostics:
        code = diagnostic.get("code")
        if code in RULES:
            counts[code] += 1
    return dict(counts)


def _base_source(base: str, path: str) -> str | None:
    """Read a file from the target branch; return None when it did not exist there."""
    result = subprocess.run(
        ["git", "show", f"origin/{base}:{path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> int:
    """Fail when a changed Python file adds missing-annotation violations."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default=os.environ.get("BASE_REF") or os.environ.get("GITHUB_BASE_REF") or "main",
    )
    args = parser.parse_args()
    changed = changed_python_sources(args.base)
    if not changed:
        print("changed-python-annotations=skipped files=0", flush=True)
        return 0

    regressions: list[str] = []
    for path, base_path in sorted(changed.items()):
        current_path = Path(path)
        if not current_path.is_file():
            continue
        try:
            current_source = current_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SystemExit(f"unable to read changed Python source {path}: {exc}") from exc

        current_counts = _ruff_annotation_counts(current_source, path)
        previous_source = _base_source(args.base, base_path) if base_path is not None else None
        previous_counts = (
            _ruff_annotation_counts(previous_source, path) if previous_source is not None else {}
        )
        for rule, previous_count, current_count in annotation_regressions(
            current_counts, previous_counts
        ):
            regressions.append(f"{path}: {rule} increased from {previous_count} to {current_count}")

    if regressions:
        print("changed-python-annotations=failed", file=sys.stderr)
        print("\n".join(regressions), file=sys.stderr)
        return 1

    print(
        f"changed-python-annotations=passed files={len(changed)} "
        "policy=no per-file annotation debt increase",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
