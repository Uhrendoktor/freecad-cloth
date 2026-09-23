"""Executable contracts for the published README visual validation path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReadmeVisualContractTests(unittest.TestCase):
    def test_turntable_uses_solver_boundary_provenance(self):
        source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
        for token in (
            "panel_boundary_edges",
            "resolve_simulation_pattern",
            "Edge%sId",
            "seam_stitch_pairs",
            "semantic-provenance=true",
        ):
            self.assertIn(token, source)
        self.assertIn("if seam_gap > 35.0", source)
        self.assertIn(
            "from freecad_cloth.simulation import TissuBackend as _tissu_backend",
            source,
        )
        self.assertLess(
            source.index("from freecad_cloth.simulation import TissuBackend as _tissu_backend"),
            source.index("def _tight_tissu_collision_envelope"),
        )

    def test_turntable_profile_matches_canonical_tunic(self):
        source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
        for token in (
            "chest = 860.0",
            "hip = 880.0",
            "ease = 10.0",
            "ParticleDistance",
            "24.0",
            "SolverIterations",
            "64",
            "FabricFriction = 0.85",
            "neckline_ratio",
        ):
            self.assertIn(token, source)
        self.assertIn("0.68, 0.08", source)

    def test_canonical_workflow_fails_closed_on_turntable_quality(self):
        source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
        for token in (
            "CLOTH_TISSU_SUBSTEPS: 10",
            "CLOTH_TISSU_COLLISION_MODE: torso-envelope",
            "semantic-provenance=true",
            "simulation-seam-diagnostic",
            "checkpoint-uniqueness=passed",
            'test "$unique" -eq 4',
        ):
            self.assertIn(token, source)

    def test_scheduled_workloads_do_not_cancel_each_other(self):
        source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
        self.assertIn(
            "github.event.schedule || github.event.pull_request.number || github.ref",
            source,
        )

    def test_actions_write_permission_is_scoped(self):
        source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
        self.assertIn(
            "permissions:\n  actions: read\n  contents: read\n  packages: read",
            source,
        )
        self.assertIn("  publish-readme-turntables:", source)
        self.assertIn(
            "    permissions:\n      contents: write\n      packages: read",
            source,
        )
        self.assertIn("  maintenance-cleanup:", source)
        self.assertIn(
            "    permissions:\n      actions: write\n      contents: write",
            source,
        )


if __name__ == "__main__":
    unittest.main()
