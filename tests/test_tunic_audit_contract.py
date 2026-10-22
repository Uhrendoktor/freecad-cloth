# Copyright (C) 2026 FreeCAD Cloth contributors
"""Static contracts for the canonical tunic fixture and PBD evidence gates."""
import subprocess
import sys
from pathlib import Path

from tests.support.assertions import require

ROOT: Path = Path(__file__).resolve().parents[1]


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_canonical_tunic_pairs_matching_front_back_semantic_edges() -> None:
    """Require matching front/back semantic edge IDs for the authored tunic panels."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="front_edge_ids = tuple(" in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected \\\"front_edge_ids = tuple(\\\" in source",
    )
    require(
        condition="back_edge_ids = tuple(" in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected \\\"back_edge_ids = tuple(\\\" in source",
    )
    require(
        condition='"SemanticEdgeIds"' in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected '\\\"SemanticEdgeIds\\\"' in source",
    )
    require(
        condition='front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected 'front_edge_ids[1], back_edge_ids[1], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected 'front_edge_ids[3], back_edge_ids[3], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected 'front_edge_ids[5], back_edge_ids[5], \\\"TunicLe",
    )
    require(
        condition='front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source,
        message="test_canonical_tunic_pairs_matching_front_back_semantic_edges: expected 'front_edge_ids[7], back_edge_ids[7], \\\"TunicLe",
    )


def test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline() -> None:
    """Verify the tunic fixture uses avatar arrangement points and leaves the neckline unpinned."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="ArrangementPoint.from_string" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"ArrangementPoint.from_string\\\" in source",
    )
    require(
        condition='shoulder_left = arrangement_world("shoulder_left")' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'shoulder_left = arrangement_world(\\\"shoulder_l",
    )
    require(
        condition='shoulder_right = arrangement_world("shoulder_right")' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'shoulder_right = arrangement_world(\\\"shoulder_",
    )
    require(
        condition='hip_point = arrangement_world("hip")' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'hip_point = arrangement_world(\\\"hip\\\")' in sour",
    )
    require(
        condition='os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'os.environ[\\\"CLOTH_PBD_COLLISION_MODE\\\"] = \\\"mes",
    )
    require(
        condition="status = target_status(target)" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"status = target_status(target)\\\" in source",
    )
    require(
        condition='scene.PinMode = "None"' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'scene.PinMode = \\\"None\\\"' in source",
    )
    require(
        condition='scene.PinMode = "Explicit"' not in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'scene.PinMode = \\\"Explicit\\\"' not in source",
    )
    require(
        condition="scene.PinSelection = []" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"scene.PinSelection = []\\\" in source",
    )
    require(
        condition="scene.PinSelection = [str(index) for index in expected_pins]" not in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"scene.PinSelection = [str(index) for index in",
    )
    require(
        condition="if solver_pins:" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"if solver_pins:\\\" in source",
    )
    require(
        condition="base_proxy_getter().source_signature = None" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"base_proxy_getter().source_signature = None\\\" ",
    )
    require(
        condition="tunic-neckline-midpoint piece=%s particle=%d snap-mm=%.2f" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"tunic-neckline-midpoint piece=%s particle=%d ",
    )
    require(
        condition="panel_indices.get(panel.Name, ())" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"panel_indices.get(panel.Name, ())\\\" in source",
    )
    require(
        condition='panel_objects = tuple(getattr(scene, "DrapePanels", ()))' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected 'panel_objects = tuple(getattr(scene, \\\"DrapePa",
    )
    require(
        condition="scene.touch()" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"scene.touch()\\\" in source",
    )
    initial_piece_links = source.index("scene.ClothPieces = [front, back]")
    initial_cache_invalidation = source.index("base_proxy_getter().source_signature = None")
    first_panel_map = source.index('panel_piece_names = getattr(proxy, "panel_piece_names", {})')
    require(
        condition=initial_piece_links < initial_cache_invalidation < first_panel_map,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected initial_piece_links < initial_cache_invalidati",
    )
    require(
        condition="tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"tunic-simulation-panel-map proxy=%s links=%d ",
    )
    require(
        condition="canonical tunic simulation did not build an authored pattern panel" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"canonical tunic simulation did not build an a",
    )
    require(
        condition="def _neckline_boundary_particles(" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"def _neckline_boundary_particles(\\\" in source",
    )
    require(
        condition='"semantic-chain-endpoints"' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected '\\\"semantic-chain-endpoints\\\"' in source",
    )
    require(
        condition='"authored-edge-projection"' in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected '\\\"authored-edge-projection\\\"' in source",
    )
    require(
        condition=(
            (
            "tunic-neckline-resolution piece=%s edge=%s method=%s chains=%d endpoint-error-mm=%.6f"
            in source
            )
        ),
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected ( \\\"tunic-neckline-resolution piece=%s edge=%s ",
    )
    require(
        condition="boundary_index >= len(boundary_chains)" not in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"boundary_index >= len(boundary_chains)\\\" not i",
    )
    require(
        condition="nearest_target_clearance" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"nearest_target_clearance\\\" in source",
    )
    require(
        condition="step0-target-vertex-clearance-mm=" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"step0-target-vertex-clearance-mm=\\\" in source",
    )
    require(
        condition="authored_shoulder_pins" not in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"authored_shoulder_pins\\\" not in source",
    )
    require(
        condition="scene.PinSelection = [str(i) for i in front_pins]" not in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"scene.PinSelection = [str(i) for i in front_p",
    )
    require(
        condition="target_surface = collision_surface(" in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"target_surface = collision_surface(\\\" in sourc",
    )
    require(
        condition="target_source.Mesh.BoundBox" not in source,
        message="test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline: expected \\\"target_source.Mesh.BoundBox\\\" not in source",
    )


def test_canonical_tunic_uses_matching_authored_mapping() -> None:
    """Verify the canonical fixture maps each front edge to its matching back edge."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="required_indices = (1, 3, 5, 7)" in audit,
        message="test_canonical_tunic_uses_matching_authored_mapping: expected \\\"required_indices = (1, 3, 5, 7)\\\" in audit",
    )
    require(
        condition='front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit,
        message="test_canonical_tunic_uses_matching_authored_mapping: expected 'front_edge_ids[1], back_edge_ids[1], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit,
        message="test_canonical_tunic_uses_matching_authored_mapping: expected 'front_edge_ids[3], back_edge_ids[3], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in audit,
        message="test_canonical_tunic_uses_matching_authored_mapping: expected 'front_edge_ids[5], back_edge_ids[5], \\\"TunicLe",
    )
    require(
        condition='front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit,
        message="test_canonical_tunic_uses_matching_authored_mapping: expected 'front_edge_ids[7], back_edge_ids[7], \\\"TunicLe",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[5], "TunicRightShoulder"' not in audit,
        message="test_canonical_tunic_uses_matching_authored_mapping: expected 'front_edge_ids[3], back_edge_ids[5], \\\"TunicRi",
    )


def test_canonical_tunic_shared_source_syntax_compiles() -> None:
    """Verify the shared tunic-audit source passes its standalone syntax check."""
    audit_path = ROOT / "tests" / "freecad_tunic_audit.py"
    result = subprocess.run(
        [sys.executable, str(audit_path), "--syntax-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    require(
        condition=result.returncode == 0,
        message=(
"shared tunic source syntax gate failed\n"
f"stdout:\n{result.stdout}\n"
f"stderr:\n{result.stderr}"
),
    )
    require(
        condition="tunic-audit-source-syntax=passed" in result.stdout,
        message="test_canonical_tunic_shared_source_syntax_compiles: expected \\\"tunic-audit-source-syntax=passed\\\" in result.s",
    )


def test_canonical_tunic_authoritative_gate_is_fail_closed() -> None:
    """Verify the authoritative seam and collision gates fail closed when their limits are exceeded."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition='os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source,
        message="test_canonical_tunic_authoritative_gate_is_fail_closed: expected 'os.environ[\\\"CLOTH_PBD_COLLISION_MODE\\\"] = \\\"mes",
    )
    require(
        condition="proxy=proxy" in source,
        message="test_canonical_tunic_authoritative_gate_is_fail_closed: expected \\\"proxy=proxy\\\" in source",
    )
    require(
        condition="authoritative tunic seams did not converge" in source,
        message="test_canonical_tunic_authoritative_gate_is_fail_closed: expected \\\"authoritative tunic seams did not converge\\\" i",
    )
    require(
        condition="if max_seam_gap > 35.0" in source,
        message="test_canonical_tunic_authoritative_gate_is_fail_closed: expected \\\"if max_seam_gap > 35.0\\\" in source",
    )
    require(
        condition="authoritative-seam-gap seam=%s" in source,
        message="test_canonical_tunic_authoritative_gate_is_fail_closed: expected \\\"authoritative-seam-gap seam=%s\\\" in source",
    )


def test_canonical_tunic_has_two_curved_open_armholes() -> None:
    """Verify the canonical pattern retains two valid curved armholes."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="elif index == 2:" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"elif index == 2:\\\" in source",
    )
    require(
        condition="elif index == 6:" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"elif index == 6:\\\" in source",
    )
    require(
        condition="def _arc_through_midpoint(" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"def _arc_through_midpoint(\\\" in source",
    )
    require(
        condition="Part.ArcOfCircle(circle, start_angle, start_angle + sweep)" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"Part.ArcOfCircle(circle, start_angle, start_a",
    )
    require(
        condition="zero_point = curve_value(circle, 0.0)" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"zero_point = curve_value(circle, 0.0)\\\" in sou",
    )
    require(
        condition="quarter_point = curve_value(circle, math.pi / 2.0)" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"quarter_point = curve_value(circle, math.pi /",
    )
    require(
        condition='getter = getattr(curve, "valueAt", None)' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'getter = getattr(curve, \\\"valueAt\\\", None)' in ",
    )
    require(
        condition='getter = getattr(curve, "value", None)' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'getter = getattr(curve, \\\"value\\\", None)' in so",
    )
    require(
        condition="tunic armhole curve has no native parameter evaluator" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"tunic armhole curve has no native parameter e",
    )
    require(
        condition="tunic armhole arc lost authored %s" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"tunic armhole arc lost authored %s\\\" in source",
    )
    sketch_builder = source.split("def _make_tunic_sketch(", 1)[1].split("\ndef _adopt_sketch", 1)[
        0
    ]
    require(
        condition=(
            (
            'sketch.addConstraint([Sketcher.Constraint("Block", index) '
            "for index in range(len(geometry))])"
            ) in sketch_builder
        ),
        message="test_canonical_tunic_has_two_curved_open_armholes: expected ( 'sketch.addConstraint([Sketcher.Constraint(\\\"",
    )
    require(
        condition='Sketcher.Constraint("Coincident"' not in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'Sketcher.Constraint(\\\"Coincident\\\"' not in sket",
    )
    require(
        condition="tunic armhole collapsed during Sketcher recompute" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"tunic armhole collapsed during Sketcher recom",
    )
    require(
        condition="armhole_z = 0.62 * float(garment_height)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"armhole_z = 0.62 * float(garment_height)\\\" in ",
    )
    require(
        condition="(x_offset + 0.74 * panel_width, armhole_z)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"(x_offset + 0.74 * panel_width, armhole_z)\\\" i",
    )
    require(
        condition="shoulder_z = 0.94 * float(garment_height)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"shoulder_z = 0.94 * float(garment_height)\\\" in",
    )
    require(
        condition="(x_offset + 0.94 * panel_width, shoulder_z)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"(x_offset + 0.94 * panel_width, shoulder_z)\\\" ",
    )
    require(
        condition="if not (armhole_z < shoulder_z < neck_z)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"if not (armhole_z < shoulder_z < neck_z)\\\" in ",
    )
    require(
        condition="shoulders must slope downward from neckline to shoulder tip" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"shoulders must slope downward from neckline t",
    )
    require(
        condition="points[3][0] - points[2][0] < 0.15 * float(panel_width)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"points[3][0] - points[2][0] < 0.15 * float(pa",
    )
    require(
        condition="shoulder_z - armhole_z < 0.20 * float(garment_height)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"shoulder_z - armhole_z < 0.20 * float(garment",
    )
    require(
        condition="side_ease_mm = 4.0" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"side_ease_mm = 4.0\\\" in sketch_builder",
    )
    require(
        condition="if index == 1:" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"if index == 1:\\\" in sketch_builder",
    )
    require(
        condition="elif index == 7:" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"elif index == 7:\\\" in sketch_builder",
    )
    require(
        condition="0.5 * (start[0] + end[0]) + side_ease_mm" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"0.5 * (start[0] + end[0]) + side_ease_mm\\\" in ",
    )
    require(
        condition="0.5 * (start[0] + end[0]) - side_ease_mm" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"0.5 * (start[0] + end[0]) - side_ease_mm\\\" in ",
    )
    require(
        condition="(x_offset + 0.06 * panel_width, shoulder_z)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"(x_offset + 0.06 * panel_width, shoulder_z)\\\" ",
    )
    require(
        condition="(x_offset + 0.26 * panel_width, armhole_z)" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"(x_offset + 0.26 * panel_width, armhole_z)\\\" i",
    )
    # Keep the inward-scooped arc inside the shoulder line; .73/.27 self-intersects.
    require(
        condition="x_offset + 0.741 * panel_width, armhole_mid_z" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"x_offset + 0.741 * panel_width, armhole_mid_z",
    )
    require(
        condition="x_offset + 0.259 * panel_width, armhole_mid_z" in sketch_builder,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"x_offset + 0.259 * panel_width, armhole_mid_z",
    )
    require(
        condition="for edge_index, inward in ((2, -1.0), (6, 1.0))" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"for edge_index, inward in ((2, -1.0), (6, 1.0",
    )
    require(
        condition='boundary.kind != "arc" or len(boundary.samples) < 8' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'boundary.kind != \\\"arc\\\" or len(boundary.sample",
    )
    require(
        condition="armhole curve has insufficient inward clearance" in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected \\\"armhole curve has insufficient inward clearan",
    )
    require(
        condition='front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'front_edge_ids[1], back_edge_ids[1], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'front_edge_ids[3], back_edge_ids[3], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'front_edge_ids[5], back_edge_ids[5], \\\"TunicLe",
    )
    require(
        condition='front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False' in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'front_edge_ids[7], back_edge_ids[7], \\\"TunicLe",
    )
    require(
        condition='front_edge_ids[2], back_edge_ids[2], "TunicRightArmhole"' not in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'front_edge_ids[2], back_edge_ids[2], \\\"TunicRi",
    )
    require(
        condition='front_edge_ids[6], back_edge_ids[6], "TunicLeftArmhole"' not in source,
        message="test_canonical_tunic_has_two_curved_open_armholes: expected 'front_edge_ids[6], back_edge_ids[6], \\\"TunicLe",
    )


def test_simulation_proxy_serializes_only_rebuildable_metadata() -> None:
    """Verify simulation proxies persist rebuildable metadata rather than native runtime state."""
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

    proxy = SimulationProxy()
    proxy.backend = object()
    proxy.panel_indices = {"panel": (1, 2)}
    proxy.seam_stitch_pairs = {"seam": ((0, 1),)}
    proxy.source_signature = ("derived",)
    proxy.last_steps = 17
    proxy.collision_surface = object()

    state = proxy.__getstate__()
    require(
        condition=state == {"schema": 1},
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected state == {\\\"schema\\\": 1}",
    )
    require(
        condition="backend" not in state,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected \\\"backend\\\" not in state",
    )
    require(
        condition="seam_stitch_pairs" not in state,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected \\\"seam_stitch_pairs\\\" not in state",
    )
    require(
        condition="collision_surface" not in state,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected \\\"collision_surface\\\" not in state",
    )

    proxy.__setstate__(state)
    require(
        condition=proxy.backend is None,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected proxy.backend is None",
    )
    require(
        condition=proxy.panel_indices == {},
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected proxy.panel_indices == {}",
    )
    require(
        condition=proxy.seam_stitch_pairs == {},
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected proxy.seam_stitch_pairs == {}",
    )
    require(
        condition=proxy.source_signature is None,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected proxy.source_signature is None",
    )
    require(
        condition=proxy.last_steps == 0,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected proxy.last_steps == 0",
    )
    require(
        condition=proxy.collision_surface is None,
        message="test_simulation_proxy_serializes_only_rebuildable_metadata: expected proxy.collision_surface is None",
    )


def test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit() -> None:
    """Verify the documented real-time simulation profile is bounded and uses mesh collision."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition="ParticleDistance = 24.0" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"ParticleDistance = 24.0\\\" in source",
    )
    require(
        condition="SolverIterations = 8" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"SolverIterations = 8\\\" in source",
    )
    require(
        condition="SolverSubsteps = 4" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"SolverSubsteps = 4\\\" in source",
    )
    require(
        condition="CLOTH_PBD_COLLISION_MODE: mesh" in workflow,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"CLOTH_PBD_COLLISION_MODE: mesh\\\" in workflow",
    )
    require(
        condition="CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in workflow,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"CLOTH_PBD_COLLISION_VOXEL_MM=8.0\\\" in workflow",
    )
    require(
        condition="voxel_mm - 8.0" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"voxel_mm - 8.0\\\" in source",
    )
    require(
        condition="(span + 200.0) / 8.0" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"(span + 200.0) / 8.0\\\" in source",
    )
    require(
        condition="configured 8 mm voxel resolution" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"configured 8 mm voxel resolution\\\" in source",
    )
    tunic_workflow = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    require(
        condition="CLOTH_PBD_SUBSTEPS=16" in tunic_workflow,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"CLOTH_PBD_SUBSTEPS=16\\\" in tunic_workflow",
    )
    require(
        condition='os.environ["CLOTH_PBD_COLLISION_VOXEL_MM"]' not in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected 'os.environ[\\\"CLOTH_PBD_COLLISION_VOXEL_MM\\\"]' n",
    )
    require(
        condition="CLOTH_PBD_SUBSTEPS: 8" in workflow,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"CLOTH_PBD_SUBSTEPS: 8\\\" in workflow",
    )
    require(
        condition='os.environ["CLOTH_PBD_SUBSTEPS"]' not in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected 'os.environ[\\\"CLOTH_PBD_SUBSTEPS\\\"]' not in sour",
    )
    require(
        condition="CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"CLOTH_PBD_COLLISION_TOLERANCE_MM: 12\\\" not in ",
    )
    require(
        condition="tunic-collision-config target-thickness-mm=%.2f" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"tunic-collision-config target-thickness-mm=%.",
    )
    simulation_commands = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationCommands.py"
    ).read_text(encoding="utf-8")
    require(
        condition="DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM" in simulation_commands,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM\\\" in ",
    )
    require(
        condition="tunic-simulation-start" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"tunic-simulation-start\\\" in source",
    )
    require(
        condition='configured_substeps = int(os.environ.get("CLOTH_PBD_SUBSTEPS", "8"))' in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected 'configured_substeps = int(os.environ.get(\\\"CLO",
    )
    require(
        condition='effective_substeps = int(getattr(active_backend, "_substeps", -1))' in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected 'effective_substeps = int(getattr(active_backe",
    )
    require(
        condition="effective_substeps != configured_substeps" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"effective_substeps != configured_substeps\\\" in",
    )
    require(
        condition="backend_substeps=%d configured_substeps=%d" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"backend_substeps=%d configured_substeps=%d\\\" i",
    )
    require(
        condition="realtime-preview=passed backend=position-based-dynamics" in source,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"realtime-preview=passed backend=position-base",
    )
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition="tools/ci/validate_manifests.py tunic-production" in workflow,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"tools/ci/validate_manifests.py tunic-producti",
    )
    validator = (ROOT / "tools" / "ci" / "validate_manifests.py").read_text(encoding="utf-8")
    require(
        condition="def validate_tunic_production()" in validator,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"def validate_tunic_production()\\\" in validator",
    )
    require(
        condition="runtime collision configuration evidence is invalid" in validator,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"runtime collision configuration evidence is i",
    )
    require(
        condition="expected_resolution = tuple(" in validator,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"expected_resolution = tuple(\\\" in validator",
    )
    require(
        condition="def _validate_realtime_metrics(data: dict)" in validator,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"def _validate_realtime_metrics(data: dict)\\\" i",
    )
    require(
        condition="_validate_realtime_metrics(data)" in validator,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"_validate_realtime_metrics(data)\\\" in validato",
    )
    require(
        condition="PBD SDF voxel must be 8 mm" in validator,
        message="test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit: expected \\\"PBD SDF voxel must be 8 mm\\\" in validator",
    )


