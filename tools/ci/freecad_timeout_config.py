"""Read the authoritative timeout budget used by FreeCAD CI runners."""

from __future__ import annotations

import tomllib
from pathlib import Path


def read_application_timeout(project_file: Path) -> int:
    """Read the positive FreeCAD application timeout from a TOML project file.

    Args:
        project_file: Path to pyproject.toml containing the FreeCAD CI configuration.

    Returns:
        Positive application runtime budget in seconds.

    Raises:
        OSError: If the configuration file cannot be read.
        tomllib.TOMLDecodeError: If the configuration file is invalid TOML.
        ValueError: If the timeout is missing or is not a positive integer.
    """
    data = tomllib.loads(project_file.read_text(encoding="utf-8"))
    value = (
        data.get("tool", {})
        .get("freecad_cloth", {})
        .get("ci", {})
        .get("freecad_application_timeout_seconds")
    )
    if not isinstance(value, int) or value <= 0:
        raise ValueError(
            "[tool.freecad_cloth.ci].freecad_application_timeout_seconds must be a positive integer"
        )
    return value
