# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate canonical simulation and visual evidence manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from math import ceil, isclose
from pathlib import Path

ROOT = Path("artifacts/simulation-ladder")
CHECKPOINTS = [0, 1, 5, 15, 45, 90]


def read(path: Path) -> dict:
    """Read a required JSON manifest from disk.

    Args:
        path: Filesystem location of the JSON manifest.

    Returns:
        Decoded manifest contents as a dictionary.

    Raises:
        SystemExit: Raised when the manifest file is missing or empty.
    """
    if not path.is_file() or not path.stat().st_size:
        msg = f"missing manifest: {path}"
        raise SystemExit(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_simulation() -> None:
    """Validate the canonical simulation collision manifests.

    Raises:
        SystemExit: Raised when a collision manifest violates its release contract.
    """
    specs = (
        ("cube", ROOT / "cube-ladder-manifest.json", 5, 3.0, "simulation-collision-ladder"),
        ("avatar", ROOT / "avatar-ladder-manifest.json", 5, 8.0, "simulation-avatar-ladder"),
    )
    for name, path, count, max_penetration, purpose in specs:
        data = read(path)
        if data.get("schema") != 1 or data.get("purpose") != purpose:
            msg = f"{name}: invalid manifest header"
            raise SystemExit(msg)
        if data.get("release_gate_effect") != "gate":
            msg = f"{name}: not a release gate"
            raise SystemExit(msg)
        if len(data.get("cases", ())) != count:
            msg = f"{name}: unexpected case count"
            raise SystemExit(msg)
        for case in data["cases"]:
            if not case.get("finite"):
                msg = f"{name}: non-finite case"
                raise SystemExit(msg)
            if case.get("solver", {}).get("backend") != "pbd":
                msg = f"{name}: wrong backend"
                raise SystemExit(msg)
            if len(case.get("checkpoints", ())) != 6:
                msg = f"{name}: unexpected checkpoint count"
                raise SystemExit(msg)
            if case.get("max_penetration_mm", 0) > max_penetration + 1e-6:
                msg = f"{name}: penetration too large"
                raise SystemExit(msg)
            for image in case.get("images", ()):
                if not (ROOT / image).is_file():
                    msg = f"{name}: missing image {image}"
                    raise SystemExit(msg)
        if data.get("structural_validation", {}).get("first_failing_rung") is not None:
            msg = f"{name}: structural rung failed"
            raise SystemExit(msg)
        print(f"{name}-collision-ladder=passed")


def validate_turntables() -> None:
    """Validate the canonical avatar and simulation turntable evidence.

    Raises:
        SystemExit: Raised when frame counts or uniqueness checks fail.
    """
    root = Path("docs/images/generated")
    directories = (
        "cloth-avatar-turntable-frames",
        "cloth-simulation-arranged-turntable-frames",
        "cloth-simulation-draped-turntable-frames",
    )
    for directory in directories:
        frames = sorted((root / directory).glob("frame-*.png"))
        if len(frames) != 73:
            msg = f"{directory}: expected 73 frames, got {len(frames)}"
            raise SystemExit(msg)
        hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in frames}
        if len(hashes) != 73:
            msg = f"{directory}: duplicate frame hashes"
            raise SystemExit(msg)
        checkpoints = []
        for frame in (0, 18, 36, 54):
            path = root / directory / f"frame-{frame:03d}.png"
            if not path.is_file():
                msg = f"{directory}: missing checkpoint {frame}"
                raise SystemExit(msg)
            checkpoints.append(hashlib.sha256(path.read_bytes()).hexdigest())
        if len(set(checkpoints)) != 4:
            msg = f"{directory}: camera checkpoints are not distinct"
            raise SystemExit(msg)

    log = root / "simulation-turntable-progress.log"
    text = log.read_text(encoding="utf-8")
    for marker in (
        "stage=scene-build-pass",
        "stage=arranged-render-pass",
        "stage=simulation-pass",
        "stage=validation-pass",
        "stage=draped-render-pass",
        "stage=total-pass",
        "blanket-turntable-pass",
        "mesh-quality=passed",
    ):
        if marker not in text:
            msg = f"turntable: missing marker {marker}"
            raise SystemExit(msg)
    displacement = re.findall(
        r"blanket-motion-diagnostic max_centroid_displacement_mm=([+-]?[0-9.]+)",
        text,
    )
    if not displacement or float(displacement[-1]) < 40.0:
        msg = "turntable: insufficient blanket displacement"
        raise SystemExit(msg)
    penetration = re.findall(
        r"collision-penetration=passed max_penetration_mm=([+-]?[0-9.]+)",
        text,
    )
    if not penetration or float(penetration[-1]) > 3.0:
        msg = "turntable: collision penetration gate failed"
        raise SystemExit(msg)
    print("turntables=passed")


