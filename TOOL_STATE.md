# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1066
active_release_branch: supervisor/complete-audit-20260923
current_main: ccac198eae37bb162830895b1d8259ca84d7047f
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  exact_head: 28b8b251ccb6991466ab7e8657d9397419f2c706
  pr_run_state: no_pull_request_run_or_status; commits 997e1f7b and 28b8b251 received no workflow run; prior push run #3413 (35849087425) failed with zero jobs
  merged_main_push_run: 35848880387
  merged_main_push_state: failure_zero_jobs
  supporting_run: 35845226384
  supporting_run_result: 200_mm_blanket_fixture_passed_real_freecad_xvfb
  latest_zero_job_main_run: 35848880387
latest_zero_job_release_run: 35849087425
branch_tree_repair: rebuilt_from_live_main; only two production test files differ from main before supervisor-state commits
supporting_timeout_root_cause: acceptance activated Cloth workbenches without explicitly bootstrapping InitGui.py
  candidate_fix: merged release bootstraps InitGui.py and emits acceptance stage markers before GUI activation
  external_ci_blocker: repeated zero-job push runs; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1067]
```

closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector
