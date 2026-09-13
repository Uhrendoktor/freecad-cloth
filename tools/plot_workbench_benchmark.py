#!/usr/bin/env python3
"""Render benchmark JSON into small, reviewable PNG plots."""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib.pyplot as plt


def plot_metric(names, values, title, ylabel, out):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def main() -> None:
    src = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    data = json.loads(src.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    names = list(data["workbenches"])
    wb = data["workbenches"]
    plot_metric(names, [wb[n]["nonblank_loc"] for n in names], "Workbench implementation size", "Non-blank Python lines", out / "implementation-size.png")
    plot_metric(names, [wb[n]["related_test_files"] for n in names], "Workbench test coverage surface", "Related test files", out / "test-surface.png")
    plot_metric(names, [wb[n]["registered_commands"] for n in names], "Registered command surface", "Commands", out / "command-surface.png")
    plot_metric(names, [wb[n]["initialize_ms"] for n in names], "Workbench initialization cost", "Median milliseconds", out / "initialize-time.png")


if __name__ == "__main__":
    main()
