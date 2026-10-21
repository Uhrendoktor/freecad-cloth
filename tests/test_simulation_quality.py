# Copyright (C) 2026 FreeCAD Cloth contributors
import sys
import unittest
from math import dist
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
from freecad_cloth.simulation.SimulationQuality import (
    QUALITY_PRESETS,
    FabricMaterial,
    preset,
    solver_parameters,
)
from freecad_cloth.simulation.SimulationQualityRuntime import (
    _RUNTIME_BASES,
    QualitySimulationProxy,
    quality_discretization,
)
from freecad_cloth.simulation.WorkflowReadinessGui import (
    WorkflowStep,
    build_workflow_checklist,
)


class SimulationQualityTests(unittest.TestCase):
    def test_quality_presets_are_monotonic_and_distinct(self):
        self.assertEqual(set(QUALITY_PRESETS), {"Fast", "Balanced", "Final"})
        self.assertGreater(preset("Fast").particle_distance, preset("Balanced").particle_distance)
        self.assertGreater(preset("Balanced").particle_distance, preset("Final").particle_distance)
        self.assertLess(preset("Fast").solver_iterations, preset("Final").solver_iterations)

    def test_material_defaults_and_solver_parameters(self):
        material = FabricMaterial()
        params = solver_parameters(preset("Final"), material)
        self.assertEqual(params["particle_distance"], 2.0)
        self.assertEqual(params["iterations"], 16)
        self.assertEqual(params["substeps"], 2)
        self.assertEqual(params["density_g_m2"], 150.0)
        self.assertEqual(params["thickness_mm"], 0.5)

    def test_material_validation_rejects_invalid_values(self):
        invalid = [
            ("density_g_m2", 0),
            ("thickness_mm", 0),
            ("stretch", 1.1),
            ("shear", -0.1),
            ("bend", 2),
            ("friction", -1),
        ]
        for field, value in invalid:
            with self.subTest(field=field), self.assertRaises(ValueError):
                FabricMaterial(**{field: value}).validate()

    def test_material_validation_rejects_nonfinite_density_and_thickness(self):
        for field in ("density_g_m2", "thickness_mm"):
            for value in (float("nan"), float("inf"), float("-inf")):
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaisesRegex(ValueError, "positive and finite"),
                ):
                    FabricMaterial(**{field: value}).validate()

    def test_material_presentation_defaults_and_validation(self):
        material = FabricMaterial()
        self.assertEqual(material.color_rgb, (0.72, 0.34, 0.46))
        self.assertEqual(material.specular, 0.25)
        self.assertEqual(material.roughness, 0.65)
        self.assertEqual(material.transparency, 0.0)
        self.assertIs(material.validate(), material)
        with self.assertRaises(ValueError):
            FabricMaterial(color_rgb=(1.0, 0.0)).validate()
        with self.assertRaises(ValueError):
            FabricMaterial(roughness=1.1).validate()
        with self.assertRaises(ValueError):
            FabricMaterial(transparency=101).validate()

    def test_material_color_normalizes_freecad_property_color_shapes(self):
        from freecad_cloth.simulation.SimulationQuality import normalize_color_rgb

        self.assertEqual(normalize_color_rgb((0.72, 0.34, 0.46, 0.0)), (0.72, 0.34, 0.46))
        self.assertEqual(
            normalize_color_rgb((184, 87, 117, 255)), (184 / 255.0, 87 / 255.0, 117 / 255.0)
        )
        with self.assertRaises(ValueError):
            normalize_color_rgb((300, 0, 0))

    def test_unknown_quality_rejected(self):
        with self.assertRaises(ValueError):
            preset("Ultra")

    def test_quality_discretization_increases_with_smaller_particle_distance(self):
        coarse = quality_discretization(4, 320.0, preset("Fast").particle_distance)
        fine = quality_discretization(4, 320.0, preset("Final").particle_distance)
        self.assertGreater(fine, coarse)

    def test_pattern_mesh_density_changes_with_particle_distance(self):
        piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
        piece_obj = type(
            "Piece",
            (),
            {
                "SewingOutline": repr(piece.outline),
                "DraftingBoundary": repr(piece.outline),
                "PieceId": piece.id,
                "Placement": None,
            },
        )()
        coarse = quality_piece_mesh(piece_obj, 100.0, 20.0)
        fine = quality_piece_mesh(piece_obj, 100.0, 5.0)
        self.assertGreater(len(fine[0]), len(coarse[0]))

    def test_quality_seam_edges_have_interior_particles(self):
        piece = PatternPiece("Test", [(0, 0), (120, 0), (120, 60), (0, 60)], id="test")
        piece_obj = type(
            "Piece",
            (),
            {
                "SewingOutline": repr(piece.outline),
                "DraftingBoundary": repr(piece.outline),
                "PieceId": piece.id,
                "Placement": None,
            },
        )()
        positions, _triangles, boundary = quality_piece_mesh(piece_obj, 100.0, 20.0)
        self.assertEqual(len(boundary), 4)
        self.assertTrue(all(len(edge) >= 3 for edge in boundary))
        for edge in boundary:
            self.assertLessEqual(
                max(dist(positions[a], positions[b]) for a, b in zip(edge, edge[1:], strict=False)),
                20.000001,
            )

    def test_refinement_preserves_authored_boundary_and_materially_tessellates(self):
        piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
        piece_obj = type(
            "Piece",
            (),
            {
                "SewingOutline": repr(piece.outline),
                "DraftingBoundary": repr(piece.outline),
                "PieceId": piece.id,
                "Placement": None,
            },
        )()
        positions, triangles, boundary = quality_piece_mesh(piece_obj, 100.0, 2.0)
        # Constrained Delaunay preserves the authored outline as semantic
        # boundary chains; refinement adds interior vertices and triangles.
        self.assertEqual(len(boundary), len(piece.outline))
        self.assertGreater(len(triangles), 100)
        self.assertGreater(sum(len(chain) for chain in boundary), len(piece.outline))
        self.assertGreater(len(positions), len(piece.outline))
        for edge_index, chain in enumerate(boundary):
            self.assertGreaterEqual(len(chain), 2)
            self.assertEqual(positions[chain[0]][:2], piece.outline[edge_index])
            self.assertEqual(
                positions[chain[-1]][:2],
                piece.outline[(edge_index + 1) % len(piece.outline)],
            )

    def test_quality_proxy_keeps_solver_state_outside_serialized_object_dict(self):
        """Guard the reload path without placing the non-serializable solver in __dict__."""
        proxy = QualitySimulationProxy()
        original = _RUNTIME_BASES[proxy]
        self.assertNotIn("_base", proxy.__dict__)
        self.assertEqual(proxy.last_steps, 0)
        restored = proxy._base_or_restore()
        self.assertIs(restored, original)
        proxy.onDocumentRestored(None)
        self.assertIsNot(_RUNTIME_BASES[proxy], restored)
        self.assertEqual(proxy.last_steps, 0)

    def test_pinned_pinned_stitch_rejects_nonzero_initial_separation(self):
        from freecad_cloth.simulation.ClothBackend import validate_pinned_stitch_pairs

        positions = ((0.0, 0.0, 0.0), (327.943695, 0.0, 0.0))
        records = (("TunicRightShoulder", "Front", "Back", ((0, 1),)),)
        with self.assertRaisesRegex(
            ValueError,
            r"impossible pinned-pinned sewing constraint: seam=TunicRightShoulder "
            r"particle_a=0 particle_b=1 initial_separation=327\.943695000 mm",
        ):
            validate_pinned_stitch_pairs(positions, (0, 1), records)

    def test_pinned_pinned_stitch_allows_numerical_zero(self):
        from freecad_cloth.simulation.ClothBackend import validate_pinned_stitch_pairs

        positions = ((0.0, 0.0, 0.0), (1.0e-12, 0.0, 0.0))
        records = (("test-seam", "A", "B", ((0, 1),)),)
        validate_pinned_stitch_pairs(positions, (0, 1), records)


