# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run a bounded FreeCAD process inside the CI container."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import shlex
import shutil
import signal
import sys
import tempfile
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
MAX_FREECAD_TIMEOUT_SECONDS = 360
DISPLAY_READINESS_ATTEMPTS = 20
DISPLAY_READINESS_INTERVAL_SECONDS = 0.25
PROCESS_SHUTDOWN_TIMEOUT_SECONDS = 5
DISPLAY_SHUTDOWN_TIMEOUT_SECONDS = 3
PROCESS_SUCCESS_EXIT_CODE = 0
PROCESS_TIMEOUT_EXIT_CODE = 124
TRUE_ENV_VALUE = "true"
USER_DATA_ENVIRONMENT_NAMES = (
    "FREECAD_USER_HOME",
    "FREECAD_USER_DATA",
    "FREECAD_USER_TEMP",
)
TEMP_ROOT = Path(tempfile.gettempdir())
WORKBENCH_STAGE_ROOT = TEMP_ROOT / "freecad-mod"
WORKBENCH_STAGE_PATH = WORKBENCH_STAGE_ROOT / "freecad-cloth"
RUNTIME_DIRECTORY = TEMP_ROOT / "runtime-cloth"
XVFB_LOG = TEMP_ROOT / "xvfb.log"
OPENBOX_LOG = TEMP_ROOT / "openbox.log"


try:
    from freecad_timeout_config import read_application_timeout
except ModuleNotFoundError:
    from tools.ci.freecad_timeout_config import read_application_timeout


def configured_timeout_seconds() -> float:
    """Read the configured FreeCAD timeout and validate an optional runtime override.

    Returns:
        Positive application runtime budget in seconds.

    Raises:
        RuntimeError: If the configured timeout or an explicit runtime override is invalid.
    """
    try:
        timeout_seconds = float(read_application_timeout(PYPROJECT))
    except ValueError as exc:
        msg = str(exc)
        raise RuntimeError(msg) from exc
    override = os.environ.get("FREECAD_APPLICATION_TIMEOUT_SECONDS")
    if override is None:
        return timeout_seconds
    try:
        override_seconds = int(override)
    except ValueError as exc:
        msg = "FREECAD_APPLICATION_TIMEOUT_SECONDS must be an integer"
        raise RuntimeError(msg) from exc
    if not 1 <= override_seconds <= MAX_FREECAD_TIMEOUT_SECONDS:
        msg = (
            "FREECAD_APPLICATION_TIMEOUT_SECONDS must be between 1 and "
            f"{MAX_FREECAD_TIMEOUT_SECONDS}"
        )
        raise RuntimeError(msg)
    return float(override_seconds)


