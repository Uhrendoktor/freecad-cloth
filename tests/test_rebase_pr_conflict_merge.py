"""Tests for the guarded rebase Pyright conflict resolver."""

from __future__ import annotations

import pytest

from tools.ci.rebase_pr_branch import merge_pyright_config


def test_merge_pyright_config_keeps_main_settings_and_unions_path_lists() -> None:
    """Keep main-side strict coverage while including paths required by the PR."""
    ours: dict[str, object] = {
        "include": ["main.py", "shared", "same.py"],
        "exclude": ["gui.py"],
        "strict": ["main_strict.py"],
        "typeCheckingMode": "standard",
    }
    theirs: dict[str, object] = {
        "include": ["pr.py", "same.py"],
        "exclude": ["tests.py"],
        "strict": ["pr_strict.py", "main_strict.py"],
        "typeCheckingMode": "basic",
        "pythonVersion": "3.12",
    }

    merged = merge_pyright_config(ours, theirs)

    assert merged["include"] == ["main.py", "shared", "same.py", "pr.py"]
    assert merged["exclude"] == ["gui.py", "tests.py"]
    assert merged["strict"] == ["main_strict.py", "pr_strict.py"]
    assert merged["typeCheckingMode"] == "standard"
    assert merged["pythonVersion"] == "3.12"


def test_merge_pyright_config_rejects_non_string_list_entries() -> None:
    """Fail closed if the path-list format changes unexpectedly."""
    with pytest.raises(ValueError, match="string entries"):
        merge_pyright_config({"include": ["main.py"]}, {"include": [12]})  # type: ignore[list-item]


def test_merge_pyright_config_preserves_base_lists_when_pr_has_no_strict_key() -> None:
    """The PR's legacy config cannot erase new strict targets added on main."""
    ours: dict[str, object] = {
        "include": ["main.py"],
        "strict": ["strict.py"],
    }
    theirs: dict[str, object] = {"include": ["AnnyAvatarBackend.py"]}

    merged = merge_pyright_config(ours, theirs)

    assert merged["include"] == ["main.py", "AnnyAvatarBackend.py"]
    assert merged["strict"] == ["strict.py"]
