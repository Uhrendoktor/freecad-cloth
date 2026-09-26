"""Contracts for the published README visual validation path."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_turntable_uses_real_blanket_drape_motion():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert 'Part::Feature' in source
    assert 'Part::Box' not in source
    assert 'makeBox(180.0, 180.0, 60.0' in source
    assert 'BlanketSource' in source
    assert 'ClothPieces = [blanket]' in source
    assert 'blanket-motion-diagnostic' in source
    assert 'blanket-turntable-pass' in source
    assert 'if displacement < 40.0' in source
    assert 'minimum_z > cube_top + 35.0' in source
    assert "stage=scene-build-pass" in source
    assert "stage=simulation-start" in source
    assert "stage=simulation-pass" in source
    assert "stage=validation-pass" in source
    assert "stage=draped-render-pass" in source
    assert "BLANKET_PARTICLE_DISTANCE = 16.0" in source
    assert "scene.SolverSubsteps = 1" in source
    assert 'set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)' in source
    assert 'arranged_objects = [cube, panel]' in source
    assert 'visible_names = {obj.Name for obj in objects}' in source
    assert 'panel.ViewObject.DisplayMode = "Shaded"' in source
    assert 'start_angle = pi / 2.0' in source
    assert 'angle = start_angle + 2.0 * pi * frame / frame_total' in source


def test_readme_turntable_uses_exact_drape_target_mesh():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    simulation_objects = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    assert 'from freecad_cloth.simulation.DrapeTarget import create_drape_target, assign_drape_target' in simulation_objects
    assert 'target = create_drape_target(doc, source_obj, target_type, deflection, thickness)' in simulation_objects
    assert 'assign_drape_target(target, source_obj, target_type)' in simulation_objects
    assert 'scene.DrapeTarget = target' in simulation_objects
    assert 'create_drape_target(doc, cube, "FreeCAD Geometry"' not in source
    assert 'assign_drape_target(target, cube, "FreeCAD Geometry")' not in source


def test_blanket_motion_gif_has_usable_frame_delay_contract():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    build = workflow.split("      - name: Build blanket motion GIF", 1)[1].split(
        "      - name: Upload blanket visual evidence", 1
    )[0]
    assert build.index("-delay 10") < build.index("motion-*.png") < build.index("-colors 128")
    assert "identify -format '%T\\n' docs/images/generated/blanket-example/blanket-motion.gif" in build
    assert 'frame_delays="$(identify -format \'%T\\n\' docs/images/generated/blanket-example/blanket-motion.gif | sort -u)"' in build
    assert 'test "$frame_delays" = "10"' in build


def test_canonical_workflow_fails_closed_on_turntable_quality():
    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    turntables = source.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    assert "CLOTH_TISSU_SUBSTEPS: 10" in turntables
    assert "CLOTH_TISSU_COLLISION_MODE: mesh" in turntables
    assert "blanket-motion-diagnostic" in source
    assert "blanket-turntable-pass" in source
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "max_centroid_displacement_mm=([+-]?[0-9.]+)" in workflow
    assert 'test "$(find docs/images/generated/cloth-simulation-draped-turntable-frames' in source
    assert 'if len(set(checkpoints)) != 4: raise SystemExit("camera checkpoints not distinct for "+directory)' in source



def test_readme_turntable_uses_no_unsupported_patternpiece_display_mode():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert "blanket.ViewObject.DisplayMode" not in source


def test_blanket_visual_fixture_uses_authoritative_quality_solver_budget():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    assert 'os.environ.setdefault("CLOTH_SIMULATION_BACKEND", "xpbd-cpu")' in source
    assert 'scene.ParticleDistance = max(12.0, float(scene.ParticleDistance))' in source
    assert 'scene.SolverIterations = 4' in source
    assert 'scene.SolverSubsteps = 1' in source
    assert 'motion-frames=passed count=%d final_steps=%d' in source
