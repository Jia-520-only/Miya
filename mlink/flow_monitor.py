"""
M-Link 消息流监控模块
提供消息流转追踪和性能统计
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlowMonitor:
    """消息流监控器"""

    def __init__(self):
        self._trace_log: List[Dict] = []
        self._flow_stats: Dict[str, Dict] = {}
        self._max_traces = 500

    async def trace_message(
        self,
        message: Any,
        status: str,
        extra: Optional[Dict] = None,
    ):
        trace = {
            "message_id": getattr(message, "id", str(time.time())),
            "flow_type": getattr(message, "flow_type", "unknown"),
            "timestamp": time.time(),
            "status": status,
            "extra": extra or {},
        }
        self._trace_log.append(trace)
        if len(self._trace_log) > self._max_traces:
            self._trace_log = self._trace_log[-self._max_traces :]

    async def record_flow(
        self,
        flow_type: str,
        message_size: int = 0,
        is_error: bool = False,
        metadata: Optional[Dict] = None,
    ):
        if flow_type not in self._flow_stats:
            self._flow_stats[flow_type] = {
                "count": 0,
                "total_size": 0,
                "errors": 0,
                "last_timestamp": None,
            }
        stats = self._flow_stats[flow_type]
        stats["count"] += 1
        stats["total_size"] += message_size
        if is_error:
            stats["errors"] += 1
        stats["last_timestamp"] = time.time()

    async def get_traces(self, limit: int = 50, flow_type: Optional[str] = None) -> List[Dict]:
        traces = self._trace_log
        if flow_type:
            traces = [t for t in traces if t.get("flow_type") == flow_type]
        return traces[-limit:]

    async def get_stats(self, flow_type: Optional[str] = None) -> Dict:
        if flow_type:
            return self._flow_stats.get(flow_type, {})
        return dict(self._flow_stats)

    async def start_monitoring(self):
        logger.info("[FlowMonitor] 监控已启动")

    async def stop_monitoring(self):
        logger.info("[FlowMonitor] 监控已停止")

    async def clear(self):
        self._trace_log.clear()
        self._flow_stats.clear()
