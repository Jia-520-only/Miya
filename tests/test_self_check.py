"""弥娅自检系统测试 — 体检报告 / 看护器官（掉线告警·自动重启·恢复·简报）/ 工具注册"""

import asyncio
import json
import time
from types import SimpleNamespace

import core.self_check
from core.self_check import collect_report, format_report, overall_status, summarize_last
from core.self_care_organ import MiyaSelfCareOrgan


def make_report(platforms=None, resources=None, tasks=None, errors=None):
    return {
        "timestamp": "2026-08-22T20:30:00",
        "platforms": {
            "total": len(platforms or []),
            "online": sum(1 for p in (platforms or []) if p["status"] == "online"),
            "abnormal": [p for p in (platforms or []) if p["status"] in ("offline", "error", "degraded")],
            "all": platforms or [],
        },
        "resources": resources or {},
        "tasks": tasks,
        "recent_errors": errors or [],
    }


def plat(pid, status, **kw):
    return {
        "platform_id": pid, "platform_name": kw.get("name", pid), "status": status,
        "latency_ms": kw.get("latency_ms", 0), "error_count": kw.get("error_count", 0),
        "reconnect_count": kw.get("reconnect_count", 0),
        "last_error": kw.get("last_error"), "consecutive_health_failures": kw.get("cf", 0),
    }


# ── 报告与格式化 ──────────────────────────────


def test_overall_status_ok_warn_error():
    ok = make_report([plat("qq", "online")])
    assert overall_status(ok) == "ok"

    warn = make_report([plat("qq", "online")], resources={"disk_percent": 95.0})
    assert overall_status(warn) == "warn"

    err = make_report([plat("lark", "offline"), plat("qq", "online")])
    assert overall_status(err) == "error"


def test_format_report_sections():
    report = make_report(
        [plat("aiocqhttp", "offline", name="OneBot/NapCat", last_error="ws closed", error_count=2),
         plat("qq", "online", latency_ms=32.5)],
        resources={"cpu_percent": 12.0, "memory_percent": 50.0, "memory_used_gb": 8.0,
                   "memory_total_gb": 16.0, "disk_percent": 70.0, "disk_used_gb": 665.0,
                   "disk_total_gb": 950.0, "daemon_uptime_seconds": 18700},
        tasks={"completed": 120, "failed": 3, "pending": 5, "failure_rate": 0.024},
        errors=["[20:06] [X] ERROR: boom"],
    )
    text = format_report(report)
    assert "自检报告" in text
    assert "OneBot/NapCat" in text and "ws closed" in text
    assert "CPU 12.0%" in text and "磁盘 70.0%" in text
    assert "已运行 5h11m" in text
    assert "失败 3 (2.4%)" in text
    assert "ERROR: boom" in text

    only_err = format_report(report, section="errors")
    assert "ERROR: boom" in only_err
    assert "CPU" not in only_err


def test_summarize_last():
    ok = summarize_last(make_report([plat("qq", "online")]))
    assert ok["overall"] == "ok" and ok["note"] == "一切正常" and ok["platforms_online"] == "1/1"

    bad = summarize_last(make_report([plat("lark", "offline", name="飞书"), plat("qq", "online")]))
    assert bad["overall"] == "error" and "飞书" in bad["note"]


def test_collect_report_with_injected_stats(monkeypatch):
    monkeypatch.setattr(core.self_check, "get_resources", lambda: {"cpu_percent": 10.0})
    monkeypatch.setattr(core.self_check, "get_task_stats", lambda: {"completed": 10, "failed": 0, "failure_rate": 0.0})
    monkeypatch.setattr(core.self_check, "get_recent_errors", lambda: ["[20:00] [X] WARNING: w"])

    stats = [plat("qq", "online", latency_ms=20.0), plat("napcat", "offline", cf=4), plat("off1", "disabled")]
    report = asyncio.run(collect_report(platform_stats=stats))
    assert report["platforms"]["total"] == 2          # disabled 不计
    assert report["platforms"]["online"] == 1
    assert [a["platform_id"] for a in report["platforms"]["abnormal"]] == ["napcat"]
    assert report["platforms"]["all"][0]["consecutive_health_failures"] == 0
    assert report["resources"]["cpu_percent"] == 10.0
    assert report["tasks"]["failure_rate"] == 0.0
    assert report["recent_errors"] == ["[20:00] [X] WARNING: w"]


