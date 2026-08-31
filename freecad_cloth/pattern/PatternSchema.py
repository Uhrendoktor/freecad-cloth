"""Versioned, deterministic serialization for sewing pattern documents."""
from dataclasses import asdict, dataclass, field
import json
from typing import Any, Dict, List, Tuple

SCHEMA_VERSION = 1


@dataclass
class PatternDocument:
    """GUI-independent document model suitable for JSON interchange."""
    pattern_id: str
    name: str
    pieces: List[Dict[str, Any]] = field(default_factory=list)
    seams: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        if not self.pattern_id.strip():
            raise ValueError("pattern_id must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version: {self.schema_version}")
        ids = [piece.get("id") for piece in self.pieces]
        if any(not isinstance(value, str) or not value for value in ids):
            raise ValueError("every piece needs a non-empty stable id")
        if len(ids) != len(set(ids)):
            raise ValueError("piece IDs must be unique")
        for seam in self.seams:
            if not seam.get("id"):
                raise ValueError("every seam needs a stable id")
            if seam.get("piece_a") not in ids or seam.get("piece_b") not in ids:
                raise ValueError("seam references an unknown piece")


def to_dict(document: PatternDocument) -> Dict[str, Any]:
    document.validate()
    return asdict(document)


def dumps(document: PatternDocument) -> str:
    """Serialize canonically so equivalent documents have identical JSON."""
    return json.dumps(to_dict(document), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def loads(text: str) -> PatternDocument:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid pattern JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("pattern document must be a JSON object")
    document = PatternDocument(**raw)
    document.validate()
    return document


def migrate(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Migration entry point; future schema versions can be added explicitly."""
    version = raw.get("schema_version", 0)
    if version == SCHEMA_VERSION:
        return dict(raw)
    raise ValueError(f"no migration available for schema version {version}")
