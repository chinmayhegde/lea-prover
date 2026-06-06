"""LeaError -> HTTP status/body mapping (design §4 table)."""

import pytest

from lea.errors import (
    ConfigFormatError,
    InvalidConfigValueError,
    McpError,
    MissingConfigKeyError,
    SkillError,
    ToolError,
    UnknownConfigKeyError,
)
from lea_api import errors


@pytest.mark.parametrize("exc, status", [
    (ConfigFormatError("x"), 400),
    (UnknownConfigKeyError("x"), 422),
    (MissingConfigKeyError("x"), 422),
    (InvalidConfigValueError("x"), 422),
    (SkillError("x"), 422),
    (ToolError("x"), 422),
    (McpError("x"), 424),
])
def test_status_mapping(exc, status):
    assert errors.status_for(exc) == status


def test_body_extracts_field():
    body = errors.to_body(InvalidConfigValueError("'model.stream' must be a boolean, got str."))
    assert body["type"] == "InvalidConfigValueError"
    assert body["field"] == "model.stream"


def test_body_without_field():
    body = errors.to_body(ConfigFormatError("Config must be a mapping, got list."))
    assert "field" not in body
