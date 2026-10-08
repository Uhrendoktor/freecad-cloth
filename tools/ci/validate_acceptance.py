"""Validate GUI artifact evidence produced by FreeCAD acceptance tests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = {
    "avatar-pose": Path("artifacts/avatar-pose-mode.png"),
    "fitting": Path("artifacts/interactive-arrange.png"),
}


def main() -> int:
    """Validate a captured GUI artifact without trusting the producer log."""
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(CASES))
    args = parser.parse_args()

    image = CASES[args.case]
    if not image.is_file() or not image.stat().st_size:
        raise SystemExit(f"missing acceptance screenshot: {image}")

    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    metrics = validate_png_capture(
        image,
        expected_width=1280,
        expected_height=720,
        min_nonwhite_pixels=500,
        min_distinct_rgb=16,
        min_opaque_pixels=500,
    )
    print(
        f"{args.case}-screenshot=passed "
        f"opaque_pixels={metrics['opaque_pixels']} "
        f"nonwhite_pixels={metrics['nonwhite_pixels']} "
        f"distinct_rgb={metrics['distinct_rgb']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())