# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-structure-and-roadmap
current_main: 65599603a394505f7bc4ab6d83ff7c5bb84123f2
open_prs: []
active_release_gates: [155, 278, 284, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]
closed_this_pass: []

architecture:
  package_root: freecad_cloth/
  domain_packages: [avatar, pattern, sewing, simulation]
  shared_packages: [common, shared]
  root_python: [Init.py, InitGui.py, sitecustomize.py]
  root_domain_implementations: forbidden
  root_compatibility_shims: forbidden
  drape_target_owner: freecad_cloth.simulation.DrapeTarget
  diagnostics_owner: freecad_cloth.common.ClothDiagnostics
  policy: migrate_callers_to_package_namespace; never_restore_root_domain_modules

workflow_contract:
  workflow_count: 1
  workflow: .github/workflows/canonical-execution.yml
  image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r2
  image_policy: publish_on_main_when_missing; PR validation may build locally with the same tag
  screenshot_display: 1280x720
  screenshot_outputs:
    - docs/images/generated/cloth-pattern-design.png
    - docs/images/generated/cloth-sewing.png
    - docs/images/generated/cloth-simulation-arranged.png
    - docs/images/generated/cloth-simulation-draped.png
    - docs/images/generated/cloth-simulation-arranged-turntable.gif
    - docs/images/generated/cloth-simulation-draped-turntable.gif
    - docs/images/generated/cloth-avatar-turntable.gif
  screenshot_artifacts: [cloth-gui-screenshots, cloth-gui-diagnostics]
  policy: preserve_existing_Docker_Xvfb_PNG_path; simulation_and_avatar_turntables_are_72_position_full_360_camera_orbits_plus_closing_frame; no_second_workflow

latest_verified_ci:
  run_id: 34839362851
  run_number: 1710
  commit: 65599603a394505f7bc4ab6d83ff7c5bb84123f2
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  publish_merged_pr_screenshots: success
  publish_readme_screenshots: success
  note: Main CI successfully published the FreeCAD r2 image to GHCR and refreshed the stable README screenshot branch with arranged, draped, and avatar turntables.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  imports: package-qualified module namespace is authoritative
  structure: package-tree cleanup in PR 414
  ci_status: canonical FreeCAD r2 image and three README turntables verified on main
```
