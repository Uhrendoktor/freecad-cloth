# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1069
active_release_branch: supervisor/release-fixture-200mm-20260923
current_main: ccac198eae37bb162830895b1d8259ca84d7047f
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  exact_head: e5676aa8091fd55d3b17a5a2cb71122e41683433
  pr_run_state: no_pull_request_run_or_status; latest push run #3428 (35849536356) failed with zero jobs/artifacts
  supporting_run: 35845226384
  supporting_run_result: 200_mm_blanket_fixture_passed_real_freecad_xvfb_artifact_10743635540
  supporting_timeout_root_cause: acceptance activated Cloth workbenches without explicitly bootstrapping InitGui.py
  candidate_fix: merged release bootstraps InitGui.py and emits acceptance stage markers before GUI activation
  external_ci_blocker: repeated zero-job push runs; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1067]
```

closed_research_issues: [1042, 1055]
duplicate_release_pr: 1066
stale_branch_cleanup: unavailable_via_current_connector