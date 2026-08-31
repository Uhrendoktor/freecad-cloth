# Tool State

```yaml
schema: 5
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-roadmap-replan-v2
current_main: 152712048f3d8ecea1e5414b92d33fa236223e7e
open_prs: []
active_release_gates: [155, 278, 284, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]
closed_this_pass: [322, 289]

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
  run_id: 33413104880
  run_number: 1101
  commit: 0335360e3fbf24750df931ed159bf17f7e0c5488
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  note: PR 397 passed Python/non-GUI and real FreeCAD/Xvfb screenshot/PNG validation before merge. Main merge commit is 152712048f3d8ecea1e5414b92d33fa236223e7e.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  docs: consolidated_into_six_canonical_docs
  next_p0: canonical_DrapeTarget_acceptance_and_end_to_end_garment_fixture
```
