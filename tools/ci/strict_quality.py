# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run strict repository checks in the pinned FreeCAD/PBD Python runtime."""

from __future__ import annotations

import hashlib
import importlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_VERSION = "freecad-quality-v1"
INSTALL_TIMEOUT_SECONDS = 180
PRE_COMMIT_TIMEOUT_SECONDS = 120
CPU_TORCH_REQUIREMENT = "torch==2.8.0+cpu"
PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
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
    """Run one bounded environment setup command.

    Args:
        arguments: Executable and argument vector passed to subprocess.run.
        timeout_seconds: Maximum time allowed for the setup operation.

    Raises:
        OSError: If the executable cannot be started.
        subprocess.CalledProcessError: If the setup command exits unsuccessfully.
        subprocess.TimeoutExpired: If the setup command exceeds its time bound.
    """
    subprocess.run(arguments, cwd=ROOT, check=True, timeout=timeout_seconds)


def _verify_runtime(python: Path) -> None:
    """Import native host modules and required developer tools before marking the cache ready.

    Args:
        python: Interpreter inside the persistent venv.

    Raises:
        subprocess.CalledProcessError: If any required runtime or tooling import is missing.
        subprocess.TimeoutExpired: If the import preflight exceeds its time bound.
    """
    modules = (*REQUIRED_RUNTIME_MODULES, "pre_commit", "ruff", "pyright")
    probe = "import importlib, sys; [importlib.import_module(name) for name in sys.argv[1:]]"
    subprocess.run((str(python), "-c", probe, *modules), cwd=ROOT, check=True, timeout=45)


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

    Raises:
        OSError: If the cache or virtual environment cannot be created.
        RuntimeError: If the container does not provide Python 3.12 or newer.
        subprocess.CalledProcessError: If installation or runtime verification fails.
        subprocess.TimeoutExpired: If bounded setup exceeds its time limit.
    """
    if sys.version_info < (3, 12):
        raise RuntimeError("Strict quality requires the Python 3.12 FreeCAD runtime.")
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
        print(f"python-quality-cache=installing key={cache_key}", flush=True)
        _run_setup(
            (
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--extra-index-url",
                PYTORCH_CPU_INDEX,
                CPU_TORCH_REQUIREMENT,
                "-e",
                ".[dev]",
            ),
            timeout_seconds=INSTALL_TIMEOUT_SECONDS,
        )

    _run_setup((str(python), "-m", "pip", "check"), timeout_seconds=45)
    _verify_runtime(python)
    if not ready_marker_is_current(environment, cache_key):
        temporary_marker = environment / ".ready.tmp"
        temporary_marker.write_text(f"{cache_key}\n", encoding="utf-8")
        os.replace(temporary_marker, environment / ".ready")
        print(f"python-quality-cache=ready key={cache_key}", flush=True)
    else:
        print(f"python-quality-cache=hit key={cache_key}", flush=True)
    return python


def collect_tracked_python_files(root: Path) -> tuple[str, ...]:
    """List every tracked Python source and stub file in repository order.

    Args:
        root: Git work-tree root used for path enumeration.

    Returns:
        Relative paths to tracked .py and .pyi files.

    Raises:
        subprocess.CalledProcessError: If Git cannot enumerate tracked Python files.
    """
    result = subprocess.run(
        ("git", "ls-files", "-z", "--", "*.py", "*.pyi"),
        cwd=root,
        check=True,
        capture_output=True,
    )
    return tuple(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


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
        QualityCommand("Markdown contract", (executable, "tools/check_markdown_contract.py")),
        QualityCommand("CI structure", (executable, "tools/ci/validate_ci_structure.py")),
        QualityCommand("Import architecture", ("lint-imports",)),
        QualityCommand(
            "Source-rewriting policy", (executable, "tools/ci/check_no_source_rewriting.py")
        ),
        QualityCommand("Strict Pyright", ("pyright", "-p", "pyrightconfig.json")),
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
    """Run all checks in order and return a failed aggregate without short-circuiting.

    Args:
        commands: Every independent strict-quality command required by CI.

    Returns:
        Zero only when all commands succeed; otherwise one.
    """
    failed = 0
    environment = os.environ.copy()
    for command in commands:
        print(f"::group::Strict quality: {command.label}", flush=True)
        try:
            result = subprocess.run(
                command.arguments,
                cwd=ROOT,
                env=environment,
                check=False,
                timeout=command.timeout_seconds,
            )
            if result.returncode:
                print(
                    f"::error::{command.label} failed with exit code {result.returncode}",
                    flush=True,
                )
                failed = 1
        except subprocess.TimeoutExpired:
            print(f"::error::{command.label} timed out", flush=True)
            failed = 1
        except OSError as error:
            print(f"::error::{command.label} could not start: {error}", flush=True)
            failed = 1
        print("::endgroup::", flush=True)
    return failed


def main() -> int:
    """Prepare the persistent runtime, execute every check, and return aggregate status.

    Returns:
        Zero only when environment setup and all required quality checks succeed.
    """
    try:
        cache_root = Path(os.environ["RUNNER_TOOL_CACHE"])
        image_id = os.environ["QUALITY_IMAGE_ID"]
        workspace_key = os.environ["WORKSPACE_CACHE_KEY"]
        python = prepare_quality_environment(cache_root, image_id, workspace_key)
        tracked_files = collect_tracked_python_files(ROOT)
        if not tracked_files:
            print(
                "::error::Git reported no tracked Python sources or stubs.",
                file=sys.stderr,
                flush=True,
            )
            return 1
        _run_setup(
            ("git", "config", "--global", "--add", "safe.directory", str(ROOT)),
            timeout_seconds=10,
        )
        os.environ["PATH"] = str(python.parent) + os.pathsep + os.environ.get("PATH", "")
        os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
        return run_quality_commands(quality_commands(python, tracked_files))
    except (
        KeyError,
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"::error::Strict quality environment failed: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
