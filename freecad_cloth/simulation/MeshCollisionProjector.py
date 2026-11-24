# Copyright (C) 2026 FreeCAD Cloth contributors
"""Position-level contact projection for closed rigid collision meshes.

The native PBD binding detects rigid-body contacts, but its rigid-body contacts are
not included in the library's position-constraint projection pass. This helper
keeps cloth particles outside a closed collision mesh after each native substep.
"""

from __future__ import annotations

import os
from time import perf_counter
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from scipy.spatial import KDTree

from freecad_cloth.shared.Collision import CollisionSurface

if TYPE_CHECKING:
    from collections.abc import Sequence


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
            msg = "collision projection clearance must be positive and finite"
            raise ValueError(msg)
        if len(surface.vertices) < 4 or len(surface.triangles) < 4:
            msg = "collision projection requires a closed triangle mesh"
            raise ValueError(msg)
        if candidate_count < 1:
            msg = "collision projection candidate count must be positive"
            raise ValueError(msg)

        self.clearance_mm = float(clearance_mm)
        self._vertices = np.asarray(surface.vertices, dtype=np.float64)
        self._triangles = np.asarray(surface.triangles, dtype=np.int64).reshape((-1, 3))
        self._source_vertices = surface.vertices
        self._source_triangles = surface.triangles
        from freecad_cloth.simulation.DrapeVisualSanity import _ClosedMeshPointClassifier

        self._inside_classifier = _ClosedMeshPointClassifier(
            self._source_vertices,
            self._source_triangles,
        )
        # Points beyond the mesh AABB expanded by clearance cannot be inside or
        # touching its clearance shell, so they need no nearest-triangle query.
        self._mesh_bounds_min = self._vertices.min(axis=0)
        self._mesh_bounds_max = self._vertices.max(axis=0)
        self._bounds_min = self._mesh_bounds_min - self.clearance_mm
        self._bounds_max = self._mesh_bounds_max + self.clearance_mm

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
            msg = "collision projection requires a closed, consistently oriented mesh"
            raise ValueError(msg)

        triangles = self._vertices[self._triangles]
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        raw_normals = np.cross(b - a, c - a)
        lengths = np.linalg.norm(raw_normals, axis=1)
        if bool(np.any(lengths <= 1e-12)):
            msg = "collision projection mesh contains degenerate triangles"
            raise ValueError(msg)

        signed_volume_times_six = float(
            np.einsum("ij,ij->i", a, np.cross(b, c)).sum(dtype=np.float64)
        )
        if abs(signed_volume_times_six) <= 1e-9:
            msg = "collision projection mesh has no reliable enclosed volume"
            raise ValueError(msg)
        orientation = 1.0 if signed_volume_times_six > 0.0 else -1.0
        self._normals = raw_normals * (orientation / lengths[:, None])
        self._triangle_vertices = triangles
        self._centroids = np.mean(triangles, axis=1)
        self._tree = KDTree(self._centroids)
        self._triangle_radii_mm = np.linalg.norm(
            triangles - self._centroids[:, None, :],
            axis=2,
        ).max(axis=1)
        self._maximum_triangle_radius_mm = float(self._triangle_radii_mm.max())
        self._last_nearest_candidate_count = 0
        # Target triangles in the packaged humanoid mesh are locally dense and
        # consistently sized. Fast preview uses two nearby faces to limit per-frame
        # work; production draping uses four and remains subject to exact zero-
        # penetration acceptance. This count controls candidate cost, not clearance.
        self._candidate_count = min(int(candidate_count), len(self._triangles))
        triangle_radius_mm = float(
            np.linalg.norm(triangles - self._centroids[:, None, :], axis=2).max()
        )
        self._search_radius_mm = self.clearance_mm + triangle_radius_mm + 1e-6

    def _clearance_values(
        self,
        clearance_mm: float | npt.ArrayLike | None,
        point_count: int,
    ) -> npt.NDArray[np.float64]:
        """Normalize a scalar or per-particle positive body clearance.

        Args:
            clearance_mm: One clearance shared by all points, one clearance per point,
                or None to use this projector's configured default.
            point_count: Number of particle positions receiving projection.

        Returns:
            A finite positive clearance value for each particle.

        Raises:
            ValueError: If the clearance is non-positive, non-finite, or has the wrong shape.
        """
        if clearance_mm is None:
            return np.full(point_count, self.clearance_mm, dtype=np.float64)
        requested = np.asarray(clearance_mm, dtype=np.float64)
        if requested.ndim == 0:
            values = np.full(point_count, float(requested), dtype=np.float64)
        elif requested.shape == (point_count,):
            values = requested.copy()
        else:
            msg = "collision projection clearance must be scalar or have shape (N,)"
            raise ValueError(msg)
        if not bool(np.isfinite(values).all()) or bool(np.any(values <= 0.0)):
            msg = "collision projection clearances must be positive and finite"
            raise ValueError(msg)
        return values

    def _closest_points_on_triangles(
        self,
        point: npt.NDArray[np.float64],
        triangle_indices: npt.NDArray[np.int64],
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Compute exact closest points from one query to a selected triangle set.

        Args:
            point: One finite query position in world millimetres.
            triangle_indices: Global target-triangle indices to evaluate.

        Returns:
            Per-triangle closest points and squared distances to the query.
        """
        triangles = self._triangle_vertices[triangle_indices]
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        ab, ac = b - a, c - a
        ap = point[None, :] - a
        d00 = np.einsum("ij,ij->i", ab, ab)
        d01 = np.einsum("ij,ij->i", ab, ac)
        d11 = np.einsum("ij,ij->i", ac, ac)
        d20 = np.einsum("ij,ij->i", ap, ab)
        d21 = np.einsum("ij,ij->i", ap, ac)
        denominator = d00 * d11 - d01 * d01
        safe_denominator = np.where(np.abs(denominator) > 1e-18, denominator, 1.0)
        v = (d11 * d20 - d01 * d21) / safe_denominator
        w = (d00 * d21 - d01 * d20) / safe_denominator
        u = 1.0 - v - w
        projected_plane = a + v[:, None] * ab + w[:, None] * ac
        barycentric_inside = (u >= -1e-10) & (v >= -1e-10) & (w >= -1e-10) & (denominator > 1e-18)

        def closest_on_edge(
            start: npt.NDArray[np.float64],
            edge: npt.NDArray[np.float64],
        ) -> npt.NDArray[np.float64]:
            start_to_point = point[None, :] - start
            edge_length_squared = np.einsum("ij,ij->i", edge, edge)
            parameter = np.divide(
                np.einsum("ij,ij->i", start_to_point, edge),
                edge_length_squared,
                out=np.zeros_like(edge_length_squared),
                where=edge_length_squared > 1e-18,
            )
            return start + np.clip(parameter, 0.0, 1.0)[:, None] * edge

        edge_points = np.stack(
            (
                closest_on_edge(a, ab),
                closest_on_edge(b, c - b),
                closest_on_edge(c, a - c),
            ),
            axis=1,
        )
        edge_delta = point[None, None, :] - edge_points
        edge_distances = np.einsum("ned,ned->ne", edge_delta, edge_delta)
        edge_indices = np.argmin(edge_distances, axis=1)
        rows = np.arange(len(triangles))
        closest_edge = edge_points[rows, edge_indices]
        closest = np.where(barycentric_inside[:, None], projected_plane, closest_edge)
        delta = point[None, :] - closest
        distance_squared = np.einsum("ij,ij->i", delta, delta)
        return closest, distance_squared

    def _nearest_surface_point(
        self,
        point: npt.NDArray[np.float64],
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Return the exact nearest point using a conservative centroid-tree query.

        The closest-centroid triangle supplies an upper bound on the true surface
        distance. Any triangle that could be closer has its centroid within that
        upper bound plus the maximum triangle-centroid radius, so the ball query
        cannot exclude the globally nearest face.

        Args:
            point: One query position in world millimetres.

        Returns:
            Exact nearest point on the mesh and its consistently outward face normal.
        """
        _centroid_distance, seed_face = self._tree.query(
            point,
            k=1,
            eps=0.0,
            workers=1,
        )
        seed_indices = np.asarray((int(seed_face),), dtype=np.int64)
        _seed_points, seed_distances = self._closest_points_on_triangles(point, seed_indices)
        upper_bound_mm = float(np.sqrt(seed_distances[0]))
        candidate_radius_mm = upper_bound_mm + self._maximum_triangle_radius_mm + 1e-9
        candidate_indices = np.asarray(
            self._tree.query_ball_point(
                point,
                candidate_radius_mm,
                eps=0.0,
                workers=1,
                return_sorted=True,
            ),
            dtype=np.int64,
        )
        if candidate_indices.size == 0:
            candidate_indices = seed_indices
        elif not bool(np.any(candidate_indices == seed_indices[0])):
            candidate_indices = np.append(candidate_indices, seed_indices)
            candidate_indices.sort()

        closest_points, distances_squared = self._closest_points_on_triangles(
            point,
            candidate_indices,
        )
        nearest_index = int(np.argmin(distances_squared))
        nearest_face = int(candidate_indices[nearest_index])
        self._last_nearest_candidate_count = int(candidate_indices.size)
        return closest_points[nearest_index].copy(), self._normals[nearest_face].copy()

    def _inside_mask(
        self,
        points: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.bool_]:
        """Classify candidate positions against the cached closed collision mesh.

        Args:
            points: Candidate positions in world millimetres.

        Returns:
            Boolean interior classifications in candidate order.
        """
        if len(points) == 0:
            return np.zeros(0, dtype=bool)

        # The collision mesh is immutable; validate and precompute it once in __init__.
        # Query arrays arrive from project(), which has already checked shape and finiteness.
        started = perf_counter()
        inside = self._inside_classifier.contains_array(points, chunk_size=32)
        if os.environ.get("CLOTH_INTER_CLOTH_DIAGNOSTICS") == "1":
            from freecad_cloth.common.Diagnostics import emit_diagnostic

            emit_diagnostic(
                "body-projection-inside-classification "
                f"points={len(points)} inside={int(np.count_nonzero(inside))} "
                f"method=cached-numpy-ray-parity elapsed_s={perf_counter() - started:.3f}"
            )
        return inside

    def _project_inside_points(
        self,
        points: npt.NDArray[np.float64],
        clearance_mm: npt.ArrayLike | None = None,
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Correct only particles confirmed inside the closed collision surface.

        Args:
            points: Candidate particle positions in world millimetres.

        Returns:
            Corrected positions and outward correction directions. Exterior points
            are returned unchanged with zero directions.
        """
        corrected = points.copy()
        directions = np.zeros_like(points)
        clearances = self._clearance_values(clearance_mm, len(points))
        inside = self._inside_mask(points)
        nearest_candidate_total = 0
        nearest_started = perf_counter()
        for index in np.flatnonzero(inside):
            nearest_point, face_normal = self._nearest_surface_point(points[index])
            nearest_candidate_total += self._last_nearest_candidate_count
            direction = nearest_point - points[index]
            direction_length = float(np.linalg.norm(direction))
            if direction_length <= 1e-10:
                # At a face/edge coincidence use its consistently oriented outward
                # normal; otherwise the nearest-point vector is the shortest exit
                # direction and remains reliable at a concave corner.
                direction = face_normal
            else:
                direction /= direction_length
            corrected[index] = nearest_point + clearances[index] * direction
            directions[index] = direction
        if os.environ.get("CLOTH_INTER_CLOTH_DIAGNOSTICS") == "1" and bool(np.any(inside)):
            from freecad_cloth.common.Diagnostics import emit_diagnostic

            emit_diagnostic(
                "body-projection-exact-nearest "
                f"inside={int(np.count_nonzero(inside))} "
                f"candidate_triangles={nearest_candidate_total} "
                f"target_triangles={len(self._triangles)} "
                f"elapsed_s={perf_counter() - nearest_started:.3f}"
            )
        return corrected, directions

    def project(
        self,
        points_mm: npt.ArrayLike,
        clearance_mm: float | npt.ArrayLike | None = None,
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Return corrected world-mm positions and outward normals for moved points.

        Zero rows in the returned normal array mark positions that did not require a
        correction. Closest-triangle calculations are vectorized across cloth points
        and a local set of target faces, avoiding point-by-all-triangles matrices.

        Args:
            points_mm: Finite N-by-3 cloth particle positions in world millimetres.

        Returns:
            Corrected N-by-3 positions and N-by-3 outward contact normals.

        Raises:
            ValueError: If the input is not a finite array with shape (N, 3)."""
        points = np.asarray(points_mm, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            msg = "collision projection points must have shape (N, 3)"
            raise ValueError(msg)
        if not bool(np.isfinite(points).all()):
            msg = "collision projection points must be finite"
            raise ValueError(msg)
        corrected = points.copy()
        contact_normals = np.zeros_like(points)
        if points.shape[0] == 0:
            return corrected, contact_normals
        clearances = self._clearance_values(clearance_mm, len(points))
        maximum_clearance = float(np.max(clearances))
        bounds_min = self._mesh_bounds_min - maximum_clearance
        bounds_max = self._mesh_bounds_max + maximum_clearance

        within_bounds = np.all(
            (points >= bounds_min) & (points <= bounds_max),
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
        active = (
            centroid_distances[:, 0]
            <= clearances[candidate_point_indices] + self._maximum_triangle_radius_mm + 1e-6
        ) | (closest_plane_signed_distance < 0.0)
        active_clearances = clearances[candidate_point_indices[active]]
        unresolved_point_indices = candidate_point_indices[~active]
        if bool(np.any(active)):
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
            barycentric_inside = (
                (u >= -1e-10) & (v >= -1e-10) & (w >= -1e-10) & (denominator > 1e-18)
            )

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
                "nked,nked->nke",
                p[:, :, None, :] - edge_points,
                p[:, :, None, :] - edge_points,
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
            active_corrected = active_points.copy()
            active_normals = np.zeros_like(active_points)
            if bool(np.any(needs_projection)):
                # Preserve tangential offsets for ordinary exterior shell contacts.
                correction_mm = (
                    active_clearances[needs_projection] - signed_distance[needs_projection]
                )
                correction = correction_mm[:, None] * outward[needs_projection]
                active_corrected[needs_projection] = active_points[needs_projection] + correction
                active_normals[needs_projection] = outward[needs_projection]

            # A nearest-centroid candidate can land on a triangle edge at a concavity.
            # Its face normal may point into another part of the solid, so normal-only
            # projection can leave an interior particle embedded. Inspect ambiguous
            # edge/positive-side candidates against the exact closed surface.
            ambiguous = (~barycentric_inside[row_indices, nearest_candidate]) | (
                signed_distance >= 0.0
            )
            ambiguous_indices = np.flatnonzero(ambiguous)
            if ambiguous_indices.size:
                inside_corrected, inside_normals = self._project_inside_points(
                    active_points[ambiguous_indices],
                    active_clearances[ambiguous_indices],
                )
                confirmed_inside = np.linalg.norm(inside_normals, axis=1) > 1e-10
                if bool(np.any(confirmed_inside)):
                    inside_indices = ambiguous_indices[confirmed_inside]
                    active_corrected[inside_indices] = inside_corrected[confirmed_inside]
                    active_normals[inside_indices] = inside_normals[confirmed_inside]

            corrected[active_point_indices] = active_corrected
            contact_normals[active_point_indices] = active_normals

        if unresolved_point_indices.size:
            unresolved_corrected, unresolved_normals = self._project_inside_points(
                points[unresolved_point_indices],
                clearances[unresolved_point_indices],
            )
            corrected[unresolved_point_indices] = unresolved_corrected
            contact_normals[unresolved_point_indices] = unresolved_normals
        return corrected, contact_normals


def project_stitched_pairs(
    projector: MeshCollisionProjector,
    positions_mm: npt.ArrayLike,
    contact_normals: npt.ArrayLike,
    stitches: Sequence[tuple[int, int]],
    pinned_indices: Sequence[int] = (),
    *,
    clearance_mm: float | npt.ArrayLike | None = None,
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

    Args:
        projector: Target-surface projector used for residual contact correction.
        positions_mm: Current finite cloth particle positions in world millimetres.
        contact_normals: Per-particle contact normals from the preceding projection.
        stitches: Particle-index pairs that must remain coincident after contact response.
        pinned_indices: Particle indices whose positions must not be reconciled.

    Returns:
        Corrected positions and contact normals with eligible stitch groups reconciled.

    Raises:
        ValueError: If arrays have incompatible shapes, non-finite values, or invalid pinned indices."""
    corrected = np.asarray(positions_mm, dtype=np.float64).copy()
    normals = np.asarray(contact_normals, dtype=np.float64).copy()
    if corrected.ndim != 2 or corrected.shape[1] != 3:
        msg = "stitched collision positions must have shape (N, 3)"
        raise ValueError(msg)
    if normals.shape != corrected.shape:
        msg = "stitched collision normals must match the position array"
        raise ValueError(msg)
    if not bool(np.isfinite(corrected).all() and np.isfinite(normals).all()):
        msg = "stitched collision positions and normals must be finite"
        raise ValueError(msg)

    particle_count = len(corrected)
    clearances = projector._clearance_values(clearance_mm, particle_count)
    pinned = {int(index) for index in pinned_indices}
    if any(index < 0 or index >= particle_count for index in pinned):
        msg = "pinned index is outside the collision position array"
        raise ValueError(msg)

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
            msg = "stitch pair index is outside the collision position array"
            raise ValueError(msg)
        if left == right:
            continue
        touched.add(left)
        touched.add(right)
        union(left, right)

    groups: dict[int, list[int]] = {}
    for index in sorted(touched):
        groups.setdefault(find(index), []).append(index)

    eligible_groups: list[list[int]] = []
    eligible_clearances: list[float] = []
    shared_points: list[npt.NDArray[np.float64]] = []
    near_shell_groups: list[list[int]] = []
    near_shell_midpoints: list[npt.NDArray[np.float64]] = []
    near_shell_clearances: list[float] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        group_clearances = clearances[group]
        if float(np.ptp(group_clearances)) > 1e-8:
            msg = "stitched particles must share one mannequin body clearance"
            raise ValueError(msg)
        group_clearance = float(group_clearances[0])
        if pinned.intersection(group):
            continue
        points = corrected[group]
        if float(np.linalg.norm(points - points[0], axis=1).max()) <= 1e-7:
            continue
        if bool(np.any(np.linalg.norm(normals[group], axis=1) > 1e-7)):
            eligible_groups.append(group)
            eligible_clearances.append(group_clearance)
            shared_points.append(points.mean(axis=0))
            continue
        # Prefer target-surface evidence over endpoint distance. A sewn pair may span
        # the body while both endpoints remain outside the collision shell; its shared
        # midpoint is still a valid stitch repair candidate when it lies inside the
        # target. The AABB and signed local-plane checks below reject remote unrelated
        # stitches without discarding those through-surface residuals.
        midpoint = points.mean(axis=0)
        bounds_min = projector._mesh_bounds_min - group_clearance
        bounds_max = projector._mesh_bounds_max + group_clearance
        if not bool(np.all((midpoint >= bounds_min) & (midpoint <= bounds_max))):
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
        search_radius = group_clearance + projector._maximum_triangle_radius_mm + 1e-6
        if float(centroid_distance) > search_radius and closest_plane_distance >= 0.0:
            continue
        near_shell_groups.append(group)
        near_shell_midpoints.append(midpoint)
        near_shell_clearances.append(group_clearance)

    # Reconcile close residual stitches at their shared midpoint. If collision
    # correction is needed, the shared point is projected to the exterior shell;
    # if its normal is zero, the midpoint is already safe and can be shared as-is.
    # Pairs beyond capture_distance and groups containing pinned particles remain
    # under the native solver.
    if near_shell_midpoints:
        midpoint_points, midpoint_normals = projector.project(
            np.asarray(near_shell_midpoints, dtype=np.float64),
            clearance_mm=np.asarray(near_shell_clearances, dtype=np.float64),
        )
        for index, group in enumerate(near_shell_groups):
            corrected[group] = midpoint_points[index]
            normals[group] = midpoint_normals[index]

    if shared_points:
        projected_points, projected_normals = projector.project(
            np.asarray(shared_points, dtype=np.float64),
            clearance_mm=np.asarray(eligible_clearances, dtype=np.float64),
        )
        for index, group in enumerate(eligible_groups):
            corrected[group] = projected_points[index]
            normals[group] = projected_normals[index]

    return corrected, normals
