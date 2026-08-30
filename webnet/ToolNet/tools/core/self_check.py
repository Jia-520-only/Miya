"""弥娅一站式体检工具 — self_check

聚合平台状态 / 系统资源 / 定时任务 / 最近报错为一份体检报告。
数据采集在 core/self_check.py（与自检看护器官共用同一套函数）。
"""

from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext


class SelfCheckTool(BaseTool):
    """对弥娅自己做一次全面体检"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "self_check",
            "description": (
                "对弥娅系统自己做一次全面体检: 平台在线状态（谁掉线/延迟/错误次数）、"
                "系统资源（CPU/内存/磁盘）、定时任务失败率、最近警告与错误日志。"
                "当用户问「系统怎么样/自检一下/平台状态」或你想确认自身运行状况时调用；"
                "想看更完整的后台日志细节时可搭配 daemon_logs 工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["all", "platforms", "resources", "tasks", "errors"],
                        "default": "all",
                        "description": "体检报告的分区: all=完整报告(默认), platforms=仅平台, resources=仅资源, tasks=仅定时任务, errors=仅最近报错",
                    },
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        from core.self_check import collect_report, format_report

        section = str(args.get("section", "all") or "all").lower()
        if section not in ("all", "platforms", "resources", "tasks", "errors"):
            section = "all"
        report = await collect_report()
        return format_report(report, section)