def _readiness_piece(name: str) -> SimpleNamespace:
    """Create a minimal PatternPiece-like object for readiness tests.

    Args:
        name: Stable fake document-object name.

    Returns:
        A namespace exposing the PatternPiece discriminator and name.
    """
    return SimpleNamespace(Name=name, PatternType="PatternPiece")


def _readiness_scene(
    pieces: tuple[object, ...] = (),
    extra_objects: tuple[object, ...] = (),
    *,
    fitting: object | None = None,
) -> SimpleNamespace:
    """Create a minimal simulation/document pair for readiness tests.

    Args:
        pieces: Pattern pieces assigned to the fake simulation.
        extra_objects: Other document objects, such as semantic seams.
        fitting: Optional persistent fitting-scene stand-in.

    Returns:
        A namespace exposing a simulation, its target and its document.
    """
    objects = (*pieces, *extra_objects)
    if fitting is not None:
        objects = (*objects, fitting)
    document = SimpleNamespace(Objects=objects)
    return SimpleNamespace(
        Document=document,
        ClothPieces=pieces,
        DrapeTarget=object(),
    )


def _readiness_target_status(
    _target: object | None,
    state: str = "ready",
) -> dict[str, object]:
    """Return a deterministic fake target status.

    Args:
        _target: Target reference, unused by this deterministic fixture.
        state: Status string to return.

    Returns:
        The target state and its user-facing message.
    """
    return {
        "state": state,
        "message": (
            "Drape target is current" if state == "ready" else "Drape target needs refresh"
        ),
    }


