# Tool State

```yaml
schema: 3
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md (missing from repository; supervisor policy retained here)
supervisor_task: cloth-sewing-workbench-roadmap-replan-v2
current_main: d18bec19536ab0831d468aacee971b8b7f834fae
open_prs: []
closed_superseded_prs: [373, 376, 375, 379, 378, 381]
completed_issue_audits: [120, 126, 252, 344]
last_merged_pr: 387
last_merged_main_sha: d18bec19536ab0831d468aacee971b8b7f834fae
active_release_gates: [143, 145, 155, 159, 161, 322, 289, 284, 369]
queued_release_gates: [162, 147, 163]
non_blocking: [148]

workflow_contract:
  workflow_count: 1
  workflow: .github/workflows/canonical-execution.yml
  screenshot_job: always_on_for_push_and_pull_request
  screenshot_display: 1280x720
  screenshot_outputs:
    - docs/images/generated/cloth-pattern-design.png
    - docs/images/generated/cloth-sewing.png
    - docs/images/generated/cloth-simulation-arranged.png
    - docs/images/generated/cloth-simulation-draped.png
  screenshot_artifacts:
    - cloth-gui-screenshots
    - cloth-gui-diagnostics
  policy: preserve_existing_Docker_Xvfb_PNG_path; no_second_workflow

latest_supervisor_ci:
  run_id: 33409828476
  commit: ba012ec5980ab21e0455740fbfb7c07d2cd3d864
  status_at_last_check: completed
  python_job: success
  gui_job: success
  note: PR 387 canonical run 1070 passed Python/non-GUI and real FreeCAD/Xvfb screenshot/PNG validation. The new document-level mannequin round-trip test skips only when the FreeCAD Python module is unavailable in the non-GUI runner; the real GUI gate remains unchanged.

policy:
  - one canonical workflow only
  - never declare an in-progress CI run successful
  - review diffs before merge
  - require terminal-green CI before dependent merge/close decisions
  - verify merged mainline after merge
  - never close an issue without an explicit state reason
  - re-cut implementation branches from current main; do not revive stale heads
  - do not weaken GUI/PNG assertions to make CI green
  - CI modifications require explicit supervisor review because the PNG export path is a release asset
```
