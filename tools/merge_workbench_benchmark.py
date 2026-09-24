#!/usr/bin/env python3
"""Merge per-workbench benchmark JSON files into one reviewable artifact."""
from __future__ import annotations

import json
import pathlib
import sys


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    names = ["Pattern", "Sewing", "Simulation"]
    data = [
        json.loads((root / f"{name}.json").read_text(encoding="utf-8"))
        for name in names
    ]
    merged = {
        "schema": data[0]["schema"],
        "python": data[0]["python"],
        "freecad_version": data[0]["freecad_version"],
        "repeats": data[0]["repeats"],
        "workbenches": {},
    }
    for item in data:
        merged["workbenches"].update(item["workbenches"])
    (root / "benchmark.json").write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