def _validate_realtime_metrics(data: dict) -> None:
    """Validate either legacy or schema-versioned realtime metrics without weakening gates.

    Args:
        data: Parsed JSON metrics used to verify the realtime performance contract.

    Raises:
        SystemExit: Raised when runtime metrics violate the schema or timing budget.
    """
    if "schema_version" not in data:
        # Retain the existing contract for historical metric artifacts.
        if (
            not data["finite"]
            or data["mean_frame_ms"] > data["frame_budget_ms"]
            or data["p95_frame_ms"] > 50.0
        ):
            msg = f"tunic: realtime performance gate failed: {data}"
            raise SystemExit(msg)
        return

    budget = data.get("frame_budget_ms")
    mean_interval = data.get("mean_frame_interval_ms")
    p95_interval = data.get("p95_frame_interval_ms")
    numeric_values = (budget, mean_interval, p95_interval)
    if (
        data.get("schema_version") != 1
        or data.get("backend") != "position-based-dynamics"
        or data.get("fixture") != "two-panel-tunic-pattern"
        or data.get("backend_finite") is not True
        or data.get("published_state_finite") is not True
        or data.get("timed_out") is not False
        or not isinstance(data.get("measured_intervals"), int)
        or data["measured_intervals"] < 120
        or not isinstance(data.get("warmup_frames_requested"), int)
        or data["warmup_frames_requested"] < 30
        or data.get("observed_ticks") != data.get("expected_ticks")
        or data.get("frames_advanced") != data.get("observed_ticks")
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in numeric_values
        )
        or mean_interval > budget
        or p95_interval > budget
    ):
        msg = f"tunic: realtime performance gate failed: {data}"
        raise SystemExit(msg)


