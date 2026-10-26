# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate canonical simulation and visual evidence manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from math import ceil, isclose
from pathlib import Path
from typing import NoReturn

ROOT = Path("artifacts/simulation-ladder")
CHECKPOINTS = (0, 1, 5, 15, 45, 90)
CHECKPOINT_COUNT = len(CHECKPOINTS)
TURNTABLE_FRAME_COUNT = 73
TURNTABLE_CHECKPOINT_FRAMES = (0, 18, 36, 54)
TURNTABLE_CHECKPOINT_COUNT = len(TURNTABLE_CHECKPOINT_FRAMES)
MIN_BLANKET_DISPLACEMENT_MM = 40.0
MAX_TURNTABLE_PENETRATION_MM = 3.0
LEGACY_MAX_P95_FRAME_MS = 50.0
MIN_MEASURED_INTERVALS = 120
MIN_WARMUP_FRAMES = 30
MANNEQUIN_MOTION_FRAME_COUNT = 10
BLANKET_CHECKPOINT_COUNT = 5
BLANKET_MOTION_FRAME_COUNT = 16
DIAGNOSTIC_CASE_COUNT = 5
MIN_SDF_RESOLUTION = 16
MAX_SDF_RESOLUTION = 256
SDF_PADDING_MM = 200.0

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

def _validate_simulation_case(name: str, case: dict, max_penetration: float) -> None:
    """Validate one simulation collision-ladder case against its release contract.

    Args:
        name: Human-readable simulation family used in failure diagnostics.
        case: Parsed case object from the collision manifest.
        max_penetration: Maximum accepted collision penetration in millimetres.

    Raises:
        SystemExit: If the case uses invalid solver settings or fails a release check.
    """
    if not case.get("finite"):
        msg = f"{name}: non-finite case"
        raise SystemExit(msg)
    if case.get("solver", {}).get("backend") != "pbd":
        msg = f"{name}: wrong backend"
        raise SystemExit(msg)
    if len(case.get("checkpoints", ())) != CHECKPOINT_COUNT:
        msg = f"{name}: unexpected checkpoint count"
        raise SystemExit(msg)
    if case.get("max_penetration_mm", 0) > max_penetration + 1e-6:
        msg = f"{name}: penetration too large"
        raise SystemExit(msg)
    for image in case.get("images", ()):
        if not (ROOT / image).is_file():
            msg = f"{name}: missing image {image}"
            raise SystemExit(msg)

def _validate_simulation_manifest(
    name: str,
    path: Path,
    expected_case_count: int,
    max_penetration: float,
    purpose: str,
) -> None:
    """Validate a complete simulation manifest and its structural diagnostics.

    Args:
        name: Human-readable simulation family used in failure diagnostics.
        path: Location of the manifest JSON file.
        expected_case_count: Number of scenarios required by the acceptance contract.
        max_penetration: Maximum accepted penetration in millimetres.
        purpose: Required manifest purpose string.

    Raises:
        SystemExit: If the header, case count, collision results, or structural audit is invalid.
    """
    data = read(path)
    if data.get("schema") != 1 or data.get("purpose") != purpose:
        msg = f"{name}: invalid manifest header"
        raise SystemExit(msg)
    if data.get("release_gate_effect") != "gate":
        msg = f"{name}: not a release gate"
        raise SystemExit(msg)
    if len(data.get("cases", ())) != expected_case_count:
        msg = f"{name}: unexpected case count"
        raise SystemExit(msg)
    for case in data["cases"]:
        _validate_simulation_case(name, case, max_penetration)
    if data.get("structural_validation", {}).get("first_failing_rung") is not None:
        msg = f"{name}: structural rung failed"
        raise SystemExit(msg)

def validate_simulation() -> None:
    """Validate the canonical simulation collision manifests."""
    specs = (
        ("cube", ROOT / "cube-ladder-manifest.json", 5, 3.0, "simulation-collision-ladder"),
        ("avatar", ROOT / "avatar-ladder-manifest.json", 5, 8.0, "simulation-avatar-ladder"),
    )
    for name, path, count, max_penetration, purpose in specs:
        _validate_simulation_manifest(name, path, count, max_penetration, purpose)
        sys.stdout.write(f"{name}-collision-ladder=passed\n")

