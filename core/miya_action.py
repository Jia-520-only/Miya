"""实际行动的开始、结束与结果判定；反馈故障不改变行动的返回语义。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from core.miya_life_event import LifeEventType, MiyaEvent

logger = logging.getLogger("Miya.Action")


def tool_outcome(value) -> dict:
    """优先使用结构化结果；普通文本只证明调用返回，不能证明外部副作用成功。"""
    structured = value
    if isinstance(value, str):
        try:
            structured = json.loads(value)
        except (ValueError, TypeError):
            pass
    status = "completed"
    success = None
    if isinstance(structured, dict):
        flag = structured.get("success", structured.get("ok"))
        named_status = str(structured.get("status", "")).lower()
        if named_status in {
            "queued", "pending", "accepted", "claimed", "processing", "cancelled", "timed_out", "unknown",
        }:
            status = named_status
        elif (named_status in {"error", "failed", "failure", "rejected", "denied", "invalid"}
              or flag is False or structured.get("error")):
            status, success = "failed", False
        elif flag is True or named_status in {"success", "succeeded", "sent"}:
            status, success = "succeeded", True
    elif value is False:
        status, success = "failed", False
    elif value is True:
        status, success = "succeeded", True
    if isinstance(value, str):
        prefix = value.lstrip()
        if prefix.startswith(("❌", "错误：", "错误:", "Error:", "工具执行失败", "MCP 调用失败:", "MCP 调用异常:")):
            status, success = "failed", False
    # DSH's process success only means its turn ended normally. Preserve its
    # execution metadata without treating that as proof the delegated task landed.
    if isinstance(structured, dict) and structured.get("execution_status") in {
        "timed_out", "cancelled", "queued", "pending", "accepted", "claimed", "processing",
    }:
        status, success = structured["execution_status"], None
    return {"status": status, "success": success, "summary": str(value)[:1000]}


class ActionFeedback:
    def __init__(self, action: str, context: dict, kind: str, action_id: str = ""):
        from core.miya_spine import get_existing_spine
        from core.miya_soul_state import LifecyclePhase

        self.spine = get_existing_spine()
        if self.spine is not None and self.spine.phase == LifecyclePhase.SHUTDOWN:
            self.spine = None
        self.action = action
        self.action_id = action_id or uuid.uuid4().hex
        self.correlation_id = str(context.get("request_id") or context.get("message_id") or self.action_id)
        self.context = {
            key: str(context.get(key) or "")
            for key in ("platform", "user_id", "group_id", "session_id", "message_id", "delivery_id")
        }
        if self.spine is not None and kind == "tool" and action != "manage_intention":
            try:
                intention_id = self.spine.match_action_intention(action, context)
                if intention_id:
                    self.context["intention_id"] = intention_id
            except Exception as exc:
                logger.warning("行动与事项关联失败 action=%s: %s", action, exc)
        self.kind = kind
        self.started_at = time.monotonic()
        self.result = {"status": "completed", "success": None}

    def publish(self, event_type: str) -> None:
        if self.spine is None:
            return
        try:
            payload = {
                "action": self.action, "action_id": self.action_id,
                "kind": self.kind, **self.context,
            }
            if event_type == LifeEventType.ACTION_RESULT:
                payload["result"] = {
                    **self.result,
                    "duration_ms": round((time.monotonic() - self.started_at) * 1000, 3),
                }
            self.spine.emit_event(MiyaEvent(
                event_type, source=self.context["platform"] or self.kind, actor="miya",
                correlation_id=self.correlation_id, payload=payload, importance=0.7,
            ))
        except Exception as exc:
            logger.warning("行动反馈记录失败 action=%s: %s", self.action, exc)


@asynccontextmanager
async def track_action(action: str, context: dict, *, kind: str, action_id: str = ""):
    feedback = ActionFeedback(action, context, kind, action_id)
    feedback.publish(LifeEventType.ACTION_STARTED)
    try:
        yield feedback
    except asyncio.CancelledError:
        feedback.result = {"status": "cancelled", "success": None}
        raise
    except TimeoutError as exc:
        feedback.result = {"status": "timed_out", "success": None, "error": str(exc)[:500]}
        raise
    except Exception as exc:
        feedback.result = {"status": "failed", "success": False, "error": str(exc)[:500]}
        raise
    finally:
        feedback.publish(LifeEventType.ACTION_RESULT)
