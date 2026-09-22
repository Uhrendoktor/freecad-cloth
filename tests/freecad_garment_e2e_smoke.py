"""Canonical public FreeCAD Pattern -> Sewing -> Fitting -> Simulation -> Export acceptance."""
import hashlib
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def _close_task():
    active = Gui.Control.activeDialog()
    if active is not None:
        Gui.Control.closeDialog()
        _events()


def _wait_task_close():
    for _ in range(40):
        _events()
        active = Gui.Control.activeDialog()
        if active is None or not bool(active):
            return
    print(
        "TASK_CLOSE_DIAGNOSTIC activeDialog=%r type=%s bool=%s"
        % (active, type(active).__name__, bool(active)),
        flush=True,
    )
    raise RuntimeError("task dialog did not close after the requested public action")


def _activate(name, commands):
    Gui.activateWorkbench(name)
    _events()
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))


def _dialog_text(dialog):
    form = getattr(dialog, "form", dialog)
    widgets = [form]
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    if hasattr(form, "findChildren"):
        widgets.extend(form.findChildren(QtWidgets.QWidget))
    return " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )


def _require_dialog(required, label, panel=None):
    dialog = Gui.Control.activeDialog()
    if dialog is None:
        raise RuntimeError("%s did not open an active public task dialog" % label)

    target = panel if panel is not None else dialog
    visible_text = _dialog_text(target)
    if all(item in visible_text for item in required):
        return target

    # FreeCAD's Control.activeDialog() may return a native task wrapper while
    # the actual Python panel is hosted in the Tasks dock. Validate the visible
    # user-facing UI through that dock rather than depending on private wrapper
    # attributes.
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    main_window = Gui.getMainWindow()
    dock = None if main_window is None else main_window.findChild(QtWidgets.QDockWidget, "Tasks")
    if dock is not None:
        dock.show()
        dock.raise_()
        _events()
        dock_text = _dialog_text(dock)
        if all(item in dock_text for item in required):
            return target

    missing = [item for item in required if item not in (dock_text if dock is not None else visible_text)]
    raise RuntimeError("%s task panel missing visible text: %s" % (label, ",".join(missing)))


def _find_pattern_pieces(doc):
    return [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]


def _make_curved(piece, doc):
    sketch = piece.Sketch
    piece_id = str(piece.PieceId)
    geometry = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 50, 0)),
        Part.ArcOfCircle(Part.Circle(App.Vector(50, 50, 0), App.Vector(0, 0, 1), 50), 0, math.pi),
        Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
    ]
    sketch.Constraints = []
    sketch.Geometry = geometry
    sketch.SemanticEdgeIds = [f"{piece_id}:edge:{index}" for index in range(4)]
    sketch.GeometryAuthority = "Sketcher"
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", 0, 2, 1, 1),
        Sketcher.Constraint("Coincident", 1, 2, 2, 1),
        Sketcher.Constraint("Coincident", 2, 2, 3, 1),
        Sketcher.Constraint("Coincident", 3, 2, 0, 1),
        Sketcher.Constraint("Horizontal", 0),
        Sketcher.Constraint("Vertical", 3),
    ])
    doc.recompute()
    if sketch.Shape.isNull() or piece.Shape.isNull():
        raise RuntimeError("curved pattern did not produce native geometry")
    return sketch



def _make_nonuniform_curved(piece, doc):
    """Give one M:N member a deliberately different, still correspondable arc."""
    sketch = piece.Sketch
    piece_id = str(piece.PieceId)
    radius = 50.02
    offset = math.sqrt(radius * radius - 50.0 * 50.0)
    start_angle = math.atan2(offset, 50.0)
    end_angle = math.pi - start_angle
    geometry = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 50, 0)),
        Part.ArcOfCircle(
            Part.Circle(App.Vector(50, 50 - offset, 0), App.Vector(0, 0, 1), radius),
            start_angle,
            end_angle,
        ),
        Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
    ]
    sketch.Constraints = []
    sketch.Geometry = geometry
    sketch.SemanticEdgeIds = [f"{piece_id}:edge:{index}" for index in range(4)]
    sketch.GeometryAuthority = "Sketcher"
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", 0, 2, 1, 1),
        Sketcher.Constraint("Coincident", 1, 2, 2, 1),
        Sketcher.Constraint("Coincident", 2, 2, 3, 1),
        Sketcher.Constraint("Coincident", 3, 2, 0, 1),
        Sketcher.Constraint("Horizontal", 0),
        Sketcher.Constraint("Vertical", 3),
    ])
    doc.recompute()
    if sketch.Shape.isNull() or piece.Shape.isNull():
        raise RuntimeError("non-uniform curved M:N counterpart did not produce native geometry")
    return sketch

