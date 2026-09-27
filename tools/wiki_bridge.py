#!/usr/bin/env python3
"""Synchronize the repository-owned human documentation with the GitHub Wiki."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI_SOURCE = REPO_ROOT / "wiki"

def run(*args: str, cwd: Path | None = None) -> None:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    subprocess.run(args, cwd=cwd, env=env, check=True)

def mirror_tree(source: Path, destination: Path) -> None:
    """Make destination an exact copy of source, excluding Git metadata."""
    destination.mkdir(parents=True, exist_ok=True)
    for entry in destination.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for entry in source.rglob("*"):
        relative = entry.relative_to(source)
        if ".git" in relative.parts:
            continue
        target = destination / relative
        if entry.is_symlink():
            raise RuntimeError(f"Symlinks are not supported in wiki documentation: {entry}")
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target)

def clone_wiki(remote_url: str, destination: Path) -> None:
    run("git", "clone", "--depth", "1", remote_url, str(destination))

def require_remote() -> str:
    remote_url = os.environ.get("WIKI_REMOTE_URL", "").strip()
    if not remote_url:
        raise SystemExit("WIKI_REMOTE_URL must contain the authenticated GitHub Wiki repository URL.")
    return remote_url

def publish() -> None:
    if not WIKI_SOURCE.is_dir():
        raise SystemExit(f"Missing wiki source directory: {WIKI_SOURCE}")
    remote_url = require_remote()
    with tempfile.TemporaryDirectory(prefix="freecad-cloth-wiki-publish-") as temp:
        wiki_checkout = Path(temp) / "wiki"
        clone_wiki(remote_url, wiki_checkout)
        mirror_tree(WIKI_SOURCE, wiki_checkout)
        run("git", "config", "user.name", "github-actions[bot]", cwd=wiki_checkout)
        run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=wiki_checkout)
        run("git", "add", "-A", cwd=wiki_checkout)
        diff = subprocess.run(("git", "diff", "--cached", "--quiet"), cwd=wiki_checkout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if diff.returncode == 0:
            print("GitHub Wiki already matches repository source.")
            return
        if diff.returncode != 1:
            raise SystemExit(diff.returncode)
        run("git", "commit", "-m", "docs: sync GitHub Wiki from repository", cwd=wiki_checkout)
        run("git", "push", "origin", "HEAD", cwd=wiki_checkout)

def import_wiki() -> None:
    remote_url = require_remote()
    WIKI_SOURCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="freecad-cloth-wiki-import-") as temp:
        wiki_checkout = Path(temp) / "wiki"
        clone_wiki(remote_url, wiki_checkout)
        mirror_tree(wiki_checkout, WIKI_SOURCE)
    print("Imported GitHub Wiki into repository source tree.")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("publish", "import"))
    args = parser.parse_args()
    if args.operation == "publish":
        publish()
    else:
        import_wiki()

if __name__ == "__main__":
    main()
