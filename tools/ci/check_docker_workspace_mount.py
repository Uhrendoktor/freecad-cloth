"""Verify Docker can read and write a bind mount of the checked-out workspace."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

IMAGE = "busybox:1.36.1"
CommandRunner = Callable[[list[str], bool, int], int]
MountInspector = Callable[[str], list[Mapping[str, str]]]


def _run_command(command: list[str], check: bool, timeout: int) -> int:
    """Execute one bounded Docker command and return its exit status."""
    return subprocess.run(command, check=check, timeout=timeout).returncode


def _runner_mounts(container_id: str) -> list[Mapping[str, str]]:
    """Read the runner container's mount table from the Docker daemon.

    Args:
        container_id: Docker-visible name or ID of the current runner container.

    Returns:
        Mount source and destination pairs reported by Docker.

    Raises:
        RuntimeError: If Docker cannot inspect the container or returns malformed metadata.
    """
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Mounts}}", container_id],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip().replace("\n", " ")[:240]
        msg = f"Docker could not inspect runner container {container_id!r}: {detail}"
        raise RuntimeError(msg)
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        msg = "Docker did not return a mount list for the runner container"
        raise RuntimeError(msg)
    mounts: list[Mapping[str, str]] = []
    for mount in payload:
        if not isinstance(mount, dict):
            msg = "Docker returned a malformed runner mount"
            raise RuntimeError(msg)
        source, destination = mount.get("Source"), mount.get("Destination")
        if isinstance(source, str) and isinstance(destination, str):
            mounts.append({"Source": source, "Destination": destination})
    return mounts


def _host_workspace_path(
    workspace: Path,
    mounts: list[Mapping[str, str]],
) -> Path:
    """Translate a runner-container workspace path to its Docker-host path.

    Args:
        workspace: Absolute workspace path visible inside the runner container.
        mounts: Mount source/destination pairs reported by Docker.

    Returns:
        The host-side path that addresses the same workspace directory.

    Raises:
        RuntimeError: If no Docker mount contains the runner workspace.
    """
    matches: list[tuple[int, Path]] = []
    for mount in mounts:
        source = mount.get("Source")
        destination = mount.get("Destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            continue
        destination_path = Path(destination)
        try:
            relative_path = workspace.relative_to(destination_path)
        except ValueError:
            continue
        source_path = Path(source)
        if source_path.is_absolute():
            matches.append((len(destination_path.parts), source_path / relative_path))
    if not matches:
        msg = f"Docker cannot map runner workspace to a host mount: {workspace}"
        raise RuntimeError(msg)
    return max(matches, key=lambda match: match[0])[1]


def _runner_container_candidates(environment: Mapping[str, str]) -> list[str]:
    """Return unique Docker identifiers to try for the current runner container.

    Args:
        environment: Process environment containing runtime and runner names.

    Returns:
        Non-empty host/container identifiers, preferring the runtime hostname.
    """
    candidates = (environment.get("HOSTNAME", ""), environment.get("RUNNER_NAME", ""))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def should_run_probe(runner_mode: str, event_name: str) -> bool:
    """Run the workspace probe only for events assigned to the local runner."""
    return runner_mode == "local" and event_name in {
        "push",
        "pull_request",
        "workflow_dispatch",
        "schedule",
        "merge_group",
    }


def validate_workspace_mount(
    workspace: Path,
    run_id: str,
    runner_container: str,
    run_command: CommandRunner = _run_command,
    mount_inspector: MountInspector = _runner_mounts,
) -> None:
    """Check Docker can access the runner workspace in both directions.

    Args:
        workspace: Workspace path visible inside the self-hosted runner container.
        run_id: Current workflow run identifier used for the temporary marker.
        runner_container: Docker-visible name or ID of the current runner container.
        run_command: Optional command runner used by deterministic tests.
        mount_inspector: Optional runner mount-table loader used by deterministic tests.

    Raises:
        RuntimeError: If Docker cannot map the workspace to a host-side mount.
    """
    run_command(["docker", "info"], True, 20)
    image_status = run_command(["docker", "image", "inspect", IMAGE], False, 10)
    if image_status != 0:
        run_command(["docker", "pull", IMAGE], True, 20)

    host_workspace = _host_workspace_path(workspace, mount_inspector(runner_container))
    marker = f"runner-bind-mount-{run_id}"
    with tempfile.TemporaryDirectory(
        prefix=".docker-workspace-probe.", dir=workspace
    ) as temporary_directory:
        probe_directory = Path(temporary_directory)
        (probe_directory / "host-marker").write_text(marker, encoding="utf-8")
        host_probe_directory = host_workspace / probe_directory.relative_to(workspace)
        container_script = (
            'test "$(cat /probe/host-marker)" = "$1"; '
            'printf "%s" "$1" > /probe/container-marker'
        )
        run_command(
            [
                "docker",
                "run",
                "--rm",
                "--mount",
                f"type=bind,source={host_probe_directory},target=/probe",
                IMAGE,
                "sh",
                "-ec",
                container_script,
                "sh",
                marker,
            ],
            True,
            15,
        )
        container_marker = (probe_directory / "container-marker").read_text(
            encoding="utf-8"
        )
        if container_marker != marker:
            raise RuntimeError("Docker workspace bind mount did not preserve write access")

    print("docker-workspace-bind-mount=ready")


def main() -> int:
    """Run the mount check only for local-first trusted workflow executions."""
    runner_mode = os.environ.get("CLOTH_CI_RUNNER_MODE", "local")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if not should_run_probe(runner_mode, event_name):
        print(f"docker-workspace-bind-mount=skipped runner_mode={runner_mode}")
        return 0
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    candidates = _runner_container_candidates(os.environ)
    if not candidates:
        msg = "RUNNER_NAME and HOSTNAME are unavailable for Docker workspace inspection"
        raise RuntimeError(msg)

    failures: list[str] = []
    for runner_container in candidates:
        try:
            validate_workspace_mount(workspace, run_id, runner_container)
        except RuntimeError as exc:
            failures.append(f"{runner_container}: {exc}")
        else:
            return 0

    try:
        container_names = subprocess.run(
            ["docker", "ps", "--all", "--format", "{{.Names}}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        container_names = f"unavailable ({type(exc).__name__})"
    msg = (
        "Docker could not resolve the current runner's host workspace mount; "
        f"tried={', '.join(candidates)}; containers={container_names[:500]}; "
        f"failures={'; '.join(failures)}"
    )
    raise RuntimeError(msg)


if __name__ == "__main__":
    raise SystemExit(main())
