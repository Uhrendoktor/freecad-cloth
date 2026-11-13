# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run strict repository checks in the pinned FreeCAD/PBD Python runtime."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from tools.ci.command_runner import (
        CommandExecutionError,
        CommandOptions,
        CommandTimeoutError,
        run_command,
    )
else:
    from command_runner import (
        CommandExecutionError,
        CommandOptions,
        CommandTimeoutError,
        run_command,
    )

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_VERSION = "freecad-quality-v1"
INSTALL_TIMEOUT_SECONDS = 900
PRE_COMMIT_TIMEOUT_SECONDS = 120
PIP_READ_TIMEOUT_SECONDS = 300
PIP_RETRY_COUNT = 10
PIP_RESUME_RETRY_COUNT = 10
CPU_TORCH_REQUIREMENT = "torch==2.8.0+cpu"
PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def quality_install_command(python: Path) -> tuple[str, ...]:
    """Build the pinned developer install command with resilient package-download timeouts.

    Args:
        python: Interpreter inside the persistent FreeCAD-aware virtual environment.

    Returns:
        Shell-free pip arguments for the unchanged CPU Torch and development requirements.
    """
    return (
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--timeout",
        str(PIP_READ_TIMEOUT_SECONDS),
        "--retries",
        str(PIP_RETRY_COUNT),
        "--resume-retries",
        str(PIP_RESUME_RETRY_COUNT),
        "--extra-index-url",
        PYTORCH_CPU_INDEX,
        CPU_TORCH_REQUIREMENT,
        "-e",
        ".[dev]",
    )


REQUIRED_RUNTIME_MODULES = (
    "FreeCAD",
    "FreeCADGui",
    "Mesh",
    "MeshPart",
    "Part",
    "Sketcher",
    "PySide.QtCore",
    "PySide.QtWidgets",
    "pivy.coin",
    "pypbd",
    "anny",
    "anny.paths",
    "clad_body.load.anny",
    "clad_body.measure",
    "triangle",
    "matplotlib.pyplot",
    "vulture.core",
)


@dataclass(frozen=True)
class QualityCommand:
    """Represent one independently reported quality check.

    Attributes:
        label: Human-readable category displayed in the Actions log.
        arguments: Executable and arguments passed directly to the process runner.
        timeout_seconds: Optional upper bound for this command.
    """

    label: str
    arguments: tuple[str, ...]
    timeout_seconds: int | None = None


def build_environment_cache_key(
    project_file: Path,
    python_version: str,
    image_id: str,
    workspace_key: str,
) -> str:
    """Build a deterministic dependency and runtime key for a cached virtual environment.

    Args:
        project_file: Project dependency manifest used to install strict-quality tools.
        python_version: Major/minor version of the FreeCAD Python interpreter.
        image_id: Immutable local Docker image ID containing native host modules.
        workspace_key: Stable hash of the persistent runner's workspace path.

    Returns:
        Twenty hexadecimal characters identifying the reusable environment.
    """
    digest = hashlib.sha256()
    digest.update(project_file.read_bytes())
    digest.update(ENVIRONMENT_VERSION.encode("utf-8"))
    digest.update(python_version.encode("utf-8"))
    digest.update(image_id.encode("utf-8"))
    digest.update(workspace_key.encode("utf-8"))
    return digest.hexdigest()[:20]


def ready_marker_is_current(environment: Path, cache_key: str) -> bool:
    """Require the exact completion marker before reusing an installed environment.

    Args:
        environment: Directory containing the persistent virtual environment.
        cache_key: Dependency/runtime key expected for the current source tree.

    Returns:
        True only when the marker records the requested key exactly.
    """
    try:
        marker = (environment / ".ready").read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return marker == cache_key


def _run_setup(arguments: tuple[str, ...], timeout_seconds: int) -> None:
    """Run one bounded environment setup command through the shell-free runner.

    Args:
        arguments: Executable and argument vector passed to the process runner.
        timeout_seconds: Maximum time allowed for the setup operation.

    Raises:
        RuntimeError: If the command cannot start, fails, or exceeds its time bound.
    """
    try:
        run_command(
            arguments,
            options=CommandOptions(cwd=ROOT, timeout=timeout_seconds),
        )
    except (CommandExecutionError, CommandTimeoutError, OSError) as error:
        msg = f"Setup command failed: {arguments[0]}: {error}"
        raise RuntimeError(msg) from error


def _verify_runtime(python: Path) -> None:
    """Import required native host modules and developer tools before cache reuse.

    Args:
        python: Interpreter inside the persistent virtual environment.

    """
    modules = (*REQUIRED_RUNTIME_MODULES, "pre_commit", "ruff", "pyright")
    probe = "import importlib, sys; [importlib.import_module(name) for name in sys.argv[1:]]"
    _run_setup((str(python), "-c", probe, *modules), timeout_seconds=45)


