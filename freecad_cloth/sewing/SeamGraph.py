"""FreeCAD-independent sewing graph and assembly metadata.

``PatternModel.Seam`` is the authoritative semantic seam contract.  The graph
stores that object directly; ``SeamPair`` is only presentation metadata and a
compatibility adapter, not a second seam representation.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from math import isfinite
from typing import cast

from freecad_cloth.common.ValidationModels import (
    TransformMatrixInput, validate_finite_number, validate_points3d,
)
from freecad_cloth.pattern.PatternModel import EdgeRef, PatternPiece, Seam
from freecad_cloth.sewing.SewingCorrespondence import arc_length_vertex_indices


@dataclass(frozen=True)
class Transform3D:
    """Rigid-free assembly transform represented by a 4x4 row-major matrix."""

    matrix: tuple[float, ...] = (
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )

    def __post_init__(self) -> None:
        validated = TransformMatrixInput(matrix=self.matrix)
        object.__setattr__(self, "matrix", validated.matrix)

    @classmethod
    def identity(cls) -> "Transform3D":
        """Provide the public identity operation."""
        return cls()

    @classmethod
    def translation(cls, x: float, y: float, z: float = 0.0) -> "Transform3D":
        """Provide the public translation operation."""
        values = list(cls().matrix)
        values[3], values[7], values[11] = (
            validate_finite_number(x), validate_finite_number(y), validate_finite_number(z)
        )
        return cls(tuple(values))

    def apply(self, point: Sequence[float]) -> tuple[float, float, float]:
        """Provide the public apply operation."""
        x, y, z = validate_points3d((point,))[0]
        m = self.matrix
        w = m[12] * x + m[13] * y + m[14] * z + m[15]
        if not isfinite(w) or abs(w) < 1e-12:
            raise ValueError("assembly transform produced invalid homogeneous scale")
        result = (
            (m[0] * x + m[1] * y + m[2] * z + m[3]) / w,
            (m[4] * x + m[5] * y + m[6] * z + m[7]) / w,
            (m[8] * x + m[9] * y + m[10] * z + m[11]) / w,
        )
        return validate_points3d((result,))[0]


@dataclass(frozen=True)
class SeamPair:
    """Canonical seam plus non-semantic stitch presentation metadata."""

    seam: Seam
    stitch_group: str = ""
    alignment: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "stitch_group", self.seam.stitch_group or self.stitch_group or self.seam.id
        )
        object.__setattr__(
            self, "alignment", self.seam.alignment if not self.alignment else self.alignment
        )

    @property
    def id(self) -> str:
        """Return the stable identifier."""
        return self.seam.id

    @property
    def piece_a(self) -> str:
        """Return the first referenced pattern piece."""
        return self.seam.piece_a

    @property
    def edge_a(self) -> EdgeRef:
        """Return the first referenced edge."""
        return self.seam.edge_a

    @property
    def piece_b(self) -> str:
        """Return the second referenced pattern piece."""
        return self.seam.piece_b

    @property
    def edge_b(self) -> EdgeRef:
        """Return the second referenced edge."""
        return self.seam.edge_b

    @property
    def reversed_b(self) -> bool:
        """Read reversal from the canonical seam; never copy it into the pair."""
        return self.seam.reversed_b

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        self.seam.validate()
        if self.stitch_group != (self.seam.stitch_group or self.seam.id):
            raise ValueError("stitch group disagrees with canonical seam metadata")
        if self.alignment != self.seam.alignment:
            raise ValueError("alignment disagrees with canonical seam metadata")


@dataclass
class SeamGraph:
    """Validated seam graph for a set of pattern pieces."""

    pieces: dict[str, PatternPiece] = field(default_factory=dict)
    seams: dict[str, SeamPair] = field(default_factory=dict)
    assembly_transforms: dict[str, Transform3D] = field(default_factory=dict)

    def add_piece(self, piece: PatternPiece) -> None:
        """Add a pattern piece to this collection."""
        piece.validate()
        if piece.id in self.pieces:
            raise ValueError(f"duplicate pattern piece id: {piece.id}")
        self.pieces[piece.id] = piece
        self.assembly_transforms.setdefault(piece.id, Transform3D.identity())

    def add_seam(self, seam: Seam, stitch_group: str = "", alignment: str = "endpoints") -> None:
        # Compatibility adapters such as SewingSemantics.SeamConstraint can
        # hand us their canonical Seam without making the graph depend on them.
        """Add a seam relationship to this collection."""
        if not isinstance(seam, Seam):
            to_seam = getattr(seam, "to_seam", None)
            if to_seam is None:
                raise TypeError("seam must be PatternModel.Seam or a canonical seam adapter")
            seam = to_seam()
        if stitch_group or alignment != "endpoints":
            seam = replace(
                seam,
                stitch_group=stitch_group or seam.stitch_group,
                alignment=alignment or seam.alignment,
            )
        pair = SeamPair(seam, stitch_group=seam.stitch_group, alignment=seam.alignment)
        pair.validate()
        if seam.id in self.seams:
            raise ValueError(f"duplicate seam id: {seam.id}")
        self._validate_seam_reference(seam)
        self.seams[seam.id] = pair

    def set_transform(self, piece_id: str, transform: Transform3D) -> None:
        """Set the transform associated with an object."""
        self._require_piece(piece_id)
        if not isinstance(transform, Transform3D):
            raise TypeError("transform must be a Transform3D")
        self.assembly_transforms[piece_id] = transform

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        for piece in self.pieces.values():
            piece.validate()
        for pair in self.seams.values():
            pair.validate()
            self._validate_seam_reference(pair.seam)
        for piece_id in self.pieces:
            if piece_id not in self.assembly_transforms:
                raise ValueError(f"missing assembly transform for piece: {piece_id}")

    def stitch_pairs(
        self,
        edge_vertices: Mapping[tuple[str, EdgeRef], Sequence[int]],
        seam_ids: Iterable[str] = (),
        edge_points: Mapping[tuple[str, EdgeRef], Sequence[Sequence[float]]] | None = None,
    ) -> tuple[tuple[int, int], ...]:
        """Return deterministic particle-index stitch pairs for selected seams."""
        selected = tuple(seam_ids) if seam_ids else tuple(self.seams)
        pairs = []
        for seam_id in selected:
            if seam_id not in self.seams:
                raise ValueError(f"unknown seam id: {seam_id}")
            seam = self.seams[seam_id].seam
            a = self._edge_vertices(edge_vertices, seam.piece_a, seam.edge_a)
            b = self._edge_vertices(edge_vertices, seam.piece_b, seam.edge_b)
            count = max(2, min(len(a), len(b)))
            if edge_points is None:
                a_sel = _sample_indices(a, seam.start_a, seam.end_a, count)
                b_sel = _sample_indices(b, seam.start_b, seam.end_b, count)
            else:
                a_points = self._edge_points(edge_points, seam.piece_a, seam.edge_a, len(a))
                b_points = self._edge_points(edge_points, seam.piece_b, seam.edge_b, len(b))
                a_sel = arc_length_vertex_indices(a, a_points, count, seam.start_a, seam.end_a)
                b_sel = arc_length_vertex_indices(b, b_points, count, seam.start_b, seam.end_b)
            if seam.reversed_b:
                b_sel = tuple(reversed(b_sel))
            pairs.extend(zip(a_sel, b_sel, strict=False))
        return tuple(pairs)

    @staticmethod
    def _edge_points(
        edge_points: Mapping[tuple[str, EdgeRef], Sequence[Sequence[float]]],
        piece_id: str,
        edge_index: EdgeRef,
        expected_count: int,
    ) -> tuple[Sequence[float], ...]:
        key = (piece_id, edge_index)
        if key not in edge_points:
            raise ValueError(f"missing mesh edge points for {piece_id}:{edge_index}")
        points = tuple(edge_points[key])
        if len(points) != expected_count:
            raise ValueError(f"mesh edge points do not match vertices for {piece_id}:{edge_index}")
        return points

    def to_metadata(self) -> dict:
        """Return deterministic JSON-friendly document metadata."""
        self.validate()
        return {
            "pieces": tuple(sorted(self.pieces)),
            "seams": tuple(
                (
                    sid,
                    pair.stitch_group,
                    pair.alignment,
                    pair.seam.piece_a,
                    pair.seam.edge_a,
                    pair.seam.piece_b,
                    pair.seam.edge_b,
                    pair.seam.start_a,
                    pair.seam.end_a,
                    pair.seam.start_b,
                    pair.seam.end_b,
                    pair.seam.reversed_b,
                    pair.seam.kind,
                )
                for sid, pair in sorted(self.seams.items())
            ),
            "assembly_transforms": tuple(
                (pid, self.assembly_transforms[pid].matrix)
                for pid in sorted(self.assembly_transforms)
            ),
        }

    def _validate_seam_reference(self, seam: Seam) -> None:
        a = self._require_piece(seam.piece_a)
        b = self._require_piece(seam.piece_b)
        if isinstance(seam.edge_a, int) and seam.edge_a >= len(a.outline):
            raise ValueError("seam edge index is outside the pattern boundary")
        if isinstance(seam.edge_b, int) and seam.edge_b >= len(b.outline):
            raise ValueError("seam edge index is outside the pattern boundary")

    def _require_piece(self, piece_id: str) -> PatternPiece:
        if piece_id not in self.pieces:
            raise ValueError(f"unknown pattern piece: {piece_id}")
        return self.pieces[piece_id]

    @staticmethod
    def _edge_vertices(
        edge_vertices: Mapping[tuple[str, EdgeRef], Sequence[object]],
        piece_id: str,
        edge_index: EdgeRef,
    ) -> tuple[int, ...]:
        key = (piece_id, edge_index)
        if key not in edge_vertices:
            raise ValueError(f"missing mesh edge vertices for {piece_id}:{edge_index}")
        raw_values = tuple(edge_vertices[key])
        if any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in raw_values):
            raise ValueError(f"mesh edge {piece_id}:{edge_index} contains invalid vertex indices")
        values = tuple(cast(int, index) for index in raw_values)
        if len(values) < 2:
            raise ValueError(f"mesh edge {piece_id}:{edge_index} needs at least two vertices")
        return values


def _sample_indices(
    values: Sequence[int], start: float, end: float, count: int
) -> list[int]:
    span = end - start
    if count < 2 or span <= 0.0:
        raise ValueError("seam range must contain at least two samples")
    last = len(values) - 1
    result = []
    for i in range(count):
        t = start + span * i / (count - 1)
        index = min(last, max(0, int(round(t * last))))
        if result and index == result[-1] and index < last:
            index += 1
        result.append(values[index])
    return result
