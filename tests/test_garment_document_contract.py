# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for the native Garment document hierarchy."""

from types import ModuleType
from unittest.mock import Mock

import pytest

from freecad_cloth.common.GarmentDocument import (
    GARMENT_GROUPS,
    create_garment_document,
    ensure_garment_hierarchy,
    garment_group,
    garment_structure,
    link_garment_object,
)
from tests.support.assertions import require


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
        self.Group: list[object] = []
        self._property_groups: dict[str, tuple[str, str]] = {}
        self.addProperty = Mock(side_effect=self._record_property)
        self.addObject = Mock(side_effect=self._record_child)

    def _record_property(self, property_type: str, name: str, group: str) -> None:
        """Record a native property declaration for assertions.

        Args:
            property_type: FreeCAD property type passed to addProperty.
            name: Persisted property name.
            group: Property editor group.
        """
        self.PropertiesList.append(name)
        self._property_groups[name] = (property_type, group)

    def _record_child(self, child: object) -> None:
        """Append a child object to the fake native container.

        Args:
            child: Document object being added to the container.
        """
        self.Group.append(child)


class _FakeDocument:
    """Document stand-in implementing the dynamic methods used by the adapter."""

    def __init__(self) -> None:
        """Initialize the document with callable runtime API stand-ins."""
        self.Objects: list[_FakeObject] = []
        self.addObject = Mock(side_effect=self._create_object)
        self.getObject = Mock(side_effect=self._get_object)
        self.recompute = Mock()

    def _create_object(self, object_type: str, name: str) -> _FakeObject:
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

    def _get_object(self, name: str) -> _FakeObject | None:
        """Find a fake document object by internal name.

        Args:
            name: Internal object name requested by getObject.

        Returns:
            The matching object, or None if no object has that name.
        """
        return next((obj for obj in self.Objects if obj.Name == name), None)


def test_hierarchy_creation_is_idempotent_and_populates_fabric_defaults() -> None:
    """Create the five standard groups once and persist a default fabric material."""
    document = _FakeDocument()
    root = ensure_garment_hierarchy(document, "Cloth Project")
    reused_root = ensure_garment_hierarchy(document, "Updated Project Label")
    structure = garment_structure(document)
    groups = structure["groups"]
    fabric = garment_group(document, "Fabric")
    fabric_children = tuple(getattr(fabric, "Group", ()))
    require(
        condition=root is reused_root,
        message="A repeated hierarchy repair must reuse the persisted Garment root.",
    )
    require(
        condition=tuple(groups) == GARMENT_GROUPS,
        message="The native Garment hierarchy must preserve all five standard groups.",
    )
    require(
        condition=getattr(root, "Label", "") == "Updated Project Label",
        message="Hierarchy repair must refresh the user-facing root label.",
    )
    fabric_material_count = sum(
        str(getattr(child, "GarmentRole", "")) == "FabricMaterial" for child in fabric_children
    )
    require(
        condition=fabric_material_count == 1,
        message="Hierarchy repair must retain one default fabric material.",
    )
    require(
        condition=document.recompute.call_count == 2,
        message="Each hierarchy repair must recompute the owning document.",
    )


def test_object_linking_is_a_standalone_no_op_and_rejects_unknown_roles() -> None:
    """Keep standalone object creation valid and reject unsupported roles after setup."""
    document = _FakeDocument()
    obj = _FakeObject("Mesh::Feature", "PatternPiece")
    require(
        condition=link_garment_object(obj, "PatternPiece", document) is obj,
        message="Objects must remain usable when no Garment root has been created.",
    )
    require(
        condition=not obj.PropertiesList,
        message="Linking without a Garment root must not mutate object properties.",
    )
    ensure_garment_hierarchy(document)
    with pytest.raises(ValueError, match="unsupported Garment hierarchy role"):
        link_garment_object(obj, "UnsupportedRole", document)


def test_document_creation_accepts_an_injected_host_module() -> None:
    """Create a document through an explicit application dependency in headless tests."""
    document = _FakeDocument()
    freecad_module = ModuleType("FreeCAD")
    new_document = Mock(return_value=document)
    setattr(freecad_module, "newDocument", new_document)

    created = create_garment_document(app_module=freecad_module)

    require(
        condition=created is document,
        message="Document creation must return the injected application's new document.",
    )
    require(
        condition=new_document.call_args.args == ("Garment",),
        message="Document creation must preserve the requested internal document name.",
    )
