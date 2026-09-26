"""Contract tests for the FreeCAD realtime benchmark entrypoint and lifecycle."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "freecad_realtime_benchmark.py"
source = SOURCE.read_text(encoding="utf-8")

init_index = source.index('init_gui = ROOT / "InitGui.py"')
realtime_import_index = source.index("from freecad_cloth.simulation.RealtimePreview import")
metrics_index = source.index('(OUT / "metrics.json").write_text')
threshold_index = source.index('raise SystemExit(2)')
finally_index = source.index("    finally:")

assert "__name__ == \"__main__\"" not in source
assert "\nmain()\n" in source
assert init_index < realtime_import_index
assert metrics_index < threshold_index < finally_index
assert "Gui.getMainWindow()" in source
assert "QApplication.instance()" in source
assert "app.quit()" in source
assert "App.exit()" not in source
assert "except BaseException" not in source[finally_index:]
print("realtime benchmark lifecycle contract: ok")
