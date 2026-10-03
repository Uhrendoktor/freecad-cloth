"""Canonical source snapshots for the Pattern -> Sewing -> Simulation flow.

The canonical headless value model is in :mod:`PatternModel`; :mod:`SeamGraph` is the processing graph projected from those values.  This module
contains only immutable, derived synchronization metadata.  UI/document objects
can retain a snapshot while a simulation is running without creating another
mutable copy of pattern or seam semantics.
"""

import hashlib
import json
from dataclasses import dataclass

from freecad_cloth.sewing.SeamGraph import SeamGraph


class SimulationLockedError(RuntimeError):
    """Raised when a source edit is attempted while a simulation is active."""


@dataclass(frozen=True)
class PatternSourceSnapshot:
    """Immutable representation of all inputs that affect derived simulation data."""

    digest: str
    pieces: tuple[tuple, ...]
    seams: tuple[tuple, ...]
    assembly_transforms: tuple[tuple, ...]

    @classmethod
    def from_graph(cls, graph: SeamGraph) -> "PatternSourceSnapshot":
        """Provide the public from graph operation."""
        graph.validate()
        pieces = tuple(
            (
                piece.id,
                piece.name,
                tuple((float(x), float(y)) for x, y in piece.outline),
                float(piece.seam_allowance),
                float(piece.grainline_angle),
                _freeze_mapping(piece.metadata),
            )
            for piece in sorted(graph.pieces.values(), key=lambda item: item.id)
        )
        seams = tuple(
            (
                seam.id,
                seam.piece_a,
                seam.edge_a,
                seam.piece_b,
                seam.edge_b,
                float(seam.start_a),
                float(seam.end_a),
                float(seam.start_b),
                float(seam.end_b),
                bool(seam.reversed_b),
                seam.alignment,
                seam.stitch_group,
                seam.kind,
            )
            for seam in (pair.seam for _, pair in sorted(graph.seams.items()))
        )
        transforms = tuple(
            (piece_id, tuple(float(value) for value in graph.assembly_transforms[piece_id].matrix))
            for piece_id in sorted(graph.assembly_transforms)
        )
        payload = {"pieces": pieces, "seams": seams, "assembly_transforms": transforms}
        digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(digest, pieces, seams, transforms)

    def diff(self, newer: "PatternSourceSnapshot") -> "SnapshotDelta":
        """Return the changes between snapshots."""
        if not isinstance(newer, PatternSourceSnapshot):
            raise TypeError("newer snapshot must be a PatternSourceSnapshot")
        old_pieces = {item[0]: item for item in self.pieces}
        new_pieces = {item[0]: item for item in newer.pieces}
        old_seams = {item[0]: item for item in self.seams}
        new_seams = {item[0]: item for item in newer.seams}
        old_transforms = {item[0]: item for item in self.assembly_transforms}
        new_transforms = {item[0]: item for item in newer.assembly_transforms}
        return SnapshotDelta(
            changed=self.digest != newer.digest,
            changed_pieces=tuple(
                sorted(
                    k
                    for k in set(old_pieces) | set(new_pieces)
                    if old_pieces.get(k) != new_pieces.get(k)
                )
            ),
            changed_seams=tuple(
                sorted(
                    k
                    for k in set(old_seams) | set(new_seams)
                    if old_seams.get(k) != new_seams.get(k)
                )
            ),
            changed_transforms=tuple(
                sorted(
                    k
                    for k in set(old_transforms) | set(new_transforms)
                    if old_transforms.get(k) != new_transforms.get(k)
                )
            ),
        )


@dataclass(frozen=True)
class SnapshotDelta:
    """Derived change classification between two source snapshots."""

    changed: bool
    changed_pieces: tuple[str, ...] = ()
    changed_seams: tuple[str, ...] = ()
    changed_transforms: tuple[str, ...] = ()

    @property
    def requires_rebuild(self) -> bool:
        """Any source change invalidates derived simulation topology/geometry."""
        return self.changed

    @property
    def requires_reprojection(self) -> bool:
        """Transform-only edits can reuse topology but must update world positions."""
        return bool(self.changed_transforms) and not self.changed_pieces and not self.changed_seams


class SynchronizationState:
    """Small lifecycle guard for consumers that own a running simulation.

    The state does not copy or mutate pattern/seam semantics.  It only records
    the immutable source snapshot used to initialize the active simulation and
    whether source edits are currently permitted.
    """

    def __init__(self):
        self._active_snapshot = None
        self._simulation_active = False

    @property
    def simulation_active(self) -> bool:
        """Return whether simulation editing is active."""
        return self._simulation_active

    @property
    def active_snapshot(self):
        """Return the active synchronized snapshot."""
        return self._active_snapshot

    def begin(self, snapshot: PatternSourceSnapshot) -> None:
        """Begin a synchronized editing session."""
        if not isinstance(snapshot, PatternSourceSnapshot):
            raise TypeError("simulation snapshot must be a PatternSourceSnapshot")
        self._active_snapshot = snapshot
        self._simulation_active = True

    def end(self) -> None:
        """End the synchronized editing session."""
        self._active_snapshot = None
        self._simulation_active = False

    def require_editable(self) -> None:
        """Require the current state to be editable."""
        if self._simulation_active:
            raise SimulationLockedError(
                "pattern/seam edits are disabled while simulation is active"
            )


def _freeze_mapping(value: dict) -> tuple:
    """Recursively convert metadata to deterministic immutable tuples."""
    if not isinstance(value, dict):
        raise TypeError("pattern metadata must be a dictionary")
    return tuple(
        (str(key), _freeze_value(item))
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
    )


def _freeze_value(value):
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported metadata value: {type(value).__name__}")


def _canonical_json(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=list
    )
