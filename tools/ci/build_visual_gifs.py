# Copyright (C) 2026 FreeCAD Cloth contributors
"""Build documentation GIFs with bounded, parallel ImageMagick invocations."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def image_tool() -> str:
    """Locate the ImageMagick executable used to assemble animation frames.

    Raises:
        SystemExit: If neither supported ImageMagick executable is available.

    Returns:
        Executable name or path suitable for subprocess invocation.
    """
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool:
        raise SystemExit("ImageMagick is required on the CI runner")
    return tool


def build(tool: str, frames: list[Path], output: Path, delay: str, timeout: int = 50) -> None:
    """Assemble PNG frames into a non-empty animated GIF.

    Args:
        tool: ImageMagick executable name or path.
        frames: Ordered PNG frame paths to encode.
        output: Destination path for the generated GIF.
        delay: ImageMagick frame delay expressed in its command-line units.
        timeout: Maximum runtime in seconds before the build is terminated.

    Raises:
        SystemExit: If no frames are supplied or the output file is missing or empty.
        subprocess.CalledProcessError: If ImageMagick exits with a non-zero status.
        subprocess.TimeoutExpired: If ImageMagick exceeds the configured time limit.
    """
    if not frames:
        raise SystemExit(f"no frames found for {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [tool, "-delay", delay, "-loop", "0", *map(str, frames), "-colors", "128", str(output)],
        check=True,
        timeout=timeout,
    )
    if not output.is_file() or not output.stat().st_size:
        raise SystemExit(f"GIF was not produced: {output}")


def main() -> int:
    """Build the requested documentation animations from captured frame sets.

    Raises:
        SystemExit: If arguments are invalid, frames are incomplete, or ImageMagick is unavailable.
        subprocess.CalledProcessError: If ImageMagick exits unsuccessfully.
        subprocess.TimeoutExpired: If an image conversion exceeds its timeout.

    Returns:
        Zero after every GIF required by the selected kind has been generated.
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
                if len(frames) != 73:
                    raise SystemExit(f"{directory}: expected 73 frames, got {len(frames)}")
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
