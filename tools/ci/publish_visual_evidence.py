"""Publish the exact README/wiki visual asset inventory to docs/screenshots."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from visual_evidence import documented_assets, verify, write_provenance


IMAGE_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
ARTIFACT_ROOTS = (
    Path("turntables"),
    Path("blanket"),
    Path("tunic"),
    Path("avatar-pose-ui"),
    Path("interactive-arrange"),
)


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def find_asset(asset: str) -> Path:
    matches = sorted(
        path
        for root in ARTIFACT_ROOTS
        if root.is_dir()
        for path in root.rglob(asset)
        if path.is_file()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(f"ambiguous visual asset {asset}: {matches}")
    raise SystemExit(f"generated visual asset not found: {asset}")


def build_tunic_gif() -> None:
    output = Path("tunic/docs/images/generated/cloth-tunic-mannequin-motion.gif")
    if output.is_file() and output.stat().st_size:
        return
    frames = sorted(Path("tunic/docs/images/generated/cloth-tunic-mannequin-motion-frames").glob("motion-*.png"))
    if not frames:
        raise SystemExit("cannot build tunic motion GIF: frames are missing")
    source = Path("tools/ci/build_visual_gifs.py")
    subprocess.run(
        ["python3", str(source), "tunic"],
        check=True,
        timeout=55,
        cwd=Path("."),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-number", required=True)
    args = parser.parse_args()

    source_root = Path.cwd()
    expected = documented_assets(source_root)
    build_tunic_gif()

    worktree = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "cloth-screenshot-publish"
    shutil.rmtree(worktree, ignore_errors=True)
    run("gh", "repo", "clone", args.repository, str(worktree), "--", "--filter=blob:none")

    branch = "docs/screenshots"
    remote_exists = subprocess.run(
        ("git", "-C", str(worktree), "ls-remote", "--exit-code", "--heads", "origin", branch),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
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
    run("git", "-C", str(worktree), "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "-C", str(worktree), "add", "docs/images/generated")
    dirty = subprocess.run(
        ("git", "-C", str(worktree), "diff", "--cached", "--quiet"),
        check=False,
    ).returncode != 0
    if dirty:
        run(
            "git", "-C", str(worktree), "commit",
            "-m", f"ci: publish README/wiki visual evidence for {args.source_sha[:12]}",
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
    print(f"visual-publish=passed source_sha={args.source_sha} asset_count={len(expected)} remote_commit={remote_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
