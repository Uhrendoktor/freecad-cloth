"""Tests for the Docker workspace bind-mount preflight."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.ci import check_docker_workspace_mount


def test_probe_pulls_its_small_image_and_checks_bidirectional_access(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], *, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        if command[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(command, 1)
        if command[1] == "run":
            mount = command[command.index("--mount") + 1]
            source = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            assert (source / "host-marker").read_text(
                encoding="utf-8"
            ) == "runner-bind-mount-test-run"
            (source / "container-marker").write_text("runner-bind-mount-test-run", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    check_docker_workspace_mount.validate_workspace_mount(
        tmp_path,
        run=fake_run,
        environ={"GITHUB_RUN_ID": "test-run"},
    )

    assert commands[0][:2] == ["docker", "info"]
    assert commands[1][:3] == ["docker", "image", "inspect"]
    assert commands[2][:3] == ["docker", "pull", "busybox:1.36.1"]
    assert commands[3][1] == "run"
    assert commands[3][commands[3].index("--mount") + 1].endswith(",target=/probe")
    assert not list(tmp_path.glob(".docker-workspace-probe.*"))


def test_main_skips_probe_for_hosted_runs(tmp_path: Path) -> None:
    def fail_if_called(
        command: list[str], *, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError(f"unexpected Docker command: {command}")

    environment = {
        "CLOTH_CI_RUNNER_MODE": "hosted",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_WORKSPACE": str(tmp_path),
    }
    assert check_docker_workspace_mount.main(environ=environment, run=fail_if_called) == 0


def test_probe_fails_when_container_cannot_write_back(tmp_path: Path) -> None:
    def fake_run(
        command: list[str], *, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 0)

    with pytest.raises(FileNotFoundError, match="container-marker"):
        check_docker_workspace_mount.validate_workspace_mount(
            tmp_path,
            run=fake_run,
            environ={"GITHUB_RUN_ID": "missing-write"},
        )
