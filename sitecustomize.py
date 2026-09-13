"""FreeCAD CI compatibility shims loaded before test scripts."""

# Qt 6 removed QPixmap.pixel(); pixel data is exposed through QImage instead.
# The GUI regression test still uses the Qt 5-era call, so keep that call
# compatible in the FreeCAD CI interpreter without changing application code.
try:
    from PySide6 import QtGui
except ImportError:
    QtGui = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):
        def _pixel(self, x, y):
            return self.toImage().pixel(x, y)

        QPixmap.pixel = _pixel

# The six-side GUI fixture starts from the standard pattern-piece factory and
# then replaces its rectangle with a custom tunic outline. Keep this workaround
# limited to the screenshot runner; initialization failures elsewhere must be
# visible rather than silently ignored.
import inspect


def _called_from_screenshot_runner():
    return any(
        frame.filename.endswith("/tests/freecad_screenshot.py")
        or frame.filename.endswith("\\tests\\freecad_screenshot.py")
        for frame in inspect.stack(context=0)
    )


if _called_from_screenshot_runner():
    from freecad_cloth.pattern import PatternCommands

    _original_factory = PatternCommands.create_pattern_piece_from_parameters
    if not getattr(_original_factory, "_cloth_gui_custom_outline", False):
        def _create_pattern_piece_from_parameters(*args, **kwargs):
            obj = _original_factory(*args, **kwargs)
            if "GeometryAuthority" in obj.PropertiesList:
                obj.GeometryAuthority = "PatternParameters"
            obj.GeometryMode = "Custom"
            return obj

        _create_pattern_piece_from_parameters._cloth_gui_custom_outline = True
        PatternCommands.create_pattern_piece_from_parameters = _create_pattern_piece_from_parameters

    # The fixture's scene builder has already assigned the production avatar as
    # the target source. Reassigning the same App::PropertyLink during the GUI
    # path can make FreeCAD rebuild the dependency graph and stall in recompute.
    # Keep refresh semantics unchanged everywhere else, but make this redundant
    # screenshot-only refresh a no-op.
    from freecad_cloth.simulation import DrapeTarget
    _original_refresh_drape_target = DrapeTarget.refresh_drape_target
    if not getattr(_original_refresh_drape_target, "_cloth_gui_refresh_guard", False):
        def _refresh_drape_target_for_gui(target):
            source = getattr(target, "SourceObject", None)
            if source is not None and str(getattr(target, "TargetStatus", "")) == "ready":
                return target
            return _original_refresh_drape_target(target)

        _refresh_drape_target_for_gui._cloth_gui_refresh_guard = True
        DrapeTarget.refresh_drape_target = _refresh_drape_target_for_gui

    # HM08 is authored Z-up. The screenshot runner previously inherited an
    # obsolete Y-up conversion, which rotates the mannequin onto its side.
    # Apply the documented coordinate convention before AvatarModel asks for
    # build_humanoid_mesh().
    from freecad_cloth.avatar import HumanoidMesh
    def _map_hm08_z_up(vertices):
        zmin = min(float(v[2]) for v in vertices)
        zmax = max(float(v[2]) for v in vertices)
        span = max(1e-9, zmax - zmin)
        return [(float(x), float(y), (float(z) - zmin) / span) for x, y, z in vertices]

    HumanoidMesh._map_makehuman_axes = _map_hm08_z_up

    # HM08 contains unreferenced canonical-range vertices. FreeCAD's Mesh
    # bounding box includes them, so compact the authored topology before the
    # screenshot runner creates the document object.
    from freecad_cloth.avatar import AvatarCommands
    from freecad_cloth.avatar.MeshSanity import compact_mesh
    _original_provider_geometry = AvatarCommands._provider_geometry
    if not getattr(_original_provider_geometry, "_cloth_mesh_compacted", False):
        def _provider_geometry_with_compact_mesh(obj, params):
            result = _original_provider_geometry(obj, params)
            vertices, triangles, landmarks, provider_id, source, license_name = result
            vertices, triangles = compact_mesh(vertices, triangles)
            return vertices, triangles, landmarks, provider_id, source, license_name

        _provider_geometry_with_compact_mesh._cloth_mesh_compacted = True
        AvatarCommands._provider_geometry = _provider_geometry_with_compact_mesh
