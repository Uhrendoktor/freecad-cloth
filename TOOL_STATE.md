# Tool State

```yaml
schema: 8
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: #647 release lifecycle closeout
current_main: main_final_closeout_state
open_prs: []
open_actionable_issues: []

architecture:
  package_root: freecad_cloth/
  domain_packages: [avatar, pattern, sewing, simulation]
  shared_packages: [common, shared]
  root_python: [Init.py, InitGui.py, sitecustomize.py]
  drape_target_owner: freecad_cloth.simulation.DrapeTarget
  diagnostics_owner: freecad_cloth.common.ClothDiagnostics
  semantic_boundaries: [PatternIR, SewingGraph, SimulationScene, DrapeTarget]
  policy: FreeCAD_owns_geometry_and_persistence; Cloth_owns_garment_semantics; solver_owns_physics; derived_simulation_state_is_rebuildable_and_invalidated

workflow_contract:
  workflow_count: 1
  workflow: .github/workflows/canonical-execution.yml
  image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
  screenshot_display: 1280x720
  screenshot_artifact: tunic-visual-audit
  turntable_artifact: readme-turntables
  runner_policy: prefer_recent_healthy_local_Docker_runner; fallback_github_hosted
  policy: preserve_Docker_Xvfb_FreeCAD_path; fail_closed_evidence; no_second_workflow

closeout_verified_ci:
  run_id: 35818705178
  run_number: 3101
  commit: 0b37cba7361cabb4815a5c6eccd97c422820335b
  pr: 1015
  status: completed
  conclusion: success
  jobs:
    - Python and FreeCAD non-GUI tests
    - Full tunic visual and simulation audit
    - Sewing staged creation smoke
    - Pattern production export smoke
    - README turntables
    - Measured FreeCAD workbench benchmark
    - Publish README turntables
  artifacts:
    tunic_visual_audit_id: 10732103838
    tunic_visual_audit_sha256: 7619ddb7bdf05e5919ccc3a77949860c0547f8599d73d5aa8205e43984ca1069
    sewing_creation_smoke_id: 10732507254
    sewing_creation_smoke_sha256: d026c03971fab055742e12cd12b3152d86e7478f21cc741a0a30a341c86b30ae
    pattern_export_id: 10732133675
    pattern_export_sha256: 475503b14ea7609a84b932b5dcb6cd7e2fe4e72f4ac9a41fc054a32361e9becb
    readme_turntables_id: 10731764698
    readme_turntables_sha256: cf31b2823d4eeb8edbf1c6c6f7245c90a9ca1f17baca3e80f2ef5c5818f20f02
    workbench_benchmark_id: 10731629572
    workbench_benchmark_sha256: 3bfca5553fcb8ba114f73fa6d6094c4c73776b084ac102cc07db70d82149fd74

release_evidence:
  garment_e2e: passed
  sewing_curved_mn: passed
  arrangement: passed_pieces_4
  garment_hierarchy: passed
  drape_target: passed_mannequin
  diagnostics: passed_stress
  save_reload: passed
  invalidation_and_repair: passed
  stale_export: blocked
  deterministic_rerun: passed
  pattern_export: passed_SVG_DXF
  canonical_visuals: six_drape_views_plus_diagnostics
  process_exit: passed
  drape_metrics:
    front: finite=true; connected_components=1; state=structurally-plausible; target_vertex_clearance_mm=4.0799
    back: finite=true; connected_components=1; state=structurally-plausible; target_vertex_clearance_mm=1.0594
  seam_coherence:
    max_correspondence_gap_mm: 20.842179
    method: solver-stitch-pairs
    mode: diagnostic_only

historical_closeout:
  merged_release_pr: 1001
  merged_release_commit: 2b09ea32426d8f26141c4a0d8e9c294509e29893
  merged_runner_pr: 904
  merged_runner_commit: 4e119229cd4df00b529d002dd32106b09504992e
  durable_state_pr: 1009
  durable_state_merge_commit: c41a071a345715f199bdade34872049faba4527d
  final_closeout_pr: 1011
  current_main_has_release_and_runner: true
  all_supervisor_records_closed_completed: true
  sewing_closeout_issue: 475_closed_completed
  stale_runner_prs: [925_closed_unmerged, 1008_closed_unmerged]
  stale_curved_sewing_pr: 999_closed_unmerged
  lifecycle_issues_closed: [1002, 1004, 1005, 1006, 987, 917, 837, 893, 828, 845, 692, 675]

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_ci_before_dependent_merge_or_close
  - inspect_artifacts_and_logs
  - never_weaken_validation
  - close_issues_only_with_explicit_state_reason
  - re_cut_implementation_branches_from_current_main
```