def _validate_turntable_frames(root: Path, directory: str) -> None:
    """Validate frame counts, image uniqueness, and camera checkpoints for one turntable.

    Args:
        root: Root directory containing generated turntable images.
        directory: Relative directory name for one turntable.

    Raises:
        SystemExit: If frames are missing, duplicated, or have indistinguishable checkpoints.
    """
    frames = sorted((root / directory).glob("frame-*.png"))
    if len(frames) != TURNTABLE_FRAME_COUNT:
        msg = f"{directory}: expected {TURNTABLE_FRAME_COUNT} frames, got {len(frames)}"
        raise SystemExit(msg)
    hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in frames}
    if len(hashes) != TURNTABLE_FRAME_COUNT:
        msg = f"{directory}: duplicate frame hashes"
        raise SystemExit(msg)
    checkpoint_hashes = []
    for frame in TURNTABLE_CHECKPOINT_FRAMES:
        path = root / directory / f"frame-{frame:03d}.png"
        if not path.is_file():
            msg = f"{directory}: missing checkpoint {frame}"
            raise SystemExit(msg)
        checkpoint_hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    if len(set(checkpoint_hashes)) != TURNTABLE_CHECKPOINT_COUNT:
        msg = f"{directory}: camera checkpoints are not distinct"
        raise SystemExit(msg)

def _validate_turntable_progress(root: Path) -> None:
    """Check simulation progress markers and the authoritative motion/penetration limits.

    Args:
        root: Directory containing generated simulation turntable evidence.

    Raises:
        SystemExit: If required stage markers, blanket movement, or penetration limits fail.
    """
    log = root / "simulation-turntable-progress.log"
    text = log.read_text(encoding="utf-8")
    markers = (
        "stage=scene-build-pass",
        "stage=arranged-render-pass",
        "stage=simulation-pass",
        "stage=validation-pass",
        "stage=draped-render-pass",
        "stage=total-pass",
        "blanket-turntable-pass",
        "mesh-quality=passed",
    )
    for marker in markers:
        if marker not in text:
            msg = f"turntable: missing marker {marker}"
            raise SystemExit(msg)
    displacement = re.findall(
        r"blanket-motion-diagnostic max_centroid_displacement_mm=([+-]?[0-9.]+)",
        text,
    )
    if not displacement or float(displacement[-1]) < MIN_BLANKET_DISPLACEMENT_MM:
        msg = "turntable: insufficient blanket displacement"
        raise SystemExit(msg)
    penetration = re.findall(
        r"collision-penetration=passed max_penetration_mm=([+-]?[0-9.]+)",
        text,
    )
    if not penetration or float(penetration[-1]) > MAX_TURNTABLE_PENETRATION_MM:
        msg = "turntable: collision penetration gate failed"
        raise SystemExit(msg)

def validate_turntables() -> None:
    """Validate the canonical avatar and simulation turntable evidence."""
    root = Path("docs/images/generated")
    directories = (
        "cloth-avatar-turntable-frames",
        "cloth-simulation-arranged-turntable-frames",
        "cloth-simulation-draped-turntable-frames",
    )
    for directory in directories:
        _validate_turntable_frames(root, directory)
    _validate_turntable_progress(root)
    sys.stdout.write("turntables=passed\n")

def _realtime_failure(data: dict) -> NoReturn:
    """Stop validation with the canonical realtime metric failure message.

    Args:
        data: Parsed metric payload being checked.

    Raises:
        SystemExit: Always, to reject metric evidence that violates its contract.
    """
    msg = f"tunic: realtime performance gate failed: {data}"
    raise SystemExit(msg)

def _validate_versioned_realtime_metadata(data: dict) -> None:
    """Validate schema and non-timing metadata for versioned realtime metrics.

    Args:
        data: Parsed schema-versioned realtime metrics.

    """
    if (
        data.get("schema_version") != 1
        or data.get("backend") != "position-based-dynamics"
        or data.get("fixture") != "two-panel-tunic-pattern"
    ):
        _realtime_failure(data)
    if data.get("backend_finite") is not True or data.get("published_state_finite") is not True:
        _realtime_failure(data)
    if data.get("timed_out") is not False:
        _realtime_failure(data)
    measured_intervals = data.get("measured_intervals")
    if not isinstance(measured_intervals, int) or measured_intervals < MIN_MEASURED_INTERVALS:
        _realtime_failure(data)
    warmup_frames = data.get("warmup_frames_requested")
    if not isinstance(warmup_frames, int) or warmup_frames < MIN_WARMUP_FRAMES:
        _realtime_failure(data)
    if data.get("observed_ticks") != data.get("expected_ticks"):
        _realtime_failure(data)
    if data.get("frames_advanced") != data.get("observed_ticks"):
        _realtime_failure(data)

