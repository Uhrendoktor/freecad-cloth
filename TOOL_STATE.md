# Tool State

```yaml
schema: 19
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1098
validated_release_code: b43b8a2982e4570f25824509674dad9b66a38677
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release:
  p0_closeout: complete
  timing_fix_pr: 1195
  timing_fix_pr_merged: true
  native_sketcher: passed
  sewing_smoke: passed
  tunic_visual: passed
  blanket_visual: passed
  readme_turntables: passed
  readme_turntable_timing: passed
  pattern_export: passed
  python: passed
  benchmark: passed
  publisher: passed
  docs_assets_published: true
  publisher_job: 108293224713
  published_docs_screenshots_commit: 2a7fd1e
  published_gif_provenance: structural_timing_verified_exact_bytes_unverified
  final_issue_1017: closed_completed
  continuation_issue_1098: closed_completed
  open_prs: 0
  open_issues: 0
final_gate: exact_release_code_green; merged_main_green; artifacts_inspected; rendered_output_inspected; docs_published; final_repo_audit
```
