"""FreeCAD-independent sewing graph and assembly metadata.

``PatternModel.Seam`` is the authoritative semantic seam contract. The graph
stores that object directly; ``SeamPair`` is only presentation metadata and a
compatibility adapter, not a second seam representation.
"""
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from PatternModel import PatternPiece, Seam


@dataclass(frozen=True)
class Transform3D:
    """Rigid-free assembly transform represented by a 4x4 row-major matrix."""
    matrix: Tuple[float, ...] = (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )

    def __post_init__(self):
        if len(self.matrix) != 16:
            raise ValueError("assembly transform must contain 16 values")
        if abs(self.matrix[15]) < 1e-12:
            raise ValueError("assembly transform has an invalid homogeneous scale")

    @classmethod
    def identity(cls):
        return cls()

    @classmethod
    def translation(cls, x: float, y: float, z: float = 0.0):
        values = list(cls().matrix)
        values[3], values[7], values[11] = float(x), float(y), float(z)
        return cls(tuple(values))

    def apply(self, point: Sequence[float]) -> Tuple[float, float, float]:
        if len(point) != 3:
            raise ValueError("point must contain three coordinates")
        x, y, z = point
        m = self.matrix
        w = m[12] * x + m[13] * y + m[14] * z + m[15]
        if abs(w) < 1e-12:
            raise ValueError("assembly transform produced invalid homogeneous scale")
        return ((m[0] * x + m[1] * y + m[2] * z + m[3]) / w,
                (m[4] * x + m[5] * y + m[6] * z + m[7]) / w,
                (m[8] * x + m[9] * y + m[10] * z + m[11]) / w)


@dataclass(frozen=True)
class SeamPair:
    """Canonical seam plus non-semantic compatibility metadata."""
    seam: Seam
    stitch_group: str = ""
    alignment: str = ""

    def __post_init__(self):
        object.__setattr__(self, "stitch_group", self.seam.stitch_group or self.stitch_group or self.seam.id)
        object.__setattr__(self, "alignment", self.seam.alignment if not self.alignment else self.alignment)

    @property
    def id(self): return self.seam.id
    @property
    def piece_a(self): return self.seam.piece_a
    @property
    def edge_a(self): return self.seam.edge_a
    @property
    def piece_b(self): return self.seam.piece_b
    @property
    def edge_b(self): return self.seam.edge_b
    @property
    def reversed_b(self): return self.seam.reversed_b

    def validate(self) -> None:
        self.seam.validate()
        if self.stitch_group != (self.seam.stitch_group or self.seam.id):
            raise ValueError("stitch group disagrees with canonical seam metadata")
        if self.alignment != self.seam.alignment:
            raise ValueError("alignment disagrees with canonical seam metadata")


