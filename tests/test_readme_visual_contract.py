"""Executable contracts for the published README and release visual validation path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReadmeVisualContractTests(unittest.TestCase):
    def test_readme_turntable_uses_real_blanket_drape(self):
        source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
        for token in (
            "Part::Box",
            "BlanketSource",
            "ClothPieces = [blanket]",
            "blanket-motion-diagnostic",
            "blanket-turntable-pass",
            "if displacement < 40.0",
            "minimum_z > cube_top + 35.0",
        ):
            self.assertIn(token, source)
        self.assertIn('create_drape_target(doc, cube, "FreeCAD Geometry"', source)
        self.assertIn('assign_drape_target(target, cube, "FreeCAD Geometry")', source)

    def test_turntable_evidence_is_fail_closed(self):
        source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
        for token in (
            "CLOTH_TISSU_SUBSTEPS: 10",
            "CLOTH_TISSU_COLLISION_MODE: mesh",
            "blanket-motion-diagnostic",
            "blanket-turntable-pass",
            'test "$(find docs/images/generated/cloth-simulation-draped-turntable-frames',
            'test "$(find docs/images/generated/cloth-simulation-arranged-turntable-frames',
            "checkpoint-uniqueness=passed",
        ):
            self.assertIn(token, source)

    def test_actual_simulation_motion_and_media_are_contractual(self):
        source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("frame_count=16", source)
        self.assertIn("material-presentation=passed viewport=true", source)
        self.assertIn("cloth-blanket-motion.gif", readme)
        self.assertIn("cloth-simulation-motion.gif", readme)

    def test_seam_world_space_and_sketcher_acceptance_are_present(self):
        pattern = (ROOT / "freecad_cloth" / "pattern" / "PatternObjects.py").read_text(encoding="utf-8")
        acceptance = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("world_space=True", pattern)
        self.assertIn("native Sketcher acceptance passed", acceptance)
        self.assertIn("authoritative semantic edge", acceptance)

    def test_workflow_is_single_and_least_privilege(self):
        workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.schedule || github.event.pull_request.number || github.ref", workflow)
        self.assertIn(
            "permissions:\n  actions: read\n  contents: read\n  packages: read",
            workflow,
        )
        self.assertIn("  publish-readme-turntables:", workflow)
        self.assertIn(
            "    permissions:\n      contents: write\n      packages: read",
            workflow,
        )
        self.assertIn("  maintenance-cleanup:", workflow)
        self.assertIn(
            "    permissions:\n      actions: write\n      contents: write",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
