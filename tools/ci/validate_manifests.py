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

ROOT = Path("artifacts/simulation-ladder")
CHECKPOINTS = [0, 1, 5, 15, 45, 90]
EXPECTED_MANIFEST_SCHEMA_VERSION = 1
EXPECTED_CHECKPOINT_COUNT = 6
EXPECTED_TURN_TABLE_FRAME_COUNT = 73
EXPECTED_TURN_TABLE_CHECKPOINT_COUNT = 4
MINIMUM_BLANKET_DISPLACEMENT_MM = 40.0
MAXIMUM_COLLISION_PENETRATION_MM = 3.0
MAXIMUM_LEGACY_P95_FRAME_MS = 50.0
MINIMUM_MEASURED_INTERVALS = 120
MINIMUM_WARMUP_FRAMES = 30
EXPECTED_TUNIC_MOTION_FRAME_COUNT = 10
EXPECTED_BLANKET_CHECKPOINT_COUNT = 5
EXPECTED_BLANKET_MOTION_FRAME_COUNT = 16
EXPECTED_DIAGNOSTIC_CASE_COUNT = 5
EXPECTED_DIAGNOSTIC_SOLVER_SUBSTEPS = 1


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


def _validate_simulation_record(
    name: str,
    case: dict,
    maximum_penetration_mm: float,
) -> None:
    """Validate evidence and collision limits for one simulation case.

    Args:
        name: Human-readable name used in diagnostics.
        case: Parsed simulation case record.
        maximum_penetration_mm: Maximum accepted penetration, in millimetres.

    Raises:
        SystemExit: If the case is non-finite, uses the wrong backend, lacks checkpoints,
            exceeds the penetration limit, or references a missing image.
    """
    if not case.get("finite"):
        msg = f"{name}: non-finite case"
        raise SystemExit(msg)
    if case.get("solver", {}).get("backend") != "pbd":
        msg = f"{name}: wrong backend"
        raise SystemExit(msg)
    if len(case.get("checkpoints", ())) != EXPECTED_CHECKPOINT_COUNT:
        msg = f"{name}: unexpected checkpoint count"
        raise SystemExit(msg)
    if case.get("max_penetration_mm", 0) > maximum_penetration_mm + 1e-6:
        msg = f"{name}: penetration too large"
        raise SystemExit(msg)
    for image in case.get("images", ()):
        if not (ROOT / image).is_file():
            msg = f"{name}: missing image {image}"
            raise SystemExit(msg)


def _validate_simulation_case(
    name: str,
    path: Path,
    expected_case_count: int,
    maximum_penetration_mm: float,
    purpose: str,
) -> None:
    """Validate the header and every case in a simulation collision manifest.

    Args:
        name: Human-readable name used in diagnostics.
        path: Manifest file to validate.
        expected_case_count: Required number of collision cases in the manifest.
        maximum_penetration_mm: Maximum accepted penetration, in millimetres.
        purpose: Manifest purpose string expected for this ladder.

    Raises:
        SystemExit: If the manifest fails a schema, evidence, or collision gate.
    """
    data = read(path)
    valid_header = (
        data.get("schema") == EXPECTED_MANIFEST_SCHEMA_VERSION
        and data.get("purpose") == purpose
    )
    if not valid_header:
        msg = f"{name}: invalid manifest header"
        raise SystemExit(msg)
    if data.get("release_gate_effect") != "gate":
        msg = f"{name}: not a release gate"
        raise SystemExit(msg)
    if len(data.get("cases", ())) != expected_case_count:
        msg = f"{name}: unexpected case count"
        raise SystemExit(msg)
    for case in data["cases"]:
        _validate_simulation_record(name, case, maximum_penetration_mm)
    if data.get("structural_validation", {}).get("first_failing_rung") is not None:
        msg = f"{name}: structural rung failed"
        raise SystemExit(msg)
    sys.stdout.write(f"{name}-collision-ladder=passed\n")


