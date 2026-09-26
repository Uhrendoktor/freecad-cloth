"""Deterministic basic cloth example: a blanket draped over a cube."""

import os
import site
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if entry not in ("", str(ROOT))]

import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets


# A generic FreeCAD cube requires Tissu's mesh collision path; torso-envelope is for avatar-style targets.
os.environ.setdefault("CLOTH_TISSU_COLLISION_MODE", "mesh")
os.environ.setdefault("CLOTH_SIMULATION_BACKEND", "xpbd-cpu")

OUT = Path(os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")) / "blanket-example"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "blanket-visual.log"


def log(message):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def save_png(view, path, state):
    view.saveImage(str(path), 640, 480, "White")
    if not path.is_file():
        raise RuntimeError("failed screenshot: %s" % state)
    try:
        metrics = validate_png_capture(
            path,
            expected_width=640,
            expected_height=480,
        )
    except (OSError, ValueError) as exc:
        raise RuntimeError("failed screenshot: %s (%s)" % (state, exc)) from exc
    log(
        "screenshot=passed state=%s width=%d height=%d nonwhite_pixels=%d distinct_rgb=%d"
        % (
            state,
            metrics["width"],
            metrics["height"],
            metrics["nonwhite_pixels"],
            metrics["distinct_rgb"],
        )
    )


def make_rectangle_sketch(doc, name, width, height):
    import Part
    import Sketcher

    sketch = doc.addObject("Sketcher::SketchObject", name)
    points = ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    sketch.addGeometry([
        Part.LineSegment(
            App.Vector(points[index][0], points[index][1], 0),
            App.Vector(points[(index + 1) % 4][0], points[(index + 1) % 4][1], 0),
        )
        for index in range(4)
    ], False)
    sketch.addConstraint([Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1) for index in range(4)])
    doc.recompute()
    return sketch, points


def adopt_sketch(doc, sketch):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name="Blanket", allowance=0.0, grainline=0.0)
    if piece.Sketch is not sketch:
        raise RuntimeError("Blanket PatternPiece did not retain native Sketcher authority")
    doc.recompute()
    return piece


def mesh_snapshot(panel):
    vertices, triangles = panel.Mesh.Topology
    points = tuple((float(vertex.x), float(vertex.y), float(vertex.z)) for vertex in vertices)
    faces = tuple(tuple(int(index) for index in triangle) for triangle in triangles)
    return points, faces


