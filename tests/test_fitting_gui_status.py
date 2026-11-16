# Copyright (C) 2026 FreeCAD Cloth contributors
"""Focused semantic-status tests for viewport Arrange / Fit feedback."""

from types import SimpleNamespace

from freecad_cloth.avatar.FittingGui import FittingTaskPanel
from freecad_cloth.common import UiDesign


def test_fitting_status_distinguishes_placement_outcomes(monkeypatch):
    """Show success and failure distinctly while keeping preview guidance informational."""
    panel = FittingTaskPanel.__new__(FittingTaskPanel)
    panel.status = object()
    updates = []

    def set_status(label, message, *, state="info"):
        updates.append((label, message, state))

    monkeypatch.setattr(UiDesign, "set_status", set_status)

    FittingTaskPanel._set_status(panel, "Snapped Front to WaistAnchor.")
    FittingTaskPanel._set_status(panel, "Placement blocked — target reference is stale.")
    FittingTaskPanel._set_status(panel, "Snap preview: Front → WaistAnchor.")
    FittingTaskPanel._set_status(panel, "Invalid source selection.", state="warning")

    assert updates == [
        (panel.status, "Snapped Front to WaistAnchor.", "success"),
        (panel.status, "Placement blocked — target reference is stale.", "error"),
        (panel.status, "Snap preview: Front → WaistAnchor.", "info"),
        (panel.status, "Invalid source selection.", "warning"),
    ]
