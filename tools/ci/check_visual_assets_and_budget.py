"""Run both CI inventory and artifact-budget checks, even if either fails."""

from __future__ import annotations

from check_artifact_budget import main as artifact_budget_main
from check_visual_asset_contract import main as visual_asset_contract_main


def main() -> int:
    """Run both checks and return failure if either check fails."""
    visual_status = visual_asset_contract_main()
    budget_status = artifact_budget_main()
    return 0 if visual_status == 0 and budget_status == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
