"""Run a bounded FreeCAD process inside the CI container."""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import traceback
from pathlib import Path


def _stage_workbench(source: Path) -> None:
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
    """Run a FreeCAD test process with the repository runtime contract."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--test-script", type=Path, required=True)
    parser.add_argument("--test-args", default="")
    args = parser.parse_args()

    if args.timeout_seconds > 120:
        raise SystemExit("timeout-seconds must not exceed 120")

    source = Path("/workspace")
    if os.environ.get("CLOTH_CI_CLEAN_USER", "").lower() == "true":
        for env_name in ("FREECAD_USER_HOME", "FREECAD_USER_DATA", "FREECAD_USER_TEMP"):
            value = os.environ.get(env_name)
            if value:
                shutil.rmtree(value, ignore_errors=True)

    import shlex

    test_args = shlex.split(args.test_args) if args.test_args else []
    runner = Path("/tmp/freecad-ci-runner.py")
    runner.write_text(
        "import runpy, sys\n"
        "from pathlib import Path\n"
        "root = Path('/workspace')\n"
        "sys.path.insert(0, str(root))\n"
        "init_gui = root / 'InitGui.py'\n"
        "exec(compile(init_gui.read_text(encoding='utf-8'), str(init_gui), 'exec'), globals(), globals())\n"
        "sys.argv = %r\n"
        "runpy.run_path(%r, run_name=\"__main__\")\n"
        % ([str(args.test_script), *test_args], str(args.test_script)),
        encoding="utf-8",
    )

    command = ["/opt/freecad/AppRun", str(runner)]

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    display = os.environ.get("DISPLAY", ":99")
    xvfb = openbox = None
    timed_out = False
    return_code: int | None = None
    try:
        xvfb, openbox = _start_display(display)
        env = {**os.environ, "DISPLAY": display}
        process = None
        try:
            with args.log_file.open("w", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    command,
                    cwd=source,
                    env=env,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                try:
                    return_code = process.wait(timeout=args.timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _stop_process_tree(process)
                    return_code = 124
            output = args.log_file.read_text(encoding="utf-8", errors="replace")
            sys.stdout.write(output)
        except BaseException:
            output = traceback.format_exc()
            return_code = 1
            args.log_file.write_text(output, encoding="utf-8")
            diagnostic = args.log_file.with_name("runtime-diagnostics.log")
            _write_diagnostics(diagnostic, return_code, False)
            sys.stdout.write(output)
            print(
                f"freecad-run-failure=launch log={args.log_file} "
                f"diagnostics={diagnostic}",
                flush=True,
            )
            return 1
        if timed_out:
            diagnostic = args.log_file.with_name("runtime-diagnostics.log")
            _write_diagnostics(diagnostic, return_code, True)
            print(
                f"freecad-run-timeout={args.timeout_seconds:g}s "
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
        with contextlib.suppress(OSError):
            runner.unlink()
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
