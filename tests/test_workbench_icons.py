# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless contract checks for Cloth workbench icon assets."""

import xml.etree.ElementTree as ET
from pathlib import Path

from freecad_cloth.avatar import AvatarCommands, FittingCommands
from freecad_cloth.common.CommandAdapter import icon_for_command
from freecad_cloth.pattern import PatternCommands, PatternMarks
from freecad_cloth.sewing import SewingCommands
from freecad_cloth.simulation import DrapeCommands, SimulationCommands

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"


def _check(condition: object, message: str) -> None:
    """Raise an explanatory test failure when an explicit condition is false.

    Args:
        condition: Observed predicate that the test requires to be true.
        message: Explanation identifying the failed icon contract.

    Raises:
        AssertionError: If the supplied condition is false.
    """
    if not condition:
        raise AssertionError(message)


def test_workbench_icons_are_valid_scalable_assets() -> None:
    """Verify required workbench icons are accessible SVG images."""
    for name in ("ClothPattern.svg", "ClothSewing.svg", "ClothSimulation.svg"):
        root = ET.parse(ICON_DIR / name).getroot()
        _check(root.tag.endswith("svg"), f"{name} must use an SVG root element")
        _check(root.attrib.get("viewBox") == "0 0 64 64", f"{name} viewBox must remain stable")
        _check(root.attrib.get("role") == "img", f"{name} must expose image semantics")
        _check(bool(root.attrib.get("aria-label")), f"{name} must have an accessible label")
        _check(
            bool(root.findall(".//*[@fill='currentColor']")),
            f"{name} must support the current theme foreground",
        )
        _check(
            "#333" not in (ICON_DIR / name).read_text(encoding="utf-8"),
            f"{name} must not hard-code the legacy foreground color",
        )


def test_all_workbench_tool_commands_have_svg_icons() -> None:
    """Verify each distinct workbench command maps to an existing SVG icon."""
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
    _check(len(commands) == len(set(commands)), "workbench command identifiers must be unique")
    for command in commands:
        icon = Path(icon_for_command(command))
        _check(icon.is_file(), f"{command} must resolve to an existing icon")
        text = icon.read_text(encoding="utf-8")
        _check("<svg" in text, f"{command} icon must contain SVG markup")
        _check("viewBox=" in text, f"{command} SVG must define a viewport")


def test_semantically_equivalent_commands_share_canonical_icons() -> None:
    """Verify command aliases resolve to the established canonical icon paths."""
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
        _check(alias_path == canonical_path, f"{alias} must share the {canonical} icon")
        _check(alias_path.is_file(), f"canonical icon for {alias} must exist")


def test_distinct_svg_assets_do_not_duplicate_the_same_artwork() -> None:
    """Verify duplicate SVG artwork is shared through canonical command mappings."""
    contents: dict[str, str] = {}
    for icon in sorted(ICON_DIR.glob("*.svg")):
        content = icon.read_text(encoding="utf-8")
        _check(
            content not in contents,
            f"{icon.name} duplicates {contents.get(content)}; share canonical icons "
            "through CommandAdapter.icon_for_command instead",
        )
        contents[content] = icon.name
