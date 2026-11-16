#!/usr/bin/env bash
set -euo pipefail

# Focused UI contract suite; intentionally excludes simulation and garment audits.
UI_TESTS=(
  tests/test_ui_design.py
  tests/test_avatar_gui_contract.py
  tests/test_fitting_gui_status.py
  tests/test_diagnostics_gui_contract.py
  tests/test_drape_gui.py
  tests/test_pattern_gui_contract.py
  tests/test_pattern_topology_repair.py
  tests/test_pattern_topology_repair_gui.py
  tests/test_sewing_commands.py
  tests/test_sewing_creation_session.py
  tests/test_sewing_gui_contract.py
  tests/test_sewing_network_gui.py
  tests/test_simulation_gui.py
  tests/test_simulation_quality_gui_contract.py
)

export CLOTH_CI_ENABLE_PBD=0
export CLOTH_EXPECTED_TEST_MODULES="$(IFS=:; printf '%s' "${UI_TESTS[*]}")"

exec python3 -m pytest \
  -p tools.ci.pytest_collection_contract \
  -q \
  "${UI_TESTS[@]}"
