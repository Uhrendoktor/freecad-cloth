# Copyright (C) 2026 FreeCAD Cloth contributors
"""Publish the exact README/wiki visual asset inventory to docs/screenshots."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

if __package__:
    import tools.ci.visual_evidence as visual_evidence

    from tools.ci.build_visual_gifs import build, image_tool
    from tools.ci.command_runner import CommandContext, CommandResult, run_command
    from tools.ci.visual_evidence import documented_assets, verify, write_provenance
else:
    import visual_evidence

    from build_visual_gifs import build, image_tool
    from command_runner import CommandContext, CommandResult, run_command
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


def run(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
    timeout: float | None = None,
) -> CommandResult:
    """Run a resolved executable directly without shell interpolation.

    Args:
        args: Executable name followed by command-line arguments.
        cwd: Optional working directory for the child process.
        check: Whether a non-zero exit status raises CommandExecutionError.
        capture_output: Whether to capture the child's stdout and stderr.
        timeout: Maximum runtime, or None to wait without a deadline.

    Returns:
        Exit status and captured text output when requested.

    Raises:
        ValueError: If the argument vector or timeout is invalid.
        FileNotFoundError: If the executable is not available on PATH.
    """
    if not args:
        msg = "an executable command is required"
        raise ValueError(msg)
    executable = shutil.which(args[0])
    if executable is None:
        msg = f"Required executable is not on PATH: {args[0]}"
        raise FileNotFoundError(msg)
    return run_command(
        (executable, *args[1:]),
        check=check,
        capture_output=capture_output,
        timeout=timeout,
        context=CommandContext(cwd=str(cwd) if cwd is not None else None),
    )


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


def build_visual_gif_set(kind: str, artifact_root: Path) -> None:
    """Normalize downloaded validation artifacts and build the selected documentation GIFs.

    Args:
        kind: GIF collection identifier accepted by the documentation asset builder.
        artifact_root: Temporary directory containing the downloaded validation outputs.

    Raises:
        SystemExit: If normalized assets would collide with existing files.
    """
    output_root = artifact_root / "docs" / "images" / "generated"
    entries = tuple(path for path in artifact_root.iterdir() if path.name != "docs")
    output_root.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        target = output_root / entry.name
        if target.exists() or target.is_symlink():
            msg = f"duplicate asset while normalizing {artifact_root}: {target}"
            raise SystemExit(msg)
        shutil.move(str(entry), str(target))
    source = Path(__file__).resolve().with_name("build_visual_gifs.py")
    run(sys.executable, str(source), kind, timeout=55, cwd=artifact_root)


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


def _publish_assets(
    args: argparse.Namespace,
    source_root: Path,
    expected: set[str],
) -> str:
    """Publish the generated assets and verify the remote publication revision.

    Args:
        args: Parsed repository and workflow provenance arguments.
        source_root: Checked-out source repository used for the documentation inventory.
        expected: Exact generated image names referenced by public documentation.

    Returns:
        Commit SHA of the verified public screenshot branch.

    Raises:
        SystemExit: If the asset inventory or the remote publication revision is invalid.
    """
    temp_root = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
    worktree = temp_root / "cloth-screenshot-publish"
    shutil.rmtree(worktree, ignore_errors=True)
    run("gh", "repo", "clone", args.repository, str(worktree), "--", "--filter=blob:none")

    branch = "docs/screenshots"
    remote_result = run(
        "git",
        "-C",
        str(worktree),
        "ls-remote",
        "--exit-code",
        "--heads",
        "origin",
        branch,
        check=False,
        capture_output=True,
    )
    remote_exists = remote_result.returncode == 0
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
        ProvenanceContext(
            source_root=source_root,
            source_sha=args.source_sha,
            run_id=args.run_id,
            run_number=args.run_number,
        ),
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
    dirty = (
        run(
            "git",
            "-C",
            str(worktree),
            "diff",
            "--cached",
            "--quiet",
            check=False,
        ).returncode
        != 0
    )
    if dirty:
        run(
            "git",
            "-C",
            str(worktree),
            "commit",
            "-m",
            f"ci: publish README/wiki visual evidence for {source_sha[:12]}",
        )
        run("git", "-C", str(worktree), "push", "origin", f"HEAD:{branch}")

    run("git", "-C", str(worktree), "fetch", "origin", branch)
    remote_commit = run(
        "git",
        "-C",
        str(worktree),
        "rev-parse",
        f"origin/{branch}",
        capture_output=True,
    ).stdout.strip()
    local_commit = run(
        "git",
        "-C",
        str(worktree),
        "rev-parse",
        "HEAD",
        capture_output=True,
    ).stdout.strip()
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

    # gh uses GH_TOKEN for clone/authentication; configure Git before the raw push.
    run("gh", "auth", "setup-git")

    source_root = Path.cwd()
    expected = documented_assets(source_root)
    build_visual_gif_set("turntables", Path("turntable-doc-assets"))
    build_visual_gif_set("blanket", Path("blanket"))
    build_visual_gif_set("tunic", Path("tunic"))
    build_surface_pen_gif()

    remote_commit = _publish_assets(args, source_root, expected)
    sys.stdout.write(
        f"visual-publish=passed source_sha={args.source_sha} "
        f"asset_count={len(expected)} remote_commit={remote_commit}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
