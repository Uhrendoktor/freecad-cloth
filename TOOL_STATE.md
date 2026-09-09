# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-structure-and-roadmap
current_main: 86eea3e33518dc82048d44677331d93407a0fe89
open_prs: [414]
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
  screenshot_display: 1280x720
  screenshot_outputs:
    - docs/images/generated/cloth-pattern-design.png
    - docs/images/generated/cloth-sewing.png
    - docs/images/generated/cloth-simulation-arranged.png
    - docs/images/generated/cloth-simulation-draped.png
  screenshot_artifacts: [cloth-gui-screenshots, cloth-gui-diagnostics]
  policy: preserve_existing_Docker_Xvfb_PNG_path; no_second_workflow

latest_verified_ci:
  run_id: 34389227217
  run_number: 1159
  commit: 86eea3e33518dc82048d44677331d93407a0fe89
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  publish_merged_pr_screenshots: success
  note: Main was green immediately before the module-tree cleanup. PR #414 is the follow-up that makes the package tree authoritative and removes remaining root/domain duplicates.

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
  ci_status: PR checks running
```
