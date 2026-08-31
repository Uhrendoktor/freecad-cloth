# Tool State

```yaml
schema: 3
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md (missing from repository; supervisor policy retained here)
supervisor_task: cloth-sewing-workbench-roadmap-replan-v2
current_main: 0eed6298cdb4b7f729d10a065385ca5b263a2783
open_prs: [373]
pr_373_head: 56a4cb8499406bd059938177c141eba8b56fb24c
pr_373_status: open_pending_terminal_ci
active_release_gates: [143, 145, 155, 159, 161, 322, 289, 284]
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
  run_id: 33405260079
  commit: 0eed6298cdb4b7f729d10a065385ca5b263a2783
  status_at_last_check: in_progress
  python_job: success
  gui_job: screenshot_generation_and_validation_success_upload_in_progress

policy:
  - one canonical workflow only
  - never declare an in-progress CI run successful
  - review diffs before merge
  - require terminal-green CI before dependent merge/close decisions
  - verify merged mainline after merge
  - never close an issue without an explicit state reason
  - re-cut implementation branches from current main; do not revive stale heads
  - do not weaken GUI/PNG assertions to make CI green
```
