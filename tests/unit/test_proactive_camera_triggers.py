"""The camera triggers inside proactive_chat must actually execute.

Written after a real failure: deleting a redundant throttle also deleted the
function-local ``import time`` that later lines still used, so every poll raised
``NameError: name 'time' is not defined`` - and the whole proactive chain,
camera included, silently stopped. It reached production because
``tests/test_proactive_chat.py`` cannot run: ``pytest-asyncio`` is not installed,
so its async tests have never executed.

These tests are deliberately synchronous (``asyncio.run``) so they run under the
current plugin set, and they call the real trigger functions rather than a helper,
because the bug was a NameError inside them.
"""

from __future__ import annotations

import asyncio
import time

import pytest


class _PresenceSnapshot:
    state = "returned"
    transition = "returned"
    confidence = 0.8
    reasons = ["重新检测到人脸"]
    last_face_seconds = 1.0
    updated_at = 0.0

    def __init__(self) -> None:
        self.updated_at = time.time()

    def describe(self) -> str:
        return "佳刚回到电脑前"


@pytest.fixture()
def chat_system(monkeypatch):
    """A real ProactiveChatSystem with only its AI call and I/O stubbed."""
    from core.proactive_chat import get_proactive_chat_system

    system = get_proactive_chat_system()

    class _AI:
        async def chat(self, **_kwargs):
            class _R:
                content = "回来啦，坐吧。"

            return _R()

    monkeypatch.setattr(system, "ai_client", _AI(), raising=False)

    # Autonomous camera observation is the consent gate these triggers check.
    monkeypatch.setattr("core.camera_control.read_state",
                        lambda: {"autonomous": True, "mode": "companion"}, raising=False)
    return system


def _context(target_id: int = 1523878699):
    from core.proactive_chat import ChatContext

    return ChatContext(chat_type="private", target_id=target_id, platform="weixin_ilink")


def _presence(monkeypatch, snapshot):
    class _Tracker:
        def snapshot(self):
            return snapshot

        def last_transition(self):
            new = _PresenceSnapshot()
            new.updated_at = float(getattr(snapshot, "updated_at", 0.0) or 0.0)
            return "returned", new.updated_at

    monkeypatch.setattr("mcpserver.screen_vision.presence.get_presence_tracker", lambda: _Tracker())


def _activity_pending(monkeypatch, kind: str, phrase: str):
    """Give the shared tracker a pending change.

    It has to replace the module's tracker, not `get_activity_tracker`: the card
    and the consume helpers close over that instance, so patching the accessor
    left this test asserting on a code path that returned early and proved
    nothing about whether the trigger really runs.
    """
    from mcpserver.screen_vision import activity as activity_module

    class _Tracker:
        def pending_change(self):
            return kind, ""

        def peek_change(self):
            return None

        def consume_change(self):
            return None

    monkeypatch.setattr(activity_module, "_tracker", _Tracker())


def test_the_presence_trigger_executes_without_raising(chat_system, monkeypatch):
    """Regression: it raised NameError once the local ``import time`` was removed."""
    _presence(monkeypatch, _PresenceSnapshot())
    context = _context()
    # The point is that this returns rather than raising. Any answer is fine.
    result = asyncio.run(chat_system._check_presence_trigger(context.target_id, context))
    assert result is None or result.should_respond


def _reset_presence_bookkeeping(system) -> None:
    system._last_presence_key = ""
    system._sent_messages_history.clear()
    system._message_cache.clear()
    system._last_trigger_by_type.clear()


def _presence_at(monkeypatch, stamp: float):
    class _Tracker:
        def snapshot(self):
            snapshot = _PresenceSnapshot()
            snapshot.updated_at = stamp
            # This is what the real tracker does: the transition lives inside the
            # newest snapshot for exactly one evaluation and is then overwritten,
            # so a poll that arrives later sees "". Reading it from the snapshot
            # is the bug these tests now guard against; the change survives in
            # `last_transition()` instead.
            snapshot.transition = ""
            return snapshot

        def last_transition(self):
            return "returned", stamp

    monkeypatch.setattr("mcpserver.screen_vision.presence.get_presence_tracker", lambda: _Tracker())


def test_two_arrivals_in_one_run_are_both_greeted(chat_system, monkeypatch):
    """Regression: the transition key was always ``returned:0``.

    It was built from ``last_face_seconds``, which is always small whenever a
    return is produced - so the second arrival looked like the first and was
    silently swallowed. One greeting per process, no matter how often Jia came
    back.

    The model here answers differently each time on purpose: the *content*
    de-duplication is a separate, deliberate rule, and a canned reply would be
    refused by it rather than by the bookkeeping under test.
    """
    _reset_presence_bookkeeping(chat_system)
    context = _context()
    spoken: list[str] = []

    class _VaryingAI:
        def __init__(self) -> None:
            self.calls = 0

        async def chat(self, **_kwargs):
            # A plain string, which is what the real AIClient returns.
            self.calls += 1
            return f"回来啦，这是第 {self.calls} 次。"

    monkeypatch.setattr(chat_system, "ai_client", _VaryingAI(), raising=False)

    for stamp in (1000.0, 2000.0, 3000.0):
        _presence_at(monkeypatch, stamp)
        result = asyncio.run(chat_system._check_presence_trigger(context.target_id, context))
        if result is not None and result.should_respond:
            spoken.append(result.message)
    assert len(spoken) >= 2, f"三次回到电脑前只问候了 {len(spoken)} 次"
    assert len(set(spoken)) == len(spoken), "每次问候都应该是独立的一句话"