def _finite_realtime_metric(data: dict, name: str) -> float:
    """Read one finite non-boolean numeric metric from a JSON payload.

    Args:
        data: Parsed realtime metrics.
        name: Required metric key to validate.

    Returns:
        The metric as a finite float.

    """
    value = data.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        _realtime_failure(data)
    return float(value)

def _validate_realtime_metrics(data: dict) -> None:
    """Validate either legacy or schema-versioned realtime metrics without weakening gates.

    Args:
        data: Parsed JSON metrics used to verify the realtime performance contract.

    """
    if "schema_version" not in data:
        # Retain the existing contract for historical metric artifacts.
        if (
            not data["finite"]
            or data["mean_frame_ms"] > data["frame_budget_ms"]
            or data["p95_frame_ms"] > LEGACY_MAX_P95_FRAME_MS
        ):
            _realtime_failure(data)
        return

    _validate_versioned_realtime_metadata(data)
    budget = _finite_realtime_metric(data, "frame_budget_ms")
    mean_interval = _finite_realtime_metric(data, "mean_frame_interval_ms")
    p95_interval = _finite_realtime_metric(data, "p95_frame_interval_ms")
    if mean_interval > budget or p95_interval > budget:
        _realtime_failure(data)

def _validate_tunic_collision_configuration(text: str) -> None:
    """Validate the mannequin thickness and signed-distance-field collision configuration.

    Args:
        text: Canonical GUI progress log containing runtime collision measurements.

    Raises:
        SystemExit: If any reported collision setting is invalid or inconsistent.
    """
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
        max(
            MIN_SDF_RESOLUTION,
            min(MAX_SDF_RESOLUTION, ceil((span + SDF_PADDING_MM) / voxel_mm)),
        )
        for span in surface_spans_mm
    )
    if sdf_resolution != expected_resolution:
        msg = (
            "tunic: runtime SDF resolution does not match its configured voxel size: "
            f"actual={sdf_resolution} expected={expected_resolution}"
        )
        raise SystemExit(msg)

def _validate_tunic_images(generated: Path, *, require_canonical_e2e: bool) -> None:
    """Require the canonical garment screenshots and mannequin motion frames.

    Args:
        generated: Directory containing the saved GUI evidence images.
        require_canonical_e2e: Whether canonical garment workflow screenshots are required.

    Raises:
        SystemExit: If required images are absent or the mannequin motion count is invalid.
    """
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
    motion_frames = generated / "cloth-tunic-mannequin-motion-frames"
    if len(list(motion_frames.glob("motion-*.png"))) != MANNEQUIN_MOTION_FRAME_COUNT:
        msg = "tunic: wrong mannequin motion frame count"
        raise SystemExit(msg)

def _validate_tunic_end_to_end() -> None:
    """Verify all mandatory markers from the canonical garment end-to-end journey.

    Raises:
        SystemExit: If the canonical garment log is missing any required acceptance marker.
    """
    e2e_path = Path("artifacts/garment-e2e.log")
    e2e = e2e_path.read_text(encoding="utf-8")
    markers = (
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
    )
    for marker in markers:
        if marker not in e2e:
            msg = f"tunic: missing E2E marker {marker}"
            raise SystemExit(msg)

