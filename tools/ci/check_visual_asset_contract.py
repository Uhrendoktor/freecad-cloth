# Copyright (C) 2026 FreeCAD Cloth contributors
"""Fail closed when documented visual assets are unused or have no CI producer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import cast

from visual_evidence import documented_assets

type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools" / "ci" / "visual_asset_sources.json"
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"
PUBLISH_ACTION = ROOT / ".github" / "actions" / "publish-visual-evidence" / "action.yml"
PUBLISHER_SCRIPT = ROOT / "tools" / "ci" / "publish_visual_evidence.py"


def _manifest_assets() -> tuple[dict[str, object] | None, list[str]]:
    """Load and validate the visual asset manifest's top-level structure.

    Returns:
        The asset mapping and an empty error list when valid, or diagnostics when invalid.
    """
    try:
        payload = cast("JSONValue", json.loads(MANIFEST.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"cannot read visual asset manifest: {exc}"]
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return None, ["unsupported visual asset manifest schema"]
    assets = payload.get("assets")
    if not isinstance(assets, dict):
        return None, ["visual asset manifest must contain an assets object"]
    return cast("dict[str, object]", assets), []


def _production_configuration(
    workflow_text: str,
    publisher_text: str,
    publisher_script_text: str,
) -> str:
    """Collect the workflow and local scripts that produce or upload visual assets.

    Args:
        workflow_text: Canonical workflow source text.
        publisher_text: Visual evidence composite-action source text.
        publisher_script_text: Publisher script source text.

    Returns:
        Combined source text used to verify asset production and upload wiring.
    """
    gif_builder = PUBLISHER_SCRIPT.with_name("build_visual_gifs.py")
    production_sources = [workflow_text, publisher_text, publisher_script_text]
    wired_gif_builder = (
        'with_name("build_visual_gifs.py")' in publisher_script_text and gif_builder.is_file()
    )
    if wired_gif_builder:
        production_sources.append(gif_builder.relative_to(ROOT).as_posix())
    return chr(10).join(production_sources)


def _asset_mapping_errors(name: str, entry: object, production_config: str) -> list[str]:
    """Validate one manifest mapping against its wired production inputs.

    Args:
        name: Documented visual asset filename.
        entry: Raw JSON value declared for this asset.
        production_config: Combined workflow and script source text.

    Returns:
        Validation diagnostics for the given asset mapping.
    """
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{name}: mapping must be an object"]
    artifact = entry.get("artifact")
    if not isinstance(artifact, str) or not artifact or artifact not in production_config:
        errors.append(f"{name}: artifact is not produced/uploaded by canonical CI: {artifact!r}")
    producers = entry.get("producers")
    if not isinstance(producers, list) or not producers:
        errors.append(f"{name}: at least one producer path is required")
        return errors
    for producer in producers:
        if not isinstance(producer, str) or not producer:
            errors.append(f"{name}: invalid producer path {producer!r}")
            continue
        path = ROOT / producer
        if not path.is_file():
            errors.append(f"{name}: producer source does not exist: {producer}")
        if producer not in production_config:
            errors.append(f"{name}: producer is not wired into canonical CI: {producer}")
    return errors


def contract_errors() -> list[str]:
    """Validate exact documentation inventory and mapped generation sources.

    Returns:
        Contract violations found in the documentation and producer mappings.
    """
    assets, manifest_errors = _manifest_assets()
    if manifest_errors:
        return manifest_errors
    if assets is None:
        return ["visual asset manifest must contain an assets object"]
    try:
        documented = documented_assets(ROOT)
    except (OSError, ValueError) as exc:
        return [f"cannot compute README/wiki image inventory: {exc}"]
    declared = set(assets)
    errors = [
        *(
            f"documented asset has no producer mapping: {name}"
            for name in sorted(documented - declared)
        ),
        *(
            f"producer mapping is unused by README/wiki: {name}"
            for name in sorted(declared - documented)
        ),
    ]
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    publisher_text = PUBLISH_ACTION.read_text(encoding="utf-8")
    publisher_script_text = PUBLISHER_SCRIPT.read_text(encoding="utf-8")
    production_config = _production_configuration(
        workflow_text,
        publisher_text,
        publisher_script_text,
    )
    required_upload_patterns = (
        "docs/images/generated/*.png",
        "docs/images/generated/*.gif",
        "docs/images/generated/*.log",
        "docs/images/generated/*.txt",
    )
    errors.extend(
        f"turntable artifact upload does not include required pattern: {pattern}"
        for pattern in required_upload_patterns
        if pattern not in workflow_text
    )
    for name in sorted(documented & declared):
        errors.extend(_asset_mapping_errors(name, assets[name], production_config))
    return errors


def main() -> int:
    """Run the contract for every event; merge pushes also require live publication.

    Returns:
        Process status indicating whether all visual asset requirements passed.
    """
    errors = contract_errors()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    publish_result = os.environ.get("VISUAL_PUBLISH_RESULT", "")
    publish_required = os.environ.get("VISUAL_PUBLISH_REQUIRED", "").lower() == "true"
    # Preserve local/manual test behavior, but require publication for both merge pushes
    # and the hosted fallback dispatch that actually runs the publisher.
    if not os.environ.get("VISUAL_PUBLISH_REQUIRED"):
        publish_required = event_name == "push" and ref == "refs/heads/main"
    if publish_required and publish_result != "success":
        errors.append(
            "main visual-evidence release must generate and publish the exact visual inventory; "
            f"publisher result was {publish_result!r}"
        )
    if errors:
        for error in errors:
            sys.stderr.write(f"visual-asset-contract-error={error}\n")
        return 1
    try:
        count = len(documented_assets(ROOT))
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"visual-asset-contract-error={exc}\n")
        return 1
    event = event_name or "local"
    sys.stdout.write(
        f"visual-asset-contract=passed documented_and_generated={count} event={event}\n"
    )
    if event_name == "push" and ref == "refs/heads/main":
        sys.stdout.write(f"merge-publication=passed result={publish_result}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