def test_a_refused_greeting_does_not_close_the_path_forever(chat_system, monkeypatch):
    """A rejected proposal must be re-proposable.

    The key used to be written before delivery, so one arrival that the
    coordinator throttled meant she never mentioned coming back again.
    """
    _reset_presence_bookkeeping(chat_system)
    context = _context()
    _presence_at(monkeypatch, 4000.0)

    first = asyncio.run(chat_system._check_presence_trigger(context.target_id, context))
    assert first is not None and first.should_respond
    key_after_proposal = chat_system._last_presence_key
    assert key_after_proposal, "提案应该记下这次在场变化"

    # The coordinator turns it down, so the bookkeeping is undone.
    first.undo()
    assert chat_system._last_presence_key == "", "被拒后这个变化应该还能再提一次"

    again = asyncio.run(chat_system._check_presence_trigger(context.target_id, context))
    assert again is not None and again.should_respond, "同一个在场变化在第一次被拒后应该能重新提案"
    _reset_presence_bookkeeping(chat_system)


def test_a_delivered_greeting_is_not_re_proposed(chat_system, monkeypatch):
    """The other half: once it really went out, the same arrival stays spent."""
    _reset_presence_bookkeeping(chat_system)
    context = _context()
    _presence_at(monkeypatch, 5000.0)

    first = asyncio.run(chat_system._check_presence_trigger(context.target_id, context))
    assert first is not None and first.should_respond
    first.settle()
    second = asyncio.run(chat_system._check_presence_trigger(context.target_id, context))
    assert second is None, "同一次在场变化不该被说两遍"
    _reset_presence_bookkeeping(chat_system)


def test_a_rejected_vision_line_survives_to_be_retried(chat_system, monkeypatch):
    """回归：投递失败后，她攒下的那句话必须还在队列里等她再试一次。

    `_is_duplicate` 有副作用——它把这句话写进 `_message_cache`——而它在投递
    **之前**就被调用了。投递失败时消息留在队列，下一次轮询（45 秒后，而
    `_duplicate_window` 是 90 秒）再读同一条，`_is_duplicate` 命中缓存返回 True，
    于是 `agent.take_message()` 把它丢掉。

    实际后果是：她看到的、已经想好要说的那句话，**第一次尝试被拒之后就永久消失**，
    队列里永远不会有一条消息被成功送出。日志里 `camera:voice:...:7/8/9/11` 序号一直
    在涨、却一条都没发出去，就是这个循环。
    """
    from mcpserver.screen_vision.vision_agent import get_vision_agent

    class _RefusingCoordinator:
        """Stands in for "the hourly quota is full" / "global cooldown"."""

        async def submit_message(self, message, **kwargs):
            return False

    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator",
                        lambda: _RefusingCoordinator())

    agent = get_vision_agent()
    agent.clear_messages()
    chat_system._message_cache.clear()
    chat_system._sent_messages_history.clear()
    agent._pending = [{"at": time.time(), "message": "歪着头看什么呢？", "summary": "佳歪着头"}]
    context = _context()

    first = asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))
    assert first is None, "被拒时不应该产出提案"
    assert [item["message"] for item in agent.peek_messages()] == ["歪着头看什么呢？"], \
        "被拒后她攒下的话必须留着"

    # The next poll finds the very same line still queued.
    second = asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))
    assert second is None
    assert [item["message"] for item in agent.peek_messages()] == ["歪着头看什么呢？"], \
        "第二次轮询不能把它当重复消息销毁——它从来没发出去过"

    # And when the coordinator finally accepts it, it goes out exactly once.
    accepted: list[str] = []

    class _AcceptingCoordinator:
        async def submit_message(self, message, **kwargs):
            accepted.append(message)
            return True

    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator",
                        lambda: _AcceptingCoordinator())
    third = asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))
    assert third is not None and third.delivered is True
    assert accepted == ["歪着头看什么呢？"]
    assert agent.peek_messages() == [], "发出去之后才该取走"
    agent.clear_messages()
    chat_system._message_cache.clear()
    chat_system._sent_messages_history.clear()


