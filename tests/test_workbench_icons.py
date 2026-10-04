"""Headless contract checks for Cloth workbench icon assets."""

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"


def test_workbench_icons_are_valid_scalable_assets():
    for name in ("ClothPattern.svg", "ClothSewing.svg", "ClothSimulation.svg"):
        root = ET.parse(ICON_DIR / name).getroot()
        assert root.tag.endswith("svg")
        assert root.attrib.get("viewBox") == "0 0 64 64"
        assert root.attrib.get("role") == "img"
        assert root.attrib.get("aria-label")
        assert root.findall(".//*[@fill='currentColor']")
        assert "#333" not in (ICON_DIR / name).read_text(encoding="utf-8")


def test_all_workbench_tool_commands_have_svg_icons():
    from freecad_cloth.avatar import AvatarCommands, FittingCommands
    from freecad_cloth.pattern import PatternCommands, PatternMarks
    from freecad_cloth.sewing import SewingCommands
    from freecad_cloth.simulation import DrapeCommands, SimulationCommands

    modules = (
        PatternCommands,
        PatternMarks,
        SimulationCommands,
        DrapeCommands,
        SewingCommands,
        FittingCommands,
        AvatarCommands,
    )
    commands = [command for module in modules for command in module.COMMANDS]
    assert len(commands) == len(set(commands))
    for command in commands:
        icon = ICON_DIR / f"{command}.svg"
        assert icon.is_file(), command
        text = icon.read_text(encoding="utf-8")
        assert "<svg" in text and "viewBox=" in text
