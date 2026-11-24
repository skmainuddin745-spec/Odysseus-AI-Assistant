"""
mcp_tool_adapter.py

Bidirectional adapter between Odysseus native ToolBlock schema and the
Model Context Protocol (MCP) tool-call format.

Converts:
  - Odysseus FUNCTION_TOOL_SCHEMAS  →  MCP ListToolsResult-compatible dicts
  - MCP tool call results            →  Odysseus ToolBlock output

This adapter is the bridge referenced in the Claude for Open Source roadmap:
  Phase 1 · MCP refactor — expose Odysseus tools as proper MCP servers so any
  MCP-compatible client (Claude Desktop, Antigravity, Continue, etc.) can call
  them without running a full Odysseus instance.

Usage
-----
    from src.mcp_tool_adapter import OdysseusMCPAdapter

    adapter = OdysseusMCPAdapter()
    mcp_schemas = adapter.to_mcp_tool_list()          # list of MCP tool dicts
    result_text = adapter.mcp_result_to_text(mcp_res)  # normalise call result
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants / type aliases
# ---------------------------------------------------------------------------

_SCHEMA_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


# ---------------------------------------------------------------------------
# OdysseusMCPAdapter
# ---------------------------------------------------------------------------


class OdysseusMCPAdapter:
    """
    Translate between Odysseus-native tool schemas and MCP wire format.

    The MCP specification (2024-11-05) defines tool schemas as JSON Schema
    objects attached to a ``tools/list`` response.  Odysseus stores its own
    schemas in ``FUNCTION_TOOL_SCHEMAS`` (OpenAI function-calling format).
    This adapter bridges the two without coupling either side.

    Parameters
    ----------
    tool_schemas : list[dict] | None
        Override the default ``FUNCTION_TOOL_SCHEMAS``.  Pass ``None`` (default)
        to auto-import from ``src.tool_schemas``.
    """

    def __init__(self, tool_schemas: list[dict] | None = None) -> None:
        if tool_schemas is None:
            from src.tool_schemas import FUNCTION_TOOL_SCHEMAS  # noqa: PLC0415

            tool_schemas = FUNCTION_TOOL_SCHEMAS
        self._schemas: list[dict] = tool_schemas

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_mcp_tool_list(self) -> list[dict[str, Any]]:
        """
        Convert Odysseus FUNCTION_TOOL_SCHEMAS to MCP ``tools/list`` format.

        Returns
        -------
        list[dict]
            One dict per tool, each with keys ``name``, ``description``,
            ``inputSchema`` (JSON Schema draft-07 compatible).
        """
        mcp_tools: list[dict[str, Any]] = []
        for entry in self._schemas:
            fn = entry.get("function", {})
            name = fn.get("name", "")
            description = fn.get("description", "")
            parameters = fn.get("parameters", {})

            # Normalise property types to MCP-safe strings
            safe_params = self._normalise_schema(parameters)

            mcp_tools.append(
                {
                    "name": name,
                    "description": description,
                    "inputSchema": safe_params,
                }
            )
        return mcp_tools

    def mcp_result_to_text(self, mcp_result: Any) -> str:
        """
        Flatten an MCP ``CallToolResult`` to a plain-text string for the
        Odysseus agent loop.

        Handles:
        - ``mcp.types.CallToolResult`` objects (with ``.content`` list)
        - Raw dicts (``{"content": [...]}`` or ``{"text": "..."}`` )
        - Strings passed through directly
        - Anything else: ``json.dumps`` fallback

        Parameters
        ----------
        mcp_result : Any
            The raw result returned from an MCP server tool call.

        Returns
        -------
        str
            UTF-8 safe text the agent loop can read.
        """
        # Already a string — pass through
        if isinstance(mcp_result, str):
            return mcp_result

        # dict with a 'text' shorthand
        if isinstance(mcp_result, dict):
            if "text" in mcp_result:
                return str(mcp_result["text"])
            if "content" in mcp_result:
                return self._extract_content_list(mcp_result["content"])

        # mcp.types.CallToolResult (has .content attribute)
        content_attr = getattr(mcp_result, "content", None)
        if content_attr is not None:
            return self._extract_content_list(content_attr)

        # Fallback
        try:
            return json.dumps(mcp_result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(mcp_result)

    def tool_names(self) -> list[str]:
        """Return just the tool names from the loaded schemas."""
        return [e.get("function", {}).get("name", "") for e in self._schemas]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_schema(schema: dict) -> dict:
        """
        Deep-copy and coerce any non-string ``type`` values to their string
        equivalents so the resulting JSON Schema is MCP-safe.
        """
        if not isinstance(schema, dict):
            return schema  # type: ignore[return-value]
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "type" and isinstance(value, list):
                # JSON Schema allows ``"type": ["string", "null"]`` — keep as-is
                result[key] = value
            elif key == "properties" and isinstance(value, dict):
                result[key] = {
                    prop: OdysseusMCPAdapter._normalise_schema(prop_schema)
                    for prop, prop_schema in value.items()
                }
            elif isinstance(value, dict):
                result[key] = OdysseusMCPAdapter._normalise_schema(value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _extract_content_list(content: Any) -> str:
        """
        Flatten a list of MCP content blocks to plain text.

        Content blocks may be dicts ``{"type": "text", "text": "..."}`` or
        ``mcp.types.TextContent`` / ``mcp.types.ImageContent`` objects.
        """
        if not isinstance(content, list):
            return str(content)
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", json.dumps(block, default=str)))
            else:
                text_attr = getattr(block, "text", None)
                if text_attr is not None:
                    parts.append(str(text_attr))
                else:
                    parts.append(str(block))
        return "\n".join(parts)
