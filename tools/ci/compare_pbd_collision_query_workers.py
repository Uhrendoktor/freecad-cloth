# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compare matched production profiles for exact mesh-collision KDTree query workers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from freecad_cloth.common.JsonTypes import JsonObject
from tools.ci.compare_pbd_openmp_team_reuse import compare_collision_query_worker_profile_sets


def main() -> int:
    """Load the four production profiles, compare them, and write the summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-1", type=Path, required=True)
    parser.add_argument("--baseline-2", type=Path, required=True)
    parser.add_argument("--candidate-1", type=Path, required=True)
    parser.add_argument("--candidate-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = (args.baseline_1, args.baseline_2, args.candidate_1, args.candidate_2)
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not all(isinstance(profile, dict) for profile in profiles):
        raise SystemExit("all experiment profiles must contain JSON objects")
    typed_profiles = [profile for profile in profiles if isinstance(profile, dict)]
    baseline: list[JsonObject] = [typed_profiles[0], typed_profiles[1]]
    candidate: list[JsonObject] = [typed_profiles[2], typed_profiles[3]]
    summary = compare_collision_query_worker_profile_sets(baseline, candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = str(summary["acceptance"])
    print(
        f"pbd-collision-query-workers={status} "
        f"projector-improvement={summary['mesh_collision_projector_improvement_percent']:.2f}% "
        f"production-wall-change={summary['production_wall_time_change_percent']:.2f}%",
        flush=True,
    )
    for reason in summary["rejection_reasons"]:
        print(f"rejection-reason={reason}", flush=True)
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
