"""Create a compact, schema-versioned index of explicitly selected CI evidence."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import platform
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA = "freecad-cloth.agent-observation"
SCHEMA_VERSION = 1
MAX_EVIDENCE_FILES = 24
MAX_EVIDENCE_FILE_BYTES = 4_000_000
MAX_EVIDENCE_BYTES = 5_000_000
ROLE_SUFFIXES = {
    "summary": {".json", ".md", ".txt", ".yaml", ".yml"},
    "metrics": {".json", ".csv"},
    "geometry": {".json", ".csv", ".stl", ".obj", ".step", ".stp", ".brep"},
    "visual": {".png", ".jpg", ".jpeg", ".webp", ".svg"},
    "model": {".fcstd", ".stl", ".obj", ".step", ".stp", ".brep"},
    "config": {".json", ".toml", ".yaml", ".yml", ".txt"},
}


class ObservationBundleError(ValueError):
    """Report invalid evidence selection or unsafe paths."""


def _resolve_relative_path(base: Path, value: str, *, must_exist: bool) -> Path:
    """Resolve a relative path while rejecting traversal and symbolic links."""
    normalized = value.strip()
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or "\\" in normalized
    ):
        raise ObservationBundleError(f"unsafe relative path: {value!r}")

    candidate = base.joinpath(*relative.parts)
    cursor = base
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ObservationBundleError(f"symbolic links are not allowed: {value!r}")
    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise ObservationBundleError(f"required evidence is missing: {value!r}") from exc
    except OSError as exc:
        raise ObservationBundleError(f"cannot resolve path {value!r}: {exc}") from exc
    if not resolved.is_relative_to(base.resolve()):
        raise ObservationBundleError(f"path escapes its evidence root: {value!r}")
    if must_exist and not resolved.exists():
        raise ObservationBundleError(f"required evidence is missing: {value!r}")
    return resolved


def _parse_evidence_specs(specifications: Sequence[str]) -> list[tuple[str, str]]:
    """Parse explicit role=path lines and reject unsupported evidence roles."""
    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_line in specifications:
        line = raw_line.strip()
        if not line:
            continue
        role, separator, relative_path = line.partition("=")
        role = role.strip()
        relative_path = relative_path.strip()
        if not separator or role not in ROLE_SUFFIXES or not relative_path:
            raise ObservationBundleError(
                "evidence entries must use an allowed role=relative/path form"
            )
        path = PurePosixPath(relative_path)
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or "\\" in relative_path
        ):
            raise ObservationBundleError(f"unsafe evidence path: {relative_path!r}")
        normalized_path = path.as_posix()
        if normalized_path in seen:
            raise ObservationBundleError(f"duplicate evidence path: {normalized_path!r}")
        if path.suffix.lower() not in ROLE_SUFFIXES[role]:
            raise ObservationBundleError(
                f"unsupported evidence extension for role {role!r}: {normalized_path!r}"
            )
        seen.add(normalized_path)
        parsed.append((role, normalized_path))

    if not parsed:
        raise ObservationBundleError("at least one explicit evidence file is required")
    if len(parsed) > MAX_EVIDENCE_FILES:
        raise ObservationBundleError(
            f"evidence count exceeds the {MAX_EVIDENCE_FILES}-file limit"
        )
    return parsed


def _sha256(path: Path) -> str:
    """Hash a file incrementally to keep peak memory usage small."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_type(path: Path) -> str:
    """Return a stable content type for common FreeCAD evidence files."""
    known = {
        ".fcstd": "application/x-freecad-document",
        ".stl": "model/stl",
        ".obj": "model/obj",
        ".step": "model/step",
        ".stp": "model/step",
        ".brep": "model/brep",
    }
    return (
        known.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )


def _integer_or_none(value: str | None) -> int | None:
    """Convert an optional integer context field without failing the export."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _pull_request_number(environment: Mapping[str, str]) -> int | None:
    """Read only the pull-request number from the GitHub event payload."""
    event_path = environment.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return None
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return None
    number = pull_request.get("number")
    return number if isinstance(number, int) and number > 0 else None


def create_observation_bundle(
    workspace: Path,
    observation_root: str,
    specifications: Sequence[str],
    label: str,
    environment: Mapping[str, str],
) -> dict[str, object]:
    """Write the observation manifest and return its schema-versioned payload."""
    workspace = workspace.resolve()
    root = _resolve_relative_path(workspace, observation_root, must_exist=True)
    if not root.is_dir():
        raise ObservationBundleError("observation-root must be an existing directory")

    output = _resolve_relative_path(root, "agent-observation.json", must_exist=False)
    if len(label) > 160 or "\n" in label or "\r" in label:
        raise ObservationBundleError(
            "observation-label must be a single line of at most 160 characters"
        )

    parsed = _parse_evidence_specs(specifications)
    resolved_evidence: list[tuple[str, str, Path, int]] = []
    total_bytes = 0
    for role, relative_path in parsed:
        path = _resolve_relative_path(root, relative_path, must_exist=True)
        if path == output or not path.is_file():
            raise ObservationBundleError(f"evidence must be a regular file: {relative_path!r}")
        size_bytes = path.stat().st_size
        if size_bytes > MAX_EVIDENCE_FILE_BYTES:
            raise ObservationBundleError(
                f"evidence file exceeds {MAX_EVIDENCE_FILE_BYTES} bytes: {relative_path!r}"
            )
        total_bytes += size_bytes
        resolved_evidence.append((role, relative_path, path, size_bytes))

    if total_bytes > MAX_EVIDENCE_BYTES:
        raise ObservationBundleError(
            f"selected evidence totals {total_bytes} bytes; limit is {MAX_EVIDENCE_BYTES}"
        )

    evidence: list[dict[str, object]] = []
    for role, relative_path, path, size_bytes in resolved_evidence:
        evidence.append(
            {
                "role": role,
                "path": relative_path,
                "media_type": _media_type(path),
                "size_bytes": size_bytes,
                "sha256": _sha256(path),
            }
        )

    repository = environment.get("GITHUB_REPOSITORY") or None
    run_id = environment.get("GITHUB_RUN_ID") or None
    run_url = (
        f"https://github.com/{repository}/actions/runs/{run_id}"
        if repository and run_id
        else None
    )
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "label": label.strip() or None,
        "context": {
            "repository": repository,
            "commit_sha": environment.get("CLOTH_HEAD_SHA") or environment.get("GITHUB_SHA") or None,
            "workflow": environment.get("GITHUB_WORKFLOW") or None,
            "job": environment.get("GITHUB_JOB") or None,
            "event_name": environment.get("GITHUB_EVENT_NAME") or None,
            "run_id": _integer_or_none(run_id),
            "run_attempt": _integer_or_none(environment.get("GITHUB_RUN_ATTEMPT")),
            "run_url": run_url,
            "pull_request_number": _pull_request_number(environment),
        },
        "execution": {
            "runner_os": environment.get("RUNNER_OS") or None,
            "runner_arch": environment.get("RUNNER_ARCH") or None,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "container_image": environment.get("OBSERVATION_IMAGE") or None,
            "test_script": environment.get("OBSERVATION_TEST_SCRIPT") or None,
            "simulation_backend": environment.get("CLOTH_SIMULATION_BACKEND") or None,
        },
        "evidence": evidence,
    }
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    """Generate an observation manifest when the opt-in action inputs are configured."""
    environment = os.environ
    if not environment.get("OBSERVATION_ARTIFACT_NAME", "").strip():
        print("agent observation export requires artifact-name to be set", file=sys.stderr)
        return 2

    try:
        create_observation_bundle(
            workspace=Path.cwd(),
            observation_root=environment.get("OBSERVATION_ROOT", "artifacts"),
            specifications=environment.get("OBSERVATION_FILES", "").replace(";", "\n").splitlines(),
            label=environment.get("OBSERVATION_LABEL", ""),
            environment=environment,
        )
    except (ObservationBundleError, OSError) as exc:
        print(f"agent observation export failed: {exc}", file=sys.stderr)
        return 2

    count = sum(
        bool(line.strip())
        for line in environment.get("OBSERVATION_FILES", "").replace(";", "\n").splitlines()
    )
    print(
        "agent-observation=written "
        "path=agent-observation.json "
        f"evidence={count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
