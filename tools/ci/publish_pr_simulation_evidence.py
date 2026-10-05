"""Publish human-reviewable PR simulation evidence without executing PR code."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-head", required=True)
    args = parser.parse_args()

    review_root = Path("tunic")
    evidence_branch = f"simulation-evidence/pr-{args.pr_number}"
    worktree = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "simulation-evidence"
    shutil.rmtree(worktree, ignore_errors=True)
    run("gh", "repo", "clone", args.repository, str(worktree), "--", "--filter=blob:none", "--no-checkout")
    run("git", "-C", str(worktree), "fetch", "origin", "main")
    run("git", "-C", str(worktree), "checkout", "--detach", "origin/main")

    remote = subprocess.run(
        ("git", "-C", str(worktree), "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{evidence_branch}"),
        check=False,
    )
    if remote.returncode == 0:
        run("git", "-C", str(worktree), "fetch", "origin", f"refs/heads/{evidence_branch}:refs/remotes/origin/{evidence_branch}")
        run("git", "-C", str(worktree), "checkout", "--detach", f"refs/remotes/origin/{evidence_branch}")
    else:
        run("git", "-C", str(worktree), "switch", "--orphan", evidence_branch)
        subprocess.run(("git", "-C", str(worktree), "rm", "-rf", "."), check=False)

    images = sorted(
        path for path in review_root.rglob("*.png") if any(
            token in path.name.lower()
            for token in ("tunic", "draped", "step-015", "step-045", "step-090", "front", "rear", "right", "left", "top", "bottom", "diagnostic")
        )
    )[:18]
    if not images:
        images = sorted(review_root.rglob("*.png"))[:18]
    if not images:
        raise SystemExit(f"No PNG evidence was produced for PR #{args.pr_number}")

    dest = worktree / f"pr-{args.pr_number}" / f"run-{args.run_id}"
    dest.mkdir(parents=True, exist_ok=True)
    for image in images:
        shutil.copy2(image, dest / image.name)
    (dest / "README.md").write_text(
        "# Simulation visual evidence\n\n"
        f"PR #{args.pr_number}, canonical workflow run {args.run_id}.\n"
        f"Source PR HEAD: {args.evidence_head}.\n",
        encoding="utf-8",
    )
    run("git", "-C", str(worktree), "add", str(dest.relative_to(worktree)))
    run(
        "git", "-C", str(worktree), "-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "-m", f"simulation evidence PR #{args.pr_number} run {args.run_id}",
    )
    run("git", "-C", str(worktree), "push", "origin", f"HEAD:{evidence_branch}")

    body = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "simulation-review.md"
    lines = [
        "<!-- simulation-evidence -->",
        f"## Simulation visual evidence — PR #{args.pr_number} / run {args.run_id}",
        "",
        "Inspect the rendered images before reading the logs.",
    ]
    for image in images[:8]:
        url = f"https://raw.githubusercontent.com/{args.repository}/{evidence_branch}/pr-{args.pr_number}/run-{args.run_id}/{image.name}"
        lines.extend(("", f"**{image.name}**", f"![{image.name}]({url})"))
    lines.extend(("", f"[Open complete evidence bundle](https://github.com/{args.repository}/tree/{evidence_branch}/pr-{args.pr_number}/run-{args.run_id})"))
    body.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run("gh", "pr", "comment", args.pr_number, "--repo", args.repository, "--body-file", str(body))
    print(f"simulation-evidence-publish=passed pr={args.pr_number} run={args.run_id} images={len(images)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
