"""Compatibility import for the canonical semantic edge-reference implementation.

The authoritative implementation lives in freecad_cloth.pattern.SeamReference.
Keep this module as a thin compatibility surface so old document/sewing imports
do not create a second implementation.
"""
from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    EdgeReference,
    EdgeReferenceError,
    MissingEdgeReference,
    NATIVE_SIGNATURE_PREFIX,
    capture_edge_reference,
    edge_signature,
    resolve_edge_reference,
    resolve_edge_reference_status,
    semantic_edge_id,
)

__all__ = [
    "ChangedEdgeReference",
    "EdgeReference",
    "EdgeReferenceError",
    "MissingEdgeReference",
    "NATIVE_SIGNATURE_PREFIX",
    "capture_edge_reference",
    "edge_signature",
    "resolve_edge_reference",
    "resolve_edge_reference_status",
    "semantic_edge_id",
]