"""Position-level contact projection for closed rigid collision meshes.

The native PBD binding detects rigid-body contacts, but its rigid-body contacts are
not included in the library's position-constraint projection pass. This helper
keeps cloth particles outside a closed collision mesh after each native substep.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.spatial import KDTree

from freecad_cloth.shared.collision import CollisionSurface


class MeshCollisionProjector:
    """Project points to the exterior clearance shell of a closed triangle mesh."""

    def __init__(self, surface: CollisionSurface, clearance_mm: float) -> None:
        """Prepare outward-facing triangles and a spatial index for the target mesh."""
        if not np.isfinite(clearance_mm) or clearance_mm <= 0.0:
            raise ValueError("collision projection clearance must be positive and finite")
        if len(surface.vertices) < 4 or len(surface.triangles) < 4:
            raise ValueError("collision projection requires a closed triangle mesh")

        self.clearance_mm = float(clearance_mm)
        self._vertices = np.asarray(surface.vertices, dtype=np.float64)
        self._triangles = np.asarray(surface.triangles, dtype=np.int64).reshape((-1, 3))

        # A closed two-manifold needs each undirected edge exactly twice, with
        # opposite directed orientation. Fail open for unsupported target meshes:
        # their native PBD collision handling remains enabled.
        directed_edges = np.concatenate(
            (
                self._triangles[:, (0, 1)],
                self._triangles[:, (1, 2)],
                self._triangles[:, (2, 0)],
            ),
            axis=0,
        )
        undirected_edges = np.sort(directed_edges, axis=1)
        _unique_edges, edge_group, edge_counts = np.unique(
            undirected_edges,
            axis=0,
            return_inverse=True,
            return_counts=True,
        )
        edge_directions = np.where(directed_edges[:, 0] < directed_edges[:, 1], 1.0, -1.0)
        edge_balance = np.bincount(edge_group, weights=edge_directions)
        if not bool(np.all(edge_counts == 2) and np.all(edge_balance == 0.0)):
            raise ValueError("collision projection requires a closed, consistently oriented mesh")

        triangles = self._vertices[self._triangles]
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        raw_normals = np.cross(b - a, c - a)
        lengths = np.linalg.norm(raw_normals, axis=1)
        if bool(np.any(lengths <= 1e-12)):
            raise ValueError("collision projection mesh contains degenerate triangles")

        signed_volume_times_six = float(
            np.einsum("ij,ij->i", a, np.cross(b, c)).sum(dtype=np.float64)
        )
        if abs(signed_volume_times_six) <= 1e-9:
            raise ValueError("collision projection mesh has no reliable enclosed volume")
        orientation = 1.0 if signed_volume_times_six > 0.0 else -1.0
        self._normals = raw_normals * (orientation / lengths[:, None])
        self._tree = KDTree(np.mean(triangles, axis=1))
        self._candidate_count = min(32, len(self._triangles))

    def project(self, points_mm: Sequence[Sequence[float]]) -> tuple[np.ndarray, np.ndarray]:
        """Return corrected world-mm positions and outward normals for moved points.

        Zero rows in the returned normal array mark positions that did not require a
        correction. Closest-triangle calculations are vectorized across cloth points
        and a local set of target faces, avoiding point-by-all-triangles matrices.
        """
        points = np.asarray(points_mm, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError("collision projection points must have shape (N, 3)")
        if not bool(np.isfinite(points).all()):
            raise ValueError("collision projection points must be finite")
        corrected = points.copy()
        contact_normals = np.zeros_like(points)
        if points.shape[0] == 0:
            return corrected, contact_normals

        _, candidate_ids = self._tree.query(
            points,
            k=self._candidate_count,
            eps=0.0,
            workers=1,
        )
        candidate_triangles = self._triangles[np.asarray(candidate_ids, dtype=np.int64)]
        triangles = self._vertices[candidate_triangles]
        a, b, c = triangles[:, :, 0, :], triangles[:, :, 1, :], triangles[:, :, 2, :]
        p = points[:, None, :]
        ab, ac = b - a, c - a
        ap = p - a

        d00 = np.einsum("nkd,nkd->nk", ab, ab)
        d01 = np.einsum("nkd,nkd->nk", ab, ac)
        d11 = np.einsum("nkd,nkd->nk", ac, ac)
        d20 = np.einsum("nkd,nkd->nk", ap, ab)
        d21 = np.einsum("nkd,nkd->nk", ap, ac)
        denominator = d00 * d11 - d01 * d01
        safe_denominator = np.where(np.abs(denominator) > 1e-18, denominator, 1.0)
        v = (d11 * d20 - d01 * d21) / safe_denominator
        w = (d00 * d21 - d01 * d20) / safe_denominator
        u = 1.0 - v - w
        projected_plane = a + v[:, :, None] * ab + w[:, :, None] * ac
        barycentric_inside = (
            (u >= -1e-10)
            & (v >= -1e-10)
            & (w >= -1e-10)
            & (denominator > 1e-18)
        )

        edge_ab = ab
        edge_bc = c - b
        edge_ca = a - c

        def closest_on_edge(start: np.ndarray, edge: np.ndarray) -> np.ndarray:
            start_to_point = p - start
            edge_length_squared = np.einsum("nkd,nkd->nk", edge, edge)
            parameter = np.divide(
                np.einsum("nkd,nkd->nk", start_to_point, edge),
                edge_length_squared,
                out=np.zeros_like(edge_length_squared),
                where=edge_length_squared > 1e-18,
            )
            parameter = np.clip(parameter, 0.0, 1.0)
            return start + parameter[:, :, None] * edge

        edge_points = np.stack(
            (
                closest_on_edge(a, edge_ab),
                closest_on_edge(b, edge_bc),
                closest_on_edge(c, edge_ca),
            ),
            axis=2,
        )
        edge_distances = np.einsum(
            "nked,nked->nke", p[:, :, None, :] - edge_points, p[:, :, None, :] - edge_points
        )
        closest_edge_index = np.argmin(edge_distances, axis=2)
        row_indices = np.arange(points.shape[0])[:, None]
        candidate_slots = np.arange(self._candidate_count)[None, :]
        projected_edge = edge_points[row_indices, candidate_slots, closest_edge_index]
        closest = np.where(barycentric_inside[:, :, None], projected_plane, projected_edge)
        squared_distance = np.einsum("nkd,nkd->nk", p - closest, p - closest)

        nearest_candidate = np.argmin(squared_distance, axis=1)
        row_indices = np.arange(points.shape[0])
        nearest_points = closest[row_indices, nearest_candidate]
        nearest_face_slots = np.asarray(candidate_ids, dtype=np.int64)[
            row_indices, nearest_candidate
        ]
        outward = self._normals[nearest_face_slots]
        signed_distance = np.einsum("nd,nd->n", points - nearest_points, outward)
        needs_projection = signed_distance < self.clearance_mm - 1e-8
        if bool(np.any(needs_projection)):
            projected = nearest_points[needs_projection] + (
                self.clearance_mm * outward[needs_projection]
            )
            corrected[needs_projection] = projected
            contact_normals[needs_projection] = outward[needs_projection]

        return corrected, contact_normals
