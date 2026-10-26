# Copyright (C) 2026 FreeCAD Cloth contributors
"""Publish the exact README/wiki visual asset inventory to docs/screenshots."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import visual_evidence
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


COMMAND_SUCCESS = 0
COMMAND_DIFFERENCE_FOUND = 1
NO_MATCHING_REMOTE_REF = 2
SCREENSHOT_BRANCH = "docs/screenshots"


@dataclass(frozen=True)
class CommandOptions:
    """Configuration for one shell-free command execution.

    Attributes:
        cwd: Optional process working directory.
        timeout: Optional maximum time allowed for the command.
        capture_output: Whether to capture standard output and standard error.
        quiet: Whether to discard command output.
    """

    cwd: Path | None = None
    timeout: float | None = None
    capture_output: bool = False
    quiet: bool = False


async def _execute_command(
    args: tuple[str, ...],
    options: CommandOptions,
) -> tuple[int, str]:
    """Execute an argument-vector command without invoking a shell.

    Args:
        args: Executable name followed by its individual command-line arguments.
        options: Working directory, timeout, and output-capture settings.

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
        if options.capture_output
        else asyncio.subprocess.DEVNULL
        if options.quiet
        else None
    )
    stderr_target = (
        asyncio.subprocess.PIPE
        if options.capture_output
        else asyncio.subprocess.DEVNULL
        if options.quiet
        else None
    )
    process = await asyncio.create_subprocess_exec(
        executable,
        *args[1:],
        cwd=options.cwd,
        stdout=stdout_target,
        stderr=stderr_target,
    )
    try:
        async with asyncio.timeout(options.timeout):
            stdout_data, _ = await process.communicate()
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        msg = f"command timed out after {options.timeout} seconds: {args[0]}"
        raise SystemExit(msg) from exc
    returncode = process.returncode
    if returncode is None:
        msg = f"command has no exit status: {args[0]}"
        raise SystemExit(msg)
    output = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""
    return returncode, output


def _command_result(
    args: tuple[str, ...],
    options: CommandOptions,
) -> tuple[int, str]:
    """Run one command and return its status and captured standard output.

    Args:
        args: Executable name followed by command-line arguments.
        options: Execution options controlling output and timeout behavior.

    Returns:
        Process exit status and captured standard output text.
    """
    return asyncio.run(_execute_command(args, options))


def run(*args: str, options: CommandOptions | None = None) -> None:
    """Run a command without a shell and fail on a non-zero exit status.

    Args:
        args: Executable name followed by the command-line arguments to run.
        options: Optional working directory, timeout, and output behavior.

    Raises:
        SystemExit: If the executable is missing, the command times out, or it fails.
    """
    command_options = options or CommandOptions()
    returncode, _ = _command_result(tuple(args), command_options)
    if returncode != COMMAND_SUCCESS:
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
    """Normalize downloaded artifacts and build the selected documentation GIFs.

    Args:
        kind: GIF collection identifier accepted by the documentation asset builder.
        artifact_root: Temporary directory containing the downloaded validation outputs.

    """
    normalize_visual_artifact(kind, artifact_root)
    source = Path(__file__).resolve().with_name("build_visual_gifs.py")
    run(
        "python3",
        str(source),
        kind,
        options=CommandOptions(cwd=artifact_root, timeout=55),
    )


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


def _build_documentation_gifs() -> None:
    """Build the documented turntable, blanket, tunic, and Surface Pen animations."""
    build_visual_gif_set("turntables", Path("turntable-doc-assets"))
    build_visual_gif_set("blanket", Path("blanket"))
    build_visual_gif_set("tunic", Path("tunic"))
    build_surface_pen_gif()


def _clone_screenshot_repository(repository: str, worktree: Path) -> None:
    """Clone the repository whose generated documentation images will be published.

    Args:
        repository: Authenticated GitHub repository slug.
        worktree: Destination path for the temporary clone.
    """
    shutil.rmtree(worktree, ignore_errors=True)
    run("gh", "repo", "clone", repository, str(worktree), "--", "--filter=blob:none")


def _checkout_screenshot_branch(worktree: Path) -> str:
    """Check out the remote screenshot branch or create it when it does not exist.

    Args:
        worktree: Local clone used for the documentation-image publication.

    Returns:
        Name of the branch that will hold generated screenshots.

    Raises:
        SystemExit: If the remote branch lookup fails for a reason other than absence.
    """
    args = (
        "git",
        "-C",
        str(worktree),
        "ls-remote",
        "--exit-code",
        "--heads",
        "origin",
        SCREENSHOT_BRANCH,
    )
    remote_status, _ = _command_result(args, CommandOptions(quiet=True))
    if remote_status == COMMAND_SUCCESS:
        run("git", "-C", str(worktree), "fetch", "origin", SCREENSHOT_BRANCH)
        run(
            "git",
            "-C",
            str(worktree),
            "checkout",
            "-B",
            SCREENSHOT_BRANCH,
            f"origin/{SCREENSHOT_BRANCH}",
        )
    elif remote_status == NO_MATCHING_REMOTE_REF:
        run("git", "-C", str(worktree), "checkout", "-b", SCREENSHOT_BRANCH)
    else:
        msg = f"unable to inspect remote screenshot branch (git status {remote_status})"
        raise SystemExit(msg)
    return SCREENSHOT_BRANCH


