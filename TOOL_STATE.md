# Tool State

```yaml
schema: 14
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1098
active_release_pr: 1075
active_release_branch: supervisor/final-release-fixed-main-20260923
current_main: 52cbbd5f8c0653a89f49abab98f90f430ef3b002
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1075
  live_head: fc03722e61bc7184fc0a25ef137f44c562a5a022
  pr_run_state: no pull_request run/status at live head; latest live-head push run #3588 / 35905788417 failed pre-job with zero jobs/artifacts
  candidate_relation_to_main: ahead_by_7; behind_by_16; behind side is subsequent supervisor/documentation history plus current main drift
  timing_fix_pr: PR_1090
  timing_fix_head: a5cb1a82cba839a853c37bd4abeda5e91937a860
  timing_fix_ci: no pull_request workflow run/status delivered
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200 mm Blanket-over-Cube real FreeCAD/Xvfb acceptance passed; 16 distinct motion frames and representative checkpoints inspected
  external_ci_blocker: exact-head pull_request delivery remains absent and push attempts fail before job allocation; connector exposes no workflow dispatch or Actions policy administration
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1075, 1084, 1088, 1090, 1098]
remote_branch_count_observed: 498
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
stale_branch_cleanup: unavailable_via_current_connector; current full branch pagination observes 498 remote branches; no fresh daily 03:00 UTC retention run evidenced
