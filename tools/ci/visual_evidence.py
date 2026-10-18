# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compute and validate the public README/wiki visual evidence contract."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

IMAGE_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".webp")
PREFIX = (
    "https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/"
    "refs/heads/docs/screenshots/docs/images/generated/"
)
ASSET_RE = re.compile(re.escape(PREFIX) + r"""([^\s'"<>\)]+)""")


def documented_assets(source_root: Path) -> set[str]:
    """Return the generated visual assets referenced by the public documentation.

    Args:
        source_root: Repository root containing the README and wiki documents.

    Returns:
        Set of generated image filenames referenced by the public documentation.

    Raises:
        ValueError: Raised when the documents contain no generated image references.
    """
    documents = [
        source_root / "README.md",
        *sorted((source_root / "docs").rglob("*.md")),
    ]
    assets: set[str] = set()
    for document in documents:
        if not document.is_file():
            continue
        text = document.read_text(encoding="utf-8")
        for match in ASSET_RE.finditer(text):
            asset = match.group(1).split("?", 1)[0]
            if asset.lower().endswith(IMAGE_SUFFIXES):
                assets.add(asset)
    if not assets:
        msg = "README/wiki contain no generated visual references"
        raise ValueError(msg)
    return assets


def public_assets(published_root: Path) -> set[str]:
    """Return the generated visual assets present in the published directory.

    Args:
        published_root: Directory containing the public image files.

    Returns:
        Set of image filenames found in the published directory.

    Raises:
        ValueError: Raised when the publication directory does not exist.
    """
    if not published_root.is_dir():
        msg = f"published image directory missing: {published_root}"
        raise ValueError(msg)
    return {
        path.name
        for path in published_root.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file.

    Args:
        path: File whose content should be hashed.

    Returns:
        Lowercase hexadecimal SHA-256 digest of the file.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_provenance(
    provenance: Path,
    published_root: Path,
    source_root: Path,
    source_sha: str,
    run_id: str,
    run_number: str,
) -> None:
    """Write the visual evidence provenance manifest.

    Args:
        provenance: Destination path for the provenance JSON document.
        published_root: Directory containing the publicly published images.
        source_root: Repository root containing documented image references.
        source_sha: Commit SHA from which the source assets were produced.
        run_id: GitHub Actions identifier for the producing run.
        run_number: Human-readable sequence number for the producing run.

    Raises:
        ValueError: Raised when the published images differ from the documented inventory.
    """
    assets = sorted(documented_assets(source_root))
    actual = public_assets(published_root)
    if assets != sorted(actual):
        msg = f"public image set mismatch; missing={sorted(set(assets) - actual)} extra={sorted(actual - set(assets))}"
        raise ValueError(
            msg
        )
    lines = [
        "# README/wiki visual evidence provenance",
        "",
        f"source_main_sha={source_sha}",
        f"workflow_run={run_id}",
        f"workflow_run_number={run_number}",
        "",
    ]
    for asset in assets:
        path = published_root / asset
        if not path.is_file() or not path.stat().st_size:
            msg = f"missing or empty generated asset: {asset}"
            raise ValueError(msg)
        lines.append(f"{sha256(path)}  docs/images/generated/{asset}")
    provenance.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify(
    source_root: Path,
    published_root: Path,
    provenance: Path,
    source_sha: str,
) -> list[str]:
    """Validate the published visual evidence against the documented source set.

    Args:
        source_root: Repository root containing documented image references.
        published_root: Directory containing the public image files.
        provenance: Path to the provenance manifest to verify.
        source_sha: Expected source commit SHA for the published assets.

    Returns:
        Human-readable errors found while comparing sources, publication, and provenance.
    """
    expected = documented_assets(source_root)
    actual = public_assets(published_root)
    errors: list[str] = []
    errors.extend(
        f"missing documented images: {sorted(expected - actual)}" for _ in [0] if expected - actual
    )
    errors.extend(
        f"undocumented public images: {sorted(actual - expected)}" for _ in [0] if actual - expected
    )
    if not provenance.is_file() or not provenance.stat().st_size:
        errors.append(f"missing provenance: {provenance}")
    else:
        lines = provenance.read_text(encoding="utf-8").splitlines()
        source_line = next((line for line in lines if line.startswith("source_main_sha=")), "")
        if source_line != f"source_main_sha={source_sha}":
            errors.append(f"stale provenance: {source_line!r}")
        recorded = {}
        for line in lines:
            if "  docs/images/generated/" in line:
                digest, name = line.split("  ", 1)
                recorded[Path(name).name] = digest
        for asset in sorted(expected):
            path = published_root / asset
            if not path.is_file() or not path.stat().st_size:
                errors.append(f"missing or empty image: {asset}")
            elif recorded.get(asset) != sha256(path):
                errors.append(f"provenance hash mismatch: {asset}")
    return errors


def main() -> int:
    """Validate the repository visual evidence contract.

    Returns:
        Process status indicating whether the published evidence is consistent.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--published-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    errors = verify(args.source_root, args.published_root, args.provenance, args.source_sha)
    if errors:
        for error in errors:
            print(f"visual-evidence-error={error}")
        return 1
    print(
        f"readme-wiki-visual-freshness=passed asset_count={len(documented_assets(args.source_root))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
