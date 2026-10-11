"""Tests for the Pydantic data-model enforcement policy."""

from __future__ import annotations

from tools.ci import check_pydantic_models
from tools.ci.check_pydantic_models import (
    repository_violations,
    serialization_exception_is_justified,
    standard_dataclass_decorators,
)


def test_stdlib_dataclass_decorator_is_rejected() -> None:
    """Require runtime validation rather than an unchecked stdlib record."""
    source = "from dataclasses import dataclass\n@dataclass\nclass Record:\n    value: int\n"
    result = standard_dataclass_decorators(source, "sample.py")
    assert result == (
        "sample.py:2: Record uses stdlib dataclasses; "
        "use pydantic.dataclasses.dataclass or pydantic.BaseModel",
    )


def test_aliased_stdlib_dataclass_decorator_is_rejected() -> None:
    """Resolve aliases for both the decorator and its module."""
    source = "import dataclasses as dc\n@dc.dataclass(frozen=True)\nclass Record:\n    value: int\n"
    assert standard_dataclass_decorators(source, "sample.py")


def test_pydantic_dataclass_is_accepted() -> None:
    """Pydantic dataclasses and BaseModel records satisfy the policy."""
    source = (
        "from pydantic.dataclasses import dataclass as model_record\n"
        "@model_record(frozen=True)\n"
        "class Record:\n"
        "    value: int\n"
    )
    assert standard_dataclass_decorators(source, "sample.py") == ()


def test_freecad_exception_requires_a_serialization_incompatibility_reason(
    monkeypatch,
) -> None:
    """Do not let generic convenience/performance notes bypass Pydantic."""
    path = "freecad_cloth/example.py"
    monkeypatch.setattr(
        check_pydantic_models,
        "FREECAD_SERIALIZATION_EXCEPTIONS",
        {
            path: (
                "FreeCAD internal serialization is incompatible with this Pydantic field.",
                "tests/test_pydantic_models_policy.py#test_freecad_exception_requires_a_serialization_incompatibility_reason",
            )
        },
    )
    assert serialization_exception_is_justified(path)
    monkeypatch.setattr(
        check_pydantic_models,
        "FREECAD_SERIALIZATION_EXCEPTIONS",
        {
            path: (
                "Performance overhead",
                "tests/test_pydantic_models_policy.py#test_freecad_exception_requires_a_serialization_incompatibility_reason",
            )
        },
    )
    assert not serialization_exception_is_justified(path)


def test_all_production_records_follow_the_pydantic_policy() -> None:
    """Prevent regressions across the whole production package."""
    assert repository_violations() == ()
