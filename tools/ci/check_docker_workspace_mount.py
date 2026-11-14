"""Verify Docker can read and write a bind mount of the checked-out workspace."""

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
    """Run only on trusted local-first events, never on pull requests."""
    return runner_mode == "local" and event_name != "pull_request"


def validate_workspace_mount(
    workspace: Path,
    run_id: str,
    run_command: CommandRunner = _run_command,
) -> None:
    """Check Docker is usable and the runner workspace is visible and writable."""
    run_command(["docker", "info"], True, 20)
    image_status = run_command(["docker", "image", "inspect", IMAGE], False, 10)
    if image_status != 0:
        run_command(["docker", "pull", IMAGE], True, 20)

    marker = f"runner-bind-mount-{run_id}"
    with tempfile.TemporaryDirectory(
        prefix=".docker-workspace-probe.", dir=workspace
    ) as temporary_directory:
        probe_directory = Path(temporary_directory)
        (probe_directory / "host-marker").write_text(marker, encoding="utf-8")
        container_script = (
            'test "$(cat /probe/host-marker)" = "$1"; printf "%s\\n" "$1" > /probe/container-marker'
        )
        run_command(
            [
                "docker",
                "run",
                "--rm",
                "--mount",
                f"type=bind,source={probe_directory},target=/probe",
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
        container_marker = (probe_directory / "container-marker").read_text(encoding="utf-8")
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
    validate_workspace_mount(workspace, os.environ.get("GITHUB_RUN_ID", "local"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
