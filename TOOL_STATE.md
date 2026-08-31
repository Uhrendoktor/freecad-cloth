# Tool State

```yaml
schema: 3
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md (missing from repository; supervisor policy retained here)
supervisor_task: cloth-sewing-workbench-roadmap-replan-v2
current_main: f0e2efa99439784d496c218e4ed6ec8ced2e5847
open_prs: [375, 378]
pr_375_head: 209b57081bb6e52b6c0e1d641932f729db2df04a
pr_375_status: draft_no_canonical_run
pr_378_head: f6d8e31704bcf7f764eb54dc8f12dc8e839cbf85
pr_378_status: canonical_ci_in_progress
closed_superseded_prs: [373, 376]
completed_issue_audits: [120, 126, 252, 344]
last_merged_pr: 377
last_merged_main_sha: 2823aadf3b3348dec75d82bc297b3cea5f6567c7
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
  run_id: 33405455692
  commit: f6d8e31704bcf7f764eb54dc8f12dc8e839cbf85
  status_at_last_check: in_progress
  python_job: success
  gui_job: screenshot_generation_in_progress
  note: PR 378 adds only a post-success screenshot-comment job; do not merge until terminal-green evidence proves the existing screenshot/export path is unaffected.

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
