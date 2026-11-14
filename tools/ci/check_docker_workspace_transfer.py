"""Verify Docker can transfer checked-out workspace files into and out of a container."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

IMAGE = "busybox:1.36.1"
CommandRunner = Callable[[list[str], bool, int], int]


def _run_command(command: list[str], check: bool, timeout: int) -> int:
    """Execute one bounded Docker command and return its exit status."""
    return subprocess.run(command, check=check, timeout=timeout).returncode


def should_run_probe(runner_mode: str, event_name: str) -> bool:
    """Run the workspace probe only for events assigned to the local runner."""
    return runner_mode == "local" and event_name in {
        "push",
        "pull_request",
        "workflow_dispatch",
        "schedule",
        "merge_group",
    }


def validate_workspace_transfer(
    workspace: Path,
    run_id: str,
    run_command: CommandRunner = _run_command,
) -> None:
    """Verify Docker can copy workspace files into and out of a temporary container.

    Args:
        workspace: Checked-out workspace containing temporary marker files.
        run_id: Workflow run identifier used to create a unique container name.
        run_command: Optional command runner used by deterministic tests.

    Raises:
        FileNotFoundError: If the container does not return the expected marker.
        RuntimeError: If the returned marker differs from the host marker.
    """
    run_command(["docker", "info"], True, 20)
    image_status = run_command(["docker", "image", "inspect", IMAGE], False, 10)
    if image_status != 0:
        run_command(["docker", "pull", IMAGE], True, 20)

    container_name = f"cloth-workspace-transfer-{run_id}-{os.getpid()}"
    marker = f"runner-workspace-transfer-{run_id}"
    created = False
    with tempfile.TemporaryDirectory(
        prefix=".docker-workspace-probe.", dir=workspace
    ) as temporary_directory:
        probe_directory = Path(temporary_directory)
        host_marker = probe_directory / "host-marker"
        returned_marker = probe_directory / "container-marker"
        host_marker.write_text(marker, encoding="utf-8")
        container_script = (
            'test "$(cat /tmp/host-marker)" = "$1"; '
            'printf "%s" "$1" > /tmp/container-marker'
        )
        run_command(
            [
                "docker",
                "create",
                "--name",
                container_name,
                IMAGE,
                "sh",
                "-ec",
                container_script,
                "sh",
                marker,
            ],
            True,
            20,
        )
        created = True
        try:
            run_command(
                ["docker", "cp", str(host_marker), f"{container_name}:/tmp/host-marker"],
                True,
                15,
            )
            run_command(["docker", "start", "--attach", container_name], True, 15)
            run_command(
                [
                    "docker",
                    "cp",
                    f"{container_name}:/tmp/container-marker",
                    str(returned_marker),
                ],
                True,
                15,
            )
            response = returned_marker.read_text(encoding="utf-8")
            if response != marker:
                raise RuntimeError("Docker workspace transfer did not preserve marker contents")
        finally:
            if created:
                run_command(["docker", "rm", "--force", container_name], False, 10)

    print("docker-workspace-transfer=ready")


def main() -> int:
    """Run the transfer check only for local-first trusted workflow executions."""
    runner_mode = os.environ.get("CLOTH_CI_RUNNER_MODE", "local")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if not should_run_probe(runner_mode, event_name):
        print(f"docker-workspace-transfer=skipped runner_mode={runner_mode}")
        return 0
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    validate_workspace_transfer(workspace, os.environ.get("GITHUB_RUN_ID", "local"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
