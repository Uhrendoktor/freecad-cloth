# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compatibility exports for the historical GarmentDocument import path."""

from ..garment_document import (
    GARMENT_GROUPS,
    GARMENT_ROOT_NAME,
    GARMENT_SCHEMA_VERSION,
    FreeCADDocumentObjectProtocol,
    create_garment_document,
    ensure_fabric_material,
    ensure_garment_hierarchy,
    garment_group,
    garment_root,
    garment_structure,
    link_garment_object,
)

__all__ = (
    "GARMENT_GROUPS",
    "GARMENT_ROOT_NAME",
    "GARMENT_SCHEMA_VERSION",
    "FreeCADDocumentObjectProtocol",
    "create_garment_document",
    "ensure_fabric_material",
    "ensure_garment_hierarchy",
    "garment_group",
    "garment_root",
    "garment_structure",
    "link_garment_object",
)