def validate_simulation() -> None:
    """Validate the canonical simulation collision manifests."""
    specifications = (
        ("cube", ROOT / "cube-ladder-manifest.json", 5, 3.0, "simulation-collision-ladder"),
        ("avatar", ROOT / "avatar-ladder-manifest.json", 5, 8.0, "simulation-avatar-ladder"),
    )
    for name, path, case_count, max_penetration, purpose in specifications:
        _validate_simulation_case(name, path, case_count, max_penetration, purpose)


def _validate_turntable_directory(root: Path, directory: str) -> None:
    """Validate frame inventory, uniqueness, and checkpoint distinction for one turntable.

    Args:
        root: Directory containing generated turntable frames.
        directory: Relative frame-directory name to check.

    Raises:
        SystemExit: If frames are missing, duplicated, or have identical checkpoints.
    """
    frames = sorted((root / directory).glob("frame-*.png"))
    if len(frames) != EXPECTED_TURN_TABLE_FRAME_COUNT:
        msg = f"{directory}: expected 73 frames, got {len(frames)}"
        raise SystemExit(msg)
    hashes = {hashlib.sha256(frame.read_bytes()).hexdigest() for frame in frames}
    if len(hashes) != EXPECTED_TURN_TABLE_FRAME_COUNT:
        msg = f"{directory}: duplicate frame hashes"
        raise SystemExit(msg)
    checkpoints = []
    for frame_index in (0, 18, 36, 54):
        path = root / directory / f"frame-{frame_index:03d}.png"
        if not path.is_file():
            msg = f"{directory}: missing checkpoint {frame_index}"
            raise SystemExit(msg)
        checkpoints.append(hashlib.sha256(path.read_bytes()).hexdigest())
    if len(set(checkpoints)) != EXPECTED_TURN_TABLE_CHECKPOINT_COUNT:
        msg = f"{directory}: camera checkpoints are not distinct"
        raise SystemExit(msg)