def prepare_quality_environment(
    cache_root: Path,
    image_id: str,
    workspace_key: str,
) -> Path:
    """Create or resume a FreeCAD-aware venv whose packages are retained on the host.

    Args:
        cache_root: Persistent runner cache root mounted into the FreeCAD container.
        image_id: Immutable PBD/FreeCAD image identifier used as part of the cache key.
        workspace_key: Stable identity for the persistent checkout workspace.

    Returns:
        Interpreter path for the ready strict-quality environment.

    """
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    project_file = ROOT / "pyproject.toml"
    cache_key = build_environment_cache_key(project_file, python_version, image_id, workspace_key)
    environment = cache_root / "venvs" / f"quality-{python_version}-{cache_key}-{workspace_key}"
    python = environment / "bin" / "python"
    environment.parent.mkdir(parents=True, exist_ok=True)
    if not python.is_file():
        _run_setup(
            (sys.executable, "-m", "venv", "--system-site-packages", str(environment)),
            timeout_seconds=30,
        )

    if not ready_marker_is_current(environment, cache_key):
        sys.stdout.write(f"python-quality-cache=installing key={cache_key}\n")
        sys.stdout.flush()
        _run_setup(
            quality_install_command(python),
            timeout_seconds=INSTALL_TIMEOUT_SECONDS,
        )

    _run_setup((str(python), "-m", "pip", "check"), timeout_seconds=45)
    _verify_runtime(python)
    if not ready_marker_is_current(environment, cache_key):
        temporary_marker = environment / ".ready.tmp"
        temporary_marker.write_text(f"{cache_key}\n", encoding="utf-8")
        temporary_marker.replace(environment / ".ready")
        sys.stdout.write(f"python-quality-cache=ready key={cache_key}\n")
        sys.stdout.flush()
    else:
        sys.stdout.write(f"python-quality-cache=hit key={cache_key}\n")
        sys.stdout.flush()
    return python


def collect_tracked_python_files(root: Path) -> tuple[str, ...]:
    """List every tracked Python source and stub file in repository order.

    Args:
        root: Git work-tree root used for path enumeration.

    Returns:
        Relative paths to tracked .py and .pyi files.

    """
    result = run_command(
        ("git", "ls-files", "-z", "--", "*.py", "*.pyi"),
        options=CommandOptions(cwd=root, capture_output=True, timeout=30),
    )
    return tuple(path for path in (result.stdout or "").split("\0") if path)


def quality_commands(python: Path, tracked_files: tuple[str, ...]) -> tuple[QualityCommand, ...]:
    """Build the complete independent static-quality command inventory.

    Args:
        python: Python executable in the persistent FreeCAD-aware virtual environment.
        tracked_files: All Git-tracked Python sources and stubs.

    Returns:
        Required architecture, typing, lint, documentation, and workflow commands.
    """
    executable = str(python)
    return (
        QualityCommand(
            "Python compilation", (executable, "-m", "compileall", "-q", "tests", "tools/ci")
        ),
        QualityCommand(
            "Focused migration regression tests",
            (
                executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_avatar_arrangement_contract.py",
                (
                    "tests/test_ci_configuration.py::"
                    "test_ruff_covers_every_tracked_python_file_without_auto_fixing"
                ),
                (
                    "tests/test_ci_configuration.py::"
                    "test_pyright_uses_the_reviewed_staged_production_inventory"
                ),
                (
                    "tests/test_ci_configuration.py::"
                    "test_new_python_modules_must_be_explicitly_reviewed_for_pyright"
                ),
                ("tests/test_ci_configuration.py::test_ty_warning_diagnostics_remain_blocking"),
                "tests/test_avatar_service_contract.py",
                "tests/test_changed_python_types.py",
                "tests/test_command_runner.py",
                "tests/test_documentation_contract.py",
                "tests/test_explicit_any_annotations.py",
                "tests/test_garment_document_contract.py",
                "tests/test_no_source_rewriting.py",
                "tests/test_pydantic_models_policy.py",
                "tests/test_sewing_creation_session.py",
                "tests/test_strict_quality_runner_contract.py",
            ),
            timeout_seconds=120,
        ),
        QualityCommand("Markdown contract", (executable, "tools/check_markdown_contract.py")),
        QualityCommand("CI structure", (executable, "tools/ci/validate_ci_structure.py")),
        QualityCommand("Import architecture", ("lint-imports",)),
        QualityCommand(
            "Source-rewriting policy", (executable, "tools/ci/check_no_source_rewriting.py")
        ),
        QualityCommand(
            "Explicit Any policy", (executable, "tools/ci/check_explicit_any_annotations.py")
        ),
        QualityCommand("Pydantic model policy", (executable, "tools/ci/check_pydantic_models.py")),
        QualityCommand("Pyright production inventory", ("pyright", "-p", "pyrightconfig.json")),
        QualityCommand(
            "Typed simulation core",
            (
                "ty",
                "check",
                "--output-format",
                "github",
                "freecad_cloth/simulation/DrapeFailureClassifier.py",
                "freecad_cloth/simulation/cloth_backend.py",
                "freecad_cloth/simulation/ClothSolver.py",
            ),
        ),
        QualityCommand(
            "Changed Python annotation ratchet",
            (executable, "tools/ci/check_changed_python_types.py"),
        ),
        QualityCommand(
            "AST-grep rule tests", ("ast-grep", "test", "--skip-snapshot-tests", "--color", "never")
        ),
        QualityCommand(
            "AST-grep repository contracts",
            ("ast-grep", "scan", "--min-severity", "error", "--color", "never", "freecad_cloth"),
        ),
        QualityCommand("Dead-code contract", (executable, "tools/check_dead_code.py")),
        QualityCommand(
            "CrossHair contracts",
            (
                "crosshair",
                "check",
                "--analysis_kind",
                "asserts",
                "--per_path_timeout",
                "15",
                "--per_condition_timeout",
                "10",
                "tools/crosshair_contracts.py",
            ),
        ),
        QualityCommand(
            "Pre-commit actionlint",
            (executable, "-m", "pre_commit", "run", "--all-files", "actionlint"),
            PRE_COMMIT_TIMEOUT_SECONDS,
        ),
        QualityCommand(
            "Pre-commit zizmor",
            (executable, "-m", "pre_commit", "run", "--all-files", "zizmor"),
            PRE_COMMIT_TIMEOUT_SECONDS,
        ),
        QualityCommand(
            "Pre-commit yamllint",
            (executable, "-m", "pre_commit", "run", "--all-files", "yamllint"),
            PRE_COMMIT_TIMEOUT_SECONDS,
        ),
        QualityCommand(
            "Python documentation contract", (executable, "tools/check_documentation_contract.py")
        ),
        QualityCommand(
            "Ruff format", (executable, "-m", "ruff", "format", "--check", *tracked_files)
        ),
        QualityCommand("Ruff lint", (executable, "-m", "ruff", "check", *tracked_files)),
    )