# ── 看护器官 ──────────────────────────────


class FakeSpine:
    def __init__(self):
        self.sent = []
        self._proactive_sender = self.sent.append
        self._loop = None


class FakeDaemon:
    """restart 会把平台翻回 online（模拟重启成功）"""

    def __init__(self, stats, fix=True):
        self.stats = stats
        self.fix = fix
        self.restarts = []

    async def restart_platform(self, pid):
        self.restarts.append(pid)
        if self.fix:
            for s in self.stats:
                if s["platform_id"] == pid:
                    s.update(status="online", last_error=None, consecutive_health_failures=0)
        return self.fix


def make_organ(tmp_path, stats, daemon, verify_seconds=3):
    organ = MiyaSelfCareOrgan()
    # 构造函数会读取真实 data/self_care_state.json（运行中的守护进程写下的
    # 告警冷却/事故记录），测试必须换成干净状态，否则告警会被真实冷却挡住
    organ._state = {
        "last_watch_at": "", "last_briefing_key": "", "platform_status": {},
        "incidents": {}, "alert_times": {}, "restarts": {}, "cycles": 0,
    }
    organ.state_path = str(tmp_path / "self_care_state.json")
    organ.last_path = str(tmp_path / "self_care_last.json")
    organ._config["store_memory"] = False
    organ._config["restart_verify_seconds"] = verify_seconds
    organ._config["daily_briefing"]["quiet_hours"] = []
    organ.bind_core(daemon=daemon)
    organ.bind_stats_fn(lambda: daemon.stats)
    organ._spine = FakeSpine()
    return organ


def patch_report_sources(monkeypatch):
    monkeypatch.setattr(core.self_check, "get_resources", lambda: {"cpu_percent": 5.0, "memory_percent": 40.0, "disk_percent": 50.0})
    monkeypatch.setattr(core.self_check, "get_task_stats", lambda: {"completed": 9, "failed": 1, "failure_rate": 0.1})
    monkeypatch.setattr(core.self_check, "get_recent_errors", lambda: [])


def test_incident_auto_restart_success(monkeypatch, tmp_path):
    patch_report_sources(monkeypatch)
    stats = [plat("aiocqhttp", "offline", name="OneBot/NapCat", last_error="ws closed", cf=2),
             plat("lark", "online")]
    daemon = FakeDaemon(stats, fix=True)
    organ = make_organ(tmp_path, stats, daemon)

    result = asyncio.run(organ.run_watch_cycle())
    assert result["success"] is True
    assert daemon.restarts == ["aiocqhttp"]                    # 自动重启了一次
    assert len(organ._spine.sent) == 1                          # 发了一条告警
    msg = organ._spine.sent[0]
    event = json.loads(msg)
    assert event["event"] == "platform_offline"
    assert event["platform_name"] == "OneBot/NapCat"
    assert event["reason"] == "ws closed"
    assert event["restart_attempted"] is True
    assert event["restart_succeeded"] is True
    # 事故保持开启，由下一轮巡检确认恢复（防连接抖动误报）
    assert "aiocqhttp" in organ._state["incidents"]
    assert organ._state["platform_status"]["lark"] == "online"

    # 下一轮: 平台已在线 → 恢复通知 + 事故清除
    asyncio.run(organ.run_watch_cycle())
    assert "aiocqhttp" not in organ._state["incidents"]
    recovery = json.loads(next(s for s in organ._spine.sent if '"event":"platform_recovered"' in s))
    assert recovery["platform_name"] == "OneBot/NapCat"
    assert recovery["status"] == "online"