def _validate_turntable_progress(root: Path) -> None:
    """Validate completion markers, blanket movement, and collision penetration in the log.

    Args:
        root: Directory containing the simulation turntable progress log.

    Raises:
        SystemExit: If any required marker or measured collision/movement gate fails.
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
    if not displacement or float(displacement[-1]) < MINIMUM_BLANKET_DISPLACEMENT_MM:
        msg = "turntable: insufficient blanket displacement"
        raise SystemExit(msg)
    penetration = re.findall(
        r"collision-penetration=passed max_penetration_mm=([+-]?[0-9.]+)",
        text,
    )
    if not penetration or float(penetration[-1]) > MAXIMUM_COLLISION_PENETRATION_MM:
        msg = "turntable: collision penetration gate failed"
        raise SystemExit(msg)


def validate_turntables() -> None:
    """Validate canonical turntable images and measured simulation evidence."""
    root = Path("docs/images/generated")
    directories = (
        "cloth-avatar-turntable-frames",
        "cloth-simulation-arranged-turntable-frames",
        "cloth-simulation-draped-turntable-frames",
    )
    for directory in directories:
        _validate_turntable_directory(root, directory)
    _validate_turntable_progress(root)
    sys.stdout.write("turntables=passed\n")


def _integer_metric_meets_minimum(data: dict, field: str, minimum: int) -> bool:
    """Check whether a metric is an integer counter meeting a required minimum.

    Args:
        data: Parsed realtime metric object.
        field: Manifest field containing the integer counter.
        minimum: Smallest acceptable value for the counter.

    Returns:
        Whether the field contains an integer at least as large as the minimum.
    """
    value = data.get(field)
    return isinstance(value, int) and value >= minimum


def _realtime_header_is_valid(data: dict) -> bool:
    """Check schema identity and discrete runtime counters without reading timing floats.

    Args:
        data: Parsed runtime metric object.

    Returns:
        Whether schema, backend, fixture, state flags, and frame counters are valid.
    """
    required_fields = (
        data.get("schema_version") == EXPECTED_MANIFEST_SCHEMA_VERSION,
        data.get("backend") == "position-based-dynamics",
        data.get("fixture") == "two-panel-tunic-pattern",
        data.get("backend_finite") is True,
        data.get("published_state_finite") is True,
        data.get("timed_out") is False,
    )
    if not all(required_fields):
        return False
    if not _integer_metric_meets_minimum(data, "measured_intervals", MINIMUM_MEASURED_INTERVALS):
        return False
    if not _integer_metric_meets_minimum(data, "warmup_frames_requested", MINIMUM_WARMUP_FRAMES):
        return False
    if data.get("observed_ticks") != data.get("expected_ticks"):
        return False
    return data.get("frames_advanced") == data.get("observed_ticks")


def _numeric_metrics_are_finite(values: tuple[object, ...]) -> bool:
    """Check that each timing metric is a finite number and not a Boolean.

    Args:
        values: Budget, mean interval, and p95 interval values from the manifest.

    Returns:
        Whether every provided timing value is a finite integer or float.
    """
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            return False
    return True


def _validate_realtime_metrics(data: dict) -> None:
    """Validate either legacy or schema-versioned realtime metrics without weakening gates.

    Args:
        data: Parsed JSON metrics used to verify the realtime performance contract.

    Raises:
        SystemExit: If runtime metrics violate the schema or timing budget.
    """
    if "schema_version" not in data:
        # Retain the existing contract for historical metric artifacts.
        if (
            not data["finite"]
            or data["mean_frame_ms"] > data["frame_budget_ms"]
            or data["p95_frame_ms"] > MAXIMUM_LEGACY_P95_FRAME_MS
        ):
            msg = f"tunic: realtime performance gate failed: {data}"
            raise SystemExit(msg)
        return

    budget = data.get("frame_budget_ms")
    mean_interval = data.get("mean_frame_interval_ms")
    p95_interval = data.get("p95_frame_interval_ms")
    numeric_values = (budget, mean_interval, p95_interval)
    if not _realtime_header_is_valid(data) or not _numeric_metrics_are_finite(numeric_values):
        msg = f"tunic: realtime performance gate failed: {data}"
        raise SystemExit(msg)
    if mean_interval > budget or p95_interval > budget:
        msg = f"tunic: realtime performance gate failed: {data}"
        raise SystemExit(msg)


def _validate_tunic_collision_configuration(text: str) -> None:
    """Validate emitted collision thickness, voxel size, tolerance, and SDF resolution.

    Args:
        text: GUI progress log containing the actual collision configuration.

    Raises:
        SystemExit: If collision configuration evidence is absent or internally inconsistent.
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
        max(16, min(256, ceil((span + 200.0) / voxel_mm))) for span in surface_spans_mm
    )
    if sdf_resolution != expected_resolution:
        msg = (
            "tunic: runtime SDF resolution does not match its configured voxel size: "
            f"actual={sdf_resolution} expected={expected_resolution}"
        )
        raise SystemExit(msg)


def _validate_tunic_images(generated: Path, *, require_canonical_e2e: bool) -> None:
    """Require non-empty images and the complete mannequin motion frame inventory.

    Args:
        generated: Directory containing generated GUI screenshots and motion frames.
        require_canonical_e2e: Whether pattern and sewing screenshots are required as well.

    Raises:
        SystemExit: If a required screenshot is missing, empty, or the frame count is wrong.
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
    motion_frames = list(
        (generated / "cloth-tunic-mannequin-motion-frames").glob("motion-*.png")
    )
    if len(motion_frames) != EXPECTED_TUNIC_MOTION_FRAME_COUNT:
        msg = "tunic: wrong mannequin motion frame count"
        raise SystemExit(msg)


def _validate_tunic_end_to_end() -> None:
    """Check all canonical garment end-to-end acceptance markers.

    Raises:
        SystemExit: If the end-to-end log is missing or any acceptance marker is absent.
    """
    e2e = Path("artifacts/garment-e2e.log").read_text(encoding="utf-8")
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
    """Validate tunic visual and collision evidence without skipping any configured gate.

    Args:
        require_canonical_e2e: Whether to require the production garment end-to-end record.

    Raises:
        SystemExit: If required log, metrics, collision settings, images, or markers fail.
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
    _validate_tunic_collision_configuration(text)
    _validate_tunic_images(generated, require_canonical_e2e=require_canonical_e2e)
    if require_canonical_e2e:
        _validate_tunic_end_to_end()
    sys.stdout.write("tunic-visual=passed\n")


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
    if len(list(root.glob("checkpoint-*.png"))) != EXPECTED_BLANKET_CHECKPOINT_COUNT:
        msg = "blanket: expected 5 checkpoints"
        raise SystemExit(msg)
    if len(list(root.glob("motion-*.png"))) != EXPECTED_BLANKET_MOTION_FRAME_COUNT:
        msg = "blanket: expected 16 motion frames"
        raise SystemExit(msg)
    sys.stdout.write("blanket-visual=passed\n")


