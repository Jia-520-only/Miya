"""队列管理器测试

测试车站-列车队列模型
"""

import asyncio

import pytest
from services.queue_manager import QueueManager, QueueRequest


@pytest.mark.asyncio
async def test_queue_manager_enqueue():
    """测试入队"""
    qm = QueueManager(
        models={"default": 0.1},
        default_interval=0.1,
    )

    qm.enqueue(
        QueueRequest(
            request_id="req-001",
            priority=1,
            payload={"text": "你好"},
            model_name="default",
        )
    )

    assert qm.pending_count() == 1


@pytest.mark.asyncio
async def test_queue_manager_priority_order():
    """测试优先级排序：P0 先于 P1"""
    processed = []

    async def handler(req: QueueRequest) -> None:
        processed.append(req.request_id)

    qm = QueueManager(
        models={"default": 0.05},
        default_interval=0.05,
    )
    qm.set_handler(handler)

    # 先投 P3, 再投 P0 (应该先处理 P0)
    qm.enqueue(
        QueueRequest(
            request_id="low",
            priority=3,
            payload={},
            model_name="default",
        )
    )
    qm.enqueue(
        QueueRequest(
            request_id="high",
            priority=0,
            payload={},
            model_name="default",
        )
    )

    await qm.start()
    await asyncio.sleep(0.3)
    await qm.stop()

    assert len(processed) >= 1
    # P0 (high) 应该先于或等于 P3 (low)
    if "high" in processed:
        assert processed[0] == "high"


@pytest.mark.asyncio
async def test_queue_manager_retry():
    """测试请求重试"""
    error_counts: dict[str, int] = {}
    processed_ids: list[str] = []

    async def handler(req: QueueRequest) -> None:
        processed_ids.append(req.request_id)
        count = error_counts.get(req.request_id, 0)
        if count < 1:
            error_counts[req.request_id] = count + 1
            raise ValueError("故意失败")

    qm = QueueManager(
        models={"default": 0.05},
        default_interval=0.05,
    )
    qm.set_handler(handler)

    qm.enqueue(
        QueueRequest(
            request_id="retry-test",
            priority=1,
            payload={},
            model_name="default",
            max_retries=1,
        )
    )

    await qm.start()
    await asyncio.sleep(0.5)
    await qm.stop()

    # 应该被处理至少 2 次 (初始 + 重试)
    assert processed_ids.count("retry-test") >= 2


@pytest.mark.asyncio
async def test_queue_manager_estimate_wait():
    """测试等待时间估算"""
    qm = QueueManager(
        models={"default": 0.1},
        default_interval=0.1,
    )

    for i in range(4):
        qm.enqueue(
            QueueRequest(
                request_id=f"req-{i}",
                priority=3,
                payload={},
                model_name="default",
            )
        )

    wait = qm.estimate_wait("default")
    assert wait > 0


@pytest.mark.asyncio
async def test_queue_manager_update_intervals():
    """测试热更新间隔"""
    qm = QueueManager(
        models={"default": 1.0, "gpt4": 2.0},
    )

    qm.update_model_intervals(
        {
            "default": 0.5,
            "gpt4": 1.0,
        }
    )

    assert qm._model_queues["default"].interval == 0.5
    assert qm._model_queues["gpt4"].interval == 1.0
