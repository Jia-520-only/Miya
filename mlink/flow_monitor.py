"""
M-Link 消息流监控
监控和追踪 M-Link 消息流，提供可视化接口
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import json

from .message import Message, MessageType, FlowType


logger = logging.getLogger(__name__)


@dataclass
class FlowTrace:
    """消息流追踪"""
    trace_id: str
    message_id: str
    flow_type: str
    source: str
    destination: str
    created_at: datetime
    events: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'trace_id': self.trace_id,
            'message_id': self.message_id,
            'flow_type': self.flow_type,
            'source': self.source,
            'destination': self.destination,
            'created_at': self.created_at.isoformat(),
            'events': self.events
        }


@dataclass
class NodeStats:
    """节点统计"""
    node_id: str
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    avg_latency_ms: float = 0.0
    last_active: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return asdict(self)


class FlowMonitor:
    """
    M-Link 消息流监控器

    功能：
    - 消息流追踪
    - 节点性能监控
    - 实时流量统计
    - 历史数据查询
    - 异常检测和告警
    """

    def __init__(
        self,
        max_traces: int = 1000,
        stats_window_seconds: int = 60,
        enable_alerts: bool = True
    ):
        """
        初始化监控器

        Args:
            max_traces: 最大追踪记录数
            stats_window_seconds: 统计窗口时间（秒）
            enable_alerts: 是否启用告警
        """
        self.max_traces = max_traces
        self.stats_window_seconds = stats_window_seconds
        self.enable_alerts = enable_alerts

        # 消息流追踪
        self._traces: Dict[str, FlowTrace] = {}
        self._traces_lock = asyncio.Lock()

        # 节点统计
        self._node_stats: Dict[str, NodeStats] = defaultdict(lambda: NodeStats(node_id=''))
        self._stats_lock = asyncio.Lock()

        # 流量统计（按时间和类型）
        self._flow_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'bytes': 0,
            'errors': 0
        })

        # 告警回调
        self._alert_callbacks: List[callable] = []

        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    async def trace_message(
        self,
        message: Message,
        event_type: str,
        event_data: Optional[Dict] = None
    ) -> FlowTrace:
        """
        追踪消息流

        Args:
            message: 消息对象
            event_type: 事件类型（created, sent, received, failed）
            event_data: 事件数据

        Returns:
            流追踪对象
        """
        async with self._traces_lock:
            trace_id = f"trace_{message.message_id[:8]}"

            # 创建或获取追踪记录
            if trace_id not in self._traces:
                self._traces[trace_id] = FlowTrace(
                    trace_id=trace_id,
                    message_id=message.message_id,
                    flow_type=message.flow_type,
                    source=message.source,
                    destination=message.destination or 'unknown',
                    created_at=datetime.now()
                )

                # 限制追踪记录数量
                if len(self._traces) > self.max_traces:
                    oldest = min(self._traces.values(), key=lambda t: t.created_at)
                    del self._traces[oldest.trace_id]

            # 添加事件
            trace = self._traces[trace_id]
            trace.events.append({
                'event_type': event_type,
                'timestamp': datetime.now().isoformat(),
                'data': event_data or {}
            })

            logger.debug(f"[FlowMonitor] 追踪消息: {trace_id}, 事件: {event_type}")
            return trace

    async def update_node_stats(
        self,
        node_id: str,
        action: str,
        latency_ms: Optional[float] = None
    ) -> None:
        """
        更新节点统计

        Args:
            node_id: 节点ID
            action: 动作（sent, received, failed）
            latency_ms: 延迟（毫秒）
        """
        async with self._stats_lock:
            stats = self._node_stats[node_id]
            stats.node_id = node_id
            stats.last_active = datetime.now()

            if action == 'sent':
                stats.messages_sent += 1
            elif action == 'received':
                stats.messages_received += 1
            elif action == 'failed':
                stats.messages_failed += 1

            # 更新平均延迟
            if latency_ms is not None:
                total_messages = stats.messages_sent + stats.messages_received
                if total_messages > 0:
                    stats.avg_latency_ms = (
                        stats.avg_latency_ms * (total_messages - 1) + latency_ms
                    ) / total_messages

    async def record_flow(
        self,
        flow_type: str,
        message_size: int,
        is_error: bool = False
    ) -> None:
        """
        记录流量

        Args:
            flow_type: 流类型
            message_size: 消息大小（字节）
            is_error: 是否为错误
        """
        self._flow_stats[flow_type]['count'] += 1
        self._flow_stats[flow_type]['bytes'] += message_size
        if is_error:
            self._flow_stats[flow_type]['errors'] += 1

    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """获取追踪记录"""
        trace = self._traces.get(trace_id)
        return trace.to_dict() if trace else None

    def get_all_traces(
        self,
        limit: int = 100,
        flow_type: Optional[str] = None
    ) -> List[Dict]:
        """
        获取所有追踪记录

        Args:
            limit: 限制数量
            flow_type: 流类型过滤

        Returns:
            追踪记录列表
        """
        traces = list(self._traces.values())

        # 按流类型过滤
        if flow_type:
            traces = [t for t in traces if t.flow_type == flow_type]

        # 按时间倒序排序
        traces.sort(key=lambda t: t.created_at, reverse=True)

        # 限制数量
        traces = traces[:limit]

        return [t.to_dict() for t in traces]

    def get_node_stats(self, node_id: Optional[str] = None) -> Any:
        """
        获取节点统计

        Args:
            node_id: 节点ID，None表示获取所有节点

        Returns:
            节点统计数据
        """
        if node_id:
            return self._node_stats.get(node_id)
        else:
            return {k: v.to_dict() for k, v in self._node_stats.items()}

    def get_flow_stats(self) -> Dict[str, Dict]:
        """获取流量统计"""
        return dict(self._flow_stats)

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        total_traces = len(self._traces)
        total_messages = sum(s['count'] for s in self._flow_stats.values())
        total_errors = sum(s['errors'] for s in self._flow_stats.values())

        # 按流类型统计
        flow_type_stats = {}
        for flow_type, stats in self._flow_stats.items():
            flow_type_stats[flow_type] = {
                'count': stats['count'],
                'bytes_mb': round(stats['bytes'] / (1024 * 1024), 2),
                'error_rate': round(stats['errors'] / stats['count'] * 100, 2) if stats['count'] > 0 else 0
            }

        # 节点统计
        active_nodes = len([s for s in self._node_stats.values() if s.last_active])

        return {
            'total_traces': total_traces,
            'total_messages': total_messages,
            'total_errors': total_errors,
            'error_rate': round(total_errors / total_messages * 100, 2) if total_messages > 0 else 0,
            'flow_type_stats': flow_type_stats,
            'total_nodes': len(self._node_stats),
            'active_nodes': active_nodes
        }

    def register_alert_callback(self, callback: callable) -> None:
        """注册告警回调"""
        self._alert_callbacks.append(callback)

    async def _check_alerts(self) -> None:
        """检查告警"""
        if not self.enable_alerts:
            return

        summary = self.get_summary()

        # 检查错误率
        if summary['error_rate'] > 5.0:  # 错误率超过5%
            alert = {
                'type': 'high_error_rate',
                'level': 'warning',
                'message': f"错误率过高: {summary['error_rate']}%",
                'timestamp': datetime.now().isoformat(),
                'data': summary
            }
            await self._send_alert(alert)

        # 检查节点活跃度
        inactive_nodes = [
            node_id for node_id, stats in self._node_stats.items()
            if stats.last_active and
            (datetime.now() - stats.last_active).total_seconds() > self.stats_window_seconds * 2
        ]
        if inactive_nodes:
            alert = {
                'type': 'inactive_nodes',
                'level': 'warning',
                'message': f"节点不活跃: {', '.join(inactive_nodes)}",
                'timestamp': datetime.now().isoformat(),
                'data': {'nodes': inactive_nodes}
            }
            await self._send_alert(alert)

    async def _send_alert(self, alert: Dict) -> None:
        """发送告警"""
        logger.warning(f"[FlowMonitor] 告警: {alert['message']}")

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"[FlowMonitor] 告警回调失败: {e}")

    async def start_monitoring(self, interval: float = 5.0) -> None:
        """
        启动监控任务

        Args:
            interval: 监控间隔（秒）
        """
        if self._running:
            return

        self._running = True

        async def monitor_loop():
            while self._running:
                await asyncio.sleep(interval)
                await self._check_alerts()

        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info(f"[FlowMonitor] 监控任务已启动 (间隔: {interval}s)")

    async def stop_monitoring(self) -> None:
        """停止监控任务"""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("[FlowMonitor] 监控任务已停止")

    def export_metrics(self) -> str:
        """
        导出监控指标（JSON格式）

        Returns:
            JSON字符串
        """
        data = {
            'timestamp': datetime.now().isoformat(),
            'summary': self.get_summary(),
            'node_stats': self.get_node_stats(),
            'flow_stats': self.get_flow_stats(),
            'recent_traces': self.get_all_traces(limit=50)
        }

        return json.dumps(data, ensure_ascii=False, indent=2)


# 全局监控器实例
_global_monitor: Optional[FlowMonitor] = None


def get_flow_monitor() -> FlowMonitor:
    """获取全局监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = FlowMonitor()
    return _global_monitor
