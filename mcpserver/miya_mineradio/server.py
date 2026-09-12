"""
miya-mineradio MCP Server entry point.
"""

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .service import service


def create_server() -> Server:
    server = Server("miya-mineradio")

    @server.list_tools()
    async def list_tools():
        # mcp 1.x 的 list_tools 必须返回 Tool 对象：
        # 返回 dict 会在 server.lowlevel 的 tool.name 处抛 AttributeError。
        return [
            Tool(
                name=item["name"],
                description=item.get("description", ""),
                inputSchema=item.get("inputSchema")
                or {"type": "object", "properties": {}, "required": []},
            )
            for item in service.get_tool_definitions()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        # service 返回 JSON 字符串，必须包成 TextContent；
        # 直接返回 str 会被 server.lowlevel 按可迭代对象逐字符拆成 content。
        result = await service.handle_tool_call(name, arguments)
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
        return [TextContent(type="text", text=text)]

    return server


async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