@dataclass
class SeamGraph:
    """Validated seam graph for a set of pattern pieces."""
    pieces: Dict[str, PatternPiece] = field(default_factory=dict)
    seams: Dict[str, SeamPair] = field(default_factory=dict)
    assembly_transforms: Dict[str, Transform3D] = field(default_factory=dict)

    def add_piece(self, piece: PatternPiece) -> None:
        piece.validate()
        if piece.id in self.pieces:
            raise ValueError(f"duplicate pattern piece id: {piece.id}")
        self.pieces[piece.id] = piece
        self.assembly_transforms.setdefault(piece.id, Transform3D.identity())

    def add_seam(self, seam: Seam, stitch_group: str = "", alignment: str = "") -> None:
        if not isinstance(seam, Seam):
            to_seam = getattr(seam, "to_seam", None)
            if to_seam is None:
                raise TypeError("seam must be PatternModel.Seam or a canonical seam adapter")
            seam = to_seam()
        if stitch_group or alignment:
            seam = replace(seam, stitch_group=stitch_group or seam.stitch_group,
                           alignment=alignment or seam.alignment)
        pair = SeamPair(seam)
        pair.validate()
        if seam.id in self.seams:
            raise ValueError(f"duplicate seam id: {seam.id}")
        self._validate_seam_reference(seam)
        self.seams[seam.id] = pair

    def set_transform(self, piece_id: str, transform: Transform3D) -> None:
        self._require_piece(piece_id)
        if not isinstance(transform, Transform3D):
            raise TypeError("transform must be a Transform3D")
        self.assembly_transforms[piece_id] = transform

    def validate(self) -> None:
        for piece in self.pieces.values(): piece.validate()
        for pair in self.seams.values():
            pair.validate(); self._validate_seam_reference(pair.seam)
        for piece_id in self.pieces:
            if piece_id not in self.assembly_transforms:
                raise ValueError(f"missing assembly transform for piece: {piece_id}")

    def stitch_pairs(self, edge_vertices: Mapping[Tuple[str, int], Sequence[int]], seam_ids: Iterable[str] = ()) -> Tuple[Tuple[int, int], ...]:
        selected = tuple(seam_ids) if seam_ids else tuple(self.seams)
        pairs = []
        for seam_id in selected:
            if seam_id not in self.seams: raise ValueError(f"unknown seam id: {seam_id}")
            seam = self.seams[seam_id].seam
            a = self._edge_vertices(edge_vertices, seam.piece_a, seam.edge_a)
            b = self._edge_vertices(edge_vertices, seam.piece_b, seam.edge_b)
            count = max(2, min(len(a), len(b)))
            a_sel = _sample_indices(a, seam.start_a, seam.end_a, count)
            b_sel = _sample_indices(b, seam.start_b, seam.end_b, count)
            if seam.reversed_b: b_sel.reverse()
            pairs.extend(zip(a_sel, b_sel))
        return tuple(pairs)

    def to_metadata(self) -> dict:
        self.validate()
        return {
            "pieces": tuple(sorted(self.pieces)),
            "seams": tuple((sid, pair.stitch_group, pair.alignment,
                            pair.seam.piece_a, pair.seam.edge_a, pair.seam.piece_b,
                            pair.seam.edge_b, pair.seam.start_a, pair.seam.end_a,
                            pair.seam.start_b, pair.seam.end_b, pair.seam.reversed_b,
                            pair.seam.kind) for sid, pair in sorted(self.seams.items())),
            "assembly_transforms": tuple((pid, self.assembly_transforms[pid].matrix)
                                          for pid in sorted(self.assembly_transforms)),
        }

    def _validate_seam_reference(self, seam: Seam) -> None:
        a = self._require_piece(seam.piece_a); b = self._require_piece(seam.piece_b)
        if isinstance(seam.edge_a, int) and seam.edge_a >= len(a.outline):
            raise ValueError("seam edge index is outside the pattern boundary")
        if isinstance(seam.edge_b, int) and seam.edge_b >= len(b.outline):
            raise ValueError("seam edge index is outside the pattern boundary")

    def _require_piece(self, piece_id: str) -> PatternPiece:
        if piece_id not in self.pieces: raise ValueError(f"unknown pattern piece: {piece_id}")
        return self.pieces[piece_id]

    @staticmethod
    def _edge_vertices(edge_vertices, piece_id, edge_index):
        key = (piece_id, edge_index)
        if key not in edge_vertices: raise ValueError(f"missing mesh edge vertices for {piece_id}:{edge_index}")
        values = tuple(int(i) for i in edge_vertices[key])
        if len(values) < 2: raise ValueError(f"mesh edge {piece_id}:{edge_index} needs at least two vertices")
        return values


def _sample_indices(values: Sequence[int], start: float, end: float, count: int):
    if count < 2 or end <= start: raise ValueError("seam range must contain at least two samples")
    last = len(values) - 1; result = []
    for i in range(count):
        t = start + (end - start) * i / (count - 1)
        index = min(last, max(0, int(round(t * last))))
        if result and index == result[-1] and index < last: index += 1
        result.append(values[index])
    return result
