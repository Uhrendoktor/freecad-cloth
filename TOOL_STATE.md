# Tool State

```yaml
schema: 9
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1044
active_release_branch: supervisor/release-final-20260923
current_main: dad152e634bcf454bc71aa02f4c1bfa858c154c1
open_actionable_issues: [1017, 1020, 1041, 1042]
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  functional_candidate: implemented
  current_ci_state: exact_head_pr_run_not_yet_exposed; branch_push_runs_fail_with_zero_jobs
  evidence_run: 35844023654
  evidence_run_head: a9ea0859ffa396dceec853cf918052ce13c5ec7a
  evidence_run_result: blanket_visual_passed; turntables_passed; tunic_audit_passed; sewing_passed; export_passed; python_passed; sketcher_timeout
  final_gate: merge_only_after_terminal_green_pr_validation_or_explicit_external_ci_blocker_with_exact_repro_path; then merged_main_reaudit
durable_records:
  state_files: [AGENT_STATUS.md, TOOL_STATE.md]
  docs_index: docs/README.md
  user_guide: docs/USER_GUIDE.md
```
