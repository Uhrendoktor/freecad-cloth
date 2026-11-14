"""Verify Docker can read and write a bind mount of the checked-out workspace."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

IMAGE = "busybox:1.36.1"
CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]


def validate_workspace_mount(
    workspace: Path,
    *,
    run: CommandRunner = subprocess.run,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Check Docker is usable and the runner workspace is visible and writable."""
    environment = os.environ if environ is None else environ
    run(["docker", "info"], check=True, timeout=20)
    image_check = run(["docker", "image", "inspect", IMAGE], check=False, timeout=10)
    if image_check.returncode != 0:
        run(["docker", "pull", IMAGE], check=True, timeout=20)

    marker = f"runner-bind-mount-{environment.get('GITHUB_RUN_ID', 'local')}"
    with tempfile.TemporaryDirectory(prefix=".docker-workspace-probe.", dir=workspace) as temporary_directory:
        probe_directory = Path(temporary_directory)
        (probe_directory / "host-marker").write_text(marker, encoding="utf-8")
        container_script = (
            'test "$(cat /probe/host-marker)" = "$1"; printf "%s\\n" "$1" > /probe/container-marker'
        )
        run(
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
            check=True,
            timeout=15,
        )
        container_marker = (probe_directory / "container-marker").read_text(encoding="utf-8")
        if container_marker != marker:
            raise RuntimeError("Docker workspace bind mount did not preserve write access")

    print("docker-workspace-bind-mount=ready")


def main(
    *,
    environ: Mapping[str, str] | None = None,
    run: CommandRunner = subprocess.run,
) -> int:
    """Run the mount check only for local-first trusted workflow executions."""
    environment = os.environ if environ is None else environ
    runner_mode = environment.get("CLOTH_CI_RUNNER_MODE", "local")
    event_name = environment.get("GITHUB_EVENT_NAME", "")
    if runner_mode != "local" or event_name == "pull_request":
        print(f"docker-workspace-bind-mount=skipped runner_mode={runner_mode}")
        return 0
    workspace = Path(environment["GITHUB_WORKSPACE"])
    validate_workspace_mount(workspace, run=run, environ=environment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