def _validate_tunic(require_canonical_e2e: bool) -> None:
    """Validate tunic evidence produced by either the canonical or production audit.

    Args:
        require_canonical_e2e: Whether to require canonical garment end-to-end evidence.

    Raises:
        SystemExit: Raised when required images, logs, metrics, or collision settings are invalid.
    """
    generated = Path("docs/images/generated")
    progress = generated / "gui-progress.log"
    metrics = Path("artifacts/freecad-realtime/metrics.json")
    if not progress.is_file() or not metrics.is_file():
        msg = "tunic: required evidence is missing"
        raise SystemExit(msg)
    data = json.loads(metrics.read_text(encoding="utf-8"))
    _validate_realtime_metrics(data)
    text = progress.read_text(encoding="utf-8")
    markers = (
        "scenario-pass",
        "tunic-collision-config target-thickness-mm=",
        "realtime-preview=passed backend=position-based-dynamics",
        "drape-metrics=",
        "diagnostic-map=passed metric=stress",
        "diagnostic-stale-guard=passed",
    )
    if any(marker not in text for marker in markers):
        msg = "tunic: progress contract failed"
        raise SystemExit(msg)

    collision = re.search(
        r"tunic-collision-config target-thickness-mm=([0-9.]+) "
        r"voxel-mm=([0-9.]+) configured-tolerance-mm=([0-9.]+) "
        r"effective-tolerance-mm=([0-9.]+) "
        r"sdf-resolution=(\d+)x(\d+)x(\d+) "
        r"span-mm=([0-9.]+)x([0-9.]+)x([0-9.]+)",
        text,
    )
    if collision is None:
        msg = "tunic: runtime collision configuration evidence is invalid"
        raise SystemExit(msg)
    thickness_mm, voxel_mm, configured_tolerance_mm, effective_tolerance_mm = (
        float(value) for value in collision.groups()[:4]
    )
    sdf_resolution = tuple(int(value) for value in collision.groups()[4:7])
    surface_spans_mm = tuple(float(value) for value in collision.groups()[7:10])
    if not isclose(thickness_mm, 5.0, abs_tol=1e-6):
        msg = f"tunic: mannequin collision thickness must be 5 mm, got {thickness_mm}"
        raise SystemExit(msg)
    if not isclose(voxel_mm, 8.0, abs_tol=1e-6):
        msg = f"tunic: PBD SDF voxel must be 8 mm, got {voxel_mm}"
        raise SystemExit(msg)
    if not isclose(configured_tolerance_mm, 2.0, abs_tol=1e-6):
        msg = f"tunic: configured collision tolerance must be 2 mm, got {configured_tolerance_mm}"
        raise SystemExit(msg)
    expected_tolerance_mm = max(configured_tolerance_mm, thickness_mm, 0.5 * voxel_mm)
    if not isclose(effective_tolerance_mm, expected_tolerance_mm, abs_tol=1e-6):
        msg = "tunic: effective collision tolerance does not match its inputs"
        raise SystemExit(msg)
    expected_resolution = tuple(
        max(16, min(256, int(ceil((span + 200.0) / voxel_mm)))) for span in surface_spans_mm
    )
    if sdf_resolution != expected_resolution:
        msg = (
            "tunic: runtime SDF resolution does not match its configured voxel size: "
            f"actual={sdf_resolution} expected={expected_resolution}"
        )
        raise SystemExit(msg)

    required_images = (
        generated / "cloth-simulation-draped.png",
        generated / "cloth-simulation-draped-front.png",
        generated / "cloth-simulation-draped-rear.png",
        generated / "cloth-simulation-draped-left.png",
        generated / "cloth-simulation-draped-right.png",
        generated / "cloth-simulation-draped-top.png",
        generated / "cloth-simulation-draped-bottom.png",
        generated / "cloth-simulation-draped-diagnostics.png",
    )
    if require_canonical_e2e:
        required_images += (
            generated / "cloth-pattern-design.png",
            generated / "cloth-sewing.png",
        )
    for path in required_images:
        if not path.is_file() or not path.stat().st_size:
            msg = f"tunic: missing image {path}"
            raise SystemExit(msg)

    if len(list((generated / "cloth-tunic-mannequin-motion-frames").glob("motion-*.png"))) != 10:
        msg = "tunic: wrong mannequin motion frame count"
        raise SystemExit(msg)

    if require_canonical_e2e:
        e2e = Path("artifacts/garment-e2e.log").read_text(encoding="utf-8")
        for marker in (
            "staged-selection=passed",
            "sewing-mn=passed sides=2,2 segments=2",
            "sewing-mn-physical=passed curved-edge=true proportional=true",
            "seam-markers=passed 3d-and-2d=true",
            "arrangement=passed pieces=4",
            "garment-hierarchy=passed groups=Patterns,Sewing,Fabric,Avatar,Simulation",
            "material-presentation=passed native=true",
            "drape-target=passed type=Mannequin",
            "diagnostics=passed metric=stress",
            "save-reload=passed pieces=4 seam=1to1 network=2segment",
            "invalidation=passed seam=",
            "invalidation-restore=passed seam=Valid",
            "stale-export=blocked",
            "diagnostics-after-invalidation=passed metric=stress",
            "determinism-signature=passed",
            "pattern-export=passed formats=SVG,DXF",
            "canonical garment end-to-end acceptance passed",
        ):
            if marker not in e2e:
                msg = f"tunic: missing E2E marker {marker}"
                raise SystemExit(msg)
    print("tunic-visual=passed")


