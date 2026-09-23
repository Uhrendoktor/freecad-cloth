# Tool State

```yaml
schema: 10
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1058
active_release_branch: supervisor/root-completion-20260923
current_main: dad152e634bcf454bc71aa02f4c1bfa858c154c1
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1058
  exact_head: 63eb2d4c7e8336855fa2b3b0c7d476cd0ee5ff70
  pr_run_state: not_exposed_after_open; older unrelated PR runs are consuming the Actions pool
  supporting_run: 35844023654
  supporting_run_result: all canonical jobs passed except native Sketcher acceptance timeout
  supporting_timeout_root_cause: acceptance activated Cloth workbenches without explicitly bootstrapping InitGui.py
  candidate_fix: bootstrap InitGui.py and emit stage markers before GUI activation
  external_ci_blocker: repeated zero-job push runs; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1041, 1042, 1053]
```
