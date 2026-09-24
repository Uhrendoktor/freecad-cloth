"""Static contract for the blanket visual FreeCAD GUI startup boundary."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_visual_example_prepares_gui_before_manual_initgui():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    run = source.split("def main():", 1)[1]

    defer_index = run.index("init_gui, deferred_init_gui = _defer_auto_initgui()")
    window_index = run.index("window = Gui.getMainWindow()")
    show_index = run.index("window.show()", window_index)
    first_events_index = run.index("events()", show_index)
    restore_index = run.index("_restore_auto_initgui(init_gui, deferred_init_gui)", first_events_index)
    init_gui_index = run.index("init_gui, deferred_init_gui", defer_index)
    guard_index = run.index('if "ClothPatternWorkbench" not in Gui.listWorkbenches():', restore_index)
    exec_index = run.index('exec(compile(open(str(init_gui)', guard_index)
    second_events_index = run.index("events()", exec_index)
    document_index = run.index('doc = App.newDocument("ClothBlanketExample")', second_events_index)

    assert defer_index < window_index < show_index < first_events_index < restore_index
    assert restore_index < guard_index < exec_index < second_events_index < document_index
    assert "InitGui.py.freecad-visual-deferred" in run
    assert 'raise RuntimeError("FreeCAD GUI did not launch")' in run


if __name__ == "__main__":
    test_visual_example_prepares_gui_before_manual_initgui()
