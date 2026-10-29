# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for drape mesh geometry and evidence classification."""

import unittest
from typing import NoReturn

from freecad_cloth.common.MeshValidation import validate_mesh
from freecad_cloth.simulation.DrapeVisualSanity import (
    inspect_drape,
    mesh_shape_sanity,
    minimum_vertex_distance,
    point_inside_closed_mesh,
    points_inside_closed_mesh,
    seam_correspondence_gap,
    summarize,
)

TETRAHEDRON_VERTICES = (
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)
TETRAHEDRON_TRIANGLES = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))


class _DrapeTargetFixture(unittest.TestCase):
    """Supply canonical target geometry for drape regression tests."""

    def setUp(self) -> None:
        """Prepare canonical target geometry used by the drape checks."""
        self.target = (
            (-100.0, -50.0, 0.0),
            (100.0, -50.0, 0.0),
            (-100.0, 50.0, 1750.0),
            (100.0, 50.0, 1750.0),
        )


class DrapeVisualSanityTests(_DrapeTargetFixture):
    """Verify point-containment and basic drape-metric behavior."""

    def test_point_inside_closed_mesh_classifies_inside_and_outside(self) -> None:
        """Distinguish points inside a closed tetrahedron from exterior points."""
        vertices = TETRAHEDRON_VERTICES
        triangles = TETRAHEDRON_TRIANGLES
        self.assertTrue(point_inside_closed_mesh((0.1, 0.1, 0.1), vertices, triangles))
        self.assertFalse(point_inside_closed_mesh((1.1, 0.1, 0.1), vertices, triangles))

    def test_bulk_point_containment_matches_single_point_api(self) -> None:
        """Require bulk point containment to match individual point queries."""
        vertices = TETRAHEDRON_VERTICES
        triangles = TETRAHEDRON_TRIANGLES
        # The second point is inside the mesh AABB but outside the tetrahedron.
        # The third is outside the AABB entirely.
        points = ((0.1, 0.1, 0.1), (0.8, 0.8, 0.1), (1.1, 0.1, 0.1))
        self.assertEqual(
            points_inside_closed_mesh(points, vertices, triangles), (True, False, False)
        )

    def test_bulk_containment_can_bypass_trimesh_acceleration(self) -> None:
        """Allow point containment to use the pure geometry path without trimesh."""
        vertices = TETRAHEDRON_VERTICES
        triangles = TETRAHEDRON_TRIANGLES
        points = ((0.1, 0.1, 0.1), (1.1, 0.1, 0.1))

        def forbidden_contains(_mesh: object, _points: object) -> NoReturn:
            """Fail if the test unexpectedly calls the optional acceleration callback.

            Args:
                _mesh: Acceleration mesh the callback would otherwise inspect.
                _points: Query points that must be handled by the pure geometry path.

            Raises:
                AssertionError: If the trimesh acceleration callback is invoked.
            """
            msg = "Trimesh acceleration should be bypassed"
            raise AssertionError(msg)

        self.assertEqual(
            points_inside_closed_mesh(
                points,
                vertices,
                triangles,
                prefer_trimesh=False,
                contains_fn=forbidden_contains,
            ),
            (True, False),
        )

    def test_point_containment_rejects_invalid_indices_and_nonfinite_coordinates(self) -> None:
        """Reject invalid triangle indices and non-finite point coordinates."""
        vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        with self.assertRaises(ValueError):
            point_inside_closed_mesh((0.1, 0.1, 0.0), vertices, ((0, 1, 3),))
        with self.assertRaises(ValueError):
            point_inside_closed_mesh((float("nan"), 0.1, 0.1), vertices, ((0, 1, 2),))

    def test_minimum_vertex_distance_uses_exact_nearest_query(self) -> None:
        """Return the exact nearest-vertex distance or no distance for empty input."""
        source = ((0.0, 0.0, 0.0), (1000.0, 0.0, 0.0))
        target = ((5.0, 0.0, 0.0), (1005.0, 0.0, 0.0))
        self.assertEqual(minimum_vertex_distance(source, target), 5.0)
        self.assertIsNone(minimum_vertex_distance((), target))

    def test_reports_structurally_plausible_drape(self) -> None:
        """Recognize canonical-style garment geometry as structurally plausible."""
        garment = (
            (-140.0, -90.0, 250.0),
            (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0),
            (140.0, 90.0, 1500.0),
        )
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        self.assertTrue(result.finite)
        self.assertEqual(result.state, "structurally-plausible")
        self.assertGreater(result.vertical_span_ratio, 0.6)
        self.assertEqual(result.vertices, 4)


