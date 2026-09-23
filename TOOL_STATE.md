# Tool State

```yaml
schema: 15
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1098
active_release_pr: 1075
active_release_branch: supervisor/final-release-fixed-main-20260923
current_main: ec9b8d9a868cb3ed8e566f237cb521067d8ad703
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1075
  live_head: 077afd75579f79410279714ebc285f2e0561956d
  pr_run_state: no pull_request run/status at live head; latest live-head push run #3594 / 35906114777 failed pre-job with zero jobs/artifacts
  candidate_relation_to_main: ahead_by_4; behind_by_19; behind side is subsequent supervisor/documentation history
  timing_fix_pr: PR_1090
  timing_fix_head: a5cb1a82cba839a853c37bd4abeda5e91937a860
  timing_fix_ci: no pull_request workflow/run status delivered
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200 mm Blanket-over-Cube real FreeCAD/Xvfb acceptance passed; 16 distinct motion frames and representative checkpoints inspected
  external_ci_blocker: exact-head pull_request delivery remains absent and push attempts fail before job allocation; connector exposes no workflow dispatch or Actions policy administration
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1084, 1088, 1098, 1105]
remote_branch_count_observed: 501
last_schedule_run: 3225/35839191664; success; 12 jobs instantiated; daily retention job skipped because event was the */5-minute schedule
daily_0300_utc: no run evidenced for 2026-09-23
published_asset_gap: docs/screenshots:docs/images/generated/cloth-blanket-motion.gif
release_duplicate_prs_closed_unmerged: [1093, 1095, 1096]
timing_duplicate_closed_unmerged: true
timing_fix_pr: 1090
timing_fix_head: a5cb1a82cba839a853c37bd4abeda5e91937a860
timing_fix_ci: no pull_request workflow/status delivered
```

closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector; current full branch pagination observes 501 remote branches; no fresh daily 03:00 UTC retention run evidenced

research_activation_issue: 1105
research_activation_pr: 1107
closed_duplicate_research: [1106]

recovery_last_reconciled: 2026-09-23T21:30:00+02:00
main_head: ec9b8d9a868cb3ed8e566f237cb521067d8ad703
startup_research_issue: 1105
superseded_startup_prs_closed: [1109, 1110]
startup_hypothesis_falsifier: fallback run 35908076546 / exact pinned FreeCAD 1.1.0 / Native Sketcher timeout exit 124
canonical_control_plane_blocker: issue_1053_zero_job_runs
