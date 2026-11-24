"""
tests/test_mcp_tool_adapter.py

Pytest smoke tests for OdysseusMCPAdapter.

These tests cover the adapter in isolation — no live MCP server, no running
Odysseus instance, no network calls.  They validate that:

  1. ``to_mcp_tool_list()`` converts a minimal FUNCTION_TOOL_SCHEMAS entry to
     the expected MCP ``tools/list`` shape.
  2. ``mcp_result_to_text()`` flattens each supported result variant to a
     non-empty string.
  3. ``_normalise_schema()`` handles nested property dicts and list-type values
     without raising.
  4. ``tool_names()`` returns the right names in order.

Run with:
    pytest tests/test_mcp_tool_adapter.py -v

Roadmap context (Phase 1 — MCP refactor):
    These tests are the initial smoke-test coverage called out in the High
    Priority section of ROADMAP.md ("Fresh install smoke tests … all need
    coverage").  Future CI will extend to integration tests against a live
    stdio MCP server started via subprocess.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Minimal stub schemas — no src import needed for unit tests
# ---------------------------------------------------------------------------

_STUB_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command (full access)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python",
            "description": "Execute Python code",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to run"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a local file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "encoding": {"type": ["string", "null"], "default": "utf-8"},
                },
                "required": ["path"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    """Return an adapter pre-loaded with stub schemas (no src import)."""
    # Import here so the test can override tool_schemas without touching src/
    from src.mcp_tool_adapter import OdysseusMCPAdapter  # noqa: PLC0415

    return OdysseusMCPAdapter(tool_schemas=_STUB_SCHEMAS)


# ---------------------------------------------------------------------------
# to_mcp_tool_list
# ---------------------------------------------------------------------------


class TestToMcpToolList:
    def test_returns_one_entry_per_schema(self, adapter):
        result = adapter.to_mcp_tool_list()
        assert len(result) == len(_STUB_SCHEMAS)

    def test_entry_has_required_mcp_keys(self, adapter):
        for entry in adapter.to_mcp_tool_list():
            assert "name" in entry, "MCP tool entry must have 'name'"
            assert "description" in entry, "MCP tool entry must have 'description'"
            assert "inputSchema" in entry, "MCP tool entry must have 'inputSchema'"

    def test_names_match_original_schemas(self, adapter):
        mcp_tools = adapter.to_mcp_tool_list()
        expected_names = [s["function"]["name"] for s in _STUB_SCHEMAS]
        actual_names = [t["name"] for t in mcp_tools]
        assert actual_names == expected_names

    def test_input_schema_has_type_object(self, adapter):
        for tool in adapter.to_mcp_tool_list():
            assert tool["inputSchema"].get("type") == "object"

    def test_list_type_preserved(self, adapter):
        """``"type": ["string", "null"]`` must survive normalisation unchanged."""
        mcp_tools = adapter.to_mcp_tool_list()
        read_file_tool = next(t for t in mcp_tools if t["name"] == "read_file")
        enc_schema = read_file_tool["inputSchema"]["properties"]["encoding"]
        assert enc_schema["type"] == ["string", "null"]


# ---------------------------------------------------------------------------
# mcp_result_to_text
# ---------------------------------------------------------------------------


class TestMcpResultToText:
    def test_string_passthrough(self, adapter):
        assert adapter.mcp_result_to_text("hello") == "hello"

    def test_dict_with_text_key(self, adapter):
        result = adapter.mcp_result_to_text({"text": "some output"})
        assert result == "some output"

    def test_dict_with_content_list(self, adapter):
        payload = {
            "content": [
                {"type": "text", "text": "line one"},
                {"type": "text", "text": "line two"},
            ]
        }
        text = adapter.mcp_result_to_text(payload)
        assert "line one" in text
        assert "line two" in text

    def test_object_with_content_attribute(self, adapter):
        """Simulate an mcp.types.CallToolResult-like object."""

        class FakeContent:
            text = "attribute-based text"

        class FakeResult:
            content = [FakeContent()]

        text = adapter.mcp_result_to_text(FakeResult())
        assert "attribute-based text" in text

    def test_integer_fallback(self, adapter):
        """Non-standard result types must not raise."""
        result = adapter.mcp_result_to_text(42)
        assert isinstance(result, str)
        assert "42" in result

    def test_empty_content_list(self, adapter):
        result = adapter.mcp_result_to_text({"content": []})
        assert result == ""

    def test_none_content_item_text(self, adapter):
        """Content block with no text key should not raise."""
        payload = {"content": [{"type": "image", "url": "http://example.com/img.png"}]}
        result = adapter.mcp_result_to_text(payload)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# tool_names
# ---------------------------------------------------------------------------


class TestToolNames:
    def test_returns_all_names(self, adapter):
        names = adapter.tool_names()
        assert names == ["bash", "python", "read_file"]

    def test_returns_list(self, adapter):
        assert isinstance(adapter.tool_names(), list)


# ---------------------------------------------------------------------------
# _normalise_schema (private, tested directly for thoroughness)
# ---------------------------------------------------------------------------


class TestNormaliseSchema:
    def test_simple_passthrough(self, adapter):
        schema = {"type": "string", "description": "a string"}
        result = adapter._normalise_schema(schema)
        assert result == schema

    def test_nested_properties(self, adapter):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
        }
        result = adapter._normalise_schema(schema)
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["count"]["type"] == "integer"

    def test_non_dict_returns_as_is(self, adapter):
        # Edge case: non-dict input (e.g., None, list)
        assert adapter._normalise_schema(None) is None  # type: ignore[arg-type]

    def test_list_type_not_flattened(self, adapter):
        schema = {"type": ["string", "null"]}
        result = adapter._normalise_schema(schema)
        assert result["type"] == ["string", "null"]
