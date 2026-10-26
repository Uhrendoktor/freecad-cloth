# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate GUI artifact evidence produced by FreeCAD acceptance tests."""

from __future__ import annotations

import argparse
import sys
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = {
    "avatar-pose": Path("artifacts/avatar-pose-mode.png"),
    "avatar-shape-editor": Path("artifacts/avatar-shape-editor.png"),
    "fitting": Path("artifacts/interactive-arrange.png"),
    "simulation-quality": Path("artifacts/simulation-quality-readiness.png"),
    "surface-pen": Path("artifacts/surface-pen.png"),
}

REQUIRED_SCREENSHOTS = {
    "simulation-quality": (Path("artifacts/simulation-quality-stale-target.png"),),
}

REQUIRED_FRAMES = {
    "surface-pen": tuple(
        Path(f"artifacts/surface-pen-frame-{index:02d}.png") for index in range(1, 5)
    ),
}

REQUIRED_GIFS = {
    "avatar-shape-editor": (
        Path("artifacts/ui-gifs/avatar-shape-edit.gif"),
        Path("artifacts/ui-gifs/avatar-dimension-drag.gif"),
    ),
    "fitting": (
        Path("artifacts/ui-gifs/arrangement-anchor.gif"),
        Path("artifacts/ui-gifs/interactive-arrange.gif"),
    ),
}

LOG_CASES = {
    "avatar-provider-lifecycle": Path("artifacts/avatar-acceptance-progress.log"),
}

REQUIRED_LOG_MARKERS = {
    "avatar-provider-lifecycle": (
        "start",
        "before-create-avatar",
        "manual-pose-applied",
        "manual-pose-reset",
        "provider-swap-applied",
        "pose-edit-applied",
        "provider-document-reload-state-verified",
        "provider-document-reloaded-and-target-refreshed",
    ),
}


class _VisualCaptureValidationModule(Protocol):
    """Describe the lazily loaded screenshot validator module."""

    validate_png_capture: Callable[..., dict[str, int]]


def _png_capture_validator() -> Callable[..., dict[str, int]]:
    """Load the screenshot decoder only when visual acceptance needs it.

    Returns:
        Callable that validates screenshot dimensions and pixel evidence.
    """
    module = cast(
        "_VisualCaptureValidationModule",
        import_module("freecad_cloth.common.VisualCaptureValidation"),
    )
    return module.validate_png_capture


def _validate_log_case(case: str) -> int:
    """Validate the required progress markers for a log-only acceptance case.

    Args:
        case: Name of the selected log-only case.

    Returns:
        Zero when all progress markers are present.

    Raises:
        SystemExit: If the progress log is absent or required markers are missing.
    """
    log_path = LOG_CASES[case]
    if not log_path.is_file() or not log_path.stat().st_size:
        msg = f"missing acceptance progress log: {log_path}"
        raise SystemExit(msg)
    log_text = log_path.read_text(encoding="utf-8")
    missing = tuple(marker for marker in REQUIRED_LOG_MARKERS[case] if marker not in log_text)
    if missing:
        msg = f"{case}: missing progress markers: {missing}"
        raise SystemExit(msg)
    sys.stdout.write(f"{case}=validated markers={len(REQUIRED_LOG_MARKERS[case])}\n")
    return 0


def _validate_visual_case(case: str) -> int:
    """Validate required visual artifacts without trusting producer logs.

    Args:
        case: Name of the selected screenshot acceptance case.

    Returns:
        Zero when every required screenshot, frame, and animation is valid.

    Raises:
        SystemExit: If required images/GIFs are missing or fail visual quality validation.
    """
    image = CASES[case]
    if not image.is_file() or not image.stat().st_size:
        msg = f"missing acceptance screenshot: {image}"
        raise SystemExit(msg)
    validate_png_capture = _png_capture_validator()
    metrics = validate_png_capture(
        image,
        expected_width=1280,
        expected_height=720,
        min_nonwhite_pixels=500,
        min_distinct_rgb=16,
        min_opaque_pixels=500,
    )
    for gif in REQUIRED_GIFS.get(case, ()):
        if not gif.is_file() or not gif.stat().st_size:
            msg = f"missing acceptance GIF: {gif}"
            raise SystemExit(msg)
        sys.stdout.write(f"{case}-gif=validated path={gif} bytes={gif.stat().st_size}\n")
    for frame in REQUIRED_FRAMES.get(case, ()):
        if not frame.is_file() or not frame.stat().st_size:
            msg = f"missing acceptance animation frame: {frame}"
            raise SystemExit(msg)
        frame_metrics = validate_png_capture(
            frame,
            expected_width=1280,
            expected_height=720,
            min_nonwhite_pixels=500,
            min_distinct_rgb=16,
            min_opaque_pixels=500,
        )
        sys.stdout.write(
            f"{case}-frame=validated path={frame} "
            f"nonwhite_pixels={frame_metrics['nonwhite_pixels']}\n"
        )
    for screenshot in REQUIRED_SCREENSHOTS.get(case, ()):
        if not screenshot.is_file() or not screenshot.stat().st_size:
            msg = f"missing acceptance state screenshot: {screenshot}"
            raise SystemExit(msg)
        validate_png_capture(
            screenshot,
            expected_width=1280,
            expected_height=720,
            min_nonwhite_pixels=500,
            min_distinct_rgb=16,
            min_opaque_pixels=500,
        )
    sys.stdout.write(
        f"{case}-screenshot=validated "
        f"opaque_pixels={metrics['opaque_pixels']} "
        f"nonwhite_pixels={metrics['nonwhite_pixels']} "
        f"distinct_rgb={metrics['distinct_rgb']}\n"
    )
    return 0


def main() -> int:
    """Validate a captured GUI artifact without trusting the producer log.

    Returns:
        Process status indicating whether the selected acceptance evidence is valid.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted((*CASES, *LOG_CASES)))
    args = parser.parse_args()
    if args.case in LOG_CASES:
        return _validate_log_case(args.case)
    return _validate_visual_case(args.case)


if __name__ == "__main__":
    raise SystemExit(main())
