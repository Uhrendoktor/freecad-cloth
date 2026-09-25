# Tool State

```yaml
schema: 18
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1098
validated_main_before_docs_reconciliation: b43b8a2982e4570f25824509674dad9b66a38677
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
final_release:
  release_pr: 1165
  merged: true
  current_main_run: 3976
  current_main_run_id: 36202078316
  current_main_run_conclusion: success
  publisher_job_id: verified_in_run_3976
  published_docs_branch: docs/screenshots
  published_docs_head: 69f115354c6d59fd21b2df9e943461ef6373fe66
  README_assets_published: true
  native_sketcher_exact_main: passed
  sewing_smoke_exact_main: passed
  tunic_visual_exact_main: passed
  blanket_visual_exact_main: passed
  README_turntable_exact_main: passed
  export_exact_main: passed
  python_exact_main: passed
  benchmark_exact_main: passed
release_qa:
  gui_startup_fix_pr: 1187
  gui_startup_fix_merged: true
  publisher_path_fix_pr: 1190
  publisher_path_fix_merged: true
  publisher_path_fix_pr_run: 3968
  publisher_path_fix_pr_run_conclusion: success
  sketcher_post_commit_fix_pr: 1191
  sketcher_post_commit_fix_merged: true
  sketcher_post_commit_fix_main_run: 3973
  sketcher_post_commit_fix_main_run_conclusion: success
  turntable_timing_fix_pr: 1195
  turntable_timing_fix_merged: true
  turntable_timing_pr_run: 3975
  turntable_timing_pr_run_conclusion: success
  turntable_timing_main_run: 3976
  turntable_timing_main_run_conclusion: success
final_gate: exact_current_main_green; artifacts_inspected; turntable_timing_verified; docs_published; final_repo_audit
