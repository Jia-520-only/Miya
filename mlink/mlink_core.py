"""
M-Link 核心模块
五流分发与路由（增强版：集成消息队列和监控）
"""
from typing import Dict, List, Optional
import asyncio
import logging
from .message import Message
from .router import Router
from .trust_transmit import TrustTransmit


logger = logging.getLogger(__name__)


class MLinkCore:
    """M-Link核心（增强版）"""

    # 五流类型
    FLOW_TYPES = {
        'data_flow': '数据流',
        'control_flow': '控制流',
        'emotion_flow': '情绪流',
        'memory_flow': '记忆流',
        'trust_flow': '信任流'
    }

    def __init__(self, enable_queue: bool = True, enable_monitor: bool = True):
        self.router = Router()
        self.trust_transmit = TrustTransmit()

        # 流量统计
        self.flow_stats = {
            flow_type: {'sent': 0, 'received': 0}
            for flow_type in self.FLOW_TYPES.keys()
        }

        # 消息队列
        self.message_queue = None
        self.enable_queue = enable_queue

        # 消息监控
        self.flow_monitor = None
        self.enable_monitor = enable_monitor

        # 初始化组件
        if enable_queue:
            try:
                from .message_queue import MessageQueue
                self.message_queue = MessageQueue()
                logger.info("[MLink] 消息队列已启用")
            except ImportError:
                logger.warning("[MLink] 消息队列模块不可用")

        if enable_monitor:
            try:
                from .flow_monitor import FlowMonitor
                self.flow_monitor = FlowMonitor()
                logger.info("[MLink] 消息流监控已启用")
            except ImportError:
                logger.warning("[MLink] 消息流监控模块不可用")

    async def send(self, message: Message, available_nodes: List[str]) -> bool:
        """
        发送消息

        Args:
            message: 消息对象
            available_nodes: 可用节点列表

        Returns:
            是否发送成功
        """
        # 追踪消息
        if self.flow_monitor:
            await self.flow_monitor.trace_message(
                message,
                'sent',
                {'destination': available_nodes}
            )

        # 路由决策
        target_node = self.router.route(message, available_nodes)
        if not target_node:
            message.status = 'failed'

            if self.flow_monitor:
                await self.flow_monitor.trace_message(message, 'failed', {'reason': 'no_route'})

            return False

        # 更新目标
        message.destination = target_node

        # 信任检查
        trust = self.trust_transmit.get_trust(message.source, target_node)
        if trust < 0.3:
            message.status = 'rejected_low_trust'

            if self.flow_monitor:
                await self.flow_monitor.trace_message(
                    message,
                    'failed',
                    {'reason': 'low_trust', 'trust_value': trust}
                )

            return False

        # 发送消息
        message.status = 'delivered'

        # 更新统计
        self.flow_stats[message.flow_type]['sent'] += 1

        # 记录流量
        if self.flow_monitor:
            await self.flow_monitor.record_flow(
                message.flow_type,
                message_size=len(str(message.content)),
                is_error=False
            )
            await self.flow_monitor.update_node_stats(
                message.source,
                'sent'
            )

        # 如果启用了消息队列，入队
        if self.message_queue:
            await self.message_queue.enqueue(message)

        return True

    async def broadcast(self, message: Message, nodes: List[str]) -> int:
        """
        广播消息到多个节点

        Returns:
            成功发送的节点数
        """
        success_count = 0

        for node in nodes:
            # 创建消息副本
            msg_copy = Message(
                msg_type=message.msg_type,
                content=message.content,
                source=message.source,
                destination=node,
                priority=message.priority
            )

            if await self.send(msg_copy, [node]):
                success_count += 1

        return success_count

    async def receive(self, message: Message) -> None:
        """接收消息"""
        message.status = 'received'
        self.flow_stats[message.flow_type]['received'] += 1

        # 追踪接收
        if self.flow_monitor:
            await self.flow_monitor.trace_message(
                message,
                'received',
                {'destination': message.destination}
            )
            await self.flow_monitor.update_node_stats(
                message.destination or 'unknown',
                'received'
            )

    def register_node(self, node_id: str, capabilities: List[str],
                      load: float = 0.0) -> None:
        """注册节点"""
        self.router.update_node_status(node_id, {
            'available': True,
            'capabilities': capabilities,
            'load': load
        })
        logger.debug(f"[MLink] 节点已注册: {node_id}")

    def unregister_node(self, node_id: str) -> None:
        """注销节点"""
        if node_id in self.router.node_status:
            self.router.node_status[node_id]['available'] = False
            logger.debug(f"[MLink] 节点已注销: {node_id}")

    def get_flow_stats(self) -> Dict:
        """获取流量统计"""
        return self.flow_stats.copy()

    def get_system_stats(self) -> Dict:
        """获取系统统计"""
        stats = {
            'flow_stats': self.get_flow_stats(),
            'router_stats': self.router.get_routing_stats(),
            'trust_stats': self.trust_transmit.get_trust_stats(),
        }

        # 添加消息队列统计
        if self.message_queue:
            stats['queue_stats'] = self.message_queue.get_stats()

        # 添加监控统计
        if self.flow_monitor:
            stats['monitor_summary'] = self.flow_monitor.get_summary()

        return stats

    async def start_monitoring(self) -> None:
        """启动监控"""
        if self.flow_monitor:
            await self.flow_monitor.start_monitoring()

        if self.message_queue:
            # 消息队列的处理器由外部设置
            pass

    async def stop_monitoring(self) -> None:
        """停止监控"""
        if self.flow_monitor:
            await self.flow_monitor.stop_monitoring()

        if self.message_queue:
            await self.message_queue.stop_processor()

    def get_monitor_data(self) -> Optional[str]:
        """获取监控数据（JSON格式）"""
        if self.flow_monitor:
            return self.flow_monitor.export_metrics()
        return None