def test_pbd_collision_body_uses_coarsened_solver_surface() -> None:
    """Verify the PBD collision body uses the explicit coarsened solver surface."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    start = backend.index("    def _add_collision_body(")
    end = backend.index("    def _build(", start)
    body_builder = backend[start:end]
    require(
        condition="collision_surface = self._collision_surface" in body_builder,
        message="test_pbd_collision_body_uses_coarsened_solver_surface: expected \\\"collision_surface = self._collision_surface\\\" ",
    )
    require(
        condition="collision_surface = self._source_collision_surface" not in body_builder,
        message="test_pbd_collision_body_uses_coarsened_solver_surface: expected \\\"collision_surface = self._source_collision_su",
    )


def test_pbd_collision_sdf_resolution_and_tolerance_are_explicit() -> None:
    """Verify collision SDF resolution and tolerance remain explicit in the source contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="CLOTH_PBD_COLLISION_VOXEL_MM" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"CLOTH_PBD_COLLISION_VOXEL_MM\\\" in backend",
    )
    require(
        condition="def _pbd_collision_resolution(surface: CollisionSurface)" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"def _pbd_collision_resolution(surface: Collis",
    )
    require(
        condition="generateSDF(" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"generateSDF(\\\" in backend",
    )
    require(
        condition="resolution," in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"resolution,\\\" in backend",
    )
    require(
        condition="representation_margin = 0.5 * _pbd_collision_voxel_mm()" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"representation_margin = 0.5 * _pbd_collision_",
    )
    require(
        condition="max(configured, thickness, representation_margin)" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"max(configured, thickness, representation_mar",
    )
    require(
        condition="self._collision_sdf_resolution = tuple(int(axis) for axis in resolution)" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"self._collision_sdf_resolution = tuple(int(ax",
    )
    require(
        condition="effective_tolerance_mm / _MM" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"effective_tolerance_mm / _MM\\\" in backend",
    )
    require(
        condition="cloth-pbd-collision-config " in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"cloth-pbd-collision-config \\\" in backend",
    )
    require(
        condition=(
            backend.index("timestep.step(self._model)") < backend.index(
            "self._project_collision_positions()"
            )
        ),
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected backend.index(\\\"timestep.step(self._model)\\\") < ",
    )
    require(
        condition="particles.setPosition(" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"particles.setPosition(\\\" in backend",
    )
    require(
        condition="inward_speed < 0.0" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"inward_speed < 0.0\\\" in backend",
    )
    require(
        condition="project_stitched_pairs(" in backend,
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected \\\"project_stitched_pairs(\\\" in backend",
    )
    require(
        condition=backend.index("project_stitched_pairs(") < backend.index("moved_indices ="),
        message="test_pbd_collision_sdf_resolution_and_tolerance_are_explicit: expected backend.index(\\\"project_stitched_pairs(\\\") < bac",
    )


def test_pbd_collision_sdf_is_cached_outside_backend_instance() -> None:
    """Verify collision SDF cache ownership is independent of backend instances."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="_PBD_COLLISION_SDF_CACHE_KEY" in backend,
        message="test_pbd_collision_sdf_is_cached_outside_backend_instance: expected \\\"_PBD_COLLISION_SDF_CACHE_KEY\\\" in backend",
    )
    require(
        condition="_PBD_COLLISION_SDF_CACHE" in backend,
        message="test_pbd_collision_sdf_is_cached_outside_backend_instance: expected \\\"_PBD_COLLISION_SDF_CACHE\\\" in backend",
    )
    require(
        condition="cache-hit" in backend,
        message="test_pbd_collision_sdf_is_cached_outside_backend_instance: expected \\\"cache-hit\\\" in backend",
    )
    require(
        condition="generateSDF(" in backend,
        message="test_pbd_collision_sdf_is_cached_outside_backend_instance: expected \\\"generateSDF(\\\" in backend",
    )
    require(
        condition="self._collision_sdf" in backend,
        message="test_pbd_collision_sdf_is_cached_outside_backend_instance: expected \\\"self._collision_sdf\\\" in backend",
    )


def test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive() -> None:
    """Verify SDF cache keys remain stable and respond to geometry changes."""
    from freecad_cloth.shared.collision import CollisionSurface
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
        _pbd_collision_sdf_cache_key,
    )

    surface = CollisionSurface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    key = _pbd_collision_sdf_cache_key(surface, [16, 16, 16])
    require(
        condition=key == _pbd_collision_sdf_cache_key(surface, [16, 16, 16]),
        message="test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive: expected key == _pbd_collision_sdf_cache_key(surface, [",
    )

    moved = CollisionSurface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    require(
        condition=key != _pbd_collision_sdf_cache_key(moved, [16, 16, 16]),
        message="test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive: expected key != _pbd_collision_sdf_cache_key(moved, [16",
    )
    require(
        condition=key != _pbd_collision_sdf_cache_key(surface, [17, 16, 16]),
        message="test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive: expected key != _pbd_collision_sdf_cache_key(surface, [",
    )


def test_pbd_ci_image_is_pinned_and_preinstalled() -> None:
    """Verify CI uses the pinned, preinstalled PBD runtime image."""
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition="pypbd==2.2.2" in dockerfile,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"pypbd==2.2.2\\\" in dockerfile",
    )
    require(
        condition="triangle==20250106" in dockerfile,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"triangle==20250106\\\" in dockerfile",
    )
    require(
        condition="/opt/pypbd-provenance.txt" in dockerfile,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"/opt/pypbd-provenance.txt\\\" in dockerfile",
    )
    require(
        condition="makehuman-hm08-base.obj" in dockerfile,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"makehuman-hm08-base.obj\\\" in dockerfile",
    )
    require(
        condition=(
            (
            "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-cloth/assets/makehuman-hm08-base.obj" in dockerfile
            )
        ),
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected ( \\\"FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-clot",
    )
    require(
        condition="1f508f6083b2f823dab15de924b3bde72e08d77c9/makehuman/data/3dobjs/base.obj" in dockerfile,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"1f508f6083b2f823dab15de924b3bde72e08d77c9/mak",
    )
    require(
        condition="8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c" in dockerfile,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"8e761e6624b8f54536409135d1636da63b32486a90d48",
    )
    require(
        condition="pbd_validation_image:" in workflow,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"pbd_validation_image:\\\" in workflow",
    )
    require(
        condition="FREECAD_PBD_IMAGE" in workflow,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"FREECAD_PBD_IMAGE\\\" in workflow",
    )
    require(
        condition="CLOTH_CI_ENABLE_PBD: 1" in workflow,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"CLOTH_CI_ENABLE_PBD: 1\\\" in workflow",
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    require(
        condition="image: ${{ env.FREECAD_PBD_IMAGE }}" in gui,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"image: ${{ env.FREECAD_PBD_IMAGE }}\\\" in gui",
    )
    require(
        condition="capture_pypbd_provenance.py" in gui,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"capture_pypbd_provenance.py\\\" in gui",
    )
    require(
        condition="artifacts/pypbd-provenance.txt" in gui,
        message="test_pbd_ci_image_is_pinned_and_preinstalled: expected \\\"artifacts/pypbd-provenance.txt\\\" in gui",
    )


def test_production_tunic_audit_runs_even_if_performance_gate_fails() -> None:
    """Verify the authoritative tunic audit runs even when a separate performance gate fails."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    benchmark = gui.split(
        "      - uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@", 1
    )[1].split("      - name: Independently validate realtime performance metrics", 1)[0]
    require(
        condition="test-script: tests/freecad_realtime_benchmark.py" in benchmark,
        message="test_production_tunic_audit_runs_even_if_performance_gate_fails: expected \\\"test-script: tests/freecad_realtime_benchmark",
    )
    require(
        condition="CLOTH_REALTIME_FRAMES=120" in benchmark,
        message="test_production_tunic_audit_runs_even_if_performance_gate_fails: expected \\\"CLOTH_REALTIME_FRAMES=120\\\" in benchmark",
    )
    require(
        condition="tools/ci/validate_realtime_benchmark.py artifacts/freecad-realtime/metrics.json" in gui,
        message="test_production_tunic_audit_runs_even_if_performance_gate_fails: expected \\\"tools/ci/validate_realtime_benchmark.py artif",
    )
    audit_step = gui.split("      - uses: ./.github/actions/freecad-test", 1)[1]
    require(
        condition="if: always()" in audit_step.split("test-script:", 1)[0],
        message="test_production_tunic_audit_runs_even_if_performance_gate_fails: expected \\\"if: always()\\\" in audit_step.split(\\\"test-scrip",
    )
    require(
        condition="test-script: tests/freecad_tunic_audit_production.py" in audit_step,
        message="test_production_tunic_audit_runs_even_if_performance_gate_fails: expected \\\"test-script: tests/freecad_tunic_audit_produc",
    )
    validator = (ROOT / "tools" / "ci" / "validate_realtime_benchmark.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="p95_frame_interval_ms exceeds the 30 FPS budget" in validator,
        message="test_production_tunic_audit_runs_even_if_performance_gate_fails: expected \\\"p95_frame_interval_ms exceeds the 30 FPS budg",
    )