def test_incident_restart_failure(monkeypatch, tmp_path):
    patch_report_sources(monkeypatch)
    stats = [plat("aiocqhttp", "offline", name="OneBot/NapCat", last_error="refused")]
    daemon = FakeDaemon(stats, fix=False)
    organ = make_organ(tmp_path, stats, daemon, verify_seconds=0)  # 0 → 验证窗口立即结束

    asyncio.run(organ.run_watch_cycle())
    inc = organ._state["incidents"]["aiocqhttp"]          # 未恢复 → 记录持续事故
    assert inc["external"] is True                        # 外部依赖平台
    event = json.loads(organ._spine.sent[0])
    assert event["event"] == "platform_offline"
    assert event["restart_succeeded"] is False
    assert event["external_dependency"] is True


def test_recovery_notice(monkeypatch, tmp_path):
    patch_report_sources(monkeypatch)
    stats = [plat("lark", "online")]
    daemon = FakeDaemon(stats)
    organ = make_organ(tmp_path, stats, daemon)
    organ._state["incidents"]["lark"] = {"since": "08-22 19:00", "name": "飞书", "reason": "x"}

    asyncio.run(organ.run_watch_cycle())
    assert "lark" not in organ._state["incidents"]
    recovery = json.loads(organ._spine.sent[0])
    assert recovery["event"] == "platform_recovered"
    assert recovery["platform_name"] == "lark"


def test_restart_limit_and_alert_cooldown(tmp_path):
    stats = [plat("x", "online")]
    organ = make_organ(tmp_path, stats, FakeDaemon(stats))
    # 最近 1 小时内已重启 3 次 → 不允许再重启
    organ._state["restarts"]["x"] = [time.time() - 60] * 3
    assert organ._restart_allowed("x") is False
    organ._state["restarts"]["x"] = [time.time() - 7200]        # 2 小时前 → 已过期
    assert organ._restart_allowed("x") is True

    # 同类告警冷却
    assert organ._alert_allowed("platform:x", 30) is True
    assert organ._alert_allowed("platform:x", 30) is False
    organ._state["alert_times"]["platform:x"] = time.time() - 3600
    assert organ._alert_allowed("platform:x", 30) is True


def test_proactive_notification_global_throttle(tmp_path):
    stats = [plat("qq", "online")]
    organ = make_organ(tmp_path, stats, FakeDaemon(stats))
    organ._config["max_proactive_notifications_per_hour"] = 2
    organ._config["proactive_notification_cooldown_minutes"] = 30

    assert organ._claim_proactive_notification("platform_offline:qq") is True
    assert organ._claim_proactive_notification("platform_recovered:qq") is True
    assert organ._claim_proactive_notification("resource:disk") is False
    assert len(organ._state["proactive_notifications"]) == 2

    # 节流只影响主动消息额度，不影响最新体检事实写入。
    report = make_report(
        [plat("qq", "online")],
        resources={"disk_percent": 96.0},
        tasks={"completed": 10, "failed": 0, "failure_rate": 0.0},
    )
    organ._write_last(report)
    with open(organ.last_path, encoding="utf-8") as f:
        latest = json.load(f)
    assert latest["resources"]["disk_percent"] == 96.0
    assert latest["tasks"]["completed"] == 10


def test_resource_alert(monkeypatch, tmp_path):
    stats = [plat("qq", "online")]
    daemon = FakeDaemon(stats)
    organ = make_organ(tmp_path, stats, daemon)
    monkeypatch.setattr(core.self_check, "get_resources",
                        lambda: {"disk_percent": 96.5, "memory_percent": 40.0, "cpu_percent": 5.0})
    monkeypatch.setattr(core.self_check, "get_task_stats", lambda: None)
    monkeypatch.setattr(core.self_check, "get_recent_errors", lambda: [])

    asyncio.run(organ.run_watch_cycle())
    resource_event = json.loads(organ._spine.sent[0])
    assert resource_event["event"] == "resource_threshold_exceeded"
    assert resource_event["resource"] == "disk"
    assert resource_event["value"] == 96.5

    # 冷却期内不再重复告警
    organ._spine.sent.clear()
    asyncio.run(organ.run_watch_cycle())
    assert not any("磁盘" in s for s in organ._spine.sent)


