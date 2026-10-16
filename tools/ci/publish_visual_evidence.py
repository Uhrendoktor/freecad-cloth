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
            raise SystemExit(f"ambiguous visual asset {asset} within {root}: {matches}")
    raise SystemExit(f"generated visual asset not found: {asset}")


def build_tunic_gif() -> None:
    """Build the tunic motion GIF when it is not already present.

    Raises:
        SystemExit: If source frames are unavailable for generating the animation.
    """
    output = Path("tunic/docs/images/generated/cloth-tunic-mannequin-motion.gif")
    if output.is_file() and output.stat().st_size:
        return
    frames = sorted(
        Path("tunic/docs/images/generated/cloth-tunic-mannequin-motion-frames").glob("motion-*.png")
    )
    if not frames:
        raise SystemExit("cannot build tunic motion GIF: frames are missing")
    source = Path(__file__).resolve().with_name("build_visual_gifs.py")
    subprocess.run(
        ["python3", str(source), "tunic"],
        check=True,
        timeout=55,
        cwd=Path("tunic"),
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
        raise SystemExit(f"surface-pen: expected 4 captured workflow frames, got {len(frames)}")
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
    build_tunic_gif()
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
        raise SystemExit(f"remote screenshot branch mismatch: {remote_commit} != {local_commit}")
    print(
        f"visual-publish=passed source_sha={args.source_sha} asset_count={len(expected)} remote_commit={remote_commit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
