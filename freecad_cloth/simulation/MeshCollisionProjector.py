# Copyright (C) 2026 FreeCAD Cloth contributors
"""Position-level contact projection for closed rigid collision meshes.

The native PBD binding detects rigid-body contacts, but its rigid-body contacts are
not included in the library's position-constraint projection pass. This helper
keeps cloth particles outside a closed collision mesh after each native substep.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from scipy.spatial import KDTree

from freecad_cloth.shared.collision import CollisionSurface


class MeshCollisionProjector:
    """Project points to the exterior clearance shell of a closed triangle mesh."""

    def __init__(
        self,
        surface: CollisionSurface,
        clearance_mm: float,
        candidate_count: int = 4,
    ) -> None:
        """Prepare outward-facing triangles and a spatial index for the target mesh."""
        if not np.isfinite(clearance_mm) or clearance_mm <= 0.0:
            raise ValueError("collision projection clearance must be positive and finite")
        if len(surface.vertices) < 4 or len(surface.triangles) < 4:
            raise ValueError("collision projection requires a closed triangle mesh")
        if candidate_count < 1:
            raise ValueError("collision projection candidate count must be positive")

        self.clearance_mm = float(clearance_mm)
        self._vertices = np.asarray(surface.vertices, dtype=np.float64)
        self._triangles = np.asarray(surface.triangles, dtype=np.int64).reshape((-1, 3))
        # Points beyond the mesh AABB expanded by clearance cannot be inside or
        # touching its clearance shell, so they need no nearest-triangle query.
        self._bounds_min = self._vertices.min(axis=0) - self.clearance_mm
        self._bounds_max = self._vertices.max(axis=0) + self.clearance_mm

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
        self._centroids = np.mean(triangles, axis=1)
        self._tree = KDTree(self._centroids)
        # Target triangles in the packaged humanoid mesh are locally dense and
        # consistently sized. Fast preview uses two nearby faces to limit per-frame
        # work; production draping uses four and remains subject to exact zero-
        # penetration acceptance. This count controls candidate cost, not clearance.
        self._candidate_count = min(int(candidate_count), len(self._triangles))
        triangle_radius_mm = float(
            np.linalg.norm(triangles - self._centroids[:, None, :], axis=2).max()
        )
        self._search_radius_mm = self.clearance_mm + triangle_radius_mm + 1e-6

    def project(
        self, points_mm: npt.ArrayLike
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
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

        within_bounds = np.all(
            (points >= self._bounds_min) & (points <= self._bounds_max),
            axis=1,
        )
        if not bool(np.any(within_bounds)):
            return corrected, contact_normals
        candidate_point_indices = np.flatnonzero(within_bounds)
        candidate_points = points[within_bounds]
        centroid_distances, candidate_ids = self._tree.query(
            candidate_points,
            k=self._candidate_count,
            eps=0.0,
            workers=1,
        )
        candidate_ids = np.asarray(candidate_ids, dtype=np.int64)
        closest_face_ids = candidate_ids[:, 0]
        closest_face_normals = self._normals[closest_face_ids]
        closest_plane_signed_distance = np.einsum(
            "nd,nd->n",
            candidate_points - self._centroids[closest_face_ids],
            closest_face_normals,
        )
        # Keep points whose closest-centroid plane says "inside" active even
        # when penetration is deep, but skip points safely outside the mesh AABB.
        active = (centroid_distances[:, 0] <= self._search_radius_mm) | (
            closest_plane_signed_distance < 0.0
        )
        if not bool(np.any(active)):
            return corrected, contact_normals
        active_point_indices = candidate_point_indices[active]
        active_points = candidate_points[active]
        active_candidate_ids = candidate_ids[active]
        candidate_triangles = self._triangles[active_candidate_ids]
        triangles = self._vertices[candidate_triangles]
        a, b, c = triangles[:, :, 0, :], triangles[:, :, 1, :], triangles[:, :, 2, :]
        p = active_points[:, None, :]
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
        barycentric_inside = (u >= -1e-10) & (v >= -1e-10) & (w >= -1e-10) & (denominator > 1e-18)

        edge_ab = ab
        edge_bc = c - b
        edge_ca = a - c

        def closest_on_edge(
            start: npt.NDArray[np.float64], edge: npt.NDArray[np.float64]
        ) -> npt.NDArray[np.float64]:
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
        row_indices = np.arange(active_points.shape[0])[:, None]
        candidate_slots = np.arange(self._candidate_count)[None, :]
        projected_edge = edge_points[row_indices, candidate_slots, closest_edge_index]
        closest = np.where(barycentric_inside[:, :, None], projected_plane, projected_edge)
        squared_distance = np.einsum("nkd,nkd->nk", p - closest, p - closest)

        nearest_candidate = np.argmin(squared_distance, axis=1)
        row_indices = np.arange(active_points.shape[0])
        nearest_points = closest[row_indices, nearest_candidate]
        nearest_face_slots = active_candidate_ids[row_indices, nearest_candidate]
        outward = self._normals[nearest_face_slots]
        signed_distance = np.einsum("nd,nd->n", active_points - nearest_points, outward)
        needs_projection = signed_distance < self.clearance_mm - 1e-8
        if bool(np.any(needs_projection)):
            active_corrected = active_points.copy()
            active_normals = np.zeros_like(active_points)
            # Correct only the signed normal distance. Snapping directly to a
            # triangle edge/vertex removes tangential displacement and can collapse
            # neighboring cloth faces when multiple particles share a closest edge.
            correction_mm = self.clearance_mm - signed_distance[needs_projection]
            correction = correction_mm[:, None] * outward[needs_projection]
            active_corrected[needs_projection] = active_points[needs_projection] + correction
            active_normals[needs_projection] = outward[needs_projection]
            corrected[active_point_indices] = active_corrected
            contact_normals[active_point_indices] = active_normals

        return corrected, contact_normals


def project_stitched_pairs(
    projector: MeshCollisionProjector,
    positions_mm: npt.ArrayLike,
    contact_normals: npt.ArrayLike,
    stitches: Sequence[tuple[int, int]],
    pinned_indices: Sequence[int] = (),
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Close stitch groups after contact projection, including near-shell residuals.

    The native PBD pass projects stitches before the backend's position-level
    collision response. Independent contact corrections can therefore separate
    two sewn vertices. Reconcile contact-touched groups at a shared point and
    project that point to the exterior clearance shell.

    A residual stitch can also stall when both endpoints sit just outside the
    shell on different sides of a curved body. Probe the midpoint of near-closed
    groups and share it between endpoints: project it to the exterior shell if
    needed, or use it unchanged when the projector reports that it is already
    safe. Groups beyond the capture distance and groups containing fixed
    particles remain unchanged, avoiding early capture of distant stitches.
    """
    corrected = np.asarray(positions_mm, dtype=np.float64).copy()
    normals = np.asarray(contact_normals, dtype=np.float64).copy()
    if corrected.ndim != 2 or corrected.shape[1] != 3:
        raise ValueError("stitched collision positions must have shape (N, 3)")
    if normals.shape != corrected.shape:
        raise ValueError("stitched collision normals must match the position array")
    if not bool(np.isfinite(corrected).all() and np.isfinite(normals).all()):
        raise ValueError("stitched collision positions and normals must be finite")

    particle_count = len(corrected)
    pinned = {int(index) for index in pinned_indices}
    if any(index < 0 or index >= particle_count for index in pinned):
        raise ValueError("pinned index is outside the collision position array")

    parent = list(range(particle_count))
    rank = [0] * particle_count
    touched: set[int] = set()

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return
        if rank[root_left] < rank[root_right]:
            root_left, root_right = root_right, root_left
        parent[root_right] = root_left
        if rank[root_left] == rank[root_right]:
            rank[root_left] += 1

    for raw_left, raw_right in stitches:
        left, right = int(raw_left), int(raw_right)
        if not 0 <= left < particle_count or not 0 <= right < particle_count:
            raise ValueError("stitch pair index is outside the collision position array")
        if left == right:
            continue
        touched.add(left)
        touched.add(right)
        union(left, right)

    groups: dict[int, list[int]] = {}
    for index in sorted(touched):
        groups.setdefault(find(index), []).append(index)

    eligible_groups: list[list[int]] = []
    shared_points: list[npt.NDArray[np.float64]] = []
    near_shell_groups: list[list[int]] = []
    near_shell_midpoints: list[npt.NDArray[np.float64]] = []
    for group in groups.values():
        if len(group) < 2 or pinned.intersection(group):
            continue
        points = corrected[group]
        if float(np.linalg.norm(points - points[0], axis=1).max()) <= 1e-7:
            continue
        if bool(np.any(np.linalg.norm(normals[group], axis=1) > 1e-7)):
            eligible_groups.append(group)
            shared_points.append(points.mean(axis=0))
            continue
        # Prefer target-surface evidence over endpoint distance. A sewn pair may span
        # the body while both endpoints remain outside the collision shell; its shared
        # midpoint is still a valid stitch repair candidate when it lies inside the
        # target. The AABB and signed local-plane checks below reject remote unrelated
        # stitches without discarding those through-surface residuals.
        midpoint = points.mean(axis=0)
        if not bool(
            np.all((midpoint >= projector._bounds_min) & (midpoint <= projector._bounds_max))
        ):
            continue
        centroid_distance, closest_face_id = projector._tree.query(
            midpoint,
            k=1,
            eps=0.0,
            workers=1,
        )
        closest_face = int(closest_face_id)
        closest_plane_distance = float(
            np.dot(
                midpoint - projector._centroids[closest_face],
                projector._normals[closest_face],
            )
        )
        # Mirror the projector's broad phase: a zero normal means "safe" both
        # near the clearance shell and far away. Only reconcile midpoints that
        # are plausible surface candidates; remote stitches remain untouched.
        if float(centroid_distance) > projector._search_radius_mm and closest_plane_distance >= 0.0:
            continue
        near_shell_groups.append(group)
        near_shell_midpoints.append(midpoint)

    # Reconcile close residual stitches at their shared midpoint. If collision
    # correction is needed, the shared point is projected to the exterior shell;
    # if its normal is zero, the midpoint is already safe and can be shared as-is.
    # Pairs beyond capture_distance and groups containing pinned particles remain
    # under the native solver.
    if near_shell_midpoints:
        midpoint_points, midpoint_normals = projector.project(
            np.asarray(near_shell_midpoints, dtype=np.float64)
        )
        for index, group in enumerate(near_shell_groups):
            corrected[group] = midpoint_points[index]
            normals[group] = midpoint_normals[index]

    if shared_points:
        projected_points, projected_normals = projector.project(
            np.asarray(shared_points, dtype=np.float64)
        )
        for index, group in enumerate(eligible_groups):
            corrected[group] = projected_points[index]
            normals[group] = projected_normals[index]

    return corrected, normals
