# Tool State

```yaml
schema: 20
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1347
critical_implementation_pr: 2048
critical_research_issue: 2043
human_judgment_issue: 2034
current_main: 25a9342c20456352d2089a88966742c61d20821e
current_branch: agent/2031-stitch-correction-limit-20260927
current_head: 9aefcc7a040a6db9161df75d43e3b630c3ffe6b5
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
open_prs_expected: 1
open_issues_expected: multiple research/child ledgers until supervisor closeout
decisions:
  solver_lane: bounded_stitch_correction_by_world_collision_thickness
  direct_stitch_api: explicit_infinity_sentinel_unbounded
  nonpositive_world_thickness: fail_closed_zero_correction
  collision_order_experiment: rejected_after_terminal_tunic_gate_failure
  deep_contact_experiment: superseded_unmerged; observation retained in #2020
  snap_acceleration_only: rejected; real_gui_still_failed_normal_ambiguity
risks:
  - exact-head canonical run must compile patched Tissu and pass focused edge-case tests
  - 90-step tunic must remain finite, attached/upright/above-hem, seam max <=35 mm, clearance >=8 mm, runtime <=60 s, with six-side rendered evidence
  - Snap semantics research #2043 has no terminal report yet
  - old manual rerun attempts may remain in progress and are not acceptance evidence
current_validation_run: 36300564038
current_validation_run_number: 5728
final_gate: incomplete
  required: exact_head_green + human_challenge + artifact_inspection + rendered_ui_inspection + merged_main_green + fresh_repo_audit
```
