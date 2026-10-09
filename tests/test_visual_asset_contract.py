"""Regression coverage for the public README/wiki visual asset contract."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_visual_asset_inventory_has_live_ci_producers():
    checker = ROOT / "tools" / "ci" / "check_visual_asset_contract.py"
    env = os.environ.copy()
    env.update({"GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/1/merge", "VISUAL_PUBLISH_RESULT": "skipped"})
    result = subprocess.run(
        [sys.executable, str(checker)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "visual-asset-contract=passed documented_and_generated=27" in result.stdout
