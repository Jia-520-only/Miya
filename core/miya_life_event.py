"""统一的弥娅生命事件模型。

事件是各入口连接到脊柱的最小共同语言。payload 保留来源特有的数据，
其余字段用于排序、追踪和让器官共享一致的上下文。
"""

from __future__ import annotations

import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


class LifeEventType:
    USER_MESSAGE = "user.message"
    ACTION_STARTED = "action.started"
    ACTION_RESULT = "action.result"
    MEMORY_RECALLED = "memory.recalled"
    INTENTION_CHANGED = "intention.changed"
    SYSTEM_EVENT = "system.event"
    PLATFORM_EVENT = "platform.event"
    LIFECYCLE_CHANGED = "lifecycle.changed"


@dataclass(slots=True)
class MiyaEvent:
    event_type: str
    source: str = "unknown"
    actor: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "source": self.source,
            "actor": self.actor,
            "payload": deepcopy(self.payload),
            "timestamp": self.timestamp,
            "importance": self.importance,
            "correlation_id": self.correlation_id,
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MiyaEvent:
        return cls(**deepcopy(data))