def _position_signature(scene):
    proxy = getattr(scene, "Proxy", None)
    backend = getattr(proxy, "backend", None)
    getter = getattr(backend, "positions", None)
    if not callable(getter):
        raise RuntimeError("simulation backend did not expose positions for determinism evidence")
    positions = tuple(getter())
    if not positions:
        raise RuntimeError("simulation produced no particle positions for determinism evidence")
    signature = []
    for position in positions:
        if len(position) != 3:
            raise RuntimeError("simulation produced a non-3D particle position")
        signature.append(
            (
                round(float(position[0]), 9),
                round(float(position[1]), 9),
                round(float(position[2]), 9),
            )
        )
    return tuple(signature)


def _position_signature_digest(signature):
    return hashlib.sha256(repr(signature).encode("utf-8")).hexdigest()


def _select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    _events()


def _select_objects(*items):
    Gui.Selection.clearSelection()
    for obj in items:
        Gui.Selection.addSelection(obj)
    _events()


def _open_staged(command):
    _close_task()
    Gui.runCommand(command, 0)
    _events()
    from freecad_cloth.sewing.SewingCommands import get_active_staged_sewing_task_panel
    panel = get_active_staged_sewing_task_panel()
    if panel is None:
        raise RuntimeError(command + " did not expose its public staged sewing task panel")
    _require_dialog(
        ("Preview", "Commit", "Cancel", "Selected semantic pattern edges"),
        command,
        panel=panel,
    )
    return panel


def _commit_staged(panel):
    button = getattr(panel, "commit_button", None)
    if button is None:
        raise RuntimeError("staged sewing panel did not expose its public Commit control")
    button.click()
    _wait_task_close()


def _cancel_staged(panel):
    button = getattr(panel, "cancel_button", None)
    if button is None:
        raise RuntimeError("staged sewing panel did not expose its public Cancel control")
    button.click()
    _wait_task_close()


def _open_quality_panel():
    _close_task()
    Gui.runCommand("ClothSimulation_Edit", 0)
    _events()
    from freecad_cloth.simulation.SimulationCommands import get_active_simulation_quality_task_panel
    panel = get_active_simulation_quality_task_panel()
    if panel is None:
        raise RuntimeError("ClothSimulation_Edit did not expose its public simulation task panel")
    _require_dialog(
        ("Preset", "Particle distance", "Density", "Avatar skin offset", "Simulation steps", "Step", "Run 30", "Reset"),
        "ClothSimulation_Edit",
        panel=panel,
    )
    return panel


def _open_diagnostics_panel():
    _close_task()
    Gui.runCommand("ClothDrape_Diagnostics", 0)
    _events()
    from freecad_cloth.simulation.DrapeCommands import get_active_diagnostics_task_panel
    panel = get_active_diagnostics_task_panel()
    if panel is None:
        raise RuntimeError("ClothDrape_Diagnostics did not expose its public diagnostics task panel")
    _require_dialog(
        ("Refresh analysis", "Create diagnostic map", "Export analysis data"),
        "ClothDrape_Diagnostics",
        panel=panel,
    )
    return panel


def _export_pair(piece, output_dir, export_format):
    from freecad_cloth.pattern.PatternExport import from_dxf_metadata, from_svg_metadata
    path_a = output_dir / ("canonical." + export_format.lower())
    path_b = output_dir / ("canonical-second." + export_format.lower())
    reader = from_svg_metadata if export_format == "SVG" else from_dxf_metadata

    _select_objects(piece)
    _close_task()
    Gui.runCommand("ClothPattern_Export", 0)
    _events()
    from freecad_cloth.pattern.PatternCommands import get_active_pattern_export_task_panel
    panel = get_active_pattern_export_task_panel()
    if panel is None:
        raise RuntimeError("ClothPattern_Export did not expose its public pattern-export task panel")
    _require_dialog(("Production Export", "read-only"), "ClothPattern_Export", panel=panel)
    panel.format.setCurrentText(export_format)
    panel.path.setText(str(path_a))
    if not panel.accept():
        raise RuntimeError("public export task panel rejected %s" % export_format)
    _events()

    first = path_a.read_bytes()
    if not first:
        raise RuntimeError("%s export is empty" % export_format)

    _close_task()
    Gui.runCommand("ClothPattern_Export", 0)
    _events()
    panel = get_active_pattern_export_task_panel()
    if panel is None:
        raise RuntimeError("second ClothPattern_Export did not expose its public pattern-export task panel")
    _require_dialog(("Production Export", "read-only"), "ClothPattern_Export", panel=panel)
    panel.format.setCurrentText(export_format)
    panel.path.setText(str(path_b))
    if not panel.accept():
        raise RuntimeError("second public export rejected %s" % export_format)
    _events()

    second = path_b.read_bytes()
    if first != second:
        raise RuntimeError("%s export is not byte-deterministic" % export_format)

    metadata = reader(first.decode("utf-8"))
    if metadata.get("piece_id") != str(piece.PieceId):
        raise RuntimeError("%s export lost piece identity" % export_format)
    if metadata.get("units") != "mm" or metadata.get("scale") != 1.0:
        raise RuntimeError("%s export lost units/scale" % export_format)
    if not metadata.get("edge_ids"):
        raise RuntimeError("%s export lost semantic edge IDs" % export_format)
    return len(first), metadata


