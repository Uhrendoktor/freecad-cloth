"""FreeCAD-independent derived geometry and construction marks for patterns."""
from dataclasses import dataclass
from math import atan2, cos, hypot
from typing import Dict, Iterable, List, Tuple
from PatternGeometry import LineSegment, ParametricPattern, Point, QuadraticBezier, Segment

@dataclass(frozen=True)
class Notch:
    id: str
    segment_id: str
    t: float
    depth: float = 3.0
    def validate(self) -> None:
        if not self.id: raise ValueError("notch ID must not be empty")
        if not 0.0 <= self.t <= 1.0: raise ValueError("notch position must be between 0 and 1")
        if self.depth <= 0: raise ValueError("notch depth must be positive")

@dataclass(frozen=True)
class PatternMark:
    """A persistent semantic construction mark attached to the sewing line."""
    id: str
    kind: str
    segment_id: str = ""
    t: float = 0.5
    angle: float = 0.0
    length: float = 40.0
    text: str = ""
    def validate(self) -> None:
        if not self.id.strip() or not self.kind.strip(): raise ValueError("pattern mark ID and kind must not be empty")
        if not 0.0 <= self.t <= 1.0: raise ValueError("pattern mark position must be between 0 and 1")
        if self.length <= 0: raise ValueError("pattern mark length must be positive")

@dataclass(frozen=True)
class OffsetEdge:
    id: str
    points: Tuple[Point, ...]

@dataclass(frozen=True)
class DerivedPattern:
    sewing_boundary: ParametricPattern
    cut_boundary: Tuple[OffsetEdge, ...]
    notches: Tuple[Notch, ...]
    marks: Tuple[PatternMark, ...] = ()

def derive_cut_boundary(pattern: ParametricPattern, width: float, edge_widths: Dict[str, float] | None = None, curve_samples: int = 32, miter_limit: float = 4.0) -> DerivedPattern:
    if width < 0: raise ValueError("seam allowance width must be non-negative")
    if curve_samples < 2: raise ValueError("curve_samples must be at least 2")
    if miter_limit < 1: raise ValueError("miter_limit must be at least 1")
    edge_widths = edge_widths or {}; unknown=set(edge_widths)-set(pattern.by_id())
    if unknown: raise ValueError(f"unknown edge width IDs: {sorted(unknown)}")
    if any(value < 0 for value in edge_widths.values()): raise ValueError("seam allowance widths must be non-negative")
    sampled=_sample_segments(pattern.segments,curve_samples); outline=[point for points in sampled for point in points[:-1]]; orientation=_signed_area(outline)
    if abs(orientation)<1e-12 and width: raise ValueError("pattern outline must enclose a non-zero area")
    outward_sign=-1.0 if orientation>0 else 1.0; cut_edges=[]
    for segment,points in zip(pattern.segments,sampled):
        allowance=edge_widths.get(segment.id,width); cut_edges.append(OffsetEdge(segment.id,tuple(_offset_polyline(points,allowance,outward_sign,miter_limit))))
    return DerivedPattern(pattern,tuple(cut_edges),())

def add_notches(derived: DerivedPattern, notches: Iterable[Notch]) -> DerivedPattern:
    by_id=derived.sewing_boundary.by_id(); result=list(derived.notches); ids={n.id for n in result}|{m.id for m in derived.marks}
    for notch in notches:
        notch.validate()
        if notch.segment_id not in by_id: raise ValueError(f"notch references unknown segment: {notch.segment_id}")
        if notch.id in ids: raise ValueError(f"duplicate construction mark ID: {notch.id}")
        ids.add(notch.id); result.append(notch)
    return DerivedPattern(derived.sewing_boundary,derived.cut_boundary,tuple(result),derived.marks)

def add_marks(derived: DerivedPattern, marks: Iterable[PatternMark]) -> DerivedPattern:
    by_id=derived.sewing_boundary.by_id(); result=list(derived.marks); ids={n.id for n in derived.notches}|{m.id for m in result}
    for mark in marks:
        mark.validate()
        if mark.segment_id and mark.segment_id not in by_id: raise ValueError(f"pattern mark references unknown segment: {mark.segment_id}")
        if mark.id in ids: raise ValueError(f"duplicate construction mark ID: {mark.id}")
        ids.add(mark.id); result.append(mark)
    return DerivedPattern(derived.sewing_boundary,derived.cut_boundary,derived.notches,tuple(result))

def notch_point(pattern: ParametricPattern, notch: Notch) -> Point:
    notch.validate(); segment=pattern.by_id().get(notch.segment_id)
    if segment is None: raise ValueError(f"notch references unknown segment: {notch.segment_id}")
    return segment.point(notch.t)

def mark_point(pattern: ParametricPattern, mark: PatternMark) -> Point:
    mark.validate()
    if not mark.segment_id: return pattern.sampled_outline(2)[0]
    segment=pattern.by_id().get(mark.segment_id)
    if segment is None: raise ValueError(f"pattern mark references unknown segment: {mark.segment_id}")
    return segment.point(mark.t)

def _sample_segments(segments: Iterable[Segment], curve_samples: int) -> List[List[Point]]:
    result=[]
    for segment in segments:
        if isinstance(segment,LineSegment): result.append([segment.start,segment.end])
        elif isinstance(segment,QuadraticBezier): result.append(segment.polyline(curve_samples))
        else: raise TypeError(f"unsupported segment type: {type(segment).__name__}")
    return result

def _offset_polyline(points: List[Point], width: float, outward_sign: float, miter_limit: float) -> List[Point]:
    if width==0: return list(points)
    if len(points)<2: raise ValueError("an edge needs at least two points")
    normals=[]
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1]; length=hypot(dx,dy)
        normals.append((0.0,0.0) if length==0 else (outward_sign*(-dy/length),outward_sign*(dx/length)))
    result=[]
    for index,point in enumerate(points):
        if index==0: normal=normals[0]
        elif index==len(points)-1: normal=normals[-1]
        else:
            n1,n2=normals[index-1],normals[index]; summed=(n1[0]+n2[0],n1[1]+n2[1]); norm=hypot(*summed); normal=n2 if norm==0 else (summed[0]/norm,summed[1]/norm)
        scale=width
        if index not in (0,len(points)-1):
            tangent_change=abs(atan2(normals[index][1],normals[index][0])-atan2(normals[index-1][1],normals[index-1][0]))
            while tangent_change>3.141592653589793: tangent_change-=2*3.141592653589793
            cosine_half=max(0.25,abs(cos(tangent_change/2))); scale=min(width/cosine_half,width*miter_limit)
        result.append((point[0]+normal[0]*scale,point[1]+normal[1]*scale))
    return result

def _signed_area(points: List[Point]) -> float:
    return 0.5*sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
