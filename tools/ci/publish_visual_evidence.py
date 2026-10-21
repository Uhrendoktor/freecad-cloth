# Copyright (C) 2026 FreeCAD Cloth contributors
"""Publish the exact README/wiki visual asset inventory to docs/screenshots."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
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


def run(*args: str, cwd: Path | None = None) -> None:
    """Run a subprocess command and fail on a non-zero exit status.

    Args:
        args: Executable name followed by the command-line arguments to run.
        cwd: Optional working directory in which the command should execute.
    """
    subprocess.run(args, cwd=cwd, check=True)


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
            raise SystemExit(f"duplicate asset while normalizing {artifact_root}: {target}")
        shutil.move(str(entry), str(target))
    return normalized_root



def build_visual_gif_set(kind: str, artifact_root: Path) -> None:
    """Normalize downloaded validation artifacts and build the selected documentation GIFs.

    Args:
        kind: GIF collection identifier accepted by the documentation asset builder.
        artifact_root: Temporary directory containing the downloaded validation outputs.

    Raises:
        SystemExit: If normalized assets would collide with existing files.
        CalledProcessError: If the documentation GIF builder exits with an error.
        TimeoutExpired: If the builder exceeds its 55-second execution limit.
    """
    normalize_visual_artifact(kind, artifact_root)
    source = Path(__file__).resolve().with_name("build_visual_gifs.py")
    subprocess.run(
        ["python3", str(source), kind],
        check=True,
        timeout=55,
        cwd=artifact_root,
    )

def build_surface_pen_gif() -> None:
    """Build a Surface Pen interaction GIF from real FreeCAD UI captures.

    Raises:
        SystemExit: If the captured workflow does not contain exactly four frames.
    """
    from build_visual_gifs import build, image_tool

    root = Path("surface-pen")
    frames = sorted(root.glob("surface-pen-frame-*.png"))
    if len(frames) != 4:
        msg = f"surface-pen: expected 4 captured workflow frames, got {len(frames)}"
        raise SystemExit(msg)
    build(image_tool(), frames, root / "surface-pen-workflow.gif", "80")


def main() -> int:
    """Publish and validate the repository visual evidence inventory.

    Raises:
        SystemExit: If the published visual inventory does not satisfy its contract.

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

    from visual_evidence import documented_assets, verify, write_provenance

    source_root = Path.cwd()
    expected = documented_assets(source_root)
    build_visual_gif_set("turntables", Path("turntable-doc-assets"))
    build_visual_gif_set("blanket", Path("blanket"))
    build_visual_gif_set("tunic", Path("tunic"))
    build_surface_pen_gif()

    worktree = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "cloth-screenshot-publish"
    shutil.rmtree(worktree, ignore_errors=True)
    run("gh", "repo", "clone", args.repository, str(worktree), "--", "--filter=blob:none")

    branch = "docs/screenshots"
    remote_exists = (
        subprocess.run(
            ("git", "-C", str(worktree), "ls-remote", "--exit-code", "--heads", "origin", branch),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
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
        args.run_id,
        args.run_number,
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
        subprocess.run(
            ("git", "-C", str(worktree), "diff", "--cached", "--quiet"),
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
            f"ci: publish README/wiki visual evidence for {args.source_sha[:12]}",
        )
        run("git", "-C", str(worktree), "push", "origin", f"HEAD:{branch}")

    run("git", "-C", str(worktree), "fetch", "origin", branch)
    remote_commit = subprocess.check_output(
        ("git", "-C", str(worktree), "rev-parse", f"origin/{branch}"),
        text=True,
    ).strip()
    local_commit = subprocess.check_output(
        ("git", "-C", str(worktree), "rev-parse", "HEAD"),
        text=True,
    ).strip()
    if remote_commit != local_commit:
        msg = f"remote screenshot branch mismatch: {remote_commit} != {local_commit}"
        raise SystemExit(msg)
    print(
        f"visual-publish=passed source_sha={args.source_sha} asset_count={len(expected)} remote_commit={remote_commit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
