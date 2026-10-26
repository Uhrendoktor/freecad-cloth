# Copyright (C) 2026 FreeCAD Cloth contributors
"""Publish the exact README/wiki visual asset inventory to docs/screenshots."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

from build_visual_gifs import build, image_tool
from visual_evidence import documented_assets, verify, write_provenance

IMAGE_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
SURFACE_PEN_FRAME_COUNT = 4
ARTIFACT_ROOTS = (
    # The tunic audit owns the canonical profiles also used by the 3D arranged/draped views.
    Path("tunic"),
    Path("turntables"),
    Path("blanket"),
    Path("avatar-pose-ui"),
    Path("avatar-shape-editor"),
    Path("interactive-arrange"),
    Path("sewing"),
    Path("surface-pen"),
    Path("avatar-doc-assets"),
    Path("turntable-doc-assets"),
)


async def _execute_command(
    args: tuple[str, ...],
    cwd: Path | None = None,
    timeout: float | None = None,
    capture_output: bool = False,
    quiet: bool = False,
) -> tuple[int, str]:
    """Execute an argument-vector command without invoking a shell.

    Args:
        args: Executable name followed by its individual command-line arguments.
        cwd: Optional working directory for the process.
        timeout: Maximum number of seconds to wait, or None for no time limit.
        capture_output: Whether to capture and return standard output.
        quiet: Whether to discard standard output and standard error.

    Returns:
        Process exit status and captured standard output text.

    Raises:
        SystemExit: If the executable is unavailable or the command exceeds its timeout.
    """
    executable = shutil.which(args[0])
    if executable is None:
        msg = f"required executable not found on PATH: {args[0]}"
        raise SystemExit(msg)
    stdout_target = (
        asyncio.subprocess.PIPE
        if capture_output
        else asyncio.subprocess.DEVNULL
        if quiet
        else None
    )
    stderr_target = (
        asyncio.subprocess.PIPE
        if capture_output
        else asyncio.subprocess.DEVNULL
        if quiet
        else None
    )
    process = await asyncio.create_subprocess_exec(
        executable,
        *args[1:],
        cwd=cwd,
        stdout=stdout_target,
        stderr=stderr_target,
    )
    try:
        stdout_data, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        msg = f"command timed out after {timeout} seconds: {args[0]}"
        raise SystemExit(msg) from exc
    returncode = process.returncode
    if returncode is None:
        msg = f"command has no exit status: {args[0]}"
        raise SystemExit(msg)
    output = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""
    return returncode, output


def run(
    *args: str,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> None:
    """Run a command without a shell and fail on a non-zero exit status.

    Args:
        args: Executable name followed by the command-line arguments to run.
        cwd: Optional working directory in which the command should execute.
        timeout: Optional execution limit in seconds.

    Raises:
        SystemExit: If the executable is missing, the command times out, or it fails.
    """
    returncode, _ = asyncio.run(_execute_command(tuple(args), cwd, timeout))
    if returncode != 0:
        msg = f"command failed with exit status {returncode}: {args[0]}"
        raise SystemExit(msg)


def find_asset(asset: str) -> Path:
    """Locate a generated visual asset using deterministic artifact-root precedence.

    Args:
        asset: Filename of the generated image or animation to locate.

    Returns:
        Path to the unique matching visual asset.

    Raises:
        SystemExit: If the asset is absent or matches multiple files in one artifact root.
    """
    for root in ARTIFACT_ROOTS:
        if not root.is_dir():
            continue
        matches = sorted(path for path in root.rglob(asset) if path.is_file())
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            msg = f"ambiguous visual asset {asset} within {root}: {matches}"
            raise SystemExit(msg)
    msg = f"generated visual asset not found: {asset}"
    raise SystemExit(msg)


def normalize_visual_artifact(kind: str, artifact_root: Path) -> Path:
    """Restore downloaded visual files to the layout expected by the GIF builder.

    Args:
        kind: GIF collection identifier used to select artifact-specific normalization.
        artifact_root: Directory containing downloaded validation files and directories.

    Returns:
        Directory containing the normalized files for the selected GIF collection.

    Raises:
        SystemExit: If normalization would overwrite an existing file or symbolic link.
    """
    output_root = artifact_root / "docs" / "images" / "generated"
    entries = tuple(path for path in artifact_root.iterdir() if path.name != "docs")
    # upload-artifact removes the matched blanket-example/ prefix, so restore it
    # when the downloaded artifact contains the motion frames at its root.
    normalized_root = output_root
    if kind == "blanket" and any(
        entry.is_file() and entry.match("motion-*.png") for entry in entries
    ):
        normalized_root = output_root / "blanket-example"
    normalized_root.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        target = normalized_root / entry.name
        if target.exists() or target.is_symlink():
            msg = f"duplicate asset while normalizing {artifact_root}: {target}"
            raise SystemExit(msg)
        shutil.move(str(entry), str(target))
    return normalized_root


def build_visual_gif_set(kind: str, artifact_root: Path) -> None:
    """Normalize downloaded validation artifacts and build the selected documentation GIFs.

    Args:
        kind: GIF collection identifier accepted by the documentation asset builder.
        artifact_root: Temporary directory containing the downloaded validation outputs.

    """
    normalize_visual_artifact(kind, artifact_root)
    source = Path(__file__).resolve().with_name("build_visual_gifs.py")
    run("python3", str(source), kind, timeout=55, cwd=artifact_root)


def build_surface_pen_gif() -> None:
    """Build a Surface Pen interaction GIF from real FreeCAD UI captures.

    Raises:
        SystemExit: If the captured workflow does not contain exactly four frames.
    """
    root = Path("surface-pen")
    frames = sorted(root.glob("surface-pen-frame-*.png"))
    if len(frames) != SURFACE_PEN_FRAME_COUNT:
        msg = (
            f"surface-pen: expected {SURFACE_PEN_FRAME_COUNT} captured workflow frames, "
            f"got {len(frames)}"
        )
        raise SystemExit(msg)
    build(image_tool(), frames, root / "surface-pen-workflow.gif", "80")


def main() -> int:
    """Publish and validate the repository visual evidence inventory.

    Returns:
        Process status indicating that the visual evidence inventory was published and verified.

    Raises:
        SystemExit: If the published visual inventory does not satisfy its contract.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-number", required=True)
    args = parser.parse_args()

    # gh uses GH_TOKEN for clone/authentication; configure Git before the raw push.
    run("gh", "auth", "setup-git")

    source_root = Path.cwd()
    expected = documented_assets(source_root)
    build_visual_gif_set("turntables", Path("turntable-doc-assets"))
    build_visual_gif_set("blanket", Path("blanket"))
    build_visual_gif_set("tunic", Path("tunic"))
    build_surface_pen_gif()

    worktree = (
        Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        / "cloth-screenshot-publish"
    )
    shutil.rmtree(worktree, ignore_errors=True)
    run("gh", "repo", "clone", args.repository, str(worktree), "--", "--filter=blob:none")

    branch = "docs/screenshots"
    remote_status, _ = asyncio.run(
        _execute_command(
            (
                "git",
                "-C",
                str(worktree),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                branch,
            ),
            quiet=True,
        )
    )
    remote_exists = remote_status == 0
    if remote_exists:
        run("git", "-C", str(worktree), "fetch", "origin", branch)
        run("git", "-C", str(worktree), "checkout", "-B", branch, f"origin/{branch}")
    else:
        run("git", "-C", str(worktree), "checkout", "-b", branch)

    published = worktree / "docs/images/generated"
    published.mkdir(parents=True, exist_ok=True)
    for path in list(published.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            path.unlink()

    for asset in sorted(expected):
        source = find_asset(asset)
        shutil.copy2(source, published / asset)

    provenance = published / "visual-evidence-provenance.txt"
    write_provenance(
        provenance,
        published,
        source_root,
        args.source_sha,
        run_id=args.run_id,
        run_number=args.run_number,
    )

    errors = verify(source_root, published, provenance, args.source_sha)
    if errors:
        raise SystemExit("; ".join(errors))

    run("git", "-C", str(worktree), "config", "user.name", "github-actions[bot]")
    run(
        "git",
        "-C",
        str(worktree),
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    run("git", "-C", str(worktree), "add", "docs/images/generated")
    diff_status, _ = asyncio.run(
        _execute_command(("git", "-C", str(worktree), "diff", "--cached", "--quiet"))
    )
    dirty = diff_status != 0
    if dirty:
        run(
            "git",
            "-C",
            str(worktree),
            "commit",
            "-m",
            f"ci: publish README/wiki visual evidence for {args.source_sha[:12]}",
        )
        run("git", "-C", str(worktree), "push", "origin", f"HEAD:{branch}")

    run("git", "-C", str(worktree), "fetch", "origin", branch)
    remote_status, remote_output = asyncio.run(
        _execute_command(
            ("git", "-C", str(worktree), "rev-parse", f"origin/{branch}"),
            capture_output=True,
        )
    )
    local_status, local_output = asyncio.run(
        _execute_command(
            ("git", "-C", str(worktree), "rev-parse", "HEAD"),
            capture_output=True,
        )
    )
    if remote_status != 0 or local_status != 0:
        msg = "unable to verify local and remote screenshot branch commits"
        raise SystemExit(msg)
    remote_commit = remote_output.strip()
    local_commit = local_output.strip()
    if remote_commit != local_commit:
        msg = f"remote screenshot branch mismatch: {remote_commit} != {local_commit}"
        raise SystemExit(msg)
    sys.stdout.write(
        "visual-publish=passed "
        f"source_sha={args.source_sha} "
        f"asset_count={len(expected)} "
        f"remote_commit={remote_commit}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