def _sync_published_assets(
    source_root: Path,
    published: Path,
    expected: set[str],
    metadata: visual_evidence.ProvenanceMetadata,
) -> None:
    """Copy documented assets and verify their provenance manifest.

    Args:
        source_root: Repository root containing README and wiki references.
        published: Destination directory in the screenshots branch.
        expected: Exact asset inventory referenced by documentation.
        metadata: Source commit and workflow identifiers for the provenance record.

    Raises:
        SystemExit: If an asset is missing or the resulting inventory fails verification.
    """
    published.mkdir(parents=True, exist_ok=True)
    for path in published.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            path.unlink()
    for asset in sorted(expected):
        source = find_asset(asset)
        shutil.copy2(source, published / asset)
    provenance = published / "visual-evidence-provenance.txt"
    write_provenance(provenance, published, source_root, metadata)
    errors = verify(source_root, published, provenance, metadata.source_sha)
    if errors:
        raise SystemExit("; ".join(errors))


def _commit_published_assets(worktree: Path, source_sha: str) -> None:
    """Commit and publish changed evidence assets while verifying diff status.

    Args:
        worktree: Local screenshots repository.
        source_sha: Commit SHA used to label this evidence publication.

    Raises:
        SystemExit: If Git cannot determine whether the index contains changes.
    """
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
    diff_status, _ = _command_result(
        ("git", "-C", str(worktree), "diff", "--cached", "--quiet"),
        CommandOptions(),
    )
    if diff_status not in {COMMAND_SUCCESS, COMMAND_DIFFERENCE_FOUND}:
        msg = f"unable to inspect staged screenshot changes (git status {diff_status})"
        raise SystemExit(msg)
    if diff_status == COMMAND_DIFFERENCE_FOUND:
        run(
            "git",
            "-C",
            str(worktree),
            "commit",
            "-m",
            f"ci: publish README/wiki visual evidence for {source_sha[:12]}",
        )
        run("git", "-C", str(worktree), "push", "origin", f"HEAD:{SCREENSHOT_BRANCH}")


def _verified_remote_commit(worktree: Path) -> str:
    """Confirm the pushed screenshot branch points at the local publication commit.

    Args:
        worktree: Local screenshots repository.

    Returns:
        Verified commit SHA advertised by the remote branch.

    Raises:
        SystemExit: If the local and remote refs cannot be read or do not match.
    """
    run("git", "-C", str(worktree), "fetch", "origin", SCREENSHOT_BRANCH)
    remote_status, remote_output = _command_result(
        ("git", "-C", str(worktree), "rev-parse", f"origin/{SCREENSHOT_BRANCH}"),
        CommandOptions(capture_output=True),
    )
    local_status, local_output = _command_result(
        ("git", "-C", str(worktree), "rev-parse", "HEAD"),
        CommandOptions(capture_output=True),
    )
    if remote_status != COMMAND_SUCCESS or local_status != COMMAND_SUCCESS:
        msg = "unable to verify local and remote screenshot branch commits"
        raise SystemExit(msg)
    remote_commit = remote_output.strip()
    local_commit = local_output.strip()
    if remote_commit != local_commit:
        msg = f"remote screenshot branch mismatch: {remote_commit} != {local_commit}"
        raise SystemExit(msg)
    return remote_commit


def main() -> int:
    """Publish and validate the repository visual evidence inventory.

    Returns:
        Process status indicating that the visual evidence inventory was published and verified.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-number", required=True)
    args = parser.parse_args()
    run("gh", "auth", "setup-git")
    source_root = Path.cwd()
    expected = documented_assets(source_root)
    _build_documentation_gifs()
    worktree = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "cloth-screenshot-publish"
    _clone_screenshot_repository(args.repository, worktree)
    _checkout_screenshot_branch(worktree)
    metadata = visual_evidence.ProvenanceMetadata(
        source_sha=args.source_sha,
        run_id=args.run_id,
        run_number=args.run_number,
    )
    published = worktree / "docs/images/generated"
    _sync_published_assets(source_root, published, expected, metadata)
    _commit_published_assets(worktree, args.source_sha)
    remote_commit = _verified_remote_commit(worktree)
    sys.stdout.write(
        "visual-publish=passed "
        f"source_sha={args.source_sha} "
        f"asset_count={len(expected)} "
        f"remote_commit={remote_commit}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
