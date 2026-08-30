"""
miya-mineradio MCP Server entry point.
"""

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .service import service


def create_server() -> Server:
    server = Server("miya-mineradio")

    @server.list_tools()
    async def list_tools():
        return service.get_tool_definitions()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> str:
        return await service.handle_tool_call(name, arguments)

    return server


async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
