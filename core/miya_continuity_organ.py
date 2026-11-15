"""统一心跳驱动的事项跟进；共享主动协调器，只报告或询问，不重放行动。"""

from __future__ import annotations

import asyncio
import logging
import time

from core.miya_intention import life_scope
from core.miya_organ import MiyaOrgan
from core.miya_soul_state import LifecyclePhase
from core.proactive_delivery import DeliveryResult

logger = logging.getLogger("Miya.Continuity")


class MiyaContinuityOrgan(MiyaOrgan):
    def __init__(self, coordinator):
        super().__init__("continuity", priority=35)
        self._coordinator = coordinator
        self._future = None
        self._last_poll = 0.0

    def on_soul_state(self, state) -> None:
        if (not self.started or not self._spine or not self._coordinator
                or state.lifecycle_phase not in {LifecyclePhase.RUNNING, LifecyclePhase.IDLE,
                                                  LifecyclePhase.DROWSY, LifecyclePhase.SLEEP}
                or self._spine._loop is None or not self._spine._loop.is_running()):
            return
        now = time.time()
        if (now - self._last_poll < 60 or now - self._spine._last_interaction < 60
                or (self._future is not None and not self._future.done())):
            return
        self._last_poll = now
        due = self._spine.due_intentions(now=now)
        if due:
            self._future = asyncio.run_coroutine_threadsafe(self.follow_up(due[0]), self._spine._loop)

    async def follow_up(self, intention: dict):
        spine = self._spine
        if (spine is None or self._coordinator is None
                or spine.phase not in {LifecyclePhase.RUNNING, LifecyclePhase.IDLE,
                                       LifecyclePhase.DROWSY, LifecyclePhase.SLEEP}
                or time.time() - spine._last_interaction < 60):
            return False
        scope = life_scope(intention)
        try:
            reserved = await asyncio.to_thread(
                spine.manage_intention, "followup_attempt", scope, intention_id=intention["intention_id"],
            )
            # 跟进预留必须先落盘；取消或重启不会立刻重复发送同一次提醒。
            if not reserved.get("persisted"):
                return False
            interaction_at = spine._last_interaction

            def still_current():
                return (spine.phase in {LifecyclePhase.RUNNING, LifecyclePhase.IDLE,
                                        LifecyclePhase.DROWSY, LifecyclePhase.SLEEP}
                        and spine._last_interaction == interaction_at
                        and any(item["intention_id"] == reserved["intention_id"]
                                and item["revision"] == reserved["revision"]
                                for item in spine.list_intentions(scope)))

            state_text = {
                "active": "还没有完成记录", "waiting": "仍在等待后续处理",
                "needs_confirmation": "结果还需要核实",
            }[reserved["status"]]
            event = {
                "source": "continuity", "event": "intention_followup",
                "summary": reserved["title"], "expected_outcome": reserved["expected_outcome"],
                "status": reserved["status"], "last_result": reserved["last_result"],
                "evidence_event_id": reserved["evidence_event_id"],
                "experience_emotion": spine.get_experience_mood(scope),
                "candidate_message": f"我还记着“{reserved['title']}”，目前{state_text}。你想现在接着处理吗？",
            }
            outcome = await self._coordinator.submit_event(
                event, key=f"intention:{reserved['intention_id']}:{reserved['revision']}",
                target_id=scope["group_id"] or scope["user_id"],
                chat_type="group" if scope["group_id"] else "private", platform=scope["platform"],
                trigger_type="intention_followup", source="continuity", guard=still_current, detailed=True,
            )
            if isinstance(outcome, DeliveryResult) and outcome.status == "skipped":
                await asyncio.to_thread(
                    spine.manage_intention, "followup_defer", scope,
                    intention_id=reserved["intention_id"], reservation_revision=reserved["revision"],
                )
            return outcome
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("事项跟进未发出: %s", exc)
            return False

    async def on_shutdown(self) -> None:
        if self._future is not None and not self._future.done():
            self._future.cancel()
            await asyncio.gather(asyncio.wrap_future(self._future), return_exceptions=True)
        await super().on_shutdown()
