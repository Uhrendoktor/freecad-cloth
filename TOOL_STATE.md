# Tool State

```yaml
schema: 11
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1066
active_release_branch: supervisor/complete-audit-20260923
active_release_head: 2a142d1c71ef6581d6c7afac20acf3018254de66
current_main: 8cee5774c25110448675e7b45d651869f3921692
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  candidate_scope: evidence-backed 200 mm blanket fixture for basic visual and README turntable
  candidate_push_run: 35847648590
  candidate_push_state: failure_zero_jobs
  merged_main_push_run: 35847198318
  merged_main_push_state: failure_zero_jobs
  supporting_run: 35845226384
  supporting_blanket_fixture: 200_mm_basic_visual
  supporting_blanket_fixture_result: passed
  supporting_readme_turntable_result: failed_drape_sanity_on_old_fixture
  supporting_sketcher_result: failed_timeout_empty_log
  external_ci_blocker: github_actions_event_delivery_or_policy; no_pull_request_run_for_current_supervisor_branches
final_gate: exact_head_canonical_pr_green; inspect_artifacts; merge; merged_main_canonical_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1041, 1042, 1043, 1048, 1053, 1055]
```
