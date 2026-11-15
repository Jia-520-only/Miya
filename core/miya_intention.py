"""持续事项的状态转换；与事件日志共用投影，不执行或重放外部行动。"""

from __future__ import annotations

import copy
import math
import time
import uuid

from core.miya_life_event import LifeEventType, MiyaEvent

TERMINAL_STATUSES = {"completed", "abandoned"}
FOLLOWUP_INTERVAL = 1800
MAX_FOLLOWUPS = 2


def life_scope(context: dict) -> dict[str, str]:
    """保留平台边界；默认会话别名归一，显式会话严格隔离。"""
    user = str(context.get("user_id") or "")
    platform = str(context.get("platform") or "unknown")
    group = str(context.get("group_id") or "")
    if group in {"0", "None", "null"}:
        group = ""
    session = str(context.get("session_id") or "")
    if session:
        from memory.context_identity import ContextIdentity

        if session in ContextIdentity.resolve(user, group, platform).session_ids:
            session = ""
    return {"user_id": user, "platform": platform, "group_id": group, "session_id": session}


def same_scope(record: dict, scope: dict) -> bool:
    return all(record.get(key, "") == value for key, value in scope.items())


def change_intention(current: dict | None, operation: str, context: dict, **values) -> dict:
    """只接受显式事项操作；完成需要行动证据或当前用户的确认原文。"""
    scope = life_scope(context)
    if not scope["user_id"] or scope["user_id"] in {"0", "global"} or scope["platform"] == "unknown":
        raise ValueError("持续事项需要明确的用户和平台")
    now = time.time()
    correlation = str(context.get("request_id") or context.get("message_id") or "")
    if operation == "remember":
        if not correlation:
            raise ValueError("持续事项需要明确的来源消息")
        title = str(values.get("title") or "").strip()
        outcome = str(values.get("expected_outcome") or "").strip()
        action = str(values.get("action_name") or "").strip()
        mode = values.get("completion_mode", "user_confirmation")
        if not title or not outcome:
            raise ValueError("请提供事项和可核实的完成条件")
        if mode not in {"action_success", "user_confirmation"} or (mode == "action_success" and not action):
            raise ValueError("行动完成模式需要指定确切的工具名")
        follow_up = values.get("follow_up", False)
        if not isinstance(follow_up, bool):
            raise ValueError("follow_up 必须是布尔值")
        return {
            "intention_id": uuid.uuid4().hex, **scope,
            "title": title[:200], "expected_outcome": outcome[:300],
            "action_name": action[:100], "completion_mode": mode,
            "status": "active", "correlation_id": correlation,
            "created_at": now, "updated_at": now, "revision": 1,
            "attempts": 0, "last_action_id": "", "pending_action_id": "", "execution_interrupted": False,
            "last_result": {},
            "evidence_event_id": "", "evidence_at": None,
            "follow_up": follow_up, "followup_count": 0,
            "next_followup_at": now + FOLLOWUP_INTERVAL if follow_up else None,
        }
    if current is None or not same_scope(current, scope):
        raise ValueError("当前会话中没有这个事项")
    if current["status"] in TERMINAL_STATUSES:
        raise ValueError("事项已收尾，请为新的约定新建事项")
    record = copy.deepcopy(current)
    record.update(updated_at=now, revision=record["revision"] + 1)
    if operation == "resume":
        if record["status"] in {"in_progress", "needs_confirmation"} or record.get("pending_action_id"):
            raise ValueError("行动结果尚未核实，请先确认结果，避免重复执行")
        if not correlation:
            raise ValueError("继续事项需要明确的来源消息")
        record.update(status="active", correlation_id=correlation, followup_count=0)
        record["next_followup_at"] = now + FOLLOWUP_INTERVAL if record["follow_up"] else None
    elif operation in {"pause", "abandon"}:
        record["status"] = "paused" if operation == "pause" else "abandoned"
        record["next_followup_at"] = None
    elif operation in {"confirm", "retry"}:
        evidence = str(values.get("evidence") or "").strip()
        message = str(context.get("current_input") or "")
        if not correlation or not evidence or evidence not in message:
            raise ValueError("完成确认需要引用当前用户消息中的确认原文")
        confirmed = operation == "confirm"
        if (not confirmed and record.get("pending_action_id") and record["status"] != "needs_confirmation"
                and not record.get("execution_interrupted")):
            raise ValueError("原行动仍在执行，请等待结果后重试")
        record.update(status="completed" if confirmed else "active", correlation_id=correlation,
                      pending_action_id="", execution_interrupted=False,
                      followup_count=record["followup_count"] if confirmed else 0,
                      next_followup_at=None if confirmed or not record["follow_up"] else now + FOLLOWUP_INTERVAL,
                      last_result={"status": "user_confirmed" if confirmed else "user_requested_retry",
                                   "success": confirmed, "summary": evidence[:300]},
                      evidence_at=now)
    elif operation == "recover":
        if record["status"] not in {"in_progress", "paused"} or not record.get("pending_action_id"):
            raise ValueError("只有中断的执行需要恢复核实")
        paused = record["status"] == "paused"
        record.update(status="paused" if paused else "needs_confirmation", execution_interrupted=True,
                      next_followup_at=now + FOLLOWUP_INTERVAL if record["follow_up"] and not paused else None)
    elif operation == "followup_attempt":
        due = record.get("next_followup_at")
        if (not record["follow_up"] or record["status"] not in {"active", "waiting", "needs_confirmation"}
                or record["followup_count"] >= MAX_FOLLOWUPS or due is None or due > now):
            raise ValueError("事项尚未到跟进时间")
        record["followup_count"] += 1
        record["next_followup_at"] = (
            now + FOLLOWUP_INTERVAL if record["followup_count"] < MAX_FOLLOWUPS else None
        )
    elif operation == "followup_defer":
        if values.get("reservation_revision") != current["revision"]:
            raise ValueError("事项已变化，忽略旧跟进的延期")
        record["followup_count"] = max(0, current["followup_count"] - 1)
        record["next_followup_at"] = now + FOLLOWUP_INTERVAL
    else:
        raise ValueError("不支持的事项操作")
    return record


