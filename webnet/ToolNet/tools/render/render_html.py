"""
HTML渲染工具 — 将 HTML 内容渲染为 PNG 截图
AI 可通过此工具将格式化的 HTML 内容转为 QQ 可发送的图片
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class RenderHtmlTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "render_html",
            "description": (
                "将HTML内容渲染为PNG图片。当你需要发送格式化的排版内容、表格、"
                "卡片、侧写等美观内容时使用此工具。返回QQ图片格式可直接发送。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "html": {
                        "type": "string",
                        "description": "完整的HTML内容（含内联CSS样式），建议宽度不超过800px",
                    },
                    "width": {
                        "type": "integer",
                        "description": "图片视口宽度（像素），默认800，范围400-1200",
                        "default": 800,
                    },
                },
                "required": ["html"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        html_content = args.get("html", "")
        if not html_content:
            return "错误：请提供 HTML 内容"

        width = min(max(int(args.get("width", 800)), 400), 1200)

        try:
            from utils.render import render_html_direct

            output_path = Path("data/cache/render") / f"render_{hash(html_content) & 0xFFFFFFFF:08x}.png"
            result = await render_html_direct(
                html_content,
                output_path,
                viewport_width=width,
            )
            if result:
                abs_path = str(result.absolute()).replace("\\", "/")
                return f"[CQ:image,file=file:///{abs_path}]"
            return "渲染失败，请稍后重试"

        except ImportError as exc:
            return f"渲染功能需要 Playwright 浏览器: {exc}"
        except Exception as exc:
            logger.error(f"HTML渲染失败: {exc}")
            return f"渲染异常: {str(exc)[:100]}"
