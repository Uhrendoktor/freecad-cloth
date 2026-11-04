# Test inventory

The authoritative pytest inventory is `GROUPS` in `tools/ci/python_validation.py`. CI runs the five groups (`core`, `pattern`, `sewing`, `gui`, and `pytest`) through the same runner.

Every `tests/test_*.py` module must occur in exactly one group. `validate_test_routing()` compares the configured groups with the files on disk and fails on missing, stale, or duplicate entries. The pytest collection plugin also fails when an explicitly requested module collects no tests. Add or move a module by editing `GROUPS`; do not maintain a second generated list of test functions.

Native FreeCAD acceptance scripts (`tests/freecad_*.py`) are run by their dedicated workflow jobs because they need the real FreeCAD/GUI runtime. They are not part of the headless pytest module groups.

Shared fixtures and helpers live under `tests/support/` and are not independent test modules.