def validate_tunic() -> None:
    """Validate the strict canonical tunic evidence."""
    _validate_tunic(require_canonical_e2e=True)


def validate_tunic_production() -> None:
    """Validate the production tunic evidence without canonical garment E2E artifacts."""
    _validate_tunic(require_canonical_e2e=False)


def validate_blanket() -> None:
    """Validate the canonical blanket visual evidence.

    Raises:
        SystemExit: Raised when required blanket evidence or markers are absent.
    """
    root = Path("docs/images/generated/blanket-example")
    log = root / "blanket-visual.log"
    if not log.is_file():
        msg = "blanket: missing log"
        raise SystemExit(msg)
    text = log.read_text(encoding="utf-8")
    for marker in (
        "blanket-visual-acceptance=passed",
        "mesh=passed",
        "movement=passed",
        "material-presentation=passed viewport=true",
    ):
        if marker not in text:
            msg = f"blanket: missing marker {marker}"
            raise SystemExit(msg)
    if len(list(root.glob("checkpoint-*.png"))) != 5:
        msg = "blanket: expected 5 checkpoints"
        raise SystemExit(msg)
    if len(list(root.glob("motion-*.png"))) != 16:
        msg = "blanket: expected 16 motion frames"
        raise SystemExit(msg)
    print("blanket-visual=passed")


def validate_diagnostic() -> None:
    """Validate the canonical diagnostic PBD evidence.

    Raises:
        SystemExit: Raised when diagnostic collision manifests are invalid.
    """
    root = Path("artifacts/pbd-contact-diagnostics")
    for name, purpose, rung in (
        ("cube-ladder-manifest.json", "simulation-collision-ladder", range(1, 6)),
        ("avatar-ladder-manifest.json", "simulation-avatar-ladder", range(6, 11)),
    ):
        data = read(root / name)
        if data.get("schema") != 1 or data.get("purpose") != purpose:
            msg = f"diagnostic {name}: invalid header"
            raise SystemExit(msg)
        if data.get("release_gate_effect") != "gate":
            msg = f"diagnostic {name}: wrong gate effect"
            raise SystemExit(msg)
        if len(data.get("cases", ())) != 5:
            msg = f"diagnostic {name}: wrong case count"
            raise SystemExit(msg)
        for record, expected_rung in zip(data["cases"], rung, strict=True):
            if record.get("case", {}).get("rung") != expected_rung:
                msg = f"diagnostic {name}: unexpected rung"
                raise SystemExit(msg)
            if record.get("solver", {}).get("backend") != "pbd":
                msg = f"diagnostic {name}: wrong backend"
                raise SystemExit(msg)
            if record.get("solver", {}).get("substeps") != 1:
                msg = f"diagnostic {name}: wrong substeps"
                raise SystemExit(msg)
            if len(record.get("checkpoints", ())) != 6:
                msg = f"diagnostic {name}: wrong checkpoints"
                raise SystemExit(msg)
            for image in record.get("images", ()):
                candidate = root / ("cube-ladder" if "rung-" in image and "cube" in image else "")
                if not (root / image).is_file() and not candidate.is_file():
                    msg = f"diagnostic {name}: missing image {image}"
                    raise SystemExit(msg)
    data = read(root / "manifest.json")
    if data.get("schema") != 1 or data.get("release_gate_effect") != "none":
        msg = "diagnostic contact manifest header failed"
        raise SystemExit(msg)
    print("diagnostic-contact=passed")


def main() -> int:
    """Validate the requested canonical manifests and visual evidence.

    Returns:
        Process status indicating whether the selected evidence is valid.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "kind",
        choices=("simulation", "turntables", "tunic", "tunic-production", "blanket", "diagnostic"),
    )
    args = parser.parse_args()
    {
        "simulation": validate_simulation,
        "turntables": validate_turntables,
        "tunic": validate_tunic,
        "tunic-production": validate_tunic_production,
        "blanket": validate_blanket,
        "diagnostic": validate_diagnostic,
    }[args.kind]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
