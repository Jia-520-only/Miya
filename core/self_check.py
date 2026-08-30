"""
弥娅自检报告 — 体检数据采集与格式化

聚合五类数据，供三处消费:
  1. self_check 工具（弥娅对话时"你问她答"）
  2. 自检看护器官 MiyaSelfCareOrgan（巡检/告警/每日简报）
  3. 时间感知注入（decision_hub 读 self_care_last.json，弥娅"知道自己在运行"）

纯函数、无状态；数据源: PlatformRegistry / psutil / data/tasks.db / core.log_stream。
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.SelfCheck")

_PROJECT_ROOT = Path(__file__).parent.parent
_TASKS_DB = _PROJECT_ROOT / "data" / "tasks.db"

_SERIOUS_STATUSES = {"offline", "error", "degraded"}

# 能力边界 — 外部依赖平台：弥娅只能重连，无法替主人启动/登录对端程序
EXTERNAL_PLATFORM_HELP = {
    "aiocqhttp": "对端是 NapCat/OneBot 外部程序，我只能重连，无法替主人启动或登录它",
    "qqofficial": "依赖腾讯开放平台，持续失败通常是网络或平台侧问题",
    "weixin_official_account": "依赖微信服务器与凭据，持续失败需要主人检查凭据",
    "weixin_ilink": "依赖 iLink 凭据文件，持续失败需要主人检查凭据",
    "lark": "飞书走长连接一般能自愈，持续失败需要主人检查开放平台配置",
}


# ── 数据采集 ──────────────────────────────────────────────


def get_platform_stats() -> List[Dict[str, Any]]:
    """全部平台状态（来自全局注册表单例）"""
    try:
        from core.unified_platform.registry import get_registry

        return get_registry().get_all_stats()
    except Exception as e:
        logger.debug(f"获取平台状态失败: {e}")
        return []


def get_resources() -> Dict[str, Any]:
    """psutil 直读系统资源（cpu_percent 非阻塞，首次调用返回 0 属正常）"""
    import psutil

    res: Dict[str, Any] = {}
    try:
        vm = psutil.virtual_memory()
        res["memory_percent"] = round(vm.percent, 1)
        res["memory_used_gb"] = round(vm.used / 1024 ** 3, 1)
        res["memory_total_gb"] = round(vm.total / 1024 ** 3, 1)
    except Exception:
        pass
    # Windows 的 / 会随当前 Python 工作目录落到某个盘符（本机曾因此把 D:
    # 显示成了不明确的“磁盘”）。按挂载点逐盘读取，旧字段仍保留为最高占用盘，
    # 供已有 API/阈值逻辑兼容；新的 disks 字段才是完整事实来源。
    try:
        mounts = []
        if hasattr(psutil, "disk_partitions"):
            for part in psutil.disk_partitions(all=False):
                mountpoint = str(getattr(part, "mountpoint", "") or "")
                if mountpoint and mountpoint not in {m[0] for m in mounts}:
                    mounts.append((mountpoint, str(getattr(part, "device", "") or "")))
        if not mounts:
            mounts = [("/", "/")]

        disks = []
        for mountpoint, device in mounts:
            try:
                du = psutil.disk_usage(mountpoint)
                drive = device[:2] if len(device) >= 2 and device[1] == ":" else mountpoint
                disks.append({
                    "drive": drive,
                    "mountpoint": mountpoint,
                    "percent": round(du.percent, 1),
                    "used_gb": round(du.used / 1024 ** 3, 1),
                    "total_gb": round(du.total / 1024 ** 3, 1),
                    "free_gb": round(du.free / 1024 ** 3, 1),
                })
            except (OSError, PermissionError):
                continue
        if disks:
            disks.sort(key=lambda item: item["percent"], reverse=True)
            res["disks"] = disks
            primary = disks[0]
            res["disk_percent"] = primary["percent"]
            res["disk_used_gb"] = primary["used_gb"]
            res["disk_total_gb"] = primary["total_gb"]
            res["disk_free_gb"] = primary["free_gb"]
            res["disk_primary_drive"] = primary["drive"]
    except Exception:
        # 兼容精简 psutil/异常平台：继续尝试旧的根路径读取。
        try:
            du = psutil.disk_usage("/")
            res["disk_percent"] = round(du.percent, 1)
            res["disk_used_gb"] = round(du.used / 1024 ** 3, 1)
            res["disk_total_gb"] = round(du.total / 1024 ** 3, 1)
            res["disk_free_gb"] = round(du.free / 1024 ** 3, 1)
        except Exception:
            pass
    try:
        res["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        pass
    try:
        res["daemon_uptime_seconds"] = max(0.0, time.time() - psutil.Process().create_time())
    except Exception:
        pass
    return res


def get_task_stats() -> Optional[Dict[str, Any]]:
    """定时任务统计（只读直连 SQLite，避免 TaskStore 初始化副作用）"""
    if not _TASKS_DB.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{_TASKS_DB}?mode=ro", uri=True)
        try:
            stats: Dict[str, int] = {}
            rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM scheduled_tasks GROUP BY status"
            ).fetchall()
            for status, cnt in rows:
                stats[status] = cnt
        finally:
            conn.close()
        done = stats.get("completed", 0)
        failed = stats.get("failed", 0)
        stats["failure_rate"] = round(failed / (done + failed), 3) if (done + failed) > 0 else 0.0
        return stats
    except Exception as e:
        logger.debug(f"读取任务统计失败: {e}")
        return None


def get_recent_errors(limit: int = 15) -> List[str]:
    """日志环形缓冲中最近的 WARNING/ERROR（每行截断，控制注入/工具输出体积）"""
    try:
        from core.log_stream import get_log_buffer

        entries, _ = get_log_buffer().snapshot(2000)
        picked = []
        for e in entries:
            if e["level"] in ("WARNING", "ERROR", "CRITICAL"):
                text = e["text"].rstrip()
                if len(text) > 160:
                    text = text[:160] + "…"
                picked.append(f"[{e['ts'].replace('T', ' ')[11:19]}] {text}")
        return picked[-limit:]
    except Exception as e:
        logger.debug(f"读取日志缓冲失败: {e}")
        return []


async def collect_report(platform_stats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """全量体检报告（结构化）。platform_stats 可注入（器官巡检/测试），默认读注册表。"""
    platforms = platform_stats if platform_stats is not None else get_platform_stats()
    active = [p for p in platforms if p.get("status") != "disabled"]
    abnormal = [
        {
            "platform_id": p.get("platform_id", "?"),
            "platform_name": p.get("platform_name") or p.get("platform_id", "?"),
            "status": p.get("status", "?"),
            "error_count": p.get("error_count", 0),
            "reconnect_count": p.get("reconnect_count", 0),
            "last_error": p.get("last_error"),
            "consecutive_health_failures": p.get("consecutive_health_failures", 0),
        }
        for p in active
        if p.get("status") in _SERIOUS_STATUSES
    ]
    online = sum(1 for p in active if p.get("status") == "online")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "platforms": {
            "total": len(active),
            "online": online,
            "abnormal": abnormal,
            "all": [
                {
                    "platform_id": p.get("platform_id", "?"),
                    "platform_name": p.get("platform_name") or p.get("platform_id", "?"),
                    "status": p.get("status", "?"),
                    "latency_ms": p.get("latency_ms", 0),
                    "error_count": p.get("error_count", 0),
                    "reconnect_count": p.get("reconnect_count", 0),
                    "last_error": p.get("last_error"),
                    "consecutive_health_failures": p.get("consecutive_health_failures", 0),
                }
                for p in active
            ],
        },
        "resources": get_resources(),
        "tasks": get_task_stats(),
        "recent_errors": get_recent_errors(),
    }


# ── 状态判定与摘要 ────────────────────────────────────────


def overall_status(report: Dict[str, Any]) -> str:
    """ok / warn / error"""
    abnormal = report.get("platforms", {}).get("abnormal", [])
    if any(a["status"] in ("offline", "error") for a in abnormal):
        return "error"
    res = report.get("resources", {})
    tasks = report.get("tasks") or {}
    disks = res.get("disks") or []
    disk_warning = any(float(d.get("percent", 0)) > 90 for d in disks if isinstance(d, dict))
    if (
        abnormal
        or disk_warning
        or (not disks and res.get("disk_percent", 0) > 90)
        or res.get("memory_percent", 0) > 90
        or res.get("cpu_percent", 0) > 95
        or (tasks.get("failed", 0) >= 5 and tasks.get("failure_rate", 0) > 0.3)
        or report.get("recent_errors")
    ):
        return "warn"
    return "ok"


def summarize_last(report: Dict[str, Any]) -> Dict[str, Any]:
    """写入 data/self_care_last.json 的最新摘要（供时间感知注入）"""
    st = overall_status(report)
    pl = report.get("platforms", {})
    abnormal = pl.get("abnormal", [])
    if st == "ok":
        note = "一切正常"
    elif st == "error":
        note = "⚠ " + "、".join(a["platform_name"] for a in abnormal) + " 离线/异常中"
    else:
        parts = []
        if abnormal:
            parts.append("、".join(a["platform_name"] for a in abnormal) + " 状态不佳")
        if report.get("recent_errors"):
            parts.append(f"最近有 {len(report['recent_errors'])} 条警告/错误日志")
        note = "⚠ " + "；".join(parts) if parts else "有需要注意的地方"
    return {
        "at": report.get("timestamp", ""),
        "overall": st,
        "platforms_online": f"{pl.get('online', 0)}/{pl.get('total', 0)}",
        "note": note,
    }


# ── 报告文本 ──────────────────────────────────────────────


def _fmt_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m:02d}m" if h > 0 else f"{m}m"


_STATUS_ICON = {"online": "✅", "offline": "❌", "error": "❌", "degraded": "⚠️"}


def format_report(report: Dict[str, Any], section: str = "all") -> str:
    """体检报告文本（工具返回 / 每日简报 / 记忆归档共用）"""
    ts = (report.get("timestamp") or "").replace("T", " ")[5:16]
    st = overall_status(report)
    st_icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(st, "❓")
    st_text = {"ok": "一切正常", "warn": "有需要注意的地方", "error": "存在故障"}.get(st, st)
    pl = report.get("platforms", {})
    res = report.get("resources", {})

    head = (
        f"🩺 弥娅自检报告 · {ts}\n"
        f"{'─' * 30}\n"
        f"总体: {st_icon} {st_text} | 平台 {pl.get('online', 0)}/{pl.get('total', 0)} 在线"
    )
    if res.get("daemon_uptime_seconds"):
        head += f" | 已运行 {_fmt_uptime(res['daemon_uptime_seconds'])}"

    tasks = report.get("tasks") or {}
    lines = [head]

    if section in ("all", "platforms"):
        lines += ["", "[平台]"]
        for p in pl.get("all", []):
            icon = _STATUS_ICON.get(p["status"], "•")
            lat = f" ({p['latency_ms']:.0f}ms)" if p["status"] == "online" and p.get("latency_ms", 0) > 0 else ""
            lines.append(f"  {icon} {p['platform_name']}: {p['status']}{lat}")
        for a in pl.get("abnormal", []):
            detail = []
            if a.get("error_count"):
                detail.append(f"错误 {a['error_count']} 次")
            if a.get("reconnect_count"):
                detail.append(f"重连 {a['reconnect_count']} 次")
            if a.get("last_error"):
                detail.append(f"最近错误: {str(a['last_error'])[:80]}")
            boundary = EXTERNAL_PLATFORM_HELP.get(a["platform_id"])
            if boundary:
                detail.append(f"能力边界: {boundary}")
            if detail:
                lines.append(f"      └ {' · '.join(detail)}")

    if section in ("all", "resources"):
        lines += ["", "[资源]"]
        r = []
        if "cpu_percent" in res:
            r.append(f"CPU {res['cpu_percent']}%")
        if "memory_percent" in res:
            r.append(f"内存 {res['memory_percent']}% ({res.get('memory_used_gb', '?')}/{res.get('memory_total_gb', '?')}GB)")
        if res.get("disks"):
            r.append("磁盘 " + ", ".join(
                f"{d.get('drive') or d.get('mountpoint')} {d.get('percent')}%"
                f"（已用 {d.get('used_gb')} / {d.get('total_gb')}GB，余 {d.get('free_gb')}GB）"
                for d in res["disks"]
            ))
        elif "disk_percent" in res:
            r.append(f"磁盘 {res['disk_percent']}% ({res.get('disk_used_gb', '?')}/{res.get('disk_total_gb', '?')}GB)")
        lines.append("  " + (" · ".join(r) if r else "不可用"))

    if section in ("all", "tasks"):
        lines += ["", "[定时任务]"]
        if tasks:
            lines.append(
                f"  完成 {tasks.get('completed', 0)} · 失败 {tasks.get('failed', 0)}"
                f" ({tasks.get('failure_rate', 0) * 100:.1f}%) · 待运行 {tasks.get('pending', 0)}"
            )
        else:
            lines.append("  暂无任务数据")

    if section in ("all", "errors"):
        lines += ["", "[最近警告/错误]"]
        errs = report.get("recent_errors", [])
        if errs:
            lines += [f"  {e}" for e in errs]
        else:
            lines.append("  ✨ 没有警告和错误")

    return "\n".join(lines)
