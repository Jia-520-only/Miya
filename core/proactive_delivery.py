"""主动投递结果与有界、单消费者的离线队列。"""

from dataclasses import dataclass
from datetime import UTC, datetime
import time


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    delivery_id: str = ""
    reason: str = ""

    def __bool__(self) -> bool:
        return self.status in {"sent", "queued"}


def delivery_accepted(result) -> bool:
    return bool(result) if isinstance(result, DeliveryResult) else result is True


def enqueue_delivery(
    pending: dict,
    target: str,
    message: str,
    delivery_id: str,
    *,
    platform: str = "terminal",
    chat_type: str = "private",
    store_memory: bool = True,
    trigger_type: str = "",
) -> None:
    now = time.time()
    for key, messages in list(pending.items()):
        pending[key] = [item for item in messages if now - item.get("_queued_at", now) < 600]
        if not pending[key]:
            pending.pop(key, None)
    bucket = pending.setdefault(str(target), [])
    if any(item.get("delivery_id") == delivery_id for item in bucket):
        return
    bucket.append({
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
        "delivery_id": delivery_id,
        "platform": platform,
        "chat_type": chat_type,
        "store_memory": store_memory,
        "trigger_type": trigger_type,
        "_queued_at": now,
    })
    del bucket[:-100]


def take_pending_deliveries(pending: dict, target: str) -> list[dict]:
    now = time.time()
    messages = pending.pop(str(target), [])
    return [
        {key: value for key, value in item.items() if key != "_queued_at"}
        for item in messages if now - item.get("_queued_at", now) < 600
    ]
