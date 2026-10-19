# Copyright (C) 2026 FreeCAD Cloth contributors
"""Build documentation GIFs with bounded, parallel ImageMagick invocations."""

from __future__ import annotations

import argparse
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

TURNTABLE_FRAME_COUNT = 73


def image_tool() -> str:
    """Locate the ImageMagick executable used to assemble animation frames.

    Returns:
        Executable path suitable for subprocess invocation.

    Raises:
        SystemExit: If neither supported ImageMagick executable is available.
    """
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool:
        msg = "ImageMagick is required on the CI runner"
        raise SystemExit(msg)
    return tool


def build(tool: str, frames: list[Path], output: Path, delay: str, timeout: int = 50) -> None:
    """Assemble PNG frames into a non-empty animated GIF.

    Args:
        tool: ImageMagick executable path.
        frames: Ordered PNG frame paths to encode.
        output: Destination path for the generated GIF.
        delay: ImageMagick frame delay expressed in its command-line units.
        timeout: Maximum runtime in seconds before the build is terminated.

    Raises:
        SystemExit: If no frames are supplied or the output file is missing or empty.
    """
    if not frames:
        msg = f"no frames found for {output}"
        raise SystemExit(msg)
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            tool,
            "-delay",
            delay,
            "-loop",
            "0",
            *map(str, frames),
            "-colors",
            "128",
            str(output),
        ],
        check=True,
        shell=False,
        timeout=timeout,
    )
    if not output.is_file() or not output.stat().st_size:
        msg = f"GIF was not produced: {output}"
        raise SystemExit(msg)


def main() -> int:
    """Build the requested documentation animations from captured frame sets.

    Returns:
        Zero after every GIF required by the selected kind has been generated.

    Raises:
        SystemExit: If arguments are invalid, frames are incomplete, or ImageMagick is unavailable.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("turntables", "blanket", "tunic"))
    args = parser.parse_args()
    tool = image_tool()
    root = Path("docs/images/generated")

    if args.kind == "turntables":
        specs = (
            ("cloth-avatar-turntable-frames", "cloth-avatar-turntable.gif"),
            (
                "cloth-simulation-arranged-turntable-frames",
                "cloth-simulation-arranged-turntable.gif",
            ),
            ("cloth-simulation-draped-turntable-frames", "cloth-simulation-draped-turntable.gif"),
        )
        jobs = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for directory, output in specs:
                frames = sorted((root / directory).glob("frame-*.png"))
                if len(frames) != TURNTABLE_FRAME_COUNT:
                    msg = (
                        f"{directory}: expected {TURNTABLE_FRAME_COUNT} frames, "
                        f"got {len(frames)}"
                    )
                    raise SystemExit(msg)
                jobs.append(pool.submit(build, tool, frames, root / output, "8"))
            for job in as_completed(jobs):
                job.result()
        return 0

    if args.kind == "blanket":
        build(
            tool,
            sorted((root / "blanket-example").glob("motion-*.png")),
            root / "blanket-example/cloth-blanket-motion.gif",
            "10",
        )
        return 0

    build(
        tool,
        sorted((root / "cloth-tunic-mannequin-motion-frames").glob("motion-*.png")),
        root / "cloth-tunic-mannequin-motion.gif",
        "10",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
