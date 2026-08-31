# Tool State

```yaml
schema: 4
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-roadmap-replan-v2
current_main: cbe6b4ceeaa6af49df7c9e9067e4af6caca1ae11
open_prs: []
active_release_gates: [322, 289, 284, 155, 278, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]

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
  run_id: 33411023425
  commit: 301a0b79fd8c97502a7282f286ea7d42288cbdc0
  status: completed
  python_job: success
  gui_job: success
  note: PR 393 passed Python/non-GUI and real FreeCAD/Xvfb screenshot/PNG validation; current main also contains the later documentation/simulation-UI commits, so run those changes through canonical CI before claiming a new green state.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  docs: consolidated_into_docs_README_ARCHITECTURE_ROADMAP_RESEARCH_DEVELOPMENT
  next_p0: stale_DrapeTarget_document_recompute_guard
```
