# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1066
active_release_branch: supervisor/complete-audit-20260923
current_main: 205f60c0fb3b47edab36a82c643bd29f3a4a3eb6
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  exact_head: 7141ed6a8c9e49dd3e85c171401aeebf28ff17c6
  pr_run_state: no_pull_request_run_or_status; push run #3405 (35848172889) failed with zero jobs
  supporting_run: 35844023654
  supporting_run_result: all canonical jobs passed except native Sketcher acceptance timeout
  supporting_timeout_root_cause: acceptance activated Cloth workbenches without explicitly bootstrapping InitGui.py
  candidate_fix: merged release bootstraps InitGui.py and emits acceptance stage markers before GUI activation
  external_ci_blocker: repeated zero-job push runs; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1042, 1043, 1053, 1055, 1067]
```