def render_motion(view, scene, panel, target_vertices, cube_top_z, out_dir, checkpoint_steps=(15, 30, 60, 120), frame_count=16, start_step=1, final_steps=120):
    import time

    motion_steps = tuple(
        round(index * final_steps / float(frame_count - 1))
        for index in range(frame_count)
    )
    checkpoint_steps = tuple(int(step) for step in checkpoint_steps)
    checkpoint_names = {step: "checkpoint-%03d.png" % step for step in checkpoint_steps}
    motion_indices = {step: index for index, step in enumerate(motion_steps)}
    targets = tuple(sorted({int(start_step)}.union(
        step for step in motion_steps if step >= int(start_step)
    ).union(
        step for step in checkpoint_steps if step >= int(start_step)
    )))
    if targets[0] != int(start_step) or targets[-1] != final_steps:
        raise RuntimeError("blanket render schedule must span %d..%d" % (start_step, final_steps))

    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    events()

    phase_started = time.perf_counter()
    previous_step = int(scene.Steps)
    if previous_step != int(start_step):
        raise RuntimeError(
            "blanket render expected prewarmed step %d, got %d"
            % (start_step, previous_step)
        )
    solver_steps = 0
    recomputes = 0
    max_recompute_ms = 0.0
    best_drape = None
    best_drape_clearance = None
    best_drape_step = None
    for target_step in targets:
        target_step = int(target_step)
        if target_step < previous_step:
            raise RuntimeError(
                "blanket render schedule is not monotonic: %d after %d"
                % (target_step, previous_step)
            )
        delta_steps = target_step - previous_step
        scene.Steps = target_step
        recompute_started = time.perf_counter()
        scene.Document.recompute()
        recompute_ms = 1000.0 * (time.perf_counter() - recompute_started)
        recomputes += 1
        solver_steps += delta_steps
        max_recompute_ms = max(max_recompute_ms, recompute_ms)
        if not bool(scene.FiniteState):
            raise RuntimeError("blanket simulation became non-finite at step %d" % target_step)
        frame_vertices, _ = mesh_snapshot(panel)
        frame_drape = inspect_drape(
            frame_vertices,
            target_vertices,
            target_height=60.0,
            target_width=180.0,
        )
        frame_min_z = min(float(vertex[2]) for vertex in frame_vertices)
        frame_clearance = frame_min_z - float(cube_top_z)
        if frame_drape.state == "structurally-plausible" and frame_clearance <= 35.0:
            if best_drape is None:
                best_drape = frame_drape
                best_drape_clearance = frame_clearance
                best_drape_step = target_step
                log(
                    "blanket-drape-gate=passed step=%d clearance_mm=%.2f vertical_ratio=%.3f lateral_ratio=%.3f"
                    % (
                        target_step,
                        frame_clearance,
                        frame_drape.vertical_span_ratio,
                        frame_drape.lateral_span_ratio,
                    )
                )
        events()
        if target_step in motion_indices:
            save_png(
                view,
                out_dir / ("motion-%03d.png" % motion_indices[target_step]),
                "blanket motion step %d" % target_step,
            )
        if target_step in checkpoint_names:
            save_png(
                view,
                out_dir / checkpoint_names[target_step],
                "blanket step %d" % target_step,
            )
        log(
            "blanket-timing target_step=%d delta_steps=%d recompute_ms=%.1f cumulative_ms=%.1f"
            % (
                target_step,
                delta_steps,
                recompute_ms,
                1000.0 * (time.perf_counter() - phase_started),
            )
        )
        previous_step = target_step

    elapsed_ms = 1000.0 * (time.perf_counter() - phase_started)
    expected_solver_steps = final_steps - int(start_step)
    if solver_steps != expected_solver_steps:
        raise RuntimeError(
            "blanket simulation step budget mismatch: expected=%d actual=%d"
            % (expected_solver_steps, solver_steps)
        )
    if recomputes != len(targets):
        raise RuntimeError(
            "blanket simulation recompute count mismatch: expected=%d actual=%d"
            % (len(targets), recomputes)
        )
    log(
        "blanket-simulation-timing prewarm_steps=%d solver_steps=%d total_solver_steps=%d "
        "recomputes=%d elapsed_ms=%.1f max_recompute_ms=%.1f final_steps=%d"
        % (
            int(start_step),
            solver_steps,
            int(start_step) + solver_steps,
            recomputes,
            elapsed_ms,
            max_recompute_ms,
            final_steps,
        )
    )
    simulated_duration_s = float(final_steps) * float(scene.TimeStep)
    log(
        "blanket-physics-timing timestep_s=%.9f simulated_duration_s=%.3f steps=%d"
        % (float(scene.TimeStep), simulated_duration_s, int(final_steps))
    )
    log("motion-frames=passed count=%d final_steps=%d" % (len(motion_steps), final_steps))
    return best_drape, best_drape_clearance, best_drape_step


def _load_cloth_modules():
    global inspect_drape, mesh_shape_sanity
    global validate_mesh, rectangle, quality_piece_mesh
    global create_pattern_piece_from_selected_sketch
    global create_simulation_scene, set_avatar_collision_source
    global QualitySimulationProxy, ensure_quality_properties, validate_png_capture

    site.addsitedir(str(ROOT))

    from freecad_cloth.common.DrapeVisualSanity import inspect_drape, mesh_shape_sanity
    from freecad_cloth.common.MeshValidation import validate_mesh
    from freecad_cloth.pattern.PatternGeometry import rectangle
    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene, set_avatar_collision_source
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy, ensure_quality_properties
    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture


def main():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show()
    events()
    _load_cloth_modules()
    init_gui = ROOT / "InitGui.py"
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), globals(), globals())
    events()
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        raise RuntimeError("ClothPatternWorkbench was not registered by visual acceptance startup")
    doc = App.newDocument("ClothBlanketExample")
    try:
        blanket_width = 200.0
        blanket_height = 200.0
        sketch, outline = make_rectangle_sketch(doc, "BlanketSketch", blanket_width, blanket_height)
        piece = adopt_sketch(doc, sketch)
        placement = App.Placement(
            App.Vector(-blanket_width / 2.0, -blanket_height / 2.0, 90.0),
            App.Rotation(),
        )
        piece.Placement = placement
        piece.Sketch.Placement = placement

        cube = doc.addObject("Part::Feature", "BlanketTargetCube")
        cube.Label = "Collision Target — Cube"
        cube.Shape = __import__("Part").makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
        doc.recompute()

        import time
        setup_started = time.perf_counter()
        scene = create_simulation_scene(doc, build=False)
        ensure_quality_properties(scene)
        scene.Proxy = QualitySimulationProxy()
        scene.ClothPieces = [piece]
        scene.GravityX = 0.0
        scene.GravityY = 0.0
        scene.GravityZ = -9810.0
        scene.StartHeight = 0.0
        scene.TimeStep = 1.0 / 240.0
        # QualitySimulationProxy consumes SolverIterations; the legacy Iterations field is ignored for this runtime path.
        scene.ParticleDistance = max(12.0, float(scene.ParticleDistance))
        scene.SolverIterations = 4
        scene.SolverSubsteps = 1
        scene.FabricColor = (0.14, 0.32, 0.78)
        scene.FabricSpecular = 0.70
        scene.FabricRoughness = 0.20
        scene.FabricTransparency = 12

        mesh_positions, _, boundary = quality_piece_mesh(piece, 0.0, scene.ParticleDistance)
        boundary_vertices = tuple(sorted(set(index for chain in boundary for index in chain), key=lambda index: index))
        if not boundary_vertices:
            raise RuntimeError("blanket quality mesh has no boundary vertices")
        top_y = max(float(mesh_positions[index][1]) for index in boundary_vertices)
        top_edge = tuple(
            index for index in boundary_vertices
            if abs(float(mesh_positions[index][1]) - top_y) <= 1e-9
        )
        if len(top_edge) < 2:
            raise RuntimeError("blanket top edge has fewer than two boundary vertices")
        top = (
            min(top_edge, key=lambda index: float(mesh_positions[index][0])),
            max(top_edge, key=lambda index: float(mesh_positions[index][0])),
        )
        pin_span = abs(float(mesh_positions[top[1]][0]) - float(mesh_positions[top[0]][0]))
        if pin_span < 0.75 * blanket_width:
            raise RuntimeError("blanket pins are not opposite top-edge corners: span=%.3f" % pin_span)
        scene.PinSelection = [str(int(index)) for index in top]
        log("blanket-pins=passed opposite-corners span=%.3f indices=%s" % (pin_span, top))

        collision_started = time.perf_counter()
        set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)
        log(
            "blanket-setup-timing build_and_collision_ms=%.1f total_setup_ms=%.1f particles=%d"
            % (
                1000.0 * (time.perf_counter() - collision_started),
                1000.0 * (time.perf_counter() - setup_started),
                int(scene.ParticleCount),
            )
        )

        for source in (piece, sketch):
            source.ViewObject.Visibility = False
        cube.ViewObject.ShapeColor = (0.62, 0.62, 0.62)
        panels = list(scene.DrapePanels)
        if len(panels) != 1:
            raise RuntimeError("blanket scenario must create one drape panel")
        panel = panels[0]
        for obj in doc.Objects:
            if obj is not panel:
                if str(getattr(obj, "ClothMeshType", "")) in {"DrapedCloth", "DrapePanel"}:
                    obj.ViewObject.Visibility = False
                if str(getattr(obj, "AvatarType", "")) == "ClothAvatar" and obj is not cube:
                    obj.ViewObject.Visibility = False
        panel.ViewObject.ShapeColor = (0.72, 0.34, 0.46)
        panel.ViewObject.DisplayMode = "Flat Lines"
        panel.ViewObject.Visibility = True
        cube.ViewObject.Visibility = True
        doc.recompute()
        events()

        view = Gui.activeDocument().activeView()
        view.viewAxonometric()
        view.fitAll()
        events()
        save_png(view, OUT / "checkpoint-000.png", "blanket initial state")

        initial_points = tuple(tuple(float(value) for value in point) for point in scene.Proxy._base_or_restore().backend.positions())
        log("blanket-solver-config particle_distance=%.1f iterations=%d particles=%d backend=%s" % (
            float(scene.ParticleDistance), int(scene.SolverIterations), int(scene.ParticleCount),
            getattr(scene.Proxy._base_or_restore().backend, "name", "unknown"),
        ))
        log("blanket-backend-contract=passed requested=%s active=%s" % (
            os.environ.get("CLOTH_SIMULATION_BACKEND", "auto"),
            getattr(scene.Proxy._base_or_restore().backend, "name", "unknown"),
        ))

        avatar_points = tuple(
            (float(vertex.Point.x), float(vertex.Point.y), float(vertex.Point.z))
            for vertex in cube.Shape.Vertexes
        )
        cube_top_z = max(float(vertex.Point.z) for vertex in cube.Shape.Vertexes)

        first_step_started = time.perf_counter()
        scene.Steps = 1
        doc.recompute()
        first_step_ms = 1000.0 * (time.perf_counter() - first_step_started)
        if not bool(scene.FiniteState):
            raise RuntimeError("blanket simulation became non-finite at first step")
        prewarm_vertices, _ = mesh_snapshot(panel)
        prewarm_drape = inspect_drape(
            prewarm_vertices,
            avatar_points,
            target_height=60.0,
            target_width=180.0,
        )
        prewarm_min_z = min(float(vertex[2]) for vertex in prewarm_vertices)
        prewarm_clearance = prewarm_min_z - cube_top_z
        events()
        save_png(view, OUT / "motion-000.png", "blanket motion step 0")
        log("blanket-first-step-timing step=1 recompute_ms=%.1f finite=%s state_steps=%d" % (
            first_step_ms, bool(scene.FiniteState), int(scene.Steps)
        ))
        if prewarm_drape.state == "structurally-plausible" and prewarm_clearance <= 35.0:
            best_drape = prewarm_drape
            best_drape_clearance = prewarm_clearance
            best_drape_step = 1
            log(
                "blanket-drape-gate=passed step=1 clearance_mm=%.2f vertical_ratio=%.3f lateral_ratio=%.3f"
                % (
                    prewarm_clearance,
                    prewarm_drape.vertical_span_ratio,
                    prewarm_drape.lateral_span_ratio,
                )
            )
        else:
            best_drape = None
            best_drape_clearance = None
            best_drape_step = None

        progress_drape, progress_clearance, progress_step = render_motion(
            view,
            scene,
            panel,
            avatar_points,
            cube_top_z,
            OUT,
            frame_count=16,
            start_step=1,
            final_steps=120,
        )
        if best_drape is None:
            best_drape = progress_drape
            best_drape_clearance = progress_clearance
            best_drape_step = progress_step
        elif progress_drape is not None and progress_step is not None and progress_step < best_drape_step:
            best_drape = progress_drape
            best_drape_clearance = progress_clearance
            best_drape_step = progress_step

        final_points = tuple(tuple(float(value) for value in point) for point in scene.Proxy._base_or_restore().backend.positions())
        if not initial_points or not final_points:
            raise RuntimeError("blanket simulation produced no particles")
        max_displacement = max(
            sum((final_points[index][axis] - initial_points[index][axis]) ** 2 for axis in range(3)) ** 0.5
            for index in range(min(len(initial_points), len(final_points)))
        )
        if max_displacement <= 1.0:
            raise RuntimeError("blanket simulation did not materially move the cloth")

        vertices, triangles = mesh_snapshot(panel)
        mesh_result = validate_mesh(vertices, triangles, prefer_trimesh=False)
        shape = mesh_shape_sanity(vertices, triangles)
        final_drape = inspect_drape(vertices, avatar_points, target_height=60.0, target_width=180.0)
        final_min_z = min(float(vertex[2]) for vertex in vertices)
        final_clearance = final_min_z - cube_top_z
        log("drape-terminal state=%s clearance_mm=%.2f cube_top_z=%.2f cloth_min_z=%.2f" % (
            final_drape.state, final_clearance, cube_top_z, final_min_z,
        ))
        if best_drape is None:
            raise RuntimeError("blanket did not satisfy drape gate at any simulated frame")
        if best_drape.state != "structurally-plausible":
            raise RuntimeError("blanket drape gate produced unexpected state: %s" % best_drape.state)
        if best_drape_clearance > 35.0:
            raise RuntimeError(
                "blanket drape gate exceeded clearance threshold: step=%d clearance=%.2f"
                % (best_drape_step, best_drape_clearance)
            )
        if not mesh_result.finite or mesh_result.components != 1 or mesh_result.degenerate_faces:
            raise RuntimeError("blanket mesh failed structural validation: %r" % mesh_result)
        if not shape["finite"] or shape["edge_spike_ratio"] > 4.0 or shape["spike_edge_fraction"] > 0.02:
            raise RuntimeError("blanket mesh has spike outliers: %r" % shape)
        if shape["footprint_aspect_ratio"] > 4.0:
            raise RuntimeError("blanket footprint became excessively elongated: %r" % shape)
        if not bool(scene.FiniteState):
            raise RuntimeError("blanket final simulation state is non-finite")
        log("mesh=passed vertices=%d faces=%d components=%d spikes=%.3f aspect=%.3f" % (
            mesh_result.vertices, mesh_result.faces, mesh_result.components,
            shape["edge_spike_ratio"], shape["footprint_aspect_ratio"],
        ))
        log("drape=passed state=%s best_step=%d clearance_mm=%.2f vertical_ratio=%.3f lateral_ratio=%.3f" % (
            best_drape.state, best_drape_step, best_drape_clearance,
            best_drape.vertical_span_ratio, best_drape.lateral_span_ratio,
        ))
        log("movement=passed max_displacement_mm=%.3f" % max_displacement)
        applied_color = tuple(float(value) for value in panel.ViewObject.ShapeColor[:3])
        expected_color = (0.14, 0.32, 0.78)
        if any(abs(applied_color[index] - expected_color[index]) > 0.02 for index in range(3)):
            raise RuntimeError("simulation viewport did not apply persisted fabric color")
        if int(panel.ViewObject.Transparency) != 12:
            raise RuntimeError("simulation viewport did not apply persisted fabric transparency")
        log("material-presentation=passed viewport=true color=0.14,0.32,0.78 transparency=12")

        log("blanket-visual-acceptance=passed")
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        events()
        window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()


try:
    main()
except BaseException as error:
    print("BLANKET VISUAL FAILURE: %r" % (error,), flush=True)
    print(traceback.format_exc(), flush=True)
    log("blanket-visual-fail exception=%r" % (error,))
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
    except BaseException:
        pass
    os._exit(1)
