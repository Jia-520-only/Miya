"""弥娅灵魂状态快照完整性测试"""

import sys
import time

sys.path.insert(0, ".")

from core.miya_soul_state import MiyaSoulState, LifecyclePhase


def test_soul_state():
    # 创建一个模拟的状态快照
    state = MiyaSoulState(
        tick_index=42,
        tick_count=42,
        uptime_seconds=126.0,
        lifecycle_phase=LifecyclePhase.RUNNING,
        message_count=7,
        proactive=True,
        proactive_message="佳，你在做什么呀？",
        organs_online={"test_organ": True},
    )

    # 验证各项方法
    assert state.is_alive(), "Should be alive in RUNNING phase"

    summary = state.summary()
    assert "Tick #42" in summary
    assert "Proactive intent" in summary

    print(f"Summary: {summary}")
    print(f"Is alive: {state.is_alive()}")
    print("All SoulState tests PASSED")


def test_lifecycle_phases():
    # RUNNING + IDLE + DROWSY are alive
    for phase in [LifecyclePhase.RUNNING, LifecyclePhase.IDLE, LifecyclePhase.DROWSY]:
        s = MiyaSoulState(lifecycle_phase=phase)
        assert s.is_alive(), f"{phase} should be alive"

    # INIT + SHUTDOWN are not alive
    for phase in [LifecyclePhase.INIT, LifecyclePhase.SHUTDOWN, LifecyclePhase.SLEEP]:
        s = MiyaSoulState(lifecycle_phase=phase)
        assert not s.is_alive(), f"{phase} should NOT be alive"

    print("All LifecyclePhase tests PASSED")


if __name__ == "__main__":
    test_soul_state()
    test_lifecycle_phases()
