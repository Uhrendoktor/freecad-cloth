"""Headless contract checks for Cloth workbench icon assets."""
from pathlib import Path
import xml.etree.ElementTree as ET

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