def test_daily_briefing(monkeypatch, tmp_path):
    patch_report_sources(monkeypatch)
    stats = [plat("qq", "online"), plat("lark", "online")]
    daemon = FakeDaemon(stats)
    organ = make_organ(tmp_path, stats, daemon)

    result = asyncio.run(organ.run_daily_briefing(8))
    assert result["success"] is True and result["sent"] is True
    # 无 ai_client → 回退到简洁事实模板（LLM 口吻路径在守护进程中生效）
    briefing = json.loads(organ._spine.sent[0])
    assert briefing["greeting"] == "早安"
    assert briefing["platforms_online"] == 2
    assert briefing["platforms_total"] == 2
    assert organ._state["last_briefing_key"].endswith(":8")
    # last.json 已写出（供时间感知注入）
    import json as _json
    from pathlib import Path as _P
    last = _json.loads(_P(organ.last_path).read_text(encoding="utf-8"))
    assert last["overall"] == "ok" and last["platforms_online"] == "2/2"


def test_daily_briefing_quiet_hours(monkeypatch, tmp_path):
    patch_report_sources(monkeypatch)
    stats = [plat("qq", "online")]
    daemon = FakeDaemon(stats)
    organ = make_organ(tmp_path, stats, daemon)
    organ._config["daily_briefing"]["quiet_hours"] = [8]

    result = asyncio.run(organ.run_daily_briefing(8))
    assert result["sent"] is False
    assert not organ._spine.sent                      # 静默时段不发消息（记忆在 store_memory 关闭时跳过）


def test_escalation_when_restart_budget_exhausted(monkeypatch, tmp_path):
    """持续掉线 + 重启额度耗尽 → 一次性升级求助，之后不重复"""
    patch_report_sources(monkeypatch)
    stats = [plat("aiocqhttp", "offline", name="OneBot/NapCat", last_error="refused")]
    daemon = FakeDaemon(stats, fix=False)
    organ = make_organ(tmp_path, stats, daemon, verify_seconds=0)
    # 预设本小时重启额度已用完
    organ._state["restarts"]["aiocqhttp"] = [time.time() - 60] * 3

    asyncio.run(organ.run_watch_cycle())       # 第一次: 事故 + 告警，不升级
    assert organ._state["incidents"]["aiocqhttp"]["escalated"] is False

    organ._spine.sent.clear()
    asyncio.run(organ.run_watch_cycle())       # 第二次: 仍掉线 + 额度耗尽 → 升级求助
    assert organ._state["incidents"]["aiocqhttp"]["escalated"] is True
    escalation = json.loads(organ._spine.sent[0])
    assert escalation["event"] == "platform_escalated"
    assert escalation["action"] == "owner_required"

    organ._spine.sent.clear()
    asyncio.run(organ.run_watch_cycle())       # 第三次: 已升级过，不再重复
    assert not organ._spine.sent


def test_write_last_reflects_incidents(monkeypatch, tmp_path):
    """进行中的事故写进 last.json——弥娅每轮对话都能看到（她知道，不只主人知道）"""
    import json as _json
    from pathlib import Path as _P

    patch_report_sources(monkeypatch)
    stats = [plat("lark", "online")]
    daemon = FakeDaemon(stats)
    organ = make_organ(tmp_path, stats, daemon)
    organ._state["incidents"]["aiocqhttp"] = {
        "since": "08-22 21:00", "since_ts": time.time(), "name": "OneBot/NapCat",
        "reason": "refused", "restarted": True, "external": True, "escalated": False,
    }

    asyncio.run(organ.run_watch_cycle())
    last = _json.loads(_P(organ.last_path).read_text(encoding="utf-8"))
    incident_note = json.loads(last["note"])
    assert incident_note[0]["platform_name"] == "OneBot/NapCat"
    assert incident_note[0]["restart_attempted"] is True
    assert last.get("incidents") == ["aiocqhttp"]

    # 升级后摘要只反映结构化的 escalated 状态
    organ._state["incidents"]["aiocqhttp"]["escalated"] = True
    asyncio.run(organ.run_watch_cycle())
    last = _json.loads(_P(organ.last_path).read_text(encoding="utf-8"))
    incident_note = _json.loads(last["note"])
    assert incident_note[0]["escalated"] is True