class DrapeShapeSanityTests(_DrapeTargetFixture):
    """Verify shape plausibility, seam correspondence, and failure summaries."""

    def test_vertical_ratio_uses_z_not_largest_footprint_axis(self) -> None:
        """Measure the vertical span against target height, not footprint width."""
        garment = (
            (-1500.0, -40.0, 100.0),
            (1500.0, -40.0, 100.0),
            (-1500.0, 40.0, 200.0),
            (1500.0, 40.0, 200.0),
        )
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=3000.0)
        self.assertAlmostEqual(result.vertical_span_ratio, 100.0 / 1750.0)
        self.assertAlmostEqual(result.lateral_span_ratio, 3000.0 / 3000.0)
        self.assertEqual(result.state, "short-drape-candidate")

    def test_lateral_ratio_uses_larger_footprint_axis(self) -> None:
        """Measure lateral span along the wider footprint axis."""
        garment = (
            (-20.0, -900.0, 300.0),
            (20.0, -900.0, 300.0),
            (-20.0, 900.0, 1500.0),
            (20.0, 900.0, 1500.0),
        )
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=2000.0)
        self.assertAlmostEqual(result.vertical_span_ratio, 1200.0 / 1750.0)
        self.assertAlmostEqual(result.lateral_span_ratio, 1800.0 / 2000.0)

    def test_empty_mesh_is_classified(self) -> None:
        """Classify an empty garment mesh and mark its metrics as non-finite."""
        result = inspect_drape((), self.target, target_height=1750.0, target_width=200.0)
        self.assertEqual(result.state, "empty")
        self.assertFalse(result.finite)

    def test_nonfinite_mesh_is_classified(self) -> None:
        """Classify a garment mesh containing non-finite coordinates."""
        result = inspect_drape(((0.0, 0.0, float("nan")),), self.target)
        self.assertEqual(result.state, "nonfinite")
        self.assertFalse(result.finite)

    def test_missing_target_is_classified_before_geometry_quality(self) -> None:
        """Report a missing target before evaluating garment geometry quality."""
        garment = ((-100.0, 0.0, 100.0), (100.0, 0.0, 1500.0))
        result = inspect_drape(garment, (), target_height=1750.0, target_width=1000.0)
        self.assertEqual(result.state, "missing-target")
        self.assertIsNone(result.target_vertex_clearance)

    def test_detached_candidate_is_reported(self) -> None:
        """Classify garment vertices that are detached from the target surface."""
        garment = ((1000.0, 1000.0, 300.0), (1100.0, 1000.0, 300.0), (1000.0, 1000.0, 1500.0))
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=200.0)
        self.assertEqual(result.state, "detached-candidate")
        self.assertGreater(result.target_vertex_clearance, 100.0)

    def test_mesh_shape_sanity_rejects_long_edge_spike(self) -> None:
        """Reject a mesh containing a disproportionately long triangle edge."""
        vertices = (
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (10.0, 10.0, 0.0),
            (0.0, 10.0, 0.0),
            (80.0, 80.0, 0.0),
        )
        triangles = ((0, 1, 2), (0, 2, 3), (2, 4, 3))
        result = mesh_shape_sanity(vertices, triangles)
        self.assertTrue(result["finite"])
        self.assertGreater(result["edge_spike_ratio"], 4.0)
        self.assertGreater(result["spike_edge_fraction"], 0.0)

    def test_mesh_shape_sanity_accepts_regular_grid(self) -> None:
        """Accept regular grid geometry without spurious edge-spike warnings."""
        vertices = (
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (0.0, 10.0, 0.0),
            (10.0, 10.0, 0.0),
            (20.0, 10.0, 0.0),
        )
        triangles = ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4))
        result = mesh_shape_sanity(vertices, triangles)
        self.assertTrue(result["finite"])
        self.assertLess(result["edge_spike_ratio"], 2.0)
        self.assertAlmostEqual(result["footprint_aspect_ratio"], 2.0)

    def test_clean_canonical_style_mesh_has_one_component(self) -> None:
        """Confirm that a connected canonical-style mesh has one component."""
        vertices = (
            (-140.0, -90.0, 250.0),
            (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0),
            (140.0, 90.0, 1500.0),
        )
        triangles = ((0, 1, 2), (1, 3, 2))
        result = validate_mesh(vertices, triangles, prefer_trimesh=False)
        self.assertEqual(result.components, 1)
        self.assertTrue(result.finite)

    def test_seam_correspondence_is_clean_for_matching_canonical_edges(self) -> None:
        """Return zero correspondence gap for matching seam boundary edges."""
        boundary = (
            (0.0, 0.0, 0.0),
            (100.0, 0.0, 0.0),
            (100.0, 100.0, 0.0),
            (0.0, 100.0, 0.0),
        )
        self.assertEqual(seam_correspondence_gap(boundary, boundary, 0, 0), 0.0)

    def test_seam_correspondence_detects_obvious_detachment(self) -> None:
        """Measure the gap between visibly detached seam boundary edges."""
        left = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
        right = ((250.0, 0.0, 0.0), (350.0, 0.0, 0.0))
        self.assertEqual(seam_correspondence_gap(left, right, 0, 0), 250.0)

    def test_summary_is_stable(self) -> None:
        """Keep the compact drape summary stable and expose finite-state evidence."""
        result = inspect_drape(((0.0, 0.0, 0.0), (10.0, 0.0, 10.0)), self.target)
        data = summarize(result)
        self.assertIn("state", data)
        self.assertIn("bounds", data)
        self.assertTrue(data["finite"])

    def test_mesh_shape_sanity_treats_zero_width_footprint_as_degenerate(self) -> None:
        """Treat a zero-width footprint as degenerate geometry."""
        vertices = (
            (0.0, 0.0, 0.0),
            (0.0, 10.0, 0.0),
            (0.0, 20.0, 0.0),
        )
        result = mesh_shape_sanity(vertices, ((0, 1, 2),))
        self.assertTrue(result["finite"])
        self.assertEqual(result["footprint_aspect_ratio"], float("inf"))


if __name__ == "__main__":
    unittest.main()
