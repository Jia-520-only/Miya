"""守护进程日志自检工具 — 让弥娅自己查看后台终端内容

读取 core/log_stream 的日志环形缓冲（与前端「后台终端」页面同源），
缓冲为空时回退读 logs/daemon.log 尾部。
"""

from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

_WARN_PLUS = {"WARNING", "ERROR", "CRITICAL"}
_ERROR_PLUS = {"ERROR", "CRITICAL"}

# 单行截断长度与条数上限 — 控制返回体积，避免撑爆弥娅的上下文
_LINE_CLIP = 200
_MAX_LIMIT = 100


def _clip(text: str, width: int = _LINE_CLIP) -> str:
    text = text.rstrip()
    return text if len(text) <= width else text[:width] + "…"


class DaemonLogsTool(BaseTool):
    """查看守护进程后台终端日志（弥娅自检用）"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "daemon_logs",
            "description": (
                "查看弥娅守护进程的后台终端日志，用于系统自检与运行状态排查。"
                "默认只看 WARNING 及以上级别、只取最新 30 条（每行截断 200 字符），足够定位问题且不撑爆上下文；"
                "需要更早的日志再用 limit/keyword 缩小范围查找。"
                "当用户让你「看看日志/自检一下/系统怎么样」，或你自己想确认后台运行状况时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["all", "warning", "error"],
                        "default": "warning",
                        "description": "级别过滤: all=全部日志, warning=警告和错误(默认), error=仅错误",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 30,
                        "description": "最多返回最近多少条日志 (1-100)",
                    },
                    "keyword": {
                        "type": "string",
                        "default": "",
                        "description": "可选，按关键词过滤日志内容",
                    },
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        level = str(args.get("level", "warning")).lower()
        if level not in ("all", "warning", "error"):
            level = "warning"
        try:
            limit = int(args.get("limit", 30))
        except (TypeError, ValueError):
            limit = 30
        limit = max(1, min(limit, _MAX_LIMIT))
        keyword = str(args.get("keyword", "") or "").strip().lower()

        from core.log_stream import get_log_buffer

        entries, _ = get_log_buffer().snapshot(2000)
        if not entries:
            return self._fallback_from_file(limit)

        stats: Dict[str, int] = {}
        for e in entries:
            stats[e["level"]] = stats.get(e["level"], 0) + 1

        def match(e: Dict) -> bool:
            if level == "warning" and e["level"] not in _WARN_PLUS:
                return False
            if level == "error" and e["level"] not in _ERROR_PLUS:
                return False
            if keyword and keyword not in e["text"].lower() and keyword not in e["name"].lower():
                return False
            return True

        matched = [e for e in entries if match(e)][-limit:]
        stat_line = " | ".join(f"{k} {v}" for k, v in sorted(stats.items()))
        header = [
            "🖥 弥娅守护进程日志 · 自检",
            "─" * 28,
            f"缓冲 {len(entries)} 条 | 匹配 {len(matched)} 条 | 统计: {stat_line}",
        ]

        if not matched:
            has_issues = any(stats.get(lv) for lv in _WARN_PLUS)
            if level == "warning" and not has_issues:
                return "\n".join(header) + "\n\n✨ 没有 WARNING 及以上级别的日志，后台一切正常～"
            return "\n".join(header) + f"\n\n没有匹配的日志 (level={level}" + (f", keyword={keyword})" if keyword else ")")

        lines = ["\n".join(header), "─" * 28]
        for e in matched:
            ts = e["ts"].replace("T", " ")[5:19]
            lines.append(_clip(f"[{ts}] {e['text']}"))
        return "\n".join(lines)

    @staticmethod
    def _fallback_from_file(limit: int) -> str:
        """缓冲为空时（如非守护进程模式）回退读 logs/daemon.log 尾部"""
        try:
            from pathlib import Path

            from core.path_resolver import get_logs_dir

            log_file = Path(get_logs_dir()) / "daemon.log"
            if log_file.exists():
                text = log_file.read_text(encoding="utf-8", errors="ignore")
                tail = [ln for ln in text.splitlines() if ln.strip()][-limit:]
                if tail:
                    return (
                        "🖥 弥娅守护进程日志 (来自 logs/daemon.log 文件回退)\n"
                        + "─" * 28 + "\n" + "\n".join(tail)
                    )
        except Exception:
            pass
        return "日志缓冲为空，且未找到可读的日志文件（可能当前不在守护进程模式运行）"
