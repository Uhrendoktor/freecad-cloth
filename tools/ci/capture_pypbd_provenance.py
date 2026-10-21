# Copyright (C) 2026 FreeCAD Cloth contributors
"""Capture immutable pyPBD provenance from the configured CI image."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    """Capture and validate the PBD provenance record.

    Raises:
        SystemExit: When the container returns an empty provenance record.

    Returns:
        Process status indicating whether provenance was captured successfully.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    result = subprocess.run(
        ["docker", "run", "--rm", args.image, "bash", "-lc", "cat /opt/pypbd-provenance.txt"],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.stdout, encoding="utf-8")
    if not args.output.stat().st_size:
        msg = f"empty provenance file: {args.output}"
        raise SystemExit(msg)
    print(f"pypbd-provenance=captured image={args.image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
