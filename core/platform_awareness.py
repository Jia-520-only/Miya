"""
弥娅统一平台感知中心 (PlatformAwareness) v9.0

弥娅系统的单一权威数据源，回答核心问题：
  "用户当前活跃在哪个平台？"

整合并取代分散在多处 (time_tracker.py, user_platform_activity.py,
proactive_chat.py, platform_context.py) 的平台追踪逻辑。

功能：
  1. record_activity() — 所有消息入口统一调用，追踪用户×平台活跃
  2. get_current_platform() — 返回用户当前活跃平台 (权威答案)
  3. get_user_platforms() — 返回用户所有平台活跃度摘要
  4. notify_mobile_pending() — 通知手机端有待发送消息 (WS push)
  5. send_to_active_platform() — 向用户当前活跃平台发送消息
  6. 自动同步到 user_platform_activity.py 和 time_tracker.py

使用方式:
    from core.platform_awareness import get_platform_awareness
    pa = get_platform_awareness()

    # 接收消息时
    pa.record_activity("1523878699", "aiocqhttp")

    # 主动发送前查询
    current = pa.get_current_platform("1523878699")  # → "aiocqhttp"

    # 发送主动消息
    await pa.send_to_active_platform("1523878699", "在干嘛呢？")
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("Miya.PlatformAwareness")

DATA_DIR = Path("data/activity")
DATA_FILE = DATA_DIR / "platform_awareness.json"
MAX_PLATFORMS_PER_USER = 20

KNOWN_PLATFORM_PRIORITY = {
    "aiocqhttp_private": 100,
    "aiocqhttp_group": 50,
    "mobile": 95,
    "desktop": 85,
    "qqofficial_private": 85,
    "qqofficial_group": 40,
    "weixin_ilink": 75,
    "terminal": 70,
    "lark": 30,
    "dingtalk": 25,
    "discord": 20,
    "telegram": 20,
    "slack": 15,
    "wecom": 15,
    "kook": 15,
    "line": 15,
    "misskey": 10,
    "mattermost": 10,
    "satori": 10,
    "generic": 5,
}

PLATFORM_TYPE_DELIVERY = {
    "mobile": "ws_poll",
    "desktop": "ws_push",
    "terminal": "cce_direct",
    "aiocqhttp": "onebot",
    "qqofficial": "qq_api",
    "weixin_ilink": "ilink",
    "weixin_official_account": "offacc_api",
    "wecom": "wecom_api",
    "lark": "lark_api",
    "dingtalk": "dingtalk_api",
    "telegram": "tg_api",
    "discord": "discord_api",
}


@dataclass
class UserPlatformState:
    user_id: str
    current_platform: str = ""
    current_platform_since: float = 0.0
    last_active_ts: float = 0.0
    platforms: Dict[str, dict] = field(default_factory=dict)
    message_count: int = 0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "current_platform": self.current_platform,
            "current_platform_since": self.current_platform_since,
            "last_active_ts": self.last_active_ts,
            "platforms": self.platforms,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> UserPlatformState:
        return cls(
            user_id=data.get("user_id", ""),
            current_platform=data.get("current_platform", ""),
            current_platform_since=data.get("current_platform_since", 0.0),
            last_active_ts=data.get("last_active_ts", 0.0),
            platforms=data.get("platforms", {}),
            message_count=data.get("message_count", 0),
        )


class PlatformAwareness:
    """弥娅统一平台感知中心 (v9.0)

    线程安全，支持同步/异步调用。
    记录每次消息交互中的平台信息，提供统一的"用户活跃平台"查询。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._states: Dict[str, UserPlatformState] = {}
        self._loaded = False

        self._mobile_pending: Dict[str, List[Dict]] = {}
        self._mobile_pending_lock = threading.Lock()

        self._ws_push_callback: Optional[Callable] = None
        self._send_message_callback: Optional[Callable] = None

        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        with self._lock:
            if self._loaded:
                return
            try:
                if DATA_FILE.exists():
                    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                    for uid, data in raw.get("states", {}).items():
                        self._states[uid] = UserPlatformState.from_dict(data)
                self._loaded = True
                logger.info(f"[PlatformAwareness] 已加载 {len(self._states)} 个用户平台状态")
            except Exception as e:
                logger.warning(f"[PlatformAwareness] 加载失败: {e}")
                self._loaded = True

    def _save(self):
        try:
            self._ensure_dir()
            with self._lock:
                data = {
                    "updated_at": time.time(),
                    "state_count": len(self._states),
                    "states": {uid: s.to_dict() for uid, s in self._states.items()},
                }
            tmp = DATA_FILE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(DATA_FILE)
        except Exception as e:
            logger.debug(f"[PlatformAwareness] 保存失败: {e}")

    def _get_or_create(self, user_id: str) -> UserPlatformState:
        uid = str(user_id)
        with self._lock:
            if uid not in self._states:
                self._states[uid] = UserPlatformState(user_id=uid)
            return self._states[uid]

    # ── 核心 API：记录活跃 ──

    def record_activity(
        self,
        user_id: str,
        platform_id: str,
        timestamp: float = None,
        message_count: int = 1,
    ) -> None:
        """记录用户在某平台上的活跃 (所有消息入口统一调用)

        Args:
            user_id: 用户 ID (规范 ID，如 QQ 号)
            platform_id: 平台 ID (aiocqhttp, desktop, mobile, weixin_ilink...)
            timestamp: 时间戳 (默认 now)
            message_count: 本次消息数
        """
        if not user_id or not platform_id:
            return

        uid = str(user_id)
        pid = str(platform_id)
        ts = timestamp or time.time()

        with self._lock:
            state = self._states.setdefault(uid, UserPlatformState(user_id=uid))
            state.last_active_ts = ts
            state.message_count += message_count

            plat = state.platforms.setdefault(pid, {"last_active": 0.0, "msg_count": 0, "first_seen": ts})
            plat["last_active"] = ts
            plat["msg_count"] = plat.get("msg_count", 0) + message_count

            prev = state.current_platform
            if prev != pid:
                state.current_platform = pid
                state.current_platform_since = ts
                logger.debug(f"[PlatformAwareness] 用户 {uid} 切换平台: {prev or '(首次)'} → {pid}")

            active_pids = sorted(
                state.platforms.keys(),
                key=lambda p: state.platforms[p].get("last_active", 0.0),
                reverse=True,
            )
            if len(active_pids) > MAX_PLATFORMS_PER_USER:
                for p in active_pids[MAX_PLATFORMS_PER_USER:]:
                    del state.platforms[p]

        self._save()

        try:
            from memory.user_platform_activity import record_platform_activity

            record_platform_activity(uid, pid, ts)
        except Exception:
            pass

        try:
            from memory.time_tracker import get_time_tracker

            tracker = get_time_tracker()
            tracker.record_interaction(uid, pid, role="user")
        except Exception:
            pass

    # ── 核心 API：查询当前活跃平台 ──

    def get_current_platform(self, user_id: str) -> str:
        """返回用户当前活跃平台 ID (权威答案)

        这是弥娅系统所有主动消息路由的单一查询入口。
        无记录返回空字符串。
        """
        with self._lock:
            state = self._states.get(str(user_id))
            if state and state.current_platform:
                plat = state.current_platform
                plat_data = state.platforms.get(plat, {})
                last = plat_data.get("last_active", 0.0)
                if last > 0 and (time.time() - last) < 7200:
                    return plat
                recent = self._find_most_recent(state)
                if recent:
                    state.current_platform = recent
                    return recent
            return ""

    def _find_most_recent(self, state: UserPlatformState) -> str:
        best_pid = ""
        best_ts = 0.0
        for pid, pdata in state.platforms.items():
            ts = pdata.get("last_active", 0.0)
            if ts > best_ts:
                best_ts = ts
                best_pid = pid
        return best_pid if (best_ts > 0 and time.time() - best_ts < 7200) else ""

    def get_user_platforms(self, user_id: str, now: float = None) -> Dict[str, dict]:
        """获取用户在所有平台上的活跃度摘要 (用于 AI 路由)"""
        if now is None:
            now = time.time()
        with self._lock:
            state = self._states.get(str(user_id))
            if not state:
                return {}
            result = {}
            for pid, pdata in state.platforms.items():
                last = pdata.get("last_active", 0.0)
                result[pid] = {
                    "last_active": last,
                    "seconds_ago": max(0.0, now - last) if last > 0 else float("inf"),
                    "message_count": pdata.get("msg_count", 0),
                    "first_seen": pdata.get("first_seen", 0.0),
                }
            return result

    def get_deep_platform_context(self, user_id: str) -> dict:
        """获取用户深度平台上下文 (v9.0: 含当前平台、切换时间、历史列表)"""
        with self._lock:
            state = self._states.get(str(user_id))
            if not state:
                return {"current_platform": "", "platforms": {}, "known_platforms": []}
            return {
                "user_id": state.user_id,
                "current_platform": state.current_platform,
                "current_platform_since": state.current_platform_since,
                "last_active_ts": state.last_active_ts,
                "message_count": state.message_count,
                "platforms": state.platforms,
                "known_platforms": sorted(
                    state.platforms.keys(),
                    key=lambda p: state.platforms[p].get("last_active", 0.0),
                    reverse=True,
                ),
            }

    # ── 移动端/桌面端待发送队列 ──

    def add_mobile_pending(self, user_id: str, message: str) -> None:
        """将消息加入手机端待发送队列"""
        with self._mobile_pending_lock:
            key = str(user_id)
            self._mobile_pending.setdefault(key, []).append(
                {
                    "message": message,
                    "timestamp": time.time(),
                }
            )
            if len(self._mobile_pending[key]) > 50:
                self._mobile_pending[key] = self._mobile_pending[key][-50:]

    def get_and_clear_mobile_pending(self, user_id: str) -> List[Dict]:
        """获取并清除手机端待发送消息"""
        with self._mobile_pending_lock:
            return self._mobile_pending.pop(str(user_id), [])

    def has_mobile_pending(self, user_id: str) -> bool:
        """检查是否有手机端待发送消息"""
        with self._mobile_pending_lock:
            return bool(self._mobile_pending.get(str(user_id)))

    def set_ws_push_callback(self, callback: Callable) -> None:
        """设置 WebSocket 推送回调 (由 ManagementAPI 注入)"""
        self._ws_push_callback = callback

    def set_send_message_callback(self, callback: Callable) -> None:
        """设置通用消息发送回调 (由 decision_hub 注入)"""
        self._send_message_callback = callback

    async def notify_mobile(self, user_id: str, message: str = None) -> None:
        """通知手机端有新消息 (WS push)

        如果手机端 WebSocket 在线，直接推送消息；
        否则加入 pending 队列等待拉取。
        """
        if message:
            self.add_mobile_pending(user_id, message)

        if self._ws_push_callback:
            try:
                await self._ws_push_callback(
                    event_type="mobile_pending",
                    user_id=str(user_id),
                    message=message,
                    pending_count=len(self._mobile_pending.get(str(user_id), [])),
                )
            except Exception as e:
                logger.debug(f"[PlatformAwareness] 手机端推送失败: {e}")

    async def send_to_active_platform(
        self,
        user_id: str,
        message: str,
        chat_type: str = "private",
        trigger_type: str = "",
    ) -> bool:
        """向用户当前活跃平台发送消息 (v9.0 统一入口)

        查询 PlatformAwareness 获取当前活跃平台，
        如果有 send_message_callback 则委托发送。

        Returns:
            True 如果消息已发送 (或加入待发送队列)
        """
        current = self.get_current_platform(user_id)
        if not current:
            current = "mobile"

        if self._send_message_callback:
            try:
                return await self._send_message_callback(
                    message=message,
                    target_id=int(user_id) if str(user_id).isdigit() else user_id,
                    chat_type=chat_type,
                    platform=current,
                    trigger_type=trigger_type,
                )
            except Exception as e:
                logger.warning(f"[PlatformAwareness] 发送失败: {e}")

        if current == "mobile":
            self.add_mobile_pending(user_id, message)
            await self.notify_mobile(user_id, message)
            return True

        return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                "user_count": len(self._states),
                "active_24h": sum(1 for s in self._states.values() if time.time() - s.last_active_ts < 86400),
                "mobile_pending_total": sum(len(v) for v in self._mobile_pending.values()),
            }

    # ── 跨平台用户 ID 注册 (v9.0) ──

    def register_platform_id(self, canonical_user_id: str, platform_id: str, platform_specific_id: str) -> None:
        """注册用户在某平台上的平台特定 ID (用于跨平台 ID 翻译)

        Args:
            canonical_user_id: 规范用户 ID (如 QQ 号 "1523878699")
            platform_id: 平台 ID (desktop, mobile, weixin_ilink...)
            platform_specific_id: 该平台上的用户 ID (如 "desktop_user")
        """
        if not canonical_user_id or not platform_id or not platform_specific_id:
            return

        uid = str(canonical_user_id)
        pid = str(platform_id)
        psid = str(platform_specific_id)

        with self._lock:
            state = self._states.setdefault(uid, UserPlatformState(user_id=uid))
            plat = state.platforms.setdefault(pid, {"last_active": 0.0, "msg_count": 0, "first_seen": time.time()})
            plat["platform_specific_id"] = psid
        self._save()
        logger.debug(f"[PlatformAwareness] 注册跨平台 ID: {uid}@{pid} = {psid}")

    def resolve_platform_id(self, canonical_user_id: str, platform_id: str) -> str:
        """将规范用户 ID 翻译为特定平台的用户 ID

        Args:
            canonical_user_id: 规范用户 ID (如 QQ 号)
            platform_id: 目标平台 ID

        Returns:
            该平台的用户 ID，无映射时返回原 canonical_user_id
        """
        with self._lock:
            state = self._states.get(str(canonical_user_id))
            if state:
                plat = state.platforms.get(str(platform_id), {})
                psid = plat.get("platform_specific_id", "")
                if psid:
                    return psid
        return str(canonical_user_id)

    def get_canonical_id(self, platform_id: str, platform_specific_id: str) -> str:
        """反向查找：根据平台特定 ID 查找规范用户 ID"""
        with self._lock:
            for uid, state in self._states.items():
                plat = state.platforms.get(str(platform_id), {})
                if plat.get("platform_specific_id", "") == str(platform_specific_id):
                    return uid
        return str(platform_specific_id)


_global_awareness: Optional[PlatformAwareness] = None
_awareness_lock = threading.Lock()


def get_platform_awareness() -> PlatformAwareness:
    """获取全局 PlatformAwareness 单例"""
    global _global_awareness
    with _awareness_lock:
        if _global_awareness is None:
            _global_awareness = PlatformAwareness()
        return _global_awareness


def reset_platform_awareness():
    """重置全局单例 (测试用)"""
    global _global_awareness
    with _awareness_lock:
        _global_awareness = None


__all__ = [
    "PlatformAwareness",
    "UserPlatformState",
    "get_platform_awareness",
    "reset_platform_awareness",
    "KNOWN_PLATFORM_PRIORITY",
    "PLATFORM_TYPE_DELIVERY",
]
