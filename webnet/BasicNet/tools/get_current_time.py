"""
获取当前时间工具
"""
from typing import Dict, Any
from datetime import datetime
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class GetCurrentTime(BaseTool):
    """获取当前时间工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_current_time",
            "description": "获取当前系统时间，支持多种格式。当用户问'现在几点'、'几点了'、'什么时间'、'今天日期'等时必须调用此工具。重要：此工具执行实际查询操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "时间格式：iso(ISO格式), text(文本格式), json(JSON格式)",
                        "enum": ["iso", "text", "json"],
                        "default": "text"
                    },
                    "include_lunar": {
                        "type": "boolean",
                        "description": "是否包含农历",
                        "default": False
                    },
                    "include_almanac": {
                        "type": "boolean",
                        "description": "是否包含黄历",
                        "default": False
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行获取时间

        Args:
            args: 格式配置
            context: 执行上下文

        Returns:
            时间信息字符串
        """
        fmt = args.get("format", "text")
        include_lunar = args.get("include_lunar", False)
        include_almanac = args.get("include_almanac", False)

        now = datetime.now()

        if fmt == "iso":
            return now.isoformat()

        elif fmt == "json":
            return f"""{{"datetime": "{now.isoformat()}", "timestamp": {int(now.timestamp())}}}"""

        else:  # text format
            result = f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"

            if include_lunar:
                # 简化农历（实际应集成lunar库）
                result += "\n农历: (需要安装zhdate库)"

            if include_almanac:
                result += "\n黄历: (需要集成日历API)"

            return result
