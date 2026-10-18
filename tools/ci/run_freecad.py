"""Run a bounded FreeCAD process inside the CI container."""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


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
        raise RuntimeError(str(exc)) from exc
    override = os.environ.get("FREECAD_APPLICATION_TIMEOUT_SECONDS")
    if override is None:
        return timeout_seconds
    try:
        override_seconds = int(override)
    except ValueError as exc:
        raise RuntimeError("FREECAD_APPLICATION_TIMEOUT_SECONDS must be an integer") from exc
    if not 1 <= override_seconds <= 360:
        raise RuntimeError("FREECAD_APPLICATION_TIMEOUT_SECONDS must be between 1 and 360")
    return float(override_seconds)


def _stage_workbench(source: Path) -> None:
    """Copy the workbench source tree to the isolated FreeCAD module directory.

    Args:
        source: Repository root containing the workbench files to stage.
    """
    target = Path("/tmp/freecad-mod/freecad-cloth")
    if target.exists():
        shutil.rmtree(target.parent)
    target.mkdir(parents=True)
    names = ("Init.py", "InitGui.py", "package.xml", "resources", "freecad_cloth", "freecad")
    for name in names:
        src = source / name
        if not src.exists():
            continue
        dst = target / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def _start_display(display: str) -> tuple[subprocess.Popen[str], subprocess.Popen[str]]:
    """Start Xvfb and Openbox and wait for the display server to respond.

    Args:
        display: X display identifier shared by FreeCAD and the window manager.

    Returns:
        Process handles for the Xvfb server and Openbox window manager.

    Raises:
        RuntimeError: Raised when the display server does not become ready in five seconds.
    """
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp/runtime-cloth"))
    runtime.mkdir(parents=True, exist_ok=True)
    xvfb_log = Path("/tmp/xvfb.log")
    openbox_log = Path("/tmp/openbox.log")
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1280x720x24", "-nolisten", "tcp"],
        stdout=xvfb_log.open("w"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    openbox = subprocess.Popen(
        ["openbox"],
        stdout=openbox_log.open("w"),
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "DISPLAY": display},
    )
    for _ in range(20):
        check = subprocess.run(
            ["xdpyinfo", "-display", display],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if check.returncode == 0:
            return xvfb, openbox
        subprocess.run(["sleep", "0.25"], check=False)
    xvfb.terminate()
    openbox.terminate()
    raise RuntimeError("Xvfb did not become ready within 5 seconds")


def _stop_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate a process group and wait for its processes to exit.

    Args:
        process: Leader process whose process group should be stopped.
    """
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _write_diagnostics(path: Path, return_code: int | None, timed_out: bool) -> None:
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
    for name in ("/tmp/xvfb.log", "/tmp/openbox.log"):
        log = Path(name)
        if log.exists():
            lines.append(f"--- {name} ---")
            lines.extend(log.read_text(encoding="utf-8", errors="replace").splitlines())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    if os.environ.get("CLOTH_CI_CLEAN_USER", "").lower() == "true":
        for env_name in ("FREECAD_USER_HOME", "FREECAD_USER_DATA", "FREECAD_USER_TEMP"):
            value = os.environ.get(env_name)
            if value:
                shutil.rmtree(value, ignore_errors=True)

    if os.environ.get("CLOTH_CI_STAGE_WORKBENCH", "").lower() == "true":
        _stage_workbench(source)

    command = ["/opt/freecad/AppRun"]
    if os.environ.get("CLOTH_CI_STAGE_WORKBENCH", "").lower() == "true":
        command.extend(["-M", "/tmp/freecad-mod", "-P", "/tmp/freecad-mod/freecad-cloth"])
    command.append(str(args.test_script))
    if args.test_args:
        import shlex

        command.extend(shlex.split(args.test_args))

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    display = os.environ.get("DISPLAY", ":99")
    xvfb = openbox = None
    timed_out = False
    return_code: int | None = None
    try:
        xvfb, openbox = _start_display(display)
        env = {**os.environ, "DISPLAY": display}
        process = subprocess.Popen(
            command,
            cwd=source,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        output = ""
        try:
            output, _ = process.communicate(timeout=timeout_seconds)
            return_code = process.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            output = (exc.output or "") if isinstance(exc.output, str) else ""
            _stop_process_tree(process)
            return_code = 124

        existing_log = ""
        if args.log_file.is_file():
            existing_log = args.log_file.read_text(encoding="utf-8", errors="replace")
        if not existing_log.strip():
            args.log_file.write_text(output, encoding="utf-8")
        sys.stdout.write(output)
        if timed_out:
            diagnostic = args.log_file.with_name("runtime-diagnostics.log")
            _write_diagnostics(diagnostic, return_code, True)
            print(
                f"freecad-run-timeout={timeout_seconds:g}s "
                f"log={args.log_file} diagnostics={diagnostic}",
                flush=True,
            )
            return 124
        if int(return_code or 0) != 0:
            diagnostic = args.log_file.with_name("runtime-diagnostics.log")
            _write_diagnostics(diagnostic, return_code, False)
            print(
                f"freecad-run-failure=exit-{int(return_code or 0)} "
                f"log={args.log_file} diagnostics={diagnostic}",
                flush=True,
            )
        return int(return_code or 0)
    finally:
        for process in (openbox, xvfb):
            if process is not None:
                process.terminate()
        for process in (openbox, xvfb):
            if process is not None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
