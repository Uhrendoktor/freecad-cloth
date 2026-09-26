"""Contract tests for the optional realtime-preview GUI integration."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "freecad_cloth" / "simulation" / "RealtimePreview.py"
WORKBENCH = ROOT / "freecad_cloth" / "simulation" / "workbench.py"

source = SOURCE.read_text(encoding="utf-8")
workbench = WORKBENCH.read_text(encoding="utf-8")
assert "def toggle_realtime_preview" in source
assert "def stop_realtime_preview" in source
assert "QTimer" in source
assert "ClothRealtimePreview" in source
assert "RealtimePreview" in workbench
assert "ClothRealtimePreview" in workbench
print("realtime preview contract: ok")

assert "register_gui_command()" not in source
assert "RealtimePreview.register_gui_command()" in workbench
