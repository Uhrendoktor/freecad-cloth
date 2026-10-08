"""Validate compact acceptance logs emitted by GUI smoke tests."""

from __future__ import annotations

import argparse
from pathlib import Path

CASES = {
    "sewing": (
        "artifacts/sewing-creation-smoke.log",
        (
            "preview-1to1=passed",
            "commit-1to1=passed",
            "cancel-1to1=passed",
            "selection-count-rejection=passed",
            "preview-mn=passed",
            "commit-mn=passed",
            "preview-free=passed",
            "commit-free=passed",
            "cancel-free=passed",
            "invalid-same-piece-preview=passed",
            "invalid-mn-partition-preview=passed",
            "curved-sampling=passed",
            "curved-mn=passed members=2,2 segments=3 physical-length=proportional",
            "curved-mn-reversal=passed segments=3",
            "correspondence-gui-evidence=passed severity=info",
            "seam-visual-3d=passed",
            "seam-visual-2d=passed top-view=true",
            "curved-mn-save-reload=passed same-endpoint-pairs=true",
            "stale-endpoint-invalidation=passed commit-blocked=true",
        ),
    ),
    "avatar-pose": (
        "artifacts/avatar-pose-ui.log",
        (
            "avatar-pose-ui=passed",
            "avatar-pose-ui-cancel=passed restored=true cleanup=true",
        ),
    ),
    "fitting": (
        "artifacts/interactive-arrange.log",
        (
            "interactive-arrange=passed snapped=true persisted=true",
            "interactive-arrange-cleanup=passed callbacks-removed=true",
        ),
    ),
    "sketcher": (
        "artifacts/sketcher-acceptance.log",
        ("native Sketcher acceptance passed",),
    ),
    "pattern-export": (
        "artifacts/pattern-production-export.log",
        (
            "pattern-export=passed formats=SVG,DXF",
            "pattern-export-smoke=completed",
        ),
    ),
    "avatar": (
        "artifacts/avatar-acceptance.log",
        ("avatar provider acceptance passed",),
    ),
    "surface-pen": (
        "artifacts/surface-pen.log",
        ("surface-pen-native-smoke=passed",),
    ),
}


def main() -> int:
    """Validate the recorded acceptance evidence and release markers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(CASES))
    args = parser.parse_args()

    log_name, markers = CASES[args.case]
    path = Path(log_name)
    if not path.is_file() or not path.stat().st_size:
        raise SystemExit(f"missing acceptance log: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise SystemExit(f"{args.case} acceptance failed; missing markers: {missing}")
    image = {
        "avatar-pose": Path("artifacts/avatar-pose-mode.png"),
        "fitting": Path("artifacts/interactive-arrange.png"),
    }.get(args.case)
    if image is not None and (not image.is_file() or not image.stat().st_size):
        raise SystemExit(f"missing acceptance screenshot: {image}")
    if args.case == "avatar-pose":
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
            "avatar-pose-screenshot=passed "
            "opaque_pixels=%d nonwhite_pixels=%d distinct_rgb=%d"
            % (
                metrics["opaque_pixels"],
                metrics["nonwhite_pixels"],
                metrics["distinct_rgb"],
            )
        )
    print(f"{args.case}-acceptance=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
