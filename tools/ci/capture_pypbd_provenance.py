# Copyright (C) 2026 FreeCAD Cloth contributors
"""Capture immutable pyPBD provenance from the configured CI image."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if __package__:
    from tools.ci.command_runner import run_command
else:
    from command_runner import run_command


def main() -> int:
    """Capture and validate the PBD provenance record.

    Returns:
        Process status indicating whether provenance was captured successfully.

    Raises:
        SystemExit: If Docker is unavailable or the container returns an empty provenance record.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    docker = shutil.which("docker")
    if docker is None:
        msg = "docker executable not found on PATH"
        raise SystemExit(msg)

    result = run_command(
        [docker, "run", "--rm", args.image, "bash", "-lc", "cat /opt/pypbd-provenance.txt"],
        check=True,
        capture_output=True,
        timeout=20,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.stdout, encoding="utf-8")
    if not args.output.stat().st_size:
        msg = f"empty provenance file: {args.output}"
        raise SystemExit(msg)
    sys.stdout.write(f"pypbd-provenance=captured image={args.image}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