def _readiness_rows(
    scene: object | None,
    state: str = "ready",
) -> dict[str, WorkflowStep]:
    """Index checklist rows by their stable key.

    Args:
        scene: Simulation scene being checked, or None.
        state: Target state returned by the fake status provider.

    Returns:
        Checklist steps indexed by their stable key.
    """
    return {
        step.key: step
        for step in build_workflow_checklist(
            scene,
            target_status_fn=lambda target: _readiness_target_status(target, state),
        )
    }


def test_readiness_missing_scene_explains_first_steps_and_blocks_simulation() -> None:
    """A missing scene produces setup guidance and blocks simulation."""
    rows = {step.key: step for step in build_workflow_checklist(None)}
    assert rows["patterns"].state == "next"
    assert rows["target"].state == "blocked"
    assert rows["simulation"].state == "blocked"
    assert "Cloth Pattern" in rows["patterns"].message


def test_readiness_distinguishes_unassigned_document_pieces() -> None:
    """Existing but unassigned pieces receive a specific actionable message."""
    piece = _readiness_piece("Front")
    scene = _readiness_scene((), (piece,))
    rows = _readiness_rows(scene, "stale")
    assert rows["patterns"].state == "next"
    assert "exist in the document" in rows["patterns"].message
    assert rows["target"].state == "blocked"
    assert rows["simulation"].state == "blocked"


def test_readiness_unsewn_multi_piece_setup_is_reviewable() -> None:
    """Missing sewing prompts a review without hard-blocking diagnostic cases."""
    scene = _readiness_scene((_readiness_piece("Front"), _readiness_piece("Back")))
    rows = _readiness_rows(scene)
    assert rows["patterns"].state == "ready"
    assert rows["sewing"].state == "review"
    assert rows["target"].state == "ready"
    assert rows["simulation"].state == "ready"
    assert "unsewn tests remain valid" in rows["sewing"].message


def test_readiness_reports_fully_placed_sewn_garment() -> None:
    """Sewing relationships and saved placements report a ready arrangement."""
    front = _readiness_piece("Front")
    back = _readiness_piece("Back")
    seam = SimpleNamespace(
        SewingType="Seam",
        SeamId="seam-front-back",
        PieceA=front,
        PieceB=back,
    )
    fitting = SimpleNamespace(
        FittingType="FittingScene",
        PatternPieces=(front, back),
        PiecePlacements=(object(), object()),
    )
    rows = _readiness_rows(_readiness_scene((front, back), (seam,), fitting=fitting))
    assert rows["sewing"].state == "ready"
    assert rows["arrangement"].state == "ready"
    assert "2 saved placement(s)" in rows["arrangement"].message


def test_readiness_target_inspection_failure_blocks_simulation() -> None:
    """Target-inspection failure never advertises simulation readiness."""

    def fail(_target: object | None) -> dict[str, object]:
        """Simulate a target inspection error.

        Args:
            _target: Target reference, unused by this failing fixture.

        Raises:
            RuntimeError: Always, emulating a stale collision-cache inspection failure.
        """
        raise RuntimeError("stale collision cache")

    rows = {
        step.key: step
        for step in build_workflow_checklist(
            _readiness_scene((_readiness_piece("Panel"),)),
            target_status_fn=fail,
        )
    }
    assert rows["target"].state == "blocked"
    assert rows["simulation"].state == "blocked"
    assert "stale collision cache" in rows["target"].message


if __name__ == "__main__":
    unittest.main()
