# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compare matched layered-outfit audits for inter-cloth KDTree query workers."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import median

from freecad_cloth.common.JsonTypes import JsonObject, JsonValue
from tools.ci.validate_layered_outfit import validate_manifest

EXPECTED_BASELINE_WORKERS = 1
EXPECTED_CANDIDATE_WORKERS = 4
MIN_QUERY_IMPROVEMENT = 0.10
MIN_INTER_CLOTH_IMPROVEMENT = 0.05
EXPECTED_CHECKPOINTS = (1, 15, 60)
_FIELD_PATTERN = re.compile(r"([a-z_]+)=([^\s]+)")


def _as_object(value: JsonValue, label: str) -> JsonObject:
    """Require one JSON object at a named manifest boundary."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _number(value: JsonValue, label: str, *, positive: bool = False) -> float:
    """Read a finite non-boolean number from a profile."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        raise ValueError(f"{label} must be finite and positive")
    return result


def _integer(value: JsonValue, label: str) -> int:
    """Read a positive integer profile metric."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _parse_fields(line: str) -> dict[str, str]:
    """Extract key=value telemetry fields from one diagnostic line."""
    return dict(_FIELD_PATTERN.findall(line))


def _parse_inter_cloth_diagnostics(path: Path, expected_workers: int) -> JsonObject:
    """Read exact query, filter, correction and complete projection timings."""
    if not path.is_file():
        raise ValueError(f"missing inter-cloth diagnostics file: {path}")
    query_seconds = 0.0
    filter_seconds = 0.0
    closest_seconds = 0.0
    correction_seconds = 0.0
    direction_seconds = 0.0
    projection_seconds = 0.0
    pass_seconds = 0.0
    raw_candidates = 0
    aabb_candidates = 0
    plane_candidates = 0
    broadphase_samples = 0
    projection_samples = 0
    pass_samples = 0
    observed_workers: set[int] = set()
    observed_eps: set[float] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("inter-cloth-broadphase "):
            fields = _parse_fields(line)
            observed_workers.add(int(fields["workers"]))
            observed_eps.add(float(fields["eps"]))
            query_seconds += float(fields["query_s"])
            filter_seconds += float(fields["filter_s"])
            raw_candidates += int(fields["raw"])
            aabb_candidates += int(fields["aabb"])
            plane_candidates += int(fields["plane"])
            broadphase_samples += 1
        elif line.startswith("inter-cloth-direction-finish "):
            fields = _parse_fields(line)
            closest_seconds += float(fields["closest_s"])
            correction_seconds += float(fields["correction_s"])
            direction_seconds += float(fields["elapsed_s"])
        elif line.startswith("inter-cloth-pass-finish "):
            fields = _parse_fields(line)
            pass_seconds += float(fields["elapsed_s"])
            pass_samples += 1
        elif line.startswith("cloth-pbd-inter-cloth-projection-finish "):
            fields = _parse_fields(line)
            projection_seconds += float(fields["elapsed_s"])
            projection_samples += 1

    if broadphase_samples == 0 or projection_samples == 0 or pass_samples == 0:
        raise ValueError(f"{path}: incomplete inter-cloth timing telemetry")
    if observed_workers != {expected_workers}:
        raise ValueError(
            f"{path}: expected query workers {expected_workers}, "
            f"observed {sorted(observed_workers)}"
        )
    if observed_eps != {0.0}:
        raise ValueError(f"{path}: query approximation epsilon changed from exact eps=0.0")
    required_totals = (query_seconds, projection_seconds, pass_seconds)
    nonnegative_totals = (
        filter_seconds,
        closest_seconds,
        correction_seconds,
        direction_seconds,
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in required_totals):
        raise ValueError(f"{path}: inter-cloth timing totals must be finite and positive")
    if any(not math.isfinite(value) or value < 0.0 for value in nonnegative_totals):
        raise ValueError(f"{path}: inter-cloth stage timings must be finite and non-negative")

    return {
        "query_seconds": query_seconds,
        "filter_seconds": filter_seconds,
        "closest_seconds": closest_seconds,
        "correction_seconds": correction_seconds,
        "direction_seconds": direction_seconds,
        "inter_cloth_projection_seconds": projection_seconds,
        "projection_pass_seconds": pass_seconds,
        "raw_candidate_pairs": raw_candidates,
        "aabb_candidate_pairs": aabb_candidates,
        "plane_candidate_pairs": plane_candidates,
        "broadphase_samples": broadphase_samples,
        "projection_samples": projection_samples,
        "pass_samples": pass_samples,
    }


def _checkpoint_signature(manifest: JsonObject) -> list[JsonObject]:
    """Return physics and geometry checkpoints without wall-time or image payloads."""
    raw_checkpoints = manifest.get("checkpoints")
    if not isinstance(raw_checkpoints, list):
        raise ValueError("manifest checkpoints must be a list")
    checkpoints: list[JsonObject] = []
    for raw in raw_checkpoints:
        checkpoint = _as_object(raw, "checkpoint")
        record = dict(checkpoint)
        record.pop("elapsed_ms", None)
        record.pop("images", None)
        checkpoints.append(record)
    return checkpoints


def _manifest_signature(manifest: JsonObject) -> JsonObject:
    """Capture source, garment geometry, runtime and physical output invariants."""
    provenance = _as_object(manifest.get("provenance"), "manifest.provenance")
    runtime = dict(_as_object(manifest.get("runtime_context"), "manifest.runtime_context"))
    runtime.pop("inter_cloth_query_workers", None)
    return {
        "provenance": provenance,
        "outfit": manifest.get("outfit"),
        "scene_map": manifest.get("scene_map"),
        "runtime_context": runtime,
        "checkpoints": _checkpoint_signature(manifest),
        "persistence": manifest.get("persistence"),
    }


def _equivalent(left: JsonValue, right: JsonValue, *, label: str) -> None:
    """Require identical structures and numerically equivalent geometric results."""
    if isinstance(left, dict) and isinstance(right, dict):
        left_object = _as_object(left, label)
        right_object = _as_object(right, label)
        if set(left_object) != set(right_object):
            raise ValueError(f"{label}: object keys differ")
        for key in left_object:
            _equivalent(left_object[key], right_object[key], label=f"{label}.{key}")
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(f"{label}: list lengths differ")
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            _equivalent(left_item, right_item, label=f"{label}[{index}]")
        return
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        if isinstance(left, int) and isinstance(right, int):
            if left != right:
                raise ValueError(f"{label}: integer geometry/physics result changed")
        elif not math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-3):
            raise ValueError(f"{label}: numeric geometry/physics result changed")
        return
    if left != right:
        raise ValueError(f"{label}: value changed")


def _load_audit(root: Path, expected_workers: int) -> JsonObject:
    """Validate one full layered outfit artifact bundle and its timing telemetry."""
    manifest_path = root / "layered-outfit-manifest.json"
    validate_manifest(manifest_path)
    manifest_value = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = _as_object(manifest_value, "layered outfit manifest")
    runtime = _as_object(manifest.get("runtime_context"), "manifest.runtime_context")
    worker_value = runtime.get("inter_cloth_query_workers")
    if (
        isinstance(worker_value, bool)
        or not isinstance(worker_value, int)
        or worker_value != expected_workers
    ):
        raise ValueError(f"{root}: manifest does not record {expected_workers} query workers")

    checkpoints_value = manifest.get("checkpoints")
    if not isinstance(checkpoints_value, list):
        raise ValueError(f"{root}: checkpoints are missing")
    checkpoints = [_as_object(item, "checkpoint") for item in checkpoints_value]
    checkpoint_steps = tuple(
        _integer(item.get("step"), f"{root}.checkpoint.step") for item in checkpoints
    )
    if checkpoint_steps != EXPECTED_CHECKPOINTS:
        raise ValueError(f"{root}: complete 1/15/60-step checkpoints are required")
    total_elapsed_ms = sum(
        _number(item.get("elapsed_ms"), f"{root}.checkpoint.elapsed_ms", positive=True)
        for item in checkpoints
    )

    provenance = _as_object(manifest.get("provenance"), "manifest.provenance")
    source_sha = provenance.get("commit_sha")
    if not isinstance(source_sha, str) or len(source_sha) != 40:
        raise ValueError(f"{root}: invalid source commit SHA")
    diagnostics = _parse_inter_cloth_diagnostics(
        root / "inter-cloth-diagnostics.log",
        expected_workers,
    )
    return {
        "manifest": manifest,
        "signature": _manifest_signature(manifest),
        "source_sha": source_sha,
        "total_elapsed_ms": total_elapsed_ms,
        "diagnostics": diagnostics,
    }


def compare_layered_query_worker_audits(
    baseline_roots: list[Path],
    candidate_roots: list[Path],
) -> JsonObject:
    """Compare two one-worker and two four-worker full layered-outfit audits."""
    if len(baseline_roots) != 2 or len(candidate_roots) != 2:
        raise ValueError("exactly two one-worker and two four-worker layered audits are required")

    baseline = [_load_audit(root, EXPECTED_BASELINE_WORKERS) for root in baseline_roots]
    candidate = [_load_audit(root, EXPECTED_CANDIDATE_WORKERS) for root in candidate_roots]
    reference_sha = baseline[0]["source_sha"]
    records = [
        *((f"baseline-{index + 1}", item) for index, item in enumerate(baseline)),
        *((f"candidate-{index + 1}", item) for index, item in enumerate(candidate)),
    ]
    for label, audit in records:
        if audit["source_sha"] != reference_sha:
            raise ValueError(f"{label}: source commit differs from the matched baseline")
        _equivalent(
            baseline[0]["signature"],
            audit["signature"],
            label=f"{label}.matched_context_and_physics",
        )
        reference_diagnostics = _as_object(
            baseline[0].get("diagnostics"), "baseline-1.diagnostics"
        )
        audit_diagnostics = _as_object(audit.get("diagnostics"), f"{label}.diagnostics")
        for key in (
            "raw_candidate_pairs",
            "aabb_candidate_pairs",
            "plane_candidate_pairs",
            "broadphase_samples",
            "projection_samples",
            "pass_samples",
        ):
            if audit_diagnostics.get(key) != reference_diagnostics.get(key):
                raise ValueError(f"{label}: exact contact candidate/work counts changed ({key})")

    def metric_samples(records_to_measure: list[JsonObject], key: str) -> list[float]:
        """Extract one positive timing or wall-time sample from each audit."""
        samples: list[float] = []
        for index, record in enumerate(records_to_measure, 1):
            metrics = _as_object(record.get("diagnostics"), f"audit-{index}.diagnostics")
            samples.append(_number(metrics.get(key), f"audit-{index}.{key}", positive=True))
        return samples

    baseline_query = metric_samples(baseline, "query_seconds")
    candidate_query = metric_samples(candidate, "query_seconds")
    baseline_projection = metric_samples(baseline, "inter_cloth_projection_seconds")
    candidate_projection = metric_samples(candidate, "inter_cloth_projection_seconds")
    baseline_wall = [
        _number(record.get("total_elapsed_ms"), f"baseline-{index}.total_elapsed_ms", positive=True)
        for index, record in enumerate(baseline, 1)
    ]
    candidate_wall = [
        _number(
            record.get("total_elapsed_ms"),
            f"candidate-{index}.total_elapsed_ms",
            positive=True,
        )
        for index, record in enumerate(candidate, 1)
    ]

    baseline_query_median = median(baseline_query)
    candidate_query_median = median(candidate_query)
    baseline_projection_median = median(baseline_projection)
    candidate_projection_median = median(candidate_projection)
    baseline_wall_median = median(baseline_wall)
    candidate_wall_median = median(candidate_wall)
    query_improvement = 1.0 - candidate_query_median / baseline_query_median
    projection_improvement = 1.0 - candidate_projection_median / baseline_projection_median
    wall_time_change = candidate_wall_median / baseline_wall_median - 1.0

    rejection_reasons: list[str] = []
    if query_improvement < MIN_QUERY_IMPROVEMENT:
        rejection_reasons.append(
            f"four-worker inter-cloth query improvement is below 10%: "
            f"{query_improvement * 100:.2f}%"
        )
    if projection_improvement < MIN_INTER_CLOTH_IMPROVEMENT:
        rejection_reasons.append(
            f"inter-cloth projection improvement is below 5%: "
            f"{projection_improvement * 100:.2f}%"
        )
    if wall_time_change > 0.0:
        rejection_reasons.append(
            f"full layered simulation checkpoint time regressed: {wall_time_change * 100:.2f}%"
        )

    return {
        "schema_version": 1,
        "experiment": "layered-inter-cloth-kdtree-query-workers",
        "repetitions_per_mode": 2,
        "baseline_query_workers": EXPECTED_BASELINE_WORKERS,
        "candidate_query_workers": EXPECTED_CANDIDATE_WORKERS,
        "source_commit_sha": reference_sha,
        "baseline_query_seconds": baseline_query,
        "candidate_query_seconds": candidate_query,
        "baseline_median_query_seconds": baseline_query_median,
        "candidate_median_query_seconds": candidate_query_median,
        "query_improvement_fraction": query_improvement,
        "query_improvement_percent": 100.0 * query_improvement,
        "baseline_inter_cloth_projection_seconds": baseline_projection,
        "candidate_inter_cloth_projection_seconds": candidate_projection,
        "baseline_median_inter_cloth_projection_seconds": baseline_projection_median,
        "candidate_median_inter_cloth_projection_seconds": candidate_projection_median,
        "inter_cloth_projection_improvement_fraction": projection_improvement,
        "inter_cloth_projection_improvement_percent": 100.0 * projection_improvement,
        "baseline_total_checkpoint_ms": baseline_wall,
        "candidate_total_checkpoint_ms": candidate_wall,
        "baseline_median_total_checkpoint_ms": baseline_wall_median,
        "candidate_median_total_checkpoint_ms": candidate_wall_median,
        "total_checkpoint_wall_time_change_fraction": wall_time_change,
        "total_checkpoint_wall_time_change_percent": 100.0 * wall_time_change,
        "acceptance": "rejected" if rejection_reasons else "passed",
        "production_acceptance": "passed_all_four_runs",
        "rejection_reasons": rejection_reasons,
    }


def main() -> int:
    """Compare four complete layered outfit artifact directories."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-1", type=Path, required=True)
    parser.add_argument("--baseline-2", type=Path, required=True)
    parser.add_argument("--candidate-1", type=Path, required=True)
    parser.add_argument("--candidate-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        summary = compare_layered_query_worker_audits(
            [args.baseline_1, args.baseline_2],
            [args.candidate_1, args.candidate_2],
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"layered inter-cloth worker comparison failed closed: {exc}") from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = str(summary["acceptance"])
    print(
        f"layered-inter-cloth-query-workers={status} "
        f"query-improvement={summary['query_improvement_percent']:.2f}% "
        f"projection-improvement={summary['inter_cloth_projection_improvement_percent']:.2f}% "
        f"checkpoint-wall-change={summary['total_checkpoint_wall_time_change_percent']:.2f}%",
        flush=True,
    )
    for reason in summary["rejection_reasons"]:
        print(f"rejection-reason={reason}", flush=True)
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