def run_acceptance():
    doc = None
    path = None
    try:
        _activate(
            "ClothPatternWorkbench",
            [
                "ClothPattern_CreateGarment",
                "ClothPattern_CreatePieceWithSketch",
                "ClothPattern_EditPiece",
                "ClothPattern_Show2D",
            ],
        )
        Gui.runCommand("ClothPattern_CreateGarment", 0)
        _events()
        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("public Garment creation command did not create an active FreeCAD document")
        from freecad_cloth.common.GarmentDocument import garment_structure
        initial_structure = garment_structure(doc)
        if set(initial_structure["groups"]) != {"Patterns", "Sewing", "Fabric", "Avatar", "Simulation"}:
            raise RuntimeError("public Garment creation command did not create the complete native hierarchy")
        fabric_members = initial_structure["groups"]["Fabric"]
        if not any(item["role"] == "FabricMaterial" for item in fabric_members):
            raise RuntimeError("public Garment creation command did not create the native FabricMaterial member")
        for _ in range(4):
            Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
            _events()
        pieces = _find_pattern_pieces(doc)
        if len(pieces) != 4:
            raise RuntimeError("public Pattern command did not create four PatternPiece objects")
        front, back, sleeve_a, sleeve_b = pieces
        for index, piece in enumerate(pieces):
            piece.Placement.Base.x = float(index * 170)
            if piece is sleeve_b:
                _make_nonuniform_curved(piece, doc)
            else:
                _make_curved(piece, doc)
        doc.recompute()

        before_ids = [tuple(getattr(piece.Sketch, "SemanticEdgeIds", ())) for piece in pieces]
        if any(len(ids) != 4 for ids in before_ids):
            raise RuntimeError("native Sketcher semantic edge IDs were not created for all pattern pieces")

        _select_objects(front)
        Gui.runCommand("ClothPattern_EditPiece", 0)
        _events()
        _require_dialog(("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"), "ClothPattern_EditPiece")
        _close_task()

        _activate(
            "ClothSewingWorkbench",
            [
                "ClothSewing_CreateSeam",
                "ClothSewing_CreateMNSewing",
                "ClothSewing_CreateOperation",
                "ClothSewing_EditOperation",
                "ClothSewing_ReverseSeam",
                "ClothSewing_ToggleAlignment",
                "ClothSewing_Validate",
                "ClothFitting_CreateScene",
                "ClothFitting_SetMeasurements",
                "ClothFitting_AddPieces",
                "ClothFitting_CreateArrangementPoint",
                "ClothFitting_ApplyArrangementPoint",
                "ClothFitting_CreateSimulation",
            ],
        )

        before = {obj.Name for obj in doc.Objects}
        _select_edges((front, 0))
        panel = _open_staged("ClothSewing_CreateSeam")
        if "Preview rejected" not in str(panel.feedback.text()) or "exactly two edges" not in str(panel.feedback.text()):
            raise RuntimeError("public staged sewing task panel did not reject invalid edge count")
        if {obj.Name for obj in doc.Objects} != before:
            raise RuntimeError("invalid staged sewing preview persisted document objects")
        _cancel_staged(panel)
        print("staged-selection=passed", flush=True)

        _select_edges((front, 2), (back, 2))
        panel = _open_staged("ClothSewing_CreateSeam")
        created_11 = tuple(panel.session.created)
        seam_11 = next((obj for obj in created_11 if getattr(obj, "SeamId", "")), None)
        if seam_11 is None or str(seam_11.Status) != "Valid":
            raise RuntimeError("public staged Sewing command did not create a valid curved 1:1 seam")
        print("sewing-1to1-preview=passed type=curved", flush=True)
        _commit_staged(panel)
        doc.recompute()
        seam_11 = next(obj for obj in doc.Objects if getattr(obj, "SeamId", "") == str(seam_11.SeamId))
        if seam_11 is None or str(seam_11.Status) != "Valid":
            raise RuntimeError("curved 1:1 sewing commit did not persist a valid seam")
        _select_objects(seam_11)
        Gui.runCommand("ClothSewing_ReverseSeam", 0)
        Gui.runCommand("ClothSewing_ToggleAlignment", 0)
        doc.recompute()
        if not bool(seam_11.ReversedB) or str(seam_11.Alignment) != "uniform":
            raise RuntimeError("public sewing direction/correspondence controls did not update seam metadata")
        Gui.runCommand("ClothSewing_ToggleAlignment", 0)
        Gui.runCommand("ClothSewing_ReverseSeam", 0)
        doc.recompute()
        if bool(seam_11.ReversedB) or str(seam_11.Alignment) != "endpoints":
            raise RuntimeError("public sewing controls did not restore canonical seam metadata")
        print("sewing-1to1=passed type=curved", flush=True)

        _select_edges((sleeve_a, 2), (sleeve_a, 3), (sleeve_b, 2), (sleeve_b, 3))
        panel = _open_staged("ClothSewing_CreateMNSewing")
        created_mn = tuple(panel.session.created)
        network = next((obj for obj in created_mn if getattr(obj, "SewingType", "") == "SewingNetwork"), None)
        if network is None or str(network.Status) != "Valid" or len(network.Seams) != 2:
            raise RuntimeError("public staged M:N preview did not create a valid two-segment network")
        print("sewing-mn-preview=passed sides=2,2 segments=2", flush=True)
        _commit_staged(panel)
        doc.recompute()
        networks = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"]
        if len(networks) != 1:
            raise RuntimeError("expected exactly one committed M:N sewing network")
        network = networks[0]
        if str(network.Status) != "Valid" or len(network.Seams) != 2 or int(network.SideACount) != 2 or int(network.SideBCount) != 2:
            raise RuntimeError("M:N sewing network did not persist valid 2:2 topology")
        if any(str(getattr(seam, "Status", "")) != "Valid" for seam in network.Seams):
            raise RuntimeError("M:N network retained an invalid member seam")
        print("sewing-mn=passed sides=2,2 segments=2", flush=True)

        from freecad_cloth.sewing.SewingObjects import _edge_length, _edge_polyline, _edge_samples, _resolved_edge
        from freecad_cloth.sewing.SewingView import build_seam_visual_shape, seam_visual_markers

        curved_points = _edge_polyline(sleeve_a, 2)
        curved_length = _edge_length(sleeve_a, 2)
        curved_chord = math.hypot(
            curved_points[-1][0] - curved_points[0][0],
            curved_points[-1][1] - curved_points[0][1],
        )
        if curved_length <= curved_chord * 1.10:
            raise RuntimeError("M:N canonical side A edge 2 did not retain deliberate curved arc length")

        variant_points = _edge_polyline(sleeve_b, 2)
        variant_length = _edge_length(sleeve_b, 2)
        variant_chord = math.hypot(
            variant_points[-1][0] - variant_points[0][0],
            variant_points[-1][1] - variant_points[0][1],
        )
        if variant_length <= variant_chord * 1.05:
            raise RuntimeError("M:N canonical side B edge 2 did not retain deliberate non-uniform curved arc length")
        variant_samples = _edge_samples(sleeve_b, 2, 0.0, 1.0, 5)
        variant_dx = [
            round(abs(variant_samples[index + 1].x - variant_samples[index].x), 6)
            for index in range(len(variant_samples) - 1)
        ]
        if len(set(variant_dx)) < 2:
            raise RuntimeError("M:N side B edge 2 did not retain non-uniform physical arc-length samples")

        arc_samples = _edge_samples(sleeve_a, 2, 0.0, 1.0, 5)
        sample_dx = [
            round(abs(arc_samples[index + 1].x - arc_samples[index].x), 6)
            for index in range(len(arc_samples) - 1)
        ]
        if len(set(sample_dx)) < 2:
            raise RuntimeError("curved M:N edge did not exercise non-uniform physical arc-length samples")

        mn_members = tuple(network.Seams)
        if len(mn_members) != 2:
            raise RuntimeError("M:N network member count changed before correspondence metadata checks")
        for member, (start, end) in zip(mn_members, ((0.0, 0.65), (0.65, 1.0))):
            member.StartA = start
            member.EndA = end
            member.StartB = start
            member.EndB = end
            member.Alignment = "uniform"
        _select_objects(mn_members[0])
        Gui.runCommand("ClothSewing_ReverseSeam", 0)
        doc.recompute()

        expected_mn_metadata = tuple(sorted(
            (
                str(member.SeamId),
                str(member.PieceA),
                int(member.EdgeA),
                float(member.StartA),
                float(member.EndA),
                str(member.PieceB),
                int(member.EdgeB),
                float(member.StartB),
                float(member.EndB),
                bool(member.ReversedB),
                str(member.Alignment),
                str(member.StitchGroup),
            )
            for member in mn_members
        ))
        if expected_mn_metadata[0][9] is not True or expected_mn_metadata[1][9] is not False:
            raise RuntimeError("M:N direction/reversal metadata did not persist the deliberate member orientation")
        if any(item[10] != "uniform" for item in expected_mn_metadata):
            raise RuntimeError("M:N member seams did not retain uniform arc-length correspondence alignment")
        if any(item[4] <= item[3] or item[7] <= item[6] for item in expected_mn_metadata):
            raise RuntimeError("M:N member seam correspondence ranges are not positive")
        if abs(float(mn_members[0].EndA) - 0.65) > 1e-9 or abs(float(mn_members[1].StartA) - 0.65) > 1e-9:
            raise RuntimeError("M:N member seam ranges did not retain the deliberate non-uniform 65/35 split")

        Gui.runCommand("ClothSewing_Show2D", 0)
        _events()
        public_marker_checks = []
        for member in mn_members:
            a = _edge_samples(
                sleeve_a,
                _resolved_edge(sleeve_a, member, "A"),
                float(member.StartA),
                float(member.EndA),
                5,
            )
            b = _edge_samples(
                sleeve_b,
                _resolved_edge(sleeve_b, member, "B"),
                float(member.StartB),
                float(member.EndB),
                5,
            )
            if bool(member.ReversedB):
                b.reverse()
            a_tuples = tuple((float(point.x), float(point.y), float(point.z)) for point in a)
            b_tuples = tuple((float(point.x), float(point.y), float(point.z)) for point in b)
            marker_data = seam_visual_markers(a_tuples, b_tuples)
            expected_shape = build_seam_visual_shape(sleeve_a, sleeve_b, member, sample_count=5)
            if member.Shape.isNull() or len(member.Shape.Edges) != len(expected_shape.Edges):
                raise RuntimeError("public sewing 2D path did not expose deterministic seam marker geometry")
            if len(member.Shape.Edges) < 15:
                raise RuntimeError("public sewing 2D path exposed too little geometry for direction/notch/correspondence markers")
            vertices = {
                (round(vertex.Point.x, 6), round(vertex.Point.y, 6), round(vertex.Point.z, 6))
                for vertex in member.Shape.Vertexes
            }
            notch_anchor_a = tuple(round(value, 6) for value in marker_data["notch_A"][0])
            notch_anchor_b = tuple(round(value, 6) for value in marker_data["notch_B"][0])
            if notch_anchor_a not in vertices or notch_anchor_b not in vertices:
                raise RuntimeError("public sewing 2D path omitted deterministic notch marker anchors")
            if len(marker_data["correspondence"]) != 5:
                raise RuntimeError("public sewing 2D path omitted deterministic correspondence samples")
            public_marker_checks.append(
                "%s:reversed=%s:edges=%d" % (member.SeamId, bool(member.ReversedB), len(member.Shape.Edges))
            )
        print(
            "sewing-mn-curved=passed curved_side=A,B edge=2 arc_length_A=%.6f arc_length_B=%.6f chord_A=%.6f chord_B=%.6f non_uniform_samples=%s"
            % (curved_length, variant_length, curved_chord, variant_chord, sample_dx + ["B:" + str(variant_dx)]),
            flush=True,
        )
        print(
            "sewing-mn-metadata=passed split=65/35 alignment=uniform reversed_first=true members=%d"
            % len(mn_members),
            flush=True,
        )
        print(
            "sewing-mn-markers=passed public_view=ClothSewing_Show2D checks=%s"
            % ",".join(public_marker_checks),
            flush=True,
        )

        _select_objects(seam_11)
        Gui.runCommand("ClothSewing_CreateOperation", 0)
        _events()
        operations = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingOperation"]
        if len(operations) != 1 or str(operations[0].Status) != "Valid":
            raise RuntimeError("public Sewing operation command did not create a valid operation")
        operation = operations[0]
        _select_objects(operation)
        Gui.runCommand("ClothSewing_EditOperation", 0)
        _events()
        from freecad_cloth.sewing.SewingCommands import get_active_sewing_operation_task_panel
        operation_panel = get_active_sewing_operation_task_panel()
        if operation_panel is None:
            raise RuntimeError("ClothSewing_EditOperation did not expose its public operation task panel")
        _require_dialog(
            ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"),
            "ClothSewing_EditOperation",
            panel=operation_panel,
        )
        operation_panel.stitches.setValue(12)
        operation_panel.alignment.setCurrentText("uniform")
        if not operation_panel.accept():
            raise RuntimeError("public Sewing operation task panel rejected the updated controls")
        _close_task()
        _wait_task_close()
        doc.recompute()
        if int(operation.StitchCount) != 12 or str(operation.Alignment) != "uniform":
            raise RuntimeError("public Sewing operation task panel did not persist controls")
        print("sewing-operation=passed", flush=True)

        _select_objects(front, back, sleeve_a, sleeve_b)
        Gui.runCommand("ClothFitting_CreateScene", 0)
        Gui.runCommand("ClothFitting_SetMeasurements", 0)
        _events()
        fitting = doc.getObject("FittingScene")
        if fitting is None:
            raise RuntimeError("public Fitting command did not create a FittingScene")
        Gui.runCommand("ClothFitting_AddPieces", 0)
        Gui.runCommand("ClothFitting_CreateArrangementPoint", 0)
        _events()
        point = next((obj for obj in doc.Objects if getattr(obj, "FittingType", "") == "ArrangementPoint"), None)
        if point is None:
            raise RuntimeError("public Fitting command did not create an arrangement point")
        _select_objects(front, point)
        Gui.runCommand("ClothFitting_ApplyArrangementPoint", 0)
        _events()
        doc.recompute()
        if len(fitting.PatternPieces) != 4 or str(fitting.FitStatus) not in {"Pieces assigned", "Ready"}:
            raise RuntimeError("public fitting scene did not persist all four pattern pieces")
        print("arrangement=passed pieces=4", flush=True)

        structure = garment_structure(doc)
        expected_members = {
            "Patterns": {piece.Name for piece in pieces},
            "Sewing": {seam_11.Name, network.Name, operation.Name},
        }
        for role, names in expected_members.items():
            actual = {item["name"] for item in structure["groups"].get(role, ())}
            if not names.issubset(actual):
                raise RuntimeError("native garment hierarchy missing %s members: %s" % (role, sorted(names - actual)))
        if not any(item["role"] == "FabricMaterial" for item in structure["groups"]["Fabric"]):
            raise RuntimeError("native garment hierarchy lost FabricMaterial")
        print("garment-hierarchy=passed groups=Patterns,Sewing,Fabric,Avatar,Simulation", flush=True)

        target_body = doc.addObject("Part::Feature", "AcceptanceTarget")
        target_body.Label = "Acceptance Target"
        target_body.Shape = Part.makeCylinder(35, 100, App.Vector(0, 0, -50))
        doc.recompute()

        _activate(
            "ClothSimulationWorkbench",
            ["ClothDrape_CreateTarget", "ClothDrape_RefreshTarget", "ClothSimulation_Step", "ClothSimulation_Reset", "ClothSimulation_Edit"],
        )
        _select_objects(target_body)
        Gui.runCommand("ClothDrape_CreateTarget", 0)
        _events()
        target = doc.getObject("DrapeTarget")
        if target is None or target.SourceObject != target_body:
            raise RuntimeError("public DrapeTarget command did not persist CAD target")
        print("drape-target=passed", flush=True)

        _select_objects(fitting)
        Gui.runCommand("ClothFitting_CreateSimulation", 0)
        _events()
        scene = doc.getObject("ClothSimulation")
        if scene is None:
            raise RuntimeError("public Fitting simulation command did not create ClothSimulation")
        doc.recompute()
        if len(scene.ClothPieces) != 4:
            raise RuntimeError("fitting-created simulation did not inherit four pattern pieces")
        # The target existed before this simulation was created; bind the same
        # persistent CAD target to the newly created public simulation object.
        _select_objects(target_body)
        Gui.runCommand("ClothDrape_CreateTarget", 0)
        _events()
        target = doc.getObject("DrapeTarget")
        if target is None or scene.DrapeTarget != target or target.SourceObject != target_body:
            raise RuntimeError("public DrapeTarget command did not attach the persistent CAD target to simulation")

        _select_objects(scene)
        quality_panel = _open_quality_panel()
        quality_panel.quality.setCurrentText("Fast")
        if not quality_panel.accept():
            raise RuntimeError("public Simulation quality task panel rejected the selected preset")
        _close_task()
        _wait_task_close()
        scene.Steps = 1
        doc.recompute()
        if not int(scene.ParticleCount) > 0 or not bool(scene.FiniteState):
            raise RuntimeError("public Simulation command did not produce a finite one-step state")

        _select_objects(scene)
        diagnostics_panel = _open_diagnostics_panel()
        diagnostics_panel.metric.setCurrentText("stress")
        diagnostics_panel.refresh_button.click()
        _events()
        if "Stress" not in str(diagnostics_panel.status.text()):
            raise RuntimeError("public diagnostics task panel did not produce stress analysis")
        diagnostics_panel.map_button.click()
        _events()
        if "Created" not in str(diagnostics_panel.status.text()):
            raise RuntimeError("public diagnostics task panel did not create a diagnostic map")
        _close_task()
        print("diagnostics=passed metric=stress", flush=True)

        with tempfile.TemporaryDirectory() as directory:
            output_dir = __import__("pathlib").Path(directory)
            path = os.path.join(directory, "canonical-garment.FCStd")
            doc.recompute()
            doc.saveAs(path)
            seam_11_name = seam_11.Name
            network_name = network.Name
            operation_name = operation.Name
            fitting_name = fitting.Name
            scene_name = scene.Name
            target_name = target.Name
            piece_names = [piece.Name for piece in pieces]
            expected_piece_ids = [str(piece.PieceId) for piece in pieces]
            target_body_name = target_body.Name
            App.closeDocument(doc.Name)
            doc = None
            reloaded = App.openDocument(path)
            reloaded.recompute()

            reloaded_pieces = [reloaded.getObject(name) for name in piece_names]
            if any(piece is None for piece in reloaded_pieces):
                raise RuntimeError("garment fixture did not preserve all four PatternPiece objects")
            if [str(piece.PieceId) for piece in reloaded_pieces] != expected_piece_ids:
                raise RuntimeError("save/reload changed persistent PatternPiece identity")
            seam_11 = reloaded.getObject(seam_11_name)
            network = reloaded.getObject(network_name)
            operation = reloaded.getObject(operation_name)
            fitting = reloaded.getObject(fitting_name)
            network_members_after_reload = tuple(network.Seams)
            reloaded_mn_metadata = tuple(sorted(
                (
                    str(member.SeamId),
                    str(member.PieceA),
                    int(member.EdgeA),
                    float(member.StartA),
                    float(member.EndA),
                    str(member.PieceB),
                    int(member.EdgeB),
                    float(member.StartB),
                    float(member.EndB),
                    bool(member.ReversedB),
                    str(member.Alignment),
                    str(member.StitchGroup),
                )
                for member in network_members_after_reload
            ))
            if reloaded_mn_metadata != expected_mn_metadata:
                raise RuntimeError("save/reload changed persisted M:N direction/reversal/correspondence metadata")
            print(
                "save-reload-mn-metadata=passed members=%d curved_edge=pattern-piece-3:edge:2"
                % len(network_members_after_reload),
                flush=True,
            )
            scene = reloaded.getObject(scene_name)
            target = reloaded.getObject(target_name)
            reloaded_structure = garment_structure(reloaded)
            if set(reloaded_structure["groups"]) != {"Patterns", "Sewing", "Fabric", "Avatar", "Simulation"}:
                raise RuntimeError("save/reload lost native garment hierarchy groups")
            hierarchy_names = {
                role: {item["name"] for item in reloaded_structure["groups"].get(role, ())}
                for role in reloaded_structure["groups"]
            }
            for role, names in expected_members.items():
                if not names.issubset(hierarchy_names[role]):
                    raise RuntimeError("save/reload lost garment hierarchy membership for %s" % role)
            if not any(item["role"] == "FabricMaterial" for item in reloaded_structure["groups"]["Fabric"]):
                raise RuntimeError("save/reload lost FabricMaterial")
            if any(obj is None for obj in (seam_11, network, operation, fitting, scene, target)):
                raise RuntimeError("garment fixture did not preserve sewing/fitting/simulation objects")
            if str(seam_11.Status) != "Valid" or str(network.Status) != "Valid" or str(operation.Status) != "Valid":
                raise RuntimeError("save/reload changed sewing validity")
            if len(network.Seams) != 2 or len(fitting.PatternPieces) != 4 or len(scene.ClothPieces) != 4:
                raise RuntimeError("save/reload changed sewing/fitting/simulation membership")
            if target.SourceObject is None or target.SourceObject.Name != target_body_name:
                raise RuntimeError("save/reload lost persistent DrapeTarget source")
            semantic_ids_after_reload = tuple(getattr(reloaded_pieces[0].Sketch, "SemanticEdgeIds", ()))
            if semantic_ids_after_reload != before_ids[0]:
                raise RuntimeError("save/reload changed native Sketcher semantic edge IDs")
            print("save-reload=passed pieces=4 seam=1to1 network=2segment", flush=True)

            curved = reloaded_pieces[0]
            seam_11 = reloaded.getObject(seam_11_name)
            semantic_ids = tuple(curved.Sketch.SemanticEdgeIds)
            dimensional = curved.Sketch.addConstraint(Sketcher.Constraint("Radius", 2, 50.0))
            curved.Sketch.renameConstraint(dimensional, "UpstreamSeamRadius")
            curved.Sketch.setDatum(dimensional, App.Units.Quantity("60 mm"))
            reloaded.recompute()
            if tuple(curved.Sketch.SemanticEdgeIds) != semantic_ids:
                raise RuntimeError("native Sketcher edit changed semantic edge IDs")
            if str(seam_11.Status) not in {"Changed reference", "Missing reference"}:
                raise RuntimeError("native Sketcher edit did not invalidate downstream curved seam: %s" % seam_11.Status)
            print("invalidation=passed seam=%s" % seam_11.Status, flush=True)

            curved.Sketch.setDatum(dimensional, App.Units.Quantity("50 mm"))
            reloaded.recompute()
            if str(seam_11.Status) not in {"Changed reference", "Missing reference"}:
                raise RuntimeError("restoring native Sketch geometry unexpectedly retargeted the curved seam")
            _select_objects(seam_11)
            Gui.runCommand("ClothSewing_RepairSeam", 0)
            _events()
            reloaded.recompute()
            if str(seam_11.Status) != "Valid":
                raise RuntimeError("explicit seam repair did not recover the curved seam")
            print("invalidation-restore=passed seam=Valid", flush=True)

            network_piece = reloaded.getObject(next(obj.Name for obj in reloaded_pieces if obj.PieceId == "pattern-piece-3"))
            if network_piece is None:
                raise RuntimeError("could not locate an M:N member PatternPiece after reload")
            network_sketch = network_piece.Sketch
            network_ids = tuple(network_sketch.SemanticEdgeIds)
            network_dim = network_sketch.addConstraint(Sketcher.Constraint("DistanceY", 2, 2, 50.0))
            network_sketch.renameConstraint(network_dim, "UpstreamNetworkEndpointY")
            network_sketch.setDatum(network_dim, App.Units.Quantity("60 mm"))
            reloaded.recompute()
            if tuple(network_sketch.SemanticEdgeIds) != network_ids:
                raise RuntimeError("M:N native Sketcher edit changed semantic edge IDs")
            network = reloaded.getObject(network_name)
            if str(network.Status) != "Invalid" or "Changed reference" not in str(network.InvalidReason):
                raise RuntimeError("M:N network did not fail closed after upstream native geometry change")
            stale_piece = next(
                obj for obj in reloaded_pieces
                if str(getattr(obj, "PieceId", "")) == "pattern-piece-3"
            )
            _select_objects(stale_piece)
            _close_task()
            Gui.runCommand("ClothPattern_Export", 0)
            _events()
            from freecad_cloth.pattern.PatternCommands import get_active_pattern_export_task_panel
            stale_export_panel = get_active_pattern_export_task_panel()
            if stale_export_panel is None:
                raise RuntimeError("ClothPattern_Export did not expose its public pattern-export task panel")
            _require_dialog(
                ("Production Export", "read-only"),
                "ClothPattern_Export stale validation",
                panel=stale_export_panel,
            )
            stale_export_path = output_dir / "stale.svg"
            stale_export_panel.format.setCurrentText("SVG")
            stale_export_panel.path.setText(str(stale_export_path))
            if stale_export_panel.accept():
                raise RuntimeError("production export did not fail closed for a stale sewing reference")
            if "Export blocked" not in str(stale_export_panel.status.text()):
                raise RuntimeError("stale export did not report a deterministic blocked status")
            _close_task()
            print("stale-export=blocked", flush=True)

            network_sketch.setDatum(network_dim, App.Units.Quantity("50 mm"))
            reloaded.recompute()
            network = reloaded.getObject(network_name)
            invalid_members = [member for member in network.Seams if str(getattr(member, "Status", "Valid")) != "Valid"]
            if not invalid_members:
                raise RuntimeError("restoring network source geometry unexpectedly retargeted all M:N seam references")
            for member in invalid_members:
                _select_objects(member)
                Gui.runCommand("ClothSewing_RepairSeam", 0)
                _events()
                _wait_task_close()
                reloaded.recompute()
            network = reloaded.getObject(network_name)
            if str(network.Status) != "Valid":
                raise RuntimeError("explicit seam repair did not recover M:N validity")

            _select_objects(target)
            Gui.runCommand("ClothDrape_RefreshTarget", 0)
            _events()
            _select_objects(scene)
            Gui.runCommand("ClothSimulation_Reset", 0)
            Gui.runCommand("ClothSimulation_Step", 0)
            _events()
            reloaded.recompute()
            if int(scene.Steps) != 1 or not bool(scene.FiniteState):
                raise RuntimeError("simulation did not rerun after save/reload and upstream invalidation")

            diagnostics_panel = _open_diagnostics_panel()
            diagnostics_panel.metric.setCurrentText("stress")
            diagnostics_panel.refresh_button.click()
            _events()
            if "Stress" not in str(diagnostics_panel.status.text()):
                raise RuntimeError("post-invalidation diagnostics did not produce stress analysis")
            diagnostics_panel.map_button.click()
            _events()
            if "Created" not in str(diagnostics_panel.status.text()):
                raise RuntimeError("post-invalidation diagnostics did not create a diagnostic map")
            _close_task()
            print("diagnostics-after-invalidation=passed metric=stress", flush=True)

            first_signature = _position_signature(scene)
            first_digest = _position_signature_digest(first_signature)
            print(
                "determinism-signature=first rounding=9 vertices=%d sha256=%s"
                % (len(first_signature), first_digest),
                flush=True,
            )

            Gui.runCommand("ClothSimulation_Reset", 0)
            Gui.runCommand("ClothSimulation_Step", 0)
            _events()
            reloaded.recompute()
            second_signature = _position_signature(scene)
            second_digest = _position_signature_digest(second_signature)
            if first_signature != second_signature:
                raise RuntimeError(
                    "repeated deterministic simulation run changed the rounded particle/mesh signature: "
                    "first_sha256=%s second_sha256=%s" % (first_digest, second_digest)
                )
            print(
                "determinism-signature=passed rounding=9 vertices=%d sha256=%s"
                % (len(second_signature), second_digest),
                flush=True,
            )

            export_results = {}
            source_before = (
                str(stale_piece.Label),
                str(stale_piece.PieceId),
                str(stale_piece.SewingOutline),
                float(stale_piece.SeamAllowance),
                float(stale_piece.GrainlineAngle),
                str(getattr(stale_piece, "GeometryAuthority", "")),
            )
            for export_format in ("SVG", "DXF"):
                size, metadata = _export_pair(stale_piece, output_dir, export_format)
                export_results[export_format] = size
                if metadata.get("piece_id") != str(stale_piece.PieceId):
                    raise RuntimeError("%s export lost piece identity" % export_format)
                if float(metadata.get("seam_allowance_mm", 0.0)) != float(stale_piece.SeamAllowance):
                    raise RuntimeError("%s export lost seam allowance" % export_format)
            source_after = (
                str(stale_piece.Label),
                str(stale_piece.PieceId),
                str(stale_piece.SewingOutline),
                float(stale_piece.SeamAllowance),
                float(stale_piece.GrainlineAngle),
                str(getattr(stale_piece, "GeometryAuthority", "")),
            )
            if source_before != source_after:
                raise RuntimeError("production export mutated authoritative PatternPiece state")
            print(
                "pattern-export=passed formats=SVG,DXF bytes=%s,%s"
                % (export_results["SVG"], export_results["DXF"]),
                flush=True,
            )

            App.closeDocument(reloaded.Name)
            doc = None
        print("pattern-e2e=passed pieces=4", flush=True)
        print("canonical garment end-to-end acceptance passed", flush=True)
    finally:
        _close_task()
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    run_acceptance()
