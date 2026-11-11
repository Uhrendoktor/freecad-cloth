# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for the native Garment document hierarchy."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.support.assertions import require as _require

from freecad_cloth.common.GarmentDocument import (
    GARMENT_GROUPS,
    FreeCADDocumentObjectProtocol,
    create_garment_document,
    ensure_garment_hierarchy,
    garment_group,
    garment_structure,
    link_garment_object,
)

_EXPECTED_RECOMPUTATIONS = 2


class _FakeObject:
    """Dynamic native-object stand-in for hierarchy and property operations."""

    def __init__(self, object_type: str, name: str) -> None:
        """Create a named native-object stand-in with mock property methods.

        Args:
            object_type: FreeCAD TypeId returned by this fake object.
            name: Internal document name for the fake object.
        """
        self.Name = name
        self.TypeId = object_type
        self.Label = name
        self.PropertiesList: list[str] = []
        self.Group: list[FreeCADDocumentObjectProtocol] = []
        self._property_groups: dict[str, tuple[str, str]] = {}
        self.addProperty: Callable[[str, str, str], FreeCADDocumentObjectProtocol] = (
            self._add_property
        )
        self.addObject: Callable[[FreeCADDocumentObjectProtocol], None] = self._add_object

    def _add_property(
        self,
        property_type: str,
        name: str,
        group: str,
    ) -> _FakeObject:
        """Register a property through the fake native-object API.

        Args:
            property_type: FreeCAD property type passed by the adapter.
            name: Persisted property name.
            group: Property-editor group.

        Returns:
            This fake object after recording the property.
        """
        self._record_property(property_type, name, group)
        return self

    def _record_property(self, property_type: str, name: str, group: str) -> None:
        """Record a native property declaration for assertions.

        Args:
            property_type: FreeCAD property type passed to addProperty.
            name: Persisted property name.
            group: Property editor group.
        """
        self.PropertiesList.append(name)
        self._property_groups[name] = (property_type, group)

    def _add_object(self, child: FreeCADDocumentObjectProtocol) -> None:
        """Attach one child through the fake native-container API.

        Args:
            child: Document object being added to the container.
        """
        self._record_child(child)

    def _record_child(self, child: FreeCADDocumentObjectProtocol) -> None:
        """Append a child object to the fake native container.

        Args:
            child: Document object being added to the container.
        """
        self.Group.append(child)


class _FakeDocument:
    """Document stand-in implementing the dynamic methods used by the adapter."""

    def __init__(self) -> None:
        """Initialize the document with callable runtime API stand-ins."""
        self.Objects: list[FreeCADDocumentObjectProtocol] = []
        self.recompute_calls = 0
        self.addObject: Callable[[str, str], FreeCADDocumentObjectProtocol] = self._add_object

    def _add_object(self, object_type: str, name: str) -> _FakeObject:
        """Create and retain a fake document object.

        Args:
            object_type: FreeCAD TypeId passed to addObject.
            name: Internal name passed to addObject.

        Returns:
            The created object appended to the document.
        """
        obj = _FakeObject(object_type, name)
        self.Objects.append(obj)
        return obj

    def recompute(self) -> None:
        """Record a native document recomputation."""
        self.recompute_calls += 1


class _FakeApplication:
    """Application stand-in for the injected FreeCAD document factory."""

    def __init__(self, document: _FakeDocument) -> None:
        """Retain the document returned by the next creation request.

        Args:
            document: Fake native document to return to the adapter.
        """
        self.document = document
        self.last_document_name: str | None = None

    def new_document(self, name: str) -> _FakeDocument:
        """Return the retained fake document for the requested internal name.

        Args:
            name: Internal name supplied to the host application.

        Returns:
            Retained fake document instance.
        """
        self.last_document_name = name
        return self.document


def test_hierarchy_creation_is_idempotent_and_populates_fabric_defaults() -> None:
    """Create the five standard groups once and persist a default fabric material."""
    document = _FakeDocument()
    root = ensure_garment_hierarchy(document, "Cloth Project")
    reused_root = ensure_garment_hierarchy(document, "Updated Project Label")
    structure = garment_structure(document)
    groups = structure["groups"]
    fabric = garment_group(document, "Fabric")
    fabric_children = tuple(getattr(fabric, "Group", ()))
    _require(
        condition=root is reused_root,
        message="A repeated hierarchy repair must reuse the persisted Garment root.",
    )
    _require(
        condition=tuple(groups) == GARMENT_GROUPS,
        message="The native Garment hierarchy must preserve all five standard groups.",
    )
    _require(
        condition=getattr(root, "Label", "") == "Updated Project Label",
        message="Hierarchy repair must refresh the user-facing root label.",
    )
    fabric_material_count = sum(
        str(getattr(child, "GarmentRole", "")) == "FabricMaterial" for child in fabric_children
    )
    _require(
        condition=fabric_material_count == 1,
        message="Hierarchy repair must retain one default fabric material.",
    )
    _require(
        condition=document.recompute_calls == _EXPECTED_RECOMPUTATIONS,
        message="Each hierarchy repair must recompute the owning document.",
    )


def test_object_linking_is_a_standalone_no_op_and_rejects_unknown_roles() -> None:
    """Keep standalone object creation valid and reject unsupported roles after setup."""
    document = _FakeDocument()
    obj = _FakeObject("Mesh::Feature", "PatternPiece")
    _require(
        condition=link_garment_object(obj, "PatternPiece", document) is obj,
        message="Objects must remain usable when no Garment root has been created.",
    )
    _require(
        condition=not obj.PropertiesList,
        message="Linking without a Garment root must not mutate object properties.",
    )
    ensure_garment_hierarchy(document)
    with pytest.raises(ValueError, match="unsupported Garment hierarchy role"):
        link_garment_object(obj, "UnsupportedRole", document)


def test_document_creation_accepts_an_injected_host_module() -> None:
    """Create a document through an explicit application dependency in headless tests."""
    document = _FakeDocument()
    application = _FakeApplication(document)

    created = create_garment_document(app_module=application)

    _require(
        condition=created is document,
        message="Document creation must return the injected application's new document.",
    )
    _require(
        condition=application.last_document_name == "Garment",
        message="Document creation must preserve the requested internal document name.",
    )
