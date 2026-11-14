"""Tests for the Docker workspace bind-mount preflight."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci import check_docker_workspace_mount


def test_probe_uses_runner_host_mount_and_checks_bidirectional_access(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "runner-workspace"
    workspace.mkdir()
    host_workspace = tmp_path / "host-workspace"
    host_workspace.mkdir()
    commands: list[list[str]] = []

    def fake_inspect(container_id: str) -> list[dict[str, str]]:
        assert container_id == "runner-container"
        return [
            {
                "Source": str(host_workspace),
                "Destination": str(workspace),
            }
        ]

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
            host_probe = Path(
                mount.split("source=", 1)[1].split(",target=", 1)[0]
            )
            relative_probe = host_probe.relative_to(host_workspace)
            runner_probe = workspace / relative_probe
            assert (runner_probe / "host-marker").read_text(encoding="utf-8") == (
                "runner-bind-mount-test-run"
            )
            (runner_probe / "container-marker").write_text(
                "runner-bind-mount-test-run", encoding="utf-8"
            )
        return 0

    check_docker_workspace_mount.validate_workspace_mount(
        workspace,
        "test-run",
        "runner-container",
        run_command=fake_run,
        mount_inspector=fake_inspect,
    )

    assert commands[0][:2] == ["docker", "info"]
    assert commands[2][:3] == ["docker", "pull", "busybox:1.36.1"]
    assert commands[3][1] == "run"
    assert not list(workspace.glob(".docker-workspace-probe.*"))


def test_workspace_path_uses_the_most_specific_runner_mount() -> None:
    workspace = Path("/_work/runner/repo")
    mounts = [
        {"Source": "/host/work", "Destination": "/_work"},
        {"Source": "/host/specific", "Destination": "/_work/runner"},
    ]

    host_path = check_docker_workspace_mount._host_workspace_path(workspace, mounts)

    assert host_path == Path("/host/specific/repo")


def test_workspace_path_fails_when_no_runner_mount_contains_it() -> None:
    with pytest.raises(RuntimeError, match="cannot map runner workspace"):
        check_docker_workspace_mount._host_workspace_path(
            Path("/_work/runner/repo"),
            [{"Source": "/host/work", "Destination": "/other"}],
        )


def test_probe_fails_when_container_cannot_write_back(tmp_path: Path) -> None:
    workspace = tmp_path / "runner-workspace"
    workspace.mkdir()

    def fake_inspect(_container_id: str) -> list[dict[str, str]]:
        return [
            {
                "Source": str(workspace),
                "Destination": str(workspace),
            }
        ]

    def successful_but_read_only(command: list[str], check: bool, timeout: int) -> int:
        assert timeout > 0
        return 0

    with pytest.raises(FileNotFoundError, match="container-marker"):
        check_docker_workspace_mount.validate_workspace_mount(
            workspace,
            "test-run",
            "runner-container",
            run_command=successful_but_read_only,
            mount_inspector=fake_inspect,
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
