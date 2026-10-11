#!/usr/bin/env python3
"""Validate local Markdown links and image references used by repository documentation."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
HTML_REF = re.compile(r"""(?:src|href)=["']([^"']+)["']""", re.IGNORECASE)


def markdown_files() -> tuple[Path, ...]:
    """Return Markdown files that form the repository documentation surface."""
    paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "CONTRIBUTING.md",
        *ROOT.glob("docs/**/*.md"),
        *ROOT.glob(".github/**/*.md"),
    ]
    return tuple(sorted({path for path in paths if path.is_file()}))


def _local_target(source: Path, target: str) -> Path | None:
    """Resolve a local Markdown or HTML target."""
    target = unquote(target.strip("<>"))
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("#"):
        return None
    if not parsed.path:
        return None
    if parsed.path.startswith("/"):
        return ROOT / parsed.path.lstrip("/")
    return source.parent / parsed.path


def check(source: Path) -> list[str]:
    """Return broken local documentation references in one Markdown file."""
    text = source.read_text(encoding="utf-8")
    references = [*MARKDOWN_LINK.findall(text), *HTML_REF.findall(text)]
    errors = []
    for target in references:
        path = _local_target(source, target)
        if path is not None and not path.exists():
            errors.append(f"{source}: broken local documentation reference: {target}")
    return errors


def main() -> int:
    """Validate all repository Markdown documentation."""
    errors = [error for path in markdown_files() for error in check(path)]
    if errors:
        print("\n".join(errors))
        return 1
    print(f"markdown-contract=passed files={len(markdown_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