def _validate_tunic(*, require_canonical_e2e: bool) -> None:
    """Validate tunic evidence with either the canonical or production audit contract.

    Args:
        require_canonical_e2e: Whether canonical garment end-to-end evidence is required.

    Raises:
        SystemExit: If required evidence or acceptance checks fail.
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
    for marker in markers:
        if marker not in text:
            msg = "tunic: progress contract failed"
            raise SystemExit(msg)
    _validate_tunic_collision_configuration(text)
    _validate_tunic_images(generated, require_canonical_e2e=require_canonical_e2e)
    if require_canonical_e2e:
        _validate_tunic_end_to_end()
    sys.stdout.write("tunic-visual=passed\n")

def validate_tunic() -> None:
    """Validate the strict canonical tunic evidence."""
    _validate_tunic(require_canonical_e2e=True)

def validate_tunic_production() -> None:
    """Validate production tunic evidence without canonical garment E2E artifacts."""
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
    markers = (
        "blanket-visual-acceptance=passed",
        "mesh=passed",
        "movement=passed",
        "material-presentation=passed viewport=true",
    )
    for marker in markers:
        if marker not in text:
            msg = f"blanket: missing marker {marker}"
            raise SystemExit(msg)
    if len(list(root.glob("checkpoint-*.png"))) != BLANKET_CHECKPOINT_COUNT:
        msg = f"blanket: expected {BLANKET_CHECKPOINT_COUNT} checkpoints"
        raise SystemExit(msg)
    if len(list(root.glob("motion-*.png"))) != BLANKET_MOTION_FRAME_COUNT:
        msg = f"blanket: expected {BLANKET_MOTION_FRAME_COUNT} motion frames"
        raise SystemExit(msg)
    sys.stdout.write("blanket-visual=passed\n")

def _validate_diagnostic_record(
    root: Path,
    name: str,
    record: dict,
    expected_rung: int,
) -> None:
    """Validate solver settings and image evidence for one diagnostic rung.

    Args:
        root: Directory containing the diagnostic manifests and images.
        name: Manifest filename used in failure diagnostics.
        record: Parsed record for one diagnostic rung.
        expected_rung: Required rung number for the record.

    Raises:
        SystemExit: If the rung number, solver setup, checkpoints, or images are invalid.
    """
    if record.get("case", {}).get("rung") != expected_rung:
        msg = f"diagnostic {name}: unexpected rung"
        raise SystemExit(msg)
    if record.get("solver", {}).get("backend") != "pbd":
        msg = f"diagnostic {name}: wrong backend"
        raise SystemExit(msg)
    if record.get("solver", {}).get("substeps") != 1:
        msg = f"diagnostic {name}: wrong substeps"
        raise SystemExit(msg)
    if len(record.get("checkpoints", ())) != CHECKPOINT_COUNT:
        msg = f"diagnostic {name}: wrong checkpoints"
        raise SystemExit(msg)
    for image in record.get("images", ()):
        candidate = root / ("cube-ladder" if "rung-" in image and "cube" in image else "")
        if not (root / image).is_file() and not candidate.is_file():
            msg = f"diagnostic {name}: missing image {image}"
            raise SystemExit(msg)


def _validate_diagnostic_ladder(
    root: Path,
    name: str,
    purpose: str,
    first_rung: int,
) -> None:
    """Validate one diagnostic collision manifest and its per-rung evidence.

    Args:
        root: Directory containing the diagnostic manifests and images.
        name: Manifest filename under the diagnostic directory.
        purpose: Required purpose value for the manifest.
        first_rung: Number of the first expected diagnostic rung.

    Raises:
        SystemExit: If the manifest header, case count, or any rung is invalid.
    """
    data = read(root / name)
    if data.get("schema") != 1 or data.get("purpose") != purpose:
        msg = f"diagnostic {name}: invalid header"
        raise SystemExit(msg)
    if data.get("release_gate_effect") != "gate":
        msg = f"diagnostic {name}: wrong gate effect"
        raise SystemExit(msg)
    if len(data.get("cases", ())) != DIAGNOSTIC_CASE_COUNT:
        msg = f"diagnostic {name}: wrong case count"
        raise SystemExit(msg)
    for offset, record in enumerate(data["cases"]):
        _validate_diagnostic_record(root, name, record, first_rung + offset)

def validate_diagnostic() -> None:
    """Validate the canonical diagnostic PBD evidence.

    Raises:
        SystemExit: Raised when diagnostic collision manifests are invalid.
    """
    root = Path("artifacts/pbd-contact-diagnostics")
    specs = (
        ("cube-ladder-manifest.json", "simulation-collision-ladder", 1),
        ("avatar-ladder-manifest.json", "simulation-avatar-ladder", 6),
    )
    for name, purpose, first_rung in specs:
        _validate_diagnostic_ladder(root, name, purpose, first_rung)
    data = read(root / "manifest.json")
    if data.get("schema") != 1 or data.get("release_gate_effect") != "none":
        msg = "diagnostic contact manifest header failed"
        raise SystemExit(msg)
    sys.stdout.write("diagnostic-contact=passed\n")

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