def test_production_tunic_wrapper_dispatches_in_freecad_macro_host() -> None:
    """Verify the production tunic wrapper dispatches through the FreeCAD macro host."""
    wrapper = (ROOT / "tests" / "freecad_tunic_audit_production.py").read_text(encoding="utf-8")
    require(
        condition='importlib.import_module("freecad_tunic_audit").main' in wrapper,
        message="test_production_tunic_wrapper_dispatches_in_freecad_macro_host: expected 'importlib.import_module(\\\"freecad_tunic_audit\\\"",
    )
    require(
        condition="main()" in wrapper,
        message="test_production_tunic_wrapper_dispatches_in_freecad_macro_host: expected \\\"main()\\\" in wrapper",
    )
    require(
        condition='if __name__ == "__main__"' not in wrapper,
        message="test_production_tunic_wrapper_dispatches_in_freecad_macro_host: expected 'if __name__ == \\\"__main__\\\"' not in wrapper",
    )


def test_canonical_tunic_fixture_matches_validated_start_geometry() -> None:
    """Verify the canonical tunic fixture matches the geometry used for validation."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit_entry = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    require(
        condition="CLOTH_TUNIC_AUDIT_PROFILE" in audit_entry,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"CLOTH_TUNIC_AUDIT_PROFILE\\\" in audit_entry",
    )
    require(
        condition="TUNIC_PRODUCTION_AUDIT" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"TUNIC_PRODUCTION_AUDIT\\\" in audit",
    )
    require(
        condition="SEAM_SOURCE = " not in audit_entry,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"SEAM_SOURCE = \\\" not in audit_entry",
    )
    require(
        condition="required_indices = (1, 3, 5, 7)" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"required_indices = (1, 3, 5, 7)\\\" in audit",
    )
    require(
        condition="TunicRightShoulder" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"TunicRightShoulder\\\" in audit",
    )
    require(
        condition="TunicLeftShoulder" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"TunicLeftShoulder\\\" in audit",
    )
    require(
        condition="ParticleDistance = 24.0" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"ParticleDistance = 24.0\\\" in audit",
    )
    require(
        condition="SolverIterations = 8" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"SolverIterations = 8\\\" in audit",
    )
    require(
        condition="SolverSubsteps = 4 if TUNIC_PRODUCTION_AUDIT else 1" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"SolverSubsteps = 4 if TUNIC_PRODUCTION_AUDIT ",
    )
    require(
        condition="tunic-simulation-start" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"tunic-simulation-start\\\" in audit",
    )
    require(
        condition="realtime-preview=passed backend=position-based-dynamics" in audit,
        message="test_canonical_tunic_fixture_matches_validated_start_geometry: expected \\\"realtime-preview=passed backend=position-base",
    )


def test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host() -> None:
    """Verify penetration auditing uses the supported NumPy ray-parity path in FreeCAD."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    inside_check = source.split("def _inside_target_count(", 1)[1].split(
        "\ndef write_drape_metrics(", 1
    )[0]
    require(
        condition="Trimesh/Rtree's native contains query" in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"Trimesh/Rtree's native contains query\\\" in ins",
    )
    require(
        condition="target_mesh.contains" not in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"target_mesh.contains\\\" not in inside_check",
    )
    require(
        condition="import trimesh" not in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"import trimesh\\\" not in inside_check",
    )
    require(
        condition="chunk_size=4" in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"chunk_size=4\\\" in inside_check",
    )
    require(
        condition="points_inside_closed_mesh(" in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"points_inside_closed_mesh(\\\" in inside_check",
    )
    require(
        condition="prefer_trimesh=False" in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"prefer_trimesh=False\\\" in inside_check",
    )
    require(
        condition="penetration-check=numpy-ray-parity" in inside_check,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"penetration-check=numpy-ray-parity\\\" in inside",
    )
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="prefer_trimesh: bool = True" in sanity,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"prefer_trimesh: bool = True\\\" in sanity",
    )
    require(
        condition="if prefer_trimesh:" in sanity,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"if prefer_trimesh:\\\" in sanity",
    )
    require(
        condition="np.einsum" in sanity,
        message="test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host: expected \\\"np.einsum\\\" in sanity",
    )