def test_format_report_boundary_note():
    """体检报告为异常的外部平台标注能力边界（弥娅读报告时知道哪些要主人动手）"""
    report = make_report([plat("aiocqhttp", "offline", name="OneBot/NapCat", last_error="refused")])
    text = format_report(report)
    assert "能力边界" in text and "无法替主人启动" in text


def test_get_resources_reports_each_drive(monkeypatch):
    """Windows 盘符逐盘采集，不把当前工作盘伪装成整机磁盘。"""
    import psutil

    monkeypatch.setattr(
        psutil,
        "disk_partitions",
        lambda all=False: [
            SimpleNamespace(device="C:\\", mountpoint="C:\\", fstype="NTFS"),
            SimpleNamespace(device="D:\\", mountpoint="D:\\", fstype="NTFS"),
        ],
    )

    def fake_disk_usage(path):
        if path == "C:\\":
            return SimpleNamespace(percent=92.3, used=923, total=1000, free=77)
        return SimpleNamespace(percent=70.0, used=700, total=1000, free=300)

    monkeypatch.setattr(psutil, "disk_usage", fake_disk_usage)
    resources = core.self_check.get_resources()
    assert [d["drive"] for d in resources["disks"]] == ["C:", "D:"]
    assert resources["disk_primary_drive"] == "C:"
    assert resources["disk_percent"] == 92.3
    assert resources["disks"][0]["free_gb"] == 0.0


def test_multi_drive_alert_identifies_drive(tmp_path):
    stats = [plat("qq", "online")]
    organ = make_organ(tmp_path, stats, FakeDaemon(stats))
    report = {"resources": {"disks": [
        {"drive": "C:", "mountpoint": "C:\\", "percent": 92.3, "used_gb": 396.4, "total_gb": 429.5, "free_gb": 33.1},
        {"drive": "D:", "mountpoint": "D:\\", "percent": 70.0, "used_gb": 377.0, "total_gb": 538.0, "free_gb": 161.0},
    ]}}
    asyncio.run(organ._check_resources(report))
    event = json.loads(organ._spine.sent[0])
    assert event["resource"] == "disk"
    assert event["drive"] == "C:"
    assert event["free_gb"] == 33.1


def test_state_persistence(tmp_path):
    stats = [plat("qq", "offline")]
    daemon = FakeDaemon(stats, fix=False)
    organ = make_organ(tmp_path, stats, daemon, verify_seconds=0)

    # 手动种入告警/事故状态，保存后重建器官应恢复
    organ._state["alert_times"]["platform:qq"] = time.time()
    organ._state["incidents"]["qq"] = {"since": "08-22 20:00", "name": "QQ", "reason": "r"}
    organ._save_state()

    organ2 = MiyaSelfCareOrgan()
    organ2._state = {"incidents": {}, "alert_times": {}, "restarts": {}}
    organ2.state_path = organ.state_path
    organ2.last_path = organ.last_path
    organ2._load_state()
    assert "qq" in organ2._state["incidents"]
    assert "platform:qq" in organ2._state["alert_times"]


def test_registry_loads_self_check():
    from webnet.ToolNet.registry import ToolRegistry

    reg = ToolRegistry()
    reg._load_core_tools()
    tool = reg.get_tool("self_check")
    assert tool is not None
    assert "体检" in tool.config["description"]
