"""Fail closed when documented visual assets are unused or have no CI producer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TypeAlias, cast

from visual_evidence import documented_assets

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools" / "ci" / "visual_asset_sources.json"
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"
PUBLISH_ACTION = ROOT / ".github" / "actions" / "publish-visual-evidence" / "action.yml"


def contract_errors() -> list[str]:
    """Validate exact documentation inventory and mapped generation sources."""
    errors: list[str] = []
    try:
        payload = cast(JSONValue, json.loads(MANIFEST.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read visual asset manifest: {exc}"]
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return ["unsupported visual asset manifest schema"]
    assets = payload.get("assets")
    if not isinstance(assets, dict):
        return ["visual asset manifest must contain an assets object"]
    try:
        documented = documented_assets(ROOT)
    except (OSError, ValueError) as exc:
        return [f"cannot compute README/wiki image inventory: {exc}"]
    declared = set(assets)
    for name in sorted(documented - declared):
        errors.append(f"documented asset has no producer mapping: {name}")
    for name in sorted(declared - documented):
        errors.append(f"producer mapping is unused by README/wiki: {name}")
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    publisher_text = PUBLISH_ACTION.read_text(encoding="utf-8")
    production_config = workflow_text + chr(10) + publisher_text
    required_upload_patterns = (
        "docs/images/generated/*.png",
        "docs/images/generated/*.gif",
        "docs/images/generated/*.log",
        "docs/images/generated/*.txt",
    )
    for pattern in required_upload_patterns:
        if pattern not in workflow_text:
            errors.append(f"turntable artifact upload does not include required pattern: {pattern}")
    for name in sorted(documented & declared):
        entry = assets[name]
        if not isinstance(entry, dict):
            errors.append(f"{name}: mapping must be an object")
            continue
        artifact = entry.get("artifact")
        if not isinstance(artifact, str) or not artifact or artifact not in production_config:
            errors.append(
                f"{name}: artifact is not produced/uploaded by canonical CI: {artifact!r}"
            )
        producers = entry.get("producers")
        if not isinstance(producers, list) or not producers:
            errors.append(f"{name}: at least one producer path is required")
            continue
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


def main() -> int:
    """Run the contract for every event; merge pushes also require live publication."""
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
            print(f"visual-asset-contract-error={error}", file=sys.stderr)
        return 1
    try:
        count = len(documented_assets(ROOT))
    except (OSError, ValueError) as exc:
        print(f"visual-asset-contract-error={exc}", file=sys.stderr)
        return 1
    event = event_name or "local"
    print(f"visual-asset-contract=passed documented_and_generated={count} event={event}")
    if event_name == "push" and ref == "refs/heads/main":
        print(f"merge-publication=passed result={publish_result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