def _validate_diagnostic_record(
    root: Path,
    filename: str,
    record: dict,
    expected_rung: int,
) -> None:
    """Validate one diagnostic rung, its solver settings, checkpoints, and referenced images.

    Args:
        root: Directory containing diagnostic manifests and associated evidence.
        filename: Manifest filename used in failure messages.
        record: Single rung record extracted from the manifest.
        expected_rung: Numeric rung identifier expected for this record.

    Raises:
        SystemExit: If the record identity, solver settings, checkpoints, or images are invalid.
    """
    if record.get("case", {}).get("rung") != expected_rung:
        msg = f"diagnostic {filename}: unexpected rung"
        raise SystemExit(msg)
    if record.get("solver", {}).get("backend") != "pbd":
        msg = f"diagnostic {filename}: wrong backend"
        raise SystemExit(msg)
    if record.get("solver", {}).get("substeps") != EXPECTED_DIAGNOSTIC_SOLVER_SUBSTEPS:
        msg = f"diagnostic {filename}: wrong substeps"
        raise SystemExit(msg)
    if len(record.get("checkpoints", ())) != EXPECTED_CHECKPOINT_COUNT:
        msg = f"diagnostic {filename}: wrong checkpoints"
        raise SystemExit(msg)
    for image in record.get("images", ()):
        candidate = root / ("cube-ladder" if "rung-" in image and "cube" in image else "")
        if not (root / image).is_file() and not candidate.is_file():
            msg = f"diagnostic {filename}: missing image {image}"
            raise SystemExit(msg)


def validate_diagnostic() -> None:
    """Validate the canonical diagnostic PBD evidence.

    Raises:
        SystemExit: If diagnostic collision manifests are invalid.
    """
    root = Path("artifacts/pbd-contact-diagnostics")
    manifests = (
        ("cube-ladder-manifest.json", "simulation-collision-ladder", range(1, 6)),
        ("avatar-ladder-manifest.json", "simulation-avatar-ladder", range(6, 11)),
    )
    for filename, purpose, rungs in manifests:
        data = read(root / filename)
        if (
            data.get("schema") != EXPECTED_MANIFEST_SCHEMA_VERSION
            or data.get("purpose") != purpose
        ):
            msg = f"diagnostic {filename}: invalid header"
            raise SystemExit(msg)
        if data.get("release_gate_effect") != "gate":
            msg = f"diagnostic {filename}: wrong gate effect"
            raise SystemExit(msg)
        if len(data.get("cases", ())) != EXPECTED_DIAGNOSTIC_CASE_COUNT:
            msg = f"diagnostic {filename}: wrong case count"
            raise SystemExit(msg)
        for record, expected_rung in zip(data["cases"], rungs, strict=True):
            _validate_diagnostic_record(root, filename, record, expected_rung)
    data = read(root / "manifest.json")
    if (
        data.get("schema") != EXPECTED_MANIFEST_SCHEMA_VERSION
        or data.get("release_gate_effect") != "none"
    ):
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
