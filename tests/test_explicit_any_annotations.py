"""Tests for explicit Any annotation rejection across Python type syntax."""

from __future__ import annotations

import pytest

from tools.ci.check_explicit_any_annotations import explicit_any_violations


@pytest.mark.parametrize(
    "source",
    (
        "from typing import Any\nvalue: Any\n",
        "import typing\nvalue: dict[str, typing.Any]\n",
        "import typing as t\nvalue: list[t.Any]\n",
        "from typing import Any as Dynamic\nclass Model:\n    payload: Dynamic\n",
        "from typing_extensions import Any as Dynamic\nvalue = list[Dynamic]\n",
        "from typing import *\nvalue: Any\n",
        "from typing import Any\nAlias = dict[str, Any]\n",
    ),
)
def test_explicit_any_references_are_rejected(source: str) -> None:
    """Reject direct, renamed, qualified, wildcard, and type-alias Any usage."""
    assert explicit_any_violations(source)


@pytest.mark.parametrize(
    "source",
    (
        "from typing import Any\ndef render(value: 'Any') -> 'list[Any]':\n    return [value]\n",
        "import typing as t\ndef render(value: 't.Any') -> None:\n    return None\n",
        "from typing import Any as Dynamic\ndef render(value: 'Dynamic') -> None:\n    return None\n",
        "from typing import Any\ndef render(value): # type: (Any) -> Any\n    return value\n",
        "from typing import Any\nvalue = 1 # type: Any\n",
    ),
)
def test_stringified_annotations_and_type_comments_are_rejected(source: str) -> None:
    """Inspect quoted forward references and legacy type comments as type syntax."""
    assert explicit_any_violations(source)


def test_ordinary_strings_are_not_parsed_as_type_syntax() -> None:
    """Leave ordinary user-facing strings alone when they contain the token Any."""
    source = "from typing import Any\nmessage = 'Any'\ncaption = 'typing.Any'\n"
    assert explicit_any_violations(source) == ()


def test_concrete_types_and_protocols_are_accepted() -> None:
    """Allow concrete aliases and structural Protocols without unrestricted Any."""
    source = '''
from typing import Protocol, TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None | list[object] | dict[str, object]

class Point(Protocol):
    x: float
    y: float

def consume(value: object) -> bool:
    return hasattr(value, "x") and hasattr(value, "y")
'''
    assert explicit_any_violations(source) == ()


def test_parse_errors_fail_closed() -> None:
    """Do not silently skip source when the AST parser cannot read it."""
    result = explicit_any_violations("value: Any =\n", "broken.py")
    assert result and result[0].startswith("broken.py:1: invalid Python syntax")
