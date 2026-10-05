"""Build documentation GIFs with bounded, parallel ImageMagick invocations."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def image_tool() -> str:
    """Return the available ImageMagick executable."""
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool:
        raise SystemExit("ImageMagick is required on the CI runner")
    return tool


def build(tool: str, frames: list[Path], output: Path, delay: str, timeout: int = 50) -> None:
    """Build a GIF from a sequence of PNG frames."""
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
    """Build the requested repository visual GIF set."""
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
            root / "blanket-example/blanket-motion.gif",
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
