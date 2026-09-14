from __future__ import annotations

import hashlib
from pathlib import Path


ICONS_DIR = Path(__file__).parents[1] / "resources" / "icons"
WORKBENCH_ICONS = {
    "ClothPattern.svg",
    "ClothSewing.svg",
    "ClothSimulation.svg",
}


def test_command_icons_are_distinct() -> None:
    """Every command icon must have unique SVG artwork."""
    hashes: dict[str, list[str]] = {}

    for path in sorted(ICONS_DIR.glob("Cloth*.svg")):
        if path.name in WORKBENCH_ICONS:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.setdefault(digest, []).append(path.name)

    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    assert not duplicates, "Duplicate command icon artwork: " + "; ".join(
        ", ".join(paths) for paths in duplicates
    )
