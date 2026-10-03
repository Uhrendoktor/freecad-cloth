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

# Canonical GUI validation must use the production Tissu backend, not the
# reference XPBD backend. The GUI workflow runs with DISPLAY=:99; keep this
# enforcement scoped to that environment so the unit suite can still exercise
# XPBD deterministically and independently.
import os


def _require_tissu():
    try:
        import tissu  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Tissu CI mode was explicitly enabled, but pytissu is unavailable; "
            "use the pinned Tissu-capable CI image instead of installing dependencies at import time"
        ) from exc


def _install_quality_backend_hook():
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    from freecad_cloth.simulation.TissuBackend import TissuBackend

    original_execute = QualitySimulationProxy.execute
    if getattr(original_execute, "_cloth_tissu_enforced", False):
        return

    def execute(self, obj):
        base = self._base_or_restore()
        current_backend = getattr(base, "backend", None)
        if getattr(current_backend, "name", None) == "tissu":
            return original_execute(self, obj)

        requested_steps = int(getattr(obj, "Steps", 0))
        obj.Steps = 0
        result = original_execute(self, obj)

        base = self._base_or_restore()
        xpbd = getattr(base, "backend", None)
        system = getattr(xpbd, "system", None)
        if system is None:
            raise RuntimeError("Tissu CI hook could not recover the prepared cloth system")
        triangles = tuple(
            dict.fromkeys(
                tri
                for panel_triangles in getattr(base, "panel_triangles", {}).values()
                for tri in panel_triangles
            )
        )
        pins = tuple(getattr(system, "pins", {}).keys())
        stitch_constraints = tuple(getattr(system, "stitches", ()))
        stitch_compliances = tuple(float(getattr(c, "compliance", 0.0)) for c in stitch_constraints)
        if stitch_compliances and len(set(stitch_compliances)) != 1:
            raise RuntimeError("Tissu CI hook cannot preserve heterogeneous stitch compliance")
        stitches = tuple((int(c.a), int(c.b)) for c in stitch_constraints)
        base.backend = TissuBackend(
            system,
            triangles=triangles,
            pins=pins,
            stitches=stitches,
            stitch_compliance=stitch_compliances[0] if stitch_compliances else 0.0,
            collision_surface=getattr(base, "collision_surface", None),
        )
        if getattr(base.backend, "name", None) != "tissu":
            raise RuntimeError("canonical GUI simulation did not select Tissu")
        print("cloth-ci-backend=tissu", flush=True)

        obj.Steps = requested_steps
        return original_execute(self, obj)

    execute._cloth_tissu_enforced = True
    QualitySimulationProxy.execute = execute


if (
    os.environ.get("DISPLAY") == ":99"
    and os.environ.get("CLOTH_CI_ENABLE_TISSU", "0") == "1"
    and os.environ.get("CLOTH_CI_DISABLE_TISSU", "0") != "1"
):
    _require_tissu()
    os.environ["CLOTH_SIMULATION_BACKEND"] = "tissu"
    _install_quality_backend_hook()
