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
    from freecad_cloth.common.CommandAdapter import icon_for_command
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
        icon = Path(icon_for_command(command))
        assert icon.is_file(), command
        text = icon.read_text(encoding="utf-8")
        assert "<svg" in text and "viewBox=" in text


def test_semantically_equivalent_commands_share_canonical_icons():
    from freecad_cloth.common.CommandAdapter import icon_for_command

    aliases = (
        ("ClothSewing_Show2D", "ClothPattern_Show2D"),
        ("ClothDrape_EditTarget", "ClothPattern_EditPiece"),
        ("ClothFitting_EditAvatar", "ClothPattern_EditPiece"),
        ("ClothSewing_EditOperation", "ClothPattern_EditPiece"),
        ("ClothSewingNetwork_EditNetwork", "ClothPattern_EditPiece"),
        ("ClothSimulation_Edit", "ClothPattern_EditPiece"),
        ("ClothPattern_CreatePieceTask", "ClothPattern_CreatePiece"),
        ("ClothSewing_CreateSeam", "ClothPattern_AddSeam"),
        ("ClothDrape_RefreshTarget", "ClothSimulation_Reset"),
        ("ClothFitting_CreateSimulation", "ClothSimulation_Create"),
        ("ClothSewing_CreateMNSewing", "ClothSewingNetwork_CreateNetwork"),
        ("ClothFitting_SetAvatarMeasurements", "ClothFitting_SetMeasurements"),
    )
    for alias, canonical in aliases:
        alias_path = Path(icon_for_command(alias))
        canonical_path = Path(icon_for_command(canonical))
        assert alias_path == canonical_path
        assert alias_path.is_file()


def test_distinct_svg_assets_do_not_duplicate_the_same_artwork():
    contents = {}
    for icon in sorted(ICON_DIR.glob("*.svg")):
        content = icon.read_text(encoding="utf-8")
        assert content not in contents, (
            f"{icon.name} duplicates {contents.get(content)}; share canonical icons "
            "through CommandAdapter.icon_for_command instead"
        )
        contents[content] = icon.name