def test_penetration_evidence_stays_on_numpy_path_in_freecad_host() -> None:
    """Verify penetration evidence remains on the supported NumPy execution path."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = source.split("def write_drape_metrics(", 1)[1].split("\ndef _arc_through_midpoint(", 1)[
        0
    ]
    evidence = audit.split("inside_points = []", 1)[1].split(
        'log(\n                    "penetration-evidence', 1
    )[0]

    require(
        condition=(
            (
            "from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh"
            not in audit
            )
        ),
        message="test_penetration_evidence_stays_on_numpy_path_in_freecad_host: expected ( \\\"from freecad_cloth.simulation.DrapeVisualSa",
    )
    require(
        condition=evidence.count("prefer_trimesh=False") == 2,
        message="test_penetration_evidence_stays_on_numpy_path_in_freecad_host: expected evidence.count(\\\"prefer_trimesh=False\\\") == 2",
    )
    require(
        condition="points_inside_closed_mesh(" in evidence,
        message="test_penetration_evidence_stays_on_numpy_path_in_freecad_host: expected \\\"points_inside_closed_mesh(\\\" in evidence",
    )
    require(
        condition="point_inside_closed_mesh(" not in evidence,
        message="test_penetration_evidence_stays_on_numpy_path_in_freecad_host: expected \\\"point_inside_closed_mesh(\\\" not in evidence",
    )


def test_tunic_visual_diagnostics_are_authoritative_after_persistence() -> None:
    """Verify visual diagnostics inspect the persisted simulation rather than a transient state."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    require(
        condition=metrics_write < screenshot < gate,
        message="test_tunic_visual_diagnostics_are_authoritative_after_persistence: expected metrics_write < screenshot < gate",
    )