def _stage_workbench(source: Path) -> None:
    """Copy the workbench source tree to the isolated FreeCAD module directory.

    Args:
        source: Repository root containing the workbench files to stage.
    """
    target = WORKBENCH_STAGE_PATH
    if target.exists():
        shutil.rmtree(WORKBENCH_STAGE_ROOT)
    target.mkdir(parents=True)
    names = (
        "Init.py",
        "InitGui.py",
        "package.xml",
        "resources",
        "freecad_cloth",
        "freecad",
    )
    for name in names:
        src = source / name
        if not src.exists():
            continue
        dst = target / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def _require_executable(name: str) -> str:
    """Resolve a display utility to an absolute executable path.

    Args:
        name: Executable name to look up on PATH.

    Returns:
        Absolute path to the executable.

    Raises:
        FileNotFoundError: If the requested executable is not installed or not on PATH.
    """
    executable = shutil.which(name)
    if executable is None:
        msg = f"Required display executable not found: {name}"
        raise FileNotFoundError(msg)
    return executable


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    """Terminate a child process and wait for its exit, escalating when necessary.

    Args:
        process: Child process to stop.
    """
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(
            process.wait(),
            timeout=DISPLAY_SHUTDOWN_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()


async def _start_display(
    display: str,
) -> tuple[asyncio.subprocess.Process, asyncio.subprocess.Process]:
    """Start Xvfb and Openbox and wait for the display server to respond.

    Args:
        display: X display identifier shared by FreeCAD and the window manager.

    Returns:
        Process handles for the Xvfb server and Openbox window manager.

    Raises:
        RuntimeError: If the display server does not become ready in five seconds.
    """
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or RUNTIME_DIRECTORY)
    runtime.mkdir(parents=True, exist_ok=True)
    xvfb_executable = _require_executable("Xvfb")
    openbox_executable = _require_executable("openbox")
    xdpyinfo_executable = _require_executable("xdpyinfo")
    with (
        XVFB_LOG.open("w", encoding="utf-8") as xvfb_log,
        OPENBOX_LOG.open("w", encoding="utf-8") as openbox_log,
    ):
        xvfb = await asyncio.create_subprocess_exec(
            xvfb_executable,
            display,
            "-screen",
            "0",
            "1280x720x24",
            "-nolisten",
            "tcp",
            stdout=xvfb_log,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            openbox = await asyncio.create_subprocess_exec(
                openbox_executable,
                stdout=openbox_log,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "DISPLAY": display},
            )
        except OSError:
            await _stop_process(xvfb)
            raise

    for _ in range(DISPLAY_READINESS_ATTEMPTS):
        check = await asyncio.create_subprocess_exec(
            xdpyinfo_executable,
            "-display",
            display,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await check.wait()
        if check.returncode == PROCESS_SUCCESS_EXIT_CODE:
            return xvfb, openbox
        await asyncio.sleep(DISPLAY_READINESS_INTERVAL_SECONDS)

    await _stop_process(xvfb)
    await _stop_process(openbox)
    msg = "Xvfb did not become ready within 5 seconds"
    raise RuntimeError(msg)


async def _stop_process_tree(process: asyncio.subprocess.Process) -> None:
    """Terminate a process group and wait for its processes to exit.

    Args:
        process: Leader process whose process group should be stopped.
    """
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        await process.wait()
        return
    try:
        await asyncio.wait_for(
            process.wait(),
            timeout=PROCESS_SHUTDOWN_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


def _write_diagnostics(path: Path, return_code: int | None, *, timed_out: bool) -> None:
    """Write the process result and available display-server logs to a diagnostic file.

    Args:
        path: Destination for the diagnostic log.
        return_code: Exit status reported by the FreeCAD process, if available.
        timed_out: Whether the application exceeded its configured runtime budget.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"freecad-run-return-code={return_code}",
        f"freecad-run-timed-out={str(timed_out).lower()}",
    ]
    for log in (XVFB_LOG, OPENBOX_LOG):
        if log.exists():
            lines.append(f"--- {log} ---")
            lines.extend(log.read_text(encoding="utf-8", errors="replace").splitlines())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clean_user_data_if_requested() -> None:
    """Remove explicitly selected FreeCAD user-data directories before a test run."""
    if os.environ.get("CLOTH_CI_CLEAN_USER", "").lower() != TRUE_ENV_VALUE:
        return
    for env_name in USER_DATA_ENVIRONMENT_NAMES:
        value = os.environ.get(env_name)
        if value:
            shutil.rmtree(value, ignore_errors=True)


def _build_command(source: Path, test_script: Path, test_args: str) -> list[str]:
    """Build the FreeCAD launcher command and optional workbench staging arguments.

    Args:
        source: Repository root used for the process working directory.
        test_script: Test entrypoint passed to FreeCAD.
        test_args: Shell-like argument text parsed into separate command arguments.

    Returns:
        Executable argument vector passed directly to FreeCAD without a shell.
    """
    command = ["/opt/freecad/AppRun"]
    if os.environ.get("CLOTH_CI_STAGE_WORKBENCH", "").lower() == TRUE_ENV_VALUE:
        _stage_workbench(source)
        command.extend(
            ["-M", str(WORKBENCH_STAGE_ROOT), "-P", str(WORKBENCH_STAGE_PATH)]
        )
    command.append(str(test_script))
    if test_args:
        command.extend(shlex.split(test_args))
    return command


async def _run_application(
    log_file: Path,
    command: list[str],
    source: Path,
    timeout_seconds: float,
    display: str,
) -> int:
    """Run FreeCAD, preserve its output, and enforce the configured runtime budget.

    Args:
        log_file: Destination for captured test output when the test did not write it.
        command: FreeCAD launcher argument vector.
        source: Repository root used as the FreeCAD working directory.
        timeout_seconds: Maximum allowed FreeCAD process runtime.
        display: X display identifier to set for FreeCAD and the display server.

    Returns:
        FreeCAD's process status, or the timeout status when its budget is exceeded.
    """
    xvfb: asyncio.subprocess.Process | None = None
    openbox: asyncio.subprocess.Process | None = None
    try:
        xvfb, openbox = await _start_display(display)
        env = {**os.environ, "DISPLAY": display}
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=source,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        communication = asyncio.create_task(process.communicate())
        timed_out = False
        try:
            output_bytes, _ = await asyncio.wait_for(
                asyncio.shield(communication),
                timeout=timeout_seconds,
            )
            return_code = process.returncode
            if return_code is None:
                return_code = PROCESS_SUCCESS_EXIT_CODE
        except TimeoutError:
            timed_out = True
            await _stop_process_tree(process)
            output_bytes, _ = await communication
            return_code = PROCESS_TIMEOUT_EXIT_CODE

        output = output_bytes.decode("utf-8", errors="replace")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        existing_log = ""
        if log_file.is_file():
            existing_log = log_file.read_text(encoding="utf-8", errors="replace")
        if not existing_log.strip():
            log_file.write_text(output, encoding="utf-8")
        sys.stdout.write(output)
        if timed_out:
            diagnostic = log_file.with_name("runtime-diagnostics.log")
            _write_diagnostics(diagnostic, return_code, timed_out=True)
            sys.stdout.write(
                f"freecad-run-timeout={timeout_seconds:g}s "
                f"log={log_file} diagnostics={diagnostic}\n"
            )
            sys.stdout.flush()
            return PROCESS_TIMEOUT_EXIT_CODE
        if return_code != PROCESS_SUCCESS_EXIT_CODE:
            diagnostic = log_file.with_name("runtime-diagnostics.log")
            _write_diagnostics(diagnostic, return_code, timed_out=False)
            sys.stdout.write(
                f"freecad-run-failure=exit-{return_code} "
                f"log={log_file} diagnostics={diagnostic}\n"
            )
            sys.stdout.flush()
        return return_code
    finally:
        for process in (openbox, xvfb):
            if process is not None:
                await _stop_process(process)


def main() -> int:
    """Run a FreeCAD test process with the repository runtime contract.

    Returns:
        Exit status reported by FreeCAD, or 124 when the runtime limit is exceeded.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--test-script", type=Path, required=True)
    parser.add_argument("--test-args", default="")
    args = parser.parse_args()

    source = Path("/workspace")
    timeout_seconds = configured_timeout_seconds()
    _clean_user_data_if_requested()
    command = _build_command(source, args.test_script, args.test_args)
    display = os.environ.get("DISPLAY", ":99")
    return asyncio.run(_run_application(args.log_file, command, source, timeout_seconds, display))


if __name__ == "__main__":
    raise SystemExit(main())
