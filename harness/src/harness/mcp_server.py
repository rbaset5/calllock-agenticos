from __future__ import annotations

import json
import os
from typing import Any

import anyio
import jsonschema
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from harness.tool_registry import get_tool, list_tools


SERVER_NAME = "calllock-ceo-gateway"
SERVER_VERSION = "0.1.0"
WRITE_ENABLE_ENV = "CALLLOCK_GATEWAY_WRITE_ENABLED"
class ToolRegistryError(RuntimeError):
    pass


class MutatingToolDisabledError(ToolRegistryError):
    pass


class ToolArgumentError(ToolRegistryError):
    pass


def is_write_enabled() -> bool:
    return os.getenv(WRITE_ENABLE_ENV) == "1"


def list_mcp_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.json_schema,
        )
        for tool in list_tools()
    ]


def invoke_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    tool = get_tool(name)
    payload = arguments or {}
    try:
        jsonschema.validate(payload, tool.json_schema)
    except jsonschema.ValidationError as exc:
        raise ToolArgumentError(exc.message) from exc
    if tool.mutating and not is_write_enabled():
        raise MutatingToolDisabledError(
            f"{name} is mutating and requires {WRITE_ENABLE_ENV}=1 for this MCP session."
        )
    result = tool.callable(**payload)
    return json.loads(json.dumps(result))


def build_server() -> Server:
    server = Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=(
            "CallLock CEO gateway MCP server. Read-only tools are always available. "
            f"Mutating tools require {WRITE_ENABLE_ENV}=1."
        ),
    )

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return list_mcp_tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
        return invoke_tool(name, arguments)

    return server


async def serve_stdio() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(NotificationOptions(), {}),
                instructions=server.instructions,
            ),
        )


def main() -> None:
    anyio.run(serve_stdio)


if __name__ == "__main__":
    main()
