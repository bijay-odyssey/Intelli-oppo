"""Strict-mode schema conversion.

Groq's json_schema strict mode rejects schemas that omit
`additionalProperties: false` or leave any property optional. Pydantic emits
both by default, so `strict_schema` has to correct them everywhere, including
inside `$defs` and array items.
"""

from pydantic import BaseModel, Field

from intelli_oppo.llm import strict_schema
from intelli_oppo.reason import VerdictOut


class Inner(BaseModel):
    a: str
    b: int = 3


class Outer(BaseModel):
    name: str = Field(default="x")
    items: list[Inner]


def _objects(node):
    """Every object schema anywhere in the tree."""
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield node
        for value in node.values():
            yield from _objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _objects(item)


def test_every_object_forbids_extra_properties():
    schema = strict_schema(Outer)
    found = list(_objects(schema))
    assert found
    assert all(obj["additionalProperties"] is False for obj in found)


def test_every_property_is_required():
    schema = strict_schema(Outer)
    for obj in _objects(schema):
        assert set(obj["required"]) == set(obj["properties"])


def test_defaults_are_stripped():
    """Strict mode rejects `default`; pydantic emits it for any field with one."""

    def has_default(node) -> bool:
        if isinstance(node, dict):
            return "default" in node or any(has_default(v) for v in node.values())
        if isinstance(node, list):
            return any(has_default(i) for i in node)
        return False

    assert not has_default(strict_schema(Outer))


def test_verdict_schema_is_strict_ready():
    schema = strict_schema(VerdictOut)
    root = schema
    assert root["additionalProperties"] is False
    assert "winner" in root["required"]
    assert "metric" in root["required"]
    assert "pivot" in root["required"]