def test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks() -> None:
    """Verify drape debugging uses the canonical tunic profile and avatar landmarks."""
    debug = (ROOT / "tests" / "freecad_drape_debug.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")

    # Keep the diagnostic A/B garment aligned to current production geometry/scene APIs.
    require(
        condition=(
            (
            "from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene"
            in debug
            )
        ),
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected ( \\\"from freecad_cloth.simulation.SimulationCom",
    )
    require(
        condition="SimulationQualityRuntimeV2" not in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"SimulationQualityRuntimeV2\\\" not in debug",
    )
    require(
        condition="neck_z = (1.0 - float(neckline_drop)) * h" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neck_z = (1.0 - float(neckline_drop)) * h\\\" in",
    )
    require(
        condition="neckline_drop=0.03" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neckline_drop=0.03\\\" in source",
    )
    require(
        condition="shoulder_headroom_mm = 20.0" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"shoulder_headroom_mm = 20.0\\\" in source",
    )
    require(
        condition=(
            (
            "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)" in source
            )
        ),
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected ( \\\"garment_height = max(560.0, (shoulder_z - h",
    )
    require(
        condition="shoulder_headroom_mm = 20.0" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"shoulder_headroom_mm = 20.0\\\" in debug",
    )
    require(
        condition=(
            (
            "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)" in debug
            )
        ),
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected ( \\\"garment_height = max(560.0, (shoulder_z - h",
    )
    require(
        condition="x_offset = 0.5 * (float(hem_width) - float(panel_width))" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"x_offset = 0.5 * (float(hem_width) - float(pa",
    )
    require(
        condition="armhole_z = 0.62 * h" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"armhole_z = 0.62 * h\\\" in debug",
    )
    require(
        condition="armhole_z = 0.62 * h" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"armhole_z = 0.62 * h\\\" in debug",
    )
    require(
        condition="shoulder_z = 0.94 * h" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"shoulder_z = 0.94 * h\\\" in debug",
    )
    require(
        condition="points[3][0] - points[2][0] < 0.15 * float(panel_width)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"points[3][0] - points[2][0] < 0.15 * float(pa",
    )
    require(
        condition="shoulder_z - armhole_z < 0.20 * h" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"shoulder_z - armhole_z < 0.20 * h\\\" in debug",
    )
    require(
        condition="side_ease_mm = 4.0" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"side_ease_mm = 4.0\\\" in debug",
    )
    require(
        condition="if idx == 1:" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"if idx == 1:\\\" in debug",
    )
    require(
        condition="elif idx == 7:" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"elif idx == 7:\\\" in debug",
    )
    require(
        condition="(x_offset + 0.74 * panel_width, armhole_z)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"(x_offset + 0.74 * panel_width, armhole_z)\\\" i",
    )
    require(
        condition="(x_offset + 0.26 * panel_width, armhole_z)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"(x_offset + 0.26 * panel_width, armhole_z)\\\" i",
    )
    require(
        condition="midpoint = App.Vector(x_offset + 0.741 * panel_width, armhole_mid_z, 0)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"midpoint = App.Vector(x_offset + 0.741 * pane",
    )
    require(
        condition="midpoint = App.Vector(x_offset + 0.259 * panel_width, armhole_mid_z, 0)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"midpoint = App.Vector(x_offset + 0.259 * pane",
    )
    require(
        condition="(x_offset + 0.06 * panel_width, 0.94 * garment_height)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"(x_offset + 0.06 * panel_width, 0.94 * garmen",
    )
    require(
        condition="(x_offset + 0.94 * panel_width, 0.94 * garment_height)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"(x_offset + 0.94 * panel_width, 0.94 * garmen",
    )
    require(
        condition="if not (armhole_z < shoulder_z < neck_z)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"if not (armhole_z < shoulder_z < neck_z)\\\" in ",
    )
    require(
        condition="neckline_scoop_depth = 0.12 * h" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neckline_scoop_depth = 0.12 * h\\\" in debug",
    )
    require(
        condition="neckline_scoop_z = neck_z - neckline_scoop_depth" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neckline_scoop_z = neck_z - neckline_scoop_de",
    )
    require(
        condition="if not (armhole_z < neckline_scoop_z < shoulder_z)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"if not (armhole_z < neckline_scoop_z < should",
    )
    require(
        condition="neckline_scoop_depth = 0.12 * float(garment_height)" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neckline_scoop_depth = 0.12 * float(garment_h",
    )
    require(
        condition="neckline_scoop_z = neck_z - neckline_scoop_depth" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neckline_scoop_z = neck_z - neckline_scoop_de",
    )
    require(
        condition="neckline_scoop_depth = 0.12 * float(garment_height)" in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"neckline_scoop_depth = 0.12 * float(garment_h",
    )
    require(
        condition='("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")' in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected '(\\\"back\\\", \\\"front\\\") if TUNIC_PRODUCTION_AUDIT e",
    )
    require(
        condition='make_piece("VisualTunicFront", front_side, 0.72, 0.03)' in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected 'make_piece(\\\"VisualTunicFront\\\", front_side, 0.",
    )
    require(
        condition='make_piece("VisualTunicBack", back_side, 0.72, 0.03)' in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected 'make_piece(\\\"VisualTunicBack\\\", back_side, 0.72",
    )
    require(
        condition="elif idx == 4:" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"elif idx == 4:\\\" in debug",
    )
    require(
        condition="elif index == 4:" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"elif index == 4:\\\" in source",
    )
    require(
        condition="true U-shaped neckline" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"true U-shaped neckline\\\" in source",
    )
    require(
        condition="ArrangementPoint.from_string(raw)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"ArrangementPoint.from_string(raw)\\\" in debug",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width = max(420.0, shoulder_width + 105",
    )
    require(
        condition="shoulder_width + 105.0" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"shoulder_width + 105.0\\\" in source",
    )
    require(
        condition="else max(450.0, panel_width + 100.0)" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"else max(450.0, panel_width + 100.0)\\\" in sour",
    )
    require(
        condition="shoulder_span_ratio" not in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"shoulder_span_ratio\\\" not in audit",
    )
    require(
        condition='"panel_width = max(420.0, shoulder_width + 105.0)":' not in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected '\\\"panel_width = max(420.0, shoulder_width + 10",
    )
    require(
        condition="clearance = max(20.0, 0.08 * body_depth)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"clearance = max(20.0, 0.08 * body_depth)\\\" in ",
    )
    require(
        condition="clearance = max(20.0, 0.08 * body_depth)" in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"clearance = max(20.0, 0.08 * body_depth)\\\" in ",
    )
    require(
        condition="clearance = max(20.0, 0.08 * body_depth)" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"clearance = max(20.0, 0.08 * body_depth)\\\" in ",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width = max(420.0, shoulder_width + 105",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width = max(420.0, shoulder_width + 105",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width = max(420.0, shoulder_width + 105",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width = max(420.0, shoulder_width + 105",
    )
    require(
        condition="hem_width = max(500.0, panel_width + 100.0)" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"hem_width = max(500.0, panel_width + 100.0)\\\" ",
    )
    require(
        condition='make_piece("DebugTunicFront", front_y, 0.72, 0.03)' in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected 'make_piece(\\\"DebugTunicFront\\\", front_y, 0.72, ",
    )
    require(
        condition="panel_width *= 1.10" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width *= 1.10\\\" in source",
    )
    require(
        condition="hem_width *= 1.10" in source,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"hem_width *= 1.10\\\" in source",
    )
    require(
        condition="panel_width *= 1.10" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"panel_width *= 1.10\\\" in debug",
    )
    require(
        condition="hem_width *= 1.10" in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected \\\"hem_width *= 1.10\\\" in debug",
    )
    require(
        condition='make_piece("DebugTunicBack", back_y, 0.72, 0.03)' in debug,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected 'make_piece(\\\"DebugTunicBack\\\", back_y, 0.72, 0.",
    )
    require(
        condition='("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")' in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected '(\\\"back\\\", \\\"front\\\") if TUNIC_PRODUCTION_AUDIT e",
    )
    require(
        condition='make_piece("VisualTunicFront", front_side, 0.72, 0.03)' in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected 'make_piece(\\\"VisualTunicFront\\\", front_side, 0.",
    )
    require(
        condition='make_piece("VisualTunicBack", back_side, 0.72, 0.03)' in audit,
        message="test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks: expected 'make_piece(\\\"VisualTunicBack\\\", back_side, 0.72",
    )


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit() -> None:
    """Verify failed visual acceptance preserves its diagnostic artifacts before exiting."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    require(
        condition="drape-metrics=" in source[:gate],
        message="test_tunic_visual_gate_preserves_failed_artifacts_before_exit: expected \\\"drape-metrics=\\\" in source[:gate]",
    )
    require(
        condition="gui-screenshot-manifest" not in source[gate:] or "task_dock.show()" in source[gate:],
        message="test_tunic_visual_gate_preserves_failed_artifacts_before_exit: expected \\\"gui-screenshot-manifest\\\" not in source[gate:]",
    )


def test_canonical_tunic_fixture_blocks_every_authored_segment() -> None:
    """Verify every authored tunic segment receives the required pattern constraint."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    start = source.index("def _make_tunic_sketch(")
    end = source.index("\ndef _adopt_sketch(", start)
    fixture = source[start:end]

    # Fixing all authored segments prevents coincident-only constraints from
    # folding otherwise unconstrained straight edges across the pattern outline.
    expected_constraint = (
        'sketch.addConstraint([Sketcher.Constraint("Block", index) '
        "for index in range(len(geometry))])"
    )
    require(
        condition=expected_constraint in fixture,
        message="test_canonical_tunic_fixture_blocks_every_authored_segment: expected expected_constraint in fixture",
    )
    require(
        condition='Sketcher.Constraint("Coincident"' not in fixture,
        message="test_canonical_tunic_fixture_blocks_every_authored_segment: expected 'Sketcher.Constraint(\\\"Coincident\\\"' not in fixt",
    )


def test_tunic_scene_dossier_logs_sampled_topology_before_simulation() -> None:
    """The actual CI fixture must emit geometry evidence before downstream evaluation."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    simulation = source.split("def simulation():", 1)[1]
    topology_audit = simulation.index("def log_tunic_outline_topology(piece):")
    sample_resolution = simulation.index("resolve_piece_ir(piece)", topology_audit)
    pattern_view = simulation.index(
        "capture_tunic_pattern_view(doc, front, back, hem_width)", topology_audit
    )
    sewing_view = simulation.index(
        "capture_tunic_sewing_view(doc, front, back, hem_width, seam_records)",
        pattern_view,
    )
    native_gate = simulation.index(
        "canonical tunic PatternIR boundary is invalid before simulation", sewing_view
    )
    simulation_start = simulation.index("scene.StartHeight = 0.0", native_gate)

    require(
        condition=(
            (
            topology_audit
            < sample_resolution
            < pattern_view
            < sewing_view
            < native_gate
            < simulation_start
            )
        ),
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected ( topology_audit < sample_resolution < pattern",
    )
    require(
        condition='"boundary-order=%r near-crossing=%r"' in simulation,
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected '\\\"boundary-order=%r near-crossing=%r\\\"' in simu",
    )
    require(
        condition="samples," in simulation,
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected \\\"samples,\\\" in simulation",
    )
    # Keep geometric validity guards in FreeCAD, but keep report classification on the host.
    require(
        condition="canonical tunic derived pattern outline is invalid before simulation" in simulation,
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected \\\"canonical tunic derived pattern outline is in",
    )
    require(
        condition="fit_assessment" not in simulation,
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected \\\"fit_assessment\\\" not in simulation",
    )
    require(
        condition="review_required" not in simulation,
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected \\\"review_required\\\" not in simulation",
    )
    require(
        condition='status["result"]' not in simulation,
        message="test_tunic_scene_dossier_logs_sampled_topology_before_simulation: expected 'status[\\\"result\\\"]' not in simulation",
    )
