"""弥娅脊柱神经生命周期测试"""

import sys
import time
import asyncio

sys.path.insert(0, ".")

from core.miya_spine import get_spine, reset_spine
from core.miya_soul_state import LifecyclePhase
from core.miya_organ import MiyaOrgan


class TestOrgan(MiyaOrgan):
    __test__ = False

    def __init__(self):
        super().__init__("test_organ", priority=10)
        self.states_received = 0
        self.phases_seen = []

    def on_soul_state(self, state):
        self.states_received += 1

    def on_lifecycle_change(self, old, new):
        self.phases_seen.append(new)


async def test():
    reset_spine()
    spine = get_spine()
    organ = TestOrgan()
    spine.register_organ(organ)

    await spine.start()
    # Let heartbeat run for ~2 seconds
    time.sleep(2)

    status = spine.get_status()
    print(f"Phase: {status['phase']}")
    print(f"Tick count: {status['tick_count']}")
    print(f"Organs: {status['organs']}")
    print(f"Organ states received: {organ.states_received}")
    print(f"Organ phases seen: {[p.value for p in organ.phases_seen]}")

    # Verify
    assert status["phase"] == "RUNNING", f"Expected RUNNING, got {status['phase']}"
    assert status["tick_count"] > 0, "Tick count should be > 0"
    assert organ.states_received > 0, "Organ should have received states"
    assert LifecyclePhase.BOOT in organ.phases_seen, "Should have seen BOOT phase"
    assert LifecyclePhase.RUNNING in organ.phases_seen, "Should have seen RUNNING phase"

    await spine.shutdown()
    print(f"Final phase: {spine.phase.value}")
    assert spine.phase == LifecyclePhase.SHUTDOWN
    print("All lifecycle tests PASSED")


if __name__ == "__main__":
    asyncio.run(test())
