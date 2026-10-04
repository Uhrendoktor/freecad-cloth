"""FreeCAD CI compatibility shims loaded before test scripts."""

import os

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


def _require_pbd():
    try:
        import pypbd  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("PositionBasedDynamics CI mode requires pyPBD") from exc

def _install_pbd_backend_hook():
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import PositionBasedDynamicsBackend
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    original_execute = QualitySimulationProxy.execute
    if getattr(original_execute, "_cloth_pbd_enforced", False):
        return
    def execute(self, obj):
        result = original_execute(self, obj)
        backend = getattr(self._base_or_restore(), "backend", None)
        if not isinstance(backend, PositionBasedDynamicsBackend):
            raise RuntimeError("canonical GUI simulation did not select PositionBasedDynamics")
        print("cloth-ci-backend=position-based-dynamics", flush=True)
        return result
    execute._cloth_pbd_enforced = True
    QualitySimulationProxy.execute = execute

if (os.environ.get("DISPLAY") == ":99"
    and os.environ.get("CLOTH_CI_ENABLE_PBD", "0") == "1"
    and os.environ.get("CLOTH_CI_DISABLE_PBD", "0") != "1"):
    _require_pbd()
    os.environ["CLOTH_SIMULATION_BACKEND"] = "position-based-dynamics"
    os.environ.setdefault("CLOTH_PBD_SUBSTEPS", "1")
    _install_pbd_backend_hook()