def run_quality_commands(commands: tuple[QualityCommand, ...]) -> int:
    """Run every required quality check and return an aggregate failure status.

    Args:
        commands: Independent strict-quality commands required by CI.

    Returns:
        Zero only when every command succeeds; otherwise one.
    """
    failed = 0
    environment = os.environ.copy()
    for command in commands:
        sys.stdout.write(f"::group::Strict quality: {command.label}\n")
        sys.stdout.flush()
        try:
            result = run_command(
                command.arguments,
                options=CommandOptions(
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    timeout=command.timeout_seconds,
                ),
            )
            if result.returncode:
                sys.stdout.write(
                    f"::error::{command.label} failed with exit code {result.returncode}\n"
                )
                sys.stdout.flush()
                failed = 1
        except CommandTimeoutError:
            sys.stdout.write(f"::error::{command.label} timed out\n")
            sys.stdout.flush()
            failed = 1
        except CommandExecutionError as error:
            sys.stdout.write(f"::error::{command.label} could not execute: {error}\n")
            sys.stdout.flush()
            failed = 1
        except OSError as error:
            sys.stdout.write(f"::error::{command.label} could not start: {error}\n")
            sys.stdout.flush()
            failed = 1
        sys.stdout.write("::endgroup::\n")
        sys.stdout.flush()
    return failed


def _run_repository_quality() -> int:
    """Prepare the pinned runtime and execute every independent strict-quality check.

    Returns:
        Zero only when the environment is ready and every required check succeeds.
    """
    cache_root = Path(os.environ["RUNNER_TOOL_CACHE"])
    image_id = os.environ["QUALITY_IMAGE_ID"]
    workspace_key = os.environ["WORKSPACE_CACHE_KEY"]
    python = prepare_quality_environment(cache_root, image_id, workspace_key)
    tracked_files = collect_tracked_python_files(ROOT)
    if not tracked_files:
        sys.stderr.write("::error::Git reported no tracked Python sources or stubs.\n")
        sys.stderr.flush()
        return 1
    _run_setup(
        ("git", "config", "--global", "--add", "safe.directory", str(ROOT)),
        timeout_seconds=10,
    )
    os.environ["PATH"] = str(python.parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
    return run_quality_commands(quality_commands(python, tracked_files))


def main() -> int:
    """Prepare the environment and return the aggregate strict-quality status.

    Returns:
        Zero only when environment setup and every required check succeeds.
    """
    try:
        return _run_repository_quality()
    except (KeyError, OSError, RuntimeError) as error:
        sys.stderr.write(f"::error::Strict quality environment failed: {error}\n")
        sys.stderr.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
