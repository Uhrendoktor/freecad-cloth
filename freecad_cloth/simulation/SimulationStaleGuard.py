"""Recompute guard for stale persistent DrapeTargets.

FreeCAD calls FeaturePython ``execute`` during ordinary document recompute.
A stale collision target is a recoverable document state, not an exception
condition. This compatibility layer gates both the base and quality simulation
proxies before they consume stale collision data.
"""

_INSTALLED = False
_ORIGINAL_EXECUTES = {}


def _ensure_state_properties(obj):
    """Add serialized lifecycle properties to old/new simulation objects."""
    if not hasattr(obj, "SimulationState"):
        try:
            obj.addProperty("App::PropertyString", "SimulationState", "State", "Simulation lifecycle state")
            obj.SimulationState = "READY_FOR_SIMULATION"
        except (AttributeError, TypeError):
            pass
    if not hasattr(obj, "InvalidationReason"):
        try:
            obj.addProperty("App::PropertyString", "InvalidationReason", "State", "Why simulation derived state is stale or invalid")
            obj.InvalidationReason = ""
        except (AttributeError, TypeError):
            pass


def _set_state(obj, state, reason=""):
    _ensure_state_properties(obj)
    try:
        obj.SimulationState = str(state)
        obj.InvalidationReason = str(reason)
    except (AttributeError, TypeError):
        pass


def _guarded_execute(self, obj):
    from freecad_cloth.simulation.DrapeTarget import target_status

    _ensure_state_properties(obj)
    target = getattr(obj, "DrapeTarget", None)
    try:
        status = target_status(target)
    except (AttributeError, TypeError, ValueError) as exc:
        _set_state(obj, "STALE", "Cannot inspect drape target: %s" % exc)
        return None

    if status["state"] != "ready":
        _set_state(obj, "STALE" if status.get("stale") else status["state"].upper(), status["reason"] or status["message"])
        return None

    original = _ORIGINAL_EXECUTES.get(type(self))
    if original is None:
        return None
    try:
        result = original(self, obj)
    except RuntimeError:
        # The target may change between the status check and collision build.
        # Only swallow the known recoverable target transition; unrelated
        # RuntimeErrors remain visible to the caller/FreeCAD.
        latest = target_status(getattr(obj, "DrapeTarget", None))
        if latest.get("stale"):
            _set_state(obj, "STALE", latest["reason"] or latest["message"])
            return None
        raise
    _set_state(obj, "READY_FOR_SIMULATION", "")
    return result


def _guard_class(cls):
    current = getattr(cls, "execute", None)
    if not callable(current) or getattr(current, "_drape_target_guard", False):
        return
    _ORIGINAL_EXECUTES[cls] = current

    def guarded(self, obj):
        return _guarded_execute(self, obj)

    guarded._drape_target_guard = True
    cls.execute = guarded


def install():
    """Install the guard once for all simulation proxy classes available now."""
    global _INSTALLED
    try:
        from freecad_cloth.simulation.SimulationObjects import SimulationProxy
        _guard_class(SimulationProxy)
    except (ImportError, AttributeError, TypeError):
        pass
    try:
        from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
        _guard_class(QualitySimulationProxy)
    except (ImportError, AttributeError, TypeError):
        pass
    _INSTALLED = bool(_ORIGINAL_EXECUTES)


try:
    install()
except (ImportError, AttributeError, TypeError):
    pass
