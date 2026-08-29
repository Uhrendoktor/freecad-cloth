"""FreeCAD runtime smoke test for persisted simulation status lifecycle."""
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import FreeCAD as App
from SimulationQualityRuntimeV2 import create_quality_simulation_scene


def main():
    doc = App.newDocument("ClothSimulationStatus")
    scene = create_quality_simulation_scene(doc)
    assert scene.SimulationStatus == "Ready"
    assert "Ready" in scene.SimulationStatusMessage

    scene.Steps = 2
    doc.recompute()
    assert scene.SimulationStatus == "Complete"
    assert scene.FiniteState
    assert "Complete" in scene.SimulationStatusMessage

    scene.ParticleDistance = 6.0
    assert scene.SimulationStatus == "Invalid"
    assert "ParticleDistance" in scene.SimulationStatusMessage
    doc.recompute()
    assert scene.SimulationStatus == "Complete"

    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "status.FCStd")
        doc.recompute()
        doc.saveAs(path)
        App.closeDocument(doc.Name)
        reopened = App.openDocument(path)
        persisted = reopened.getObject(scene.Name)
        assert persisted.SimulationStatus == "Complete"
        assert persisted.ParticleDistance == 6.0
        App.closeDocument(reopened.Name)

    print("FreeCAD simulation status lifecycle smoke test passed")


if __name__ == "__main__":
    main()
