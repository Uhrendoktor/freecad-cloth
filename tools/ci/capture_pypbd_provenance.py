# Copyright (C) 2026 FreeCAD Cloth contributors
"""Capture immutable pyPBD provenance from the configured CI image."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from subprocess import run


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
        raise SystemExit("docker executable not found on PATH")

    result = run(
        [docker, "run", "--rm", args.image, "bash", "-lc", "cat /opt/pypbd-provenance.txt"],
        check=True,
        shell=False,
        capture_output=True,
        text=True,
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
