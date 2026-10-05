"""Build documentation GIFs with a bounded ImageMagick invocation."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def image_tool() -> str:
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool:
        raise SystemExit("ImageMagick is required on the CI runner")
    return tool


def build(tool: str, frames: list[Path], output: Path, delay: str) -> None:
    if not frames:
        raise SystemExit(f"no frames found for {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [tool, "-delay", delay, "-loop", "0", *map(str, frames), "-colors", "128", str(output)],
        check=True,
        timeout=60,
    )
    if not output.is_file() or not output.stat().st_size:
        raise SystemExit(f"GIF was not produced: {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("turntables", "blanket", "tunic"))
    args = parser.parse_args()
    tool = image_tool()

    if args.kind == "turntables":
        root = Path("docs/images/generated")
        for directory, output in (
            ("cloth-avatar-turntable-frames", "cloth-avatar-turntable.gif"),
            ("cloth-simulation-arranged-turntable-frames", "cloth-simulation-arranged-turntable.gif"),
            ("cloth-simulation-draped-turntable-frames", "cloth-simulation-draped-turntable.gif"),
        ):
            frames = sorted((root / directory).glob("frame-*.png"))
            if len(frames) != 73:
                raise SystemExit(f"{directory}: expected 73 frames, got {len(frames)}")
            build(tool, frames, root / output, "8")
        return 0

    if args.kind == "blanket":
        root = Path("docs/images/generated/blanket-example")
        build(tool, sorted(root.glob("motion-*.png")), root / "blanket-motion.gif", "10")
        return 0

    root = Path("docs/images/generated/cloth-tunic-mannequin-motion-frames")
    build(
        tool,
        sorted(root.glob("motion-*.png")),
        Path("docs/images/generated/cloth-tunic-mannequin-motion.gif"),
        "10",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
