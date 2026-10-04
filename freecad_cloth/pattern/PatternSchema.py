"""Versioned, deterministic serialization for sewing pattern documents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import cast

type JSONValue = object
type JSONObject = dict[str, JSONValue]
type JSONRecord = dict[str, JSONValue]

SCHEMA_VERSION = 1


@dataclass
class PatternDocument:
    """GUI-independent document model suitable for JSON interchange."""

    pattern_id: str
    name: str
    pieces: list[JSONRecord] = field(default_factory=lambda: cast(list[JSONRecord], []))
    seams: list[JSONRecord] = field(default_factory=lambda: cast(list[JSONRecord], []))
    metadata: JSONObject = field(default_factory=lambda: cast(JSONObject, {}))
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        """Validate stable identifiers and schema compatibility."""
        if not self.pattern_id.strip():
            raise ValueError("pattern_id must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version: {self.schema_version}")
        ids: list[str] = []
        for piece in self.pieces:
            value = piece.get("id")
            if not isinstance(value, str) or not value:
                raise ValueError("every piece needs a non-empty stable id")
            ids.append(value)
        if len(ids) != len(set(ids)):
            raise ValueError("piece IDs must be unique")
        for seam in self.seams:
            seam_id = seam.get("id")
            if not isinstance(seam_id, str) or not seam_id:
                raise ValueError("every seam needs a stable id")
            piece_a = seam.get("piece_a")
            piece_b = seam.get("piece_b")
            if piece_a not in ids or piece_b not in ids:
                raise ValueError("seam references an unknown piece")


def to_dict(document: PatternDocument) -> JSONObject:
    """Validate and return the document as JSON-compatible data."""
    document.validate()
    return cast(JSONObject, asdict(document))


def dumps(document: PatternDocument) -> str:
    """Serialize canonically so equivalent documents have identical JSON."""
    return json.dumps(to_dict(document), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _required_string(raw: JSONObject, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _records(raw: JSONObject, key: str) -> list[JSONRecord]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    records: list[JSONRecord] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise ValueError(f"every {key} entry must be an object")
        mapping = cast(dict[object, object], item)
        records.append({str(name): value for name, value in mapping.items()})
    return records


def loads(text: str) -> PatternDocument:
    """Parse and validate a pattern JSON document."""
    try:
        raw_value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid pattern JSON") from exc
    if not isinstance(raw_value, dict):
        raise ValueError("pattern document must be a JSON object")
    raw = cast(JSONObject, raw_value)
    metadata_value = raw.get("metadata", {})
    schema_value = raw.get("schema_version", SCHEMA_VERSION)
    if not isinstance(metadata_value, dict):
        raise ValueError("metadata must be an object")
    if type(schema_value) is not int:
        raise ValueError("schema_version must be an integer")
    metadata_mapping = cast(dict[object, object], metadata_value)
    document = PatternDocument(
        pattern_id=_required_string(raw, "pattern_id"),
        name=_required_string(raw, "name"),
        pieces=_records(raw, "pieces"),
        seams=_records(raw, "seams"),
        metadata={str(name): value for name, value in metadata_mapping.items()},
        schema_version=schema_value,
    )
    document.validate()
    return document


def migrate(raw: JSONObject) -> JSONObject:
    """Migrate a parsed JSON object when an explicit schema migration exists."""
    version = raw.get("schema_version", 0)
    if version == SCHEMA_VERSION:
        return dict(raw)
    raise ValueError(f"no migration available for schema version {version}")
