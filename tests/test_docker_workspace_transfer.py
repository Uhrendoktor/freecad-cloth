"""Tests for the Docker workspace copy-in/copy-out preflight."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci import check_docker_workspace_transfer


def test_probe_copies_workspace_files_into_and_out_of_container(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    container_files: dict[str, str] = {}

    def fake_run(command: list[str], check: bool, timeout: int) -> int:
        commands.append(command)
        assert timeout > 0
        if command[1] == "info":
            assert check
            return 0
        if command[1:3] == ["image", "inspect"]:
            assert not check
            return 1
        if command[1] == "create":
            assert check
            return 0
        if command[1] == "cp":
            assert check
            source, destination = command[2], command[3]
            if destination.endswith(":/tmp/host-marker"):
                container_files["host-marker"] = Path(source).read_text(encoding="utf-8")
            else:
                assert source.endswith(":/tmp/container-marker")
                Path(destination).write_text(
                    container_files["container-marker"], encoding="utf-8"
                )
        if command[1] == "start":
            assert check
            assert container_files["host-marker"] == "runner-workspace-transfer-test-run"
            container_files["container-marker"] = container_files["host-marker"]
        return 0

    check_docker_workspace_transfer.validate_workspace_transfer(
        tmp_path, "test-run", run_command=fake_run
    )

    assert commands[0][:2] == ["docker", "info"]
    assert commands[2][1] == "create"
    assert commands[3][:2] == ["docker", "cp"]
    assert commands[4][:3] == ["docker", "start", "--attach"]
    assert commands[5][:2] == ["docker", "cp"]
    assert commands[6][:3] == ["docker", "rm", "--force"]
    assert all("--mount" not in command for command in commands)
    assert not list(tmp_path.glob(".docker-workspace-probe.*"))


def test_probe_fails_when_container_does_not_return_the_marker(tmp_path: Path) -> None:
    def successful_without_response(command: list[str], check: bool, timeout: int) -> int:
        assert timeout > 0
        return 0

    with pytest.raises(FileNotFoundError, match="container-marker"):
        check_docker_workspace_transfer.validate_workspace_transfer(
            tmp_path, "test-run", run_command=successful_without_response
        )


def test_probe_runs_only_for_trusted_local_events() -> None:
    should_run = check_docker_workspace_transfer.should_run_probe
    assert should_run("local", "push")
    assert should_run("local", "pull_request")
    assert should_run("local", "workflow_dispatch")
    assert should_run("local", "schedule")
    assert should_run("local", "merge_group")
    assert not should_run("local", "workflow_run")
    assert not should_run("hosted", "workflow_dispatch")