def project_intention(current: dict | None, event: MiyaEvent) -> dict | None:
    """用于 SQLite 原子投影与内存状态更新的同一个 reducer。"""
    if event.event_type == LifeEventType.INTENTION_CHANGED:
        record = copy.deepcopy(event.payload["intention"])
        if current and not same_scope(record, life_scope(current)):
            return None
        if current and record["revision"] <= current["revision"]:
            return None
        if event.payload.get("operation") in {"remember", "confirm", "retry", "abandon"}:
            record["evidence_event_id"] = event.event_id
        return record
    if (not current or not same_scope(current, life_scope(event.payload))
            or event.payload.get("action") != current["action_name"]):
        return None
    record = copy.deepcopy(current)
    if event.event_type == LifeEventType.ACTION_STARTED:
        if current["status"] not in {"active", "waiting"} or current["correlation_id"] != event.correlation_id:
            return None
        record.update(status="in_progress", last_action_id=event.payload["action_id"],
                      pending_action_id=event.payload["action_id"], execution_interrupted=False,
                      attempts=current["attempts"] + 1)
    elif event.event_type == LifeEventType.ACTION_RESULT:
        if not current.get("pending_action_id") or current["pending_action_id"] != event.payload.get("action_id"):
            return None
        result = event.payload.get("result", {})
        status, success = result.get("status"), result.get("success")
        if status in {"queued", "pending", "accepted", "claimed"}:
            state = "waiting"
        elif status in {"cancelled", "timed_out"} or success not in (True, False):
            state = "needs_confirmation"
        elif success is False:
            state = "waiting"
        elif success is True:
            state = "completed" if current["completion_mode"] == "action_success" else "needs_confirmation"
        else:
            state = "needs_confirmation"
        if current["status"] in {"paused", "abandoned"}:
            state = current["status"]
        record.update(status=state, pending_action_id="", execution_interrupted=False, last_result=copy.deepcopy(result),
                      evidence_event_id=event.event_id, evidence_at=event.timestamp)
        record["next_followup_at"] = (
            event.timestamp + FOLLOWUP_INTERVAL
            if record["follow_up"] and state in {"active", "waiting", "needs_confirmation"} else None
        )
    else:
        return None
    record.update(updated_at=event.timestamp, revision=current["revision"] + 1)
    return record


def experience_emotion(current: dict, intentions: list[dict], *, now: float | None = None) -> dict:
    """在现有情绪谱上投影同会话经历；时间衰减，不反复累加或改写基础人格。"""
    now = time.time() if now is None else now
    emotions = dict(current)
    adjustments = {}
    evidence = []
    for record in intentions:
        when, event_id = record.get("evidence_at"), record.get("evidence_event_id")
        if when is None or not event_id or record["status"] in {"paused", "abandoned"}:
            continue
        age = max(0, now - when)
        if age > 86400:
            continue
        result = record.get("last_result", {})
        success = result.get("success")
        # 排队与未知结果不会被解释成失败或成功。
        if success is not True and success is not False:
            continue
        emotion = "joy" if success else "sadness"
        if emotion not in emotions:
            continue
        amount = (0.12 if success else 0.08) * math.exp(-age / 21600)
        adjustments[emotion] = min(0.18, adjustments.get(emotion, 0) + amount)
        evidence.append(event_id)
    for emotion, amount in adjustments.items():
        emotions[emotion] = min(1.0, emotions[emotion] + amount)
    return {
        "current": emotions,
        "dominant": max(emotions, key=emotions.get) if emotions else None,
        "intensity": max(emotions.values()) if emotions else None,
        "evidence_event_ids": list(dict.fromkeys(evidence)),
        "source": "emotion_with_experiences",
    }
