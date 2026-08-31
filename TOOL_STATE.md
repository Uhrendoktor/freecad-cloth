# Tool State

```yaml
schema: 5
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-structure-and-roadmap
current_main: b7b2eab1b740078dd12d6be9ab42b223170e1600
open_prs: []
active_release_gates: [155, 278, 284, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]
closed_this_pass: []

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
  run_id: 33415287754
  run_number: 1143
  commit: 03cd25f54bf2c7a0301329030cbc2bc4992b8942
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  publish_merged_pr_screenshots: success
  note: The merged structure code passed the canonical Python and real FreeCAD/Xvfb screenshot/PNG acceptance on main. Subsequent supervisor-state commits are documentation-only and do not alter executable workbench code.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  docs: project_structure_and_feature_matrix_added
  architecture: package_boundaries_merged_without_breaking_FreeCAD_entry_points
  next_p0: canonical_DrapeTarget_acceptance_and_end_to_end_garment_fixture
```
