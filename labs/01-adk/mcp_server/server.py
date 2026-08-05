"""Cymbal ops tools served as a local stdio MCP server.

This server wraps the ops tools in `tools.py` as MCP tools and serves them
over stdio, from a subprocess that the agent launches on your own machine.
The tool functions are defined in this package, in `mcp_server/tools.py`, and
are exposed here over MCP, so the agent gets access only through MCP and never
by importing the functions. Nothing here needs a cloud project.

The agent normally launches the server through StdioConnectionParams. You can
also run it by hand.

    python mcp_server/server.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# The tools are defined in this MCP server package, in mcp_server/tools.py,
# and not in the agent.
sys.path.insert(0, os.path.dirname(__file__))

import mcp.types as types  # noqa: E402
from mcp.server.lowlevel import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

from tools import (  # noqa: E402
    get_error_rate,
    get_service_health,
    list_services,
)

SERVER_NAME = "cymbal-ops-local"


def build_server() -> Server:
    """Builds the MCP server that exposes the Cymbal ops tools over stdio.

    Returns:
        A low-level MCP `Server` with the three ops tools registered.
    """
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        """Advertises the tool catalogue to the connected MCP client."""
        return [
            types.Tool(
                name="list_services",
                description="List the Cymbal services Nimbus can observe.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="get_service_health",
                description="Current health summary for one Cymbal service.",
                inputSchema={
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                },
            ),
            types.Tool(
                name="get_error_rate",
                description=(
                    "Error rate + severity for a service over a window."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "window": {"type": "string"},
                    },
                    "required": ["service"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.ContentBlock]:
        """Dispatches an MCP tool call to the local Python function."""
        if name == "list_services":
            result = list_services()
        elif name == "get_service_health":
            result = get_service_health(arguments.get("service", ""))
        elif name == "get_error_rate":
            result = get_error_rate(
                arguments.get("service", ""),
                arguments.get("window", "1h"),
            )
        else:
            raise ValueError(f"unknown tool: {name}")
        return [types.TextContent(type="text", text=json.dumps(result))]

    return server


async def main() -> None:
    """Serves the MCP tools on stdio until the client disconnects."""
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
