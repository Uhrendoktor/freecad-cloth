# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless contract checks for Cloth workbench icon assets."""

import importlib
from pathlib import Path

from defusedxml import ElementTree

from tests.support.assertions import require, require_contains, require_not_none

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"


def test_workbench_icons_are_valid_scalable_assets() -> None:
    """Validate scalable icon metadata and reject hard-coded legacy colors."""
    for name in ("ClothPattern.svg", "ClothSewing.svg", "ClothSimulation.svg"):
        icon_path = ICON_DIR / name
        root = require_not_none(
            ElementTree.parse(icon_path).getroot(),
            message=f"{name} did not parse to an SVG root element.",
        )
        require(
            condition=root.tag.endswith("svg"),
            message=f"{name} must have an SVG root element.",
        )
        require(
            condition=root.attrib.get("viewBox") == "0 0 64 64",
            message=f"{name} must expose the expected 64-by-64 viewBox.",
        )
        require(
            condition=root.attrib.get("role") == "img",
            message=f"{name} must expose its image role.",
        )
        require(
            condition=bool(root.attrib.get("aria-label")),
            message=f"{name} must provide an accessible label.",
        )
        require(
            condition=bool(root.findall(".//*[@fill='currentColor']")),
            message=f"{name} should use currentColor for theme-aware shapes.",
        )
        require_contains(
            source=icon_path.read_text(encoding="utf-8"),
            fragment="#333",
            message=f"{name} must not embed the legacy #333 color.",
        )


def test_all_workbench_tool_commands_have_svg_icons() -> None:
    """Ensure every declared tool command maps to a readable SVG icon."""
    icon_for_command = importlib.import_module(
        "freecad_cloth.common.CommandAdapter"
    ).icon_for_command
    module_names = (
        "freecad_cloth.pattern.PatternCommands",
        "freecad_cloth.pattern.PatternMarks",
        "freecad_cloth.simulation.SimulationCommands",
        "freecad_cloth.simulation.DrapeCommands",
        "freecad_cloth.sewing.SewingCommands",
        "freecad_cloth.avatar.FittingCommands",
        "freecad_cloth.avatar.AvatarCommands",
    )
    modules = tuple(importlib.import_module(name) for name in module_names)
    commands = [command for module in modules for command in module.COMMANDS]
    require(
        condition=len(commands) == len(set(commands)),
        message="Workbench command identifiers must be unique across command modules.",
    )
    for command in commands:
        icon = Path(icon_for_command(command))
        require(
            condition=icon.is_file(),
            message=f"Command {command!r} must map to an existing icon.",
        )
        text = icon.read_text(encoding="utf-8")
        require_contains(
            source=text,
            fragment="<svg",
            message=f"Icon for {command!r} must contain an SVG root element.",
        )
        require_contains(
            source=text,
            fragment="viewBox=",
            message=f"Icon for {command!r} must provide a viewBox.",
        )


def test_semantically_equivalent_commands_share_canonical_icons() -> None:
    """Keep equivalent command aliases mapped to their shared canonical icon."""
    icon_for_command = importlib.import_module(
        "freecad_cloth.common.CommandAdapter"
    ).icon_for_command
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
        require(
            condition=alias_path == canonical_path,
            message=f"Alias {alias!r} should share the icon for {canonical!r}.",
        )
        require(
            condition=alias_path.is_file(),
            message=f"Canonical icon for alias {alias!r} must exist.",
        )


def test_distinct_svg_assets_do_not_duplicate_the_same_artwork() -> None:
    """Reject byte-identical SVGs when a canonical icon can be reused instead."""
    contents: dict[str, str] = {}
    for icon in sorted(ICON_DIR.glob("*.svg")):
        content = icon.read_text(encoding="utf-8")
        require(
            condition=content not in contents,
            message=(
                f"{icon.name} duplicates {contents.get(content)}; share canonical icons "
                "through CommandAdapter.icon_for_command instead."
            ),
        )
        contents[content] = icon.name
