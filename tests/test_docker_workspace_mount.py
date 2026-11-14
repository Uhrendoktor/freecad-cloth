"""Tests for the Docker workspace bind-mount preflight."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci import check_docker_workspace_mount


def test_probe_pulls_its_small_image_and_checks_bidirectional_access(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], check: bool, timeout: int) -> int:
        commands.append(command)
        assert timeout > 0
        if command[1] == "info":
            assert check
            return 0
        if command[1:3] == ["image", "inspect"]:
            assert not check
            return 1
        if command[1] == "run":
            assert check
            mount = command[command.index("--mount") + 1]
            source = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            assert (source / "host-marker").read_text(encoding="utf-8") == (
                "runner-bind-mount-test-run"
            )
            (source / "container-marker").write_text(
                "runner-bind-mount-test-run", encoding="utf-8"
            )
        return 0

    check_docker_workspace_mount.validate_workspace_mount(
        tmp_path, "test-run", run_command=fake_run
    )

    assert commands[0][:2] == ["docker", "info"]
    assert commands[2][:3] == ["docker", "pull", "busybox:1.36.1"]
    assert commands[3][1] == "run"
    assert commands[3][commands[3].index("--mount") + 1].endswith(",target=/probe")
    assert not list(tmp_path.glob(".docker-workspace-probe.*"))


def test_probe_fails_when_container_cannot_write_back(tmp_path: Path) -> None:
    def successful_but_read_only(command: list[str], check: bool, timeout: int) -> int:
        assert timeout > 0
        return 0

    with pytest.raises(FileNotFoundError, match="container-marker"):
        check_docker_workspace_mount.validate_workspace_mount(
            tmp_path, "test-run", run_command=successful_but_read_only
        )


def test_probe_runs_only_for_trusted_local_events() -> None:
    should_run = check_docker_workspace_mount.should_run_probe
    assert should_run("local", "push")
    assert should_run("local", "pull_request")
    assert should_run("local", "workflow_dispatch")
    assert should_run("local", "schedule")
    assert should_run("local", "merge_group")
    assert not should_run("local", "workflow_run")
    assert not should_run("hosted", "workflow_dispatch")