def test_a_retried_vision_line_keeps_the_same_coordinator_key(chat_system, monkeypatch):
    """重试同一条话时 key 必须稳定。

    以前每次尝试都把 `_vision_voice_seq` 加一，于是同一条消息每次重试都是全新的
    key，协调器的同类冷却对它完全失效——能不能发出去只取决于总配额还剩多少。
    """
    from mcpserver.screen_vision.vision_agent import get_vision_agent

    keys: list[str] = []

    class _RefusingCoordinator:
        async def submit_message(self, message, **kwargs):
            keys.append(str(kwargs.get("key") or ""))
            return False

    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator",
                        lambda: _RefusingCoordinator())

    agent = get_vision_agent()
    agent.clear_messages()
    chat_system._message_cache.clear()
    chat_system._sent_messages_history.clear()
    stamp = time.time()
    agent._pending = [{"at": stamp, "message": "又歪着头了", "summary": "佳歪着头"}]
    context = _context()

    asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))
    asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))
    assert len(keys) == 2
    assert keys[0] == keys[1], f"同一条话重试时 key 不该变: {keys}"
    agent.clear_messages()
    chat_system._message_cache.clear()
    chat_system._sent_messages_history.clear()


def test_the_activity_trigger_executes_without_raising(chat_system, monkeypatch):
    _activity_pending(monkeypatch, "typing", "在敲键盘")
    context = _context()
    result = asyncio.run(chat_system._check_activity_trigger(context.target_id, context))
    assert result is None or result.should_respond


def test_the_vision_voice_trigger_executes_without_raising(chat_system, monkeypatch):
    """The outlet for what she decided was worth saying while watching."""
    from mcpserver.screen_vision.vision_agent import get_vision_agent

    agent = get_vision_agent()
    agent._pending = [{"at": time.time(), "message": "回来啦", "summary": "佳回来了"}]
    context = _context()
    result = asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))
    assert result is None or result.should_respond
    agent.clear_messages()


def test_stale_vision_voice_is_dropped_after_newer_camera_state(chat_system, monkeypatch):
    from mcpserver.screen_vision.vision_agent import get_vision_agent

    agent = get_vision_agent()
    stamp = time.time()
    agent._pending = [{
        "at": stamp,
        "message": "这会儿没看到人，可能离开电脑前了。",
        "summary": "画面里没看到人",
        "faces": 0,
    }]
    monkeypatch.setattr(
        "mcpserver.screen_vision.vision_stream.get_vision_stream",
        lambda: type("Stream", (), {"latest": lambda self: {
            "at": stamp + 1,
            "reading": {"faces": 1},
        }})(),
    )
    result = asyncio.run(chat_system._check_miya_vision_trigger(
        1523878699, _context()
    ))
    assert result is None
    assert agent.peek_messages() == []


def test_a_line_she_already_decided_is_delivered_exactly_once(chat_system, monkeypatch):
    """The trigger delivers it itself, so both senders must skip it.

    Without the flag the message went out through the coordinator *and* was
    handed to the send outlet again - a duplicate that only the five-minute
    global cooldown happened to swallow, while the log claimed it was sent.
    """
    from mcpserver.screen_vision.vision_agent import get_vision_agent

    delivered: list[tuple] = []

    class _Coordinator:
        async def submit_message(self, message, **kwargs):
            delivered.append((message, kwargs))
            return True

    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator", lambda: _Coordinator())

    agent = get_vision_agent()
    agent._pending = [{"at": time.time(), "message": "歪着头看什么呢？", "summary": "佳歪着头"}]
    context = _context()
    result = asyncio.run(chat_system._check_miya_vision_trigger(context.target_id, context))

    assert result is not None and result.message == "歪着头看什么呢？"
    assert result.delivered is True, "已投递的消息必须标记出来，否则会被发第二遍"
    assert [item[0] for item in delivered] == ["歪着头看什么呢？"]
    assert agent.peek_messages() == [], "投递成功后她攒下的话要被取走，而不是留着重发"
    agent.clear_messages()


def test_both_senders_honour_the_delivered_flag():
    """Source-level: the flag is only useful if every dispatcher checks it.

    ``check_and_respond`` has two callers that put a result on the wire - the
    background poll loop and the ordinary reply path in the decision hub - so
    both have to look at ``delivered``.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    poll = (root / "core" / "proactive_chat.py").read_text(encoding="utf-8")
    hub = (root / "hub" / "decision_hub.py").read_text(encoding="utf-8")
    assert "result.delivered" in poll, "后台轮询没有检查 delivered，会重复发送"
    assert "result.delivered" in hub, "决策层没有检查 delivered，会重复分发"


def test_time_is_imported_at_module_scope():
    """The durable fix: any function in the module may use ``time`` freely.

    A duplicate function-local import is what made the removal look safe.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "core" / "proactive_chat.py").read_text(encoding="utf-8")
    header = source.split("from dataclasses", 1)[0]
    assert "import time" in header, "模块级必须 import time，否则函数内一旦漏了就整条链路挂掉"


def test_no_async_test_in_this_file_is_silently_skipped():
    """Documents why this file is written synchronously.

    ``pytest-asyncio`` is absent, so an ``async def`` test here would not run at
    all - which is how a NameError reached production. Checked by parsing the
    file rather than searching its text, because a substring search matches the
    warning message itself.
    """
    import ast
    from pathlib import Path

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    async_tests = [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and isinstance(node, ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    ]
    assert async_tests == [], f"这些测试会被静默跳过: {async_tests}"
