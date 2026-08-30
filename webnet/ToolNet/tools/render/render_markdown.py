"""
Markdown渲染工具 — 将 Markdown 内容渲染为精美 PNG 截图
AI 可通过此工具将 Markdown 格式的内容（如报告、总结、分析结果）转为图片
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class RenderMarkdownTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "render_markdown",
            "description": (
                "将Markdown内容渲染为精美PNG图片。当需要发送格式化的分析报告、总结、"
                "侧写、帮助文档、FAQ等富文本内容时使用此工具。返回QQ图片格式。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Markdown格式的文本内容",
                    },
                    "title": {
                        "type": "string",
                        "description": "可选标题，显示在页面顶部",
                    },
                    "width": {
                        "type": "integer",
                        "description": "图片宽度（像素），默认800",
                        "default": 800,
                    },
                },
                "required": ["content"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        markdown_content = args.get("content", "")
        if not markdown_content:
            return "错误：请提供 Markdown 内容"

        title = args.get("title", "")
        width = min(max(int(args.get("width", 800)), 400), 1200)

        try:
            from utils.render import render_markdown_to_image

            content_hash = abs(hash(markdown_content)) & 0xFFFFFFFF
            output_path = Path("data/cache/render") / f"md_{content_hash:08x}.png"
            result = await render_markdown_to_image(
                markdown_content,
                output_path,
                viewport_width=width,
                title=title,
            )
            if result:
                abs_path = str(result.absolute()).replace("\\", "/")
                return f"[CQ:image,file=file:///{abs_path}]"
            return "渲染失败，请稍后重试"

        except ImportError as exc:
            return f"渲染功能需要 Playwright 浏览器: {exc}"
        except Exception as exc:
            logger.error(f"Markdown渲染失败: {exc}")
            return f"渲染异常: {str(exc)[:100]}"
