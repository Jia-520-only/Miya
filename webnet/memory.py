"""
全局记忆子网 (MemoryNet)
弥娅的记忆系统中枢，统一管理所有对话历史和记忆数据

核心功能：
- 对话历史持久化
- Undefined 手动记忆
- 潮汐记忆/梦境压缩
- 提供 M-Link memory_flow 接口
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from mlink.message import Message, MessageType, FlowType
from core.conversation_history import get_conversation_history_manager
from memory.undefined_memory import get_undefined_memory_adapter
from core.memory_system_initializer import get_memory_system_initializer

logger = logging.getLogger(__name__)


class MemoryNet:
    """
    全局记忆子网

    弥娅架构中的记忆中枢：
    - 统一管理所有对话历史
    - 提供 M-Link memory_flow 接口
    - 支持所有子网访问（PC UI、QQ、其他）
    - 确保记忆的全局一致性
    """

    def __init__(self, mlink):
        self.mlink = mlink
        self.memory_system = None  # MemorySystemInitializer
        self.conversation_history = None  # ConversationHistoryManager
        self.undefined_memory = None  # UndefinedMemoryAdapter

        # 统计信息
        self.stats = {
            "total_messages_stored": 0,
            "total_memories_added": 0,
            "total_retrievals": 0,
            "last_access": None
        }

        logger.info("全局记忆子网初始化完成")

    async def initialize(self):
        """初始化记忆子网"""
        try:
            logger.info("[MemoryNet] 初始化全局记忆系统...")

            # 获取全局记忆系统初始化器
            self.memory_system = await get_memory_system_initializer()

            # 获取各个子系统
            self.conversation_history = await self.memory_system.get_conversation_history_manager()
            self.undefined_memory = await self.memory_system.get_undefined_memory()

            # 注册 M-Link 节点
            self.mlink.register_node("memory", [
                "conversation_history",
                "undefined_memory",
                "memory_flow"
            ])

            logger.info("[MemoryNet] 全局记忆系统初始化成功")
            logger.info(f"[MemoryNet] 记忆流 (memory_flow) 已启用")

        except Exception as e:
            logger.error(f"[MemoryNet] 初始化失败: {e}", exc_info=True)
            raise

    async def handle_message(self, message: Message) -> Message:
        """
        处理记忆流消息

        支持的操作类型：
        - add_conversation: 添加对话历史
        - get_conversation: 获取对话历史
        - add_memory: 添加 Undefined 记忆
        - search_memory: 搜索 Undefined 记忆
        - get_statistics: 获取统计信息
        - export: 导出记忆数据
        """
        try:
            action = message.content.get("action", "")

            if action == "add_conversation":
                return await self._handle_add_conversation(message)

            elif action == "get_conversation":
                return await self._handle_get_conversation(message)

            elif action == "add_memory":
                return await self._handle_add_memory(message)

            elif action == "search_memory":
                return await self._handle_search_memory(message)

            elif action == "get_statistics":
                return await self._handle_get_statistics(message)

            elif action == "export":
                return await self._handle_export(message)

            else:
                logger.warning(f"[MemoryNet] 未知操作: {action}")
                return Message(
                    type=MessageType.ERROR,
                    source="memory",
                    target=message.source,
                    content={"error": f"未知操作: {action}"}
                )

        except Exception as e:
            logger.error(f"[MemoryNet] 处理消息失败: {e}", exc_info=True)
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    async def _handle_add_conversation(self, message: Message) -> Message:
        """处理添加对话历史请求"""
        try:
            session_id = message.content.get("session_id")
            role = message.content.get("role")
            content = message.content.get("content")
            agent_id = message.content.get("agent_id")
            images = message.content.get("images", [])
            metadata = message.content.get("metadata", {})

            if not session_id or not role or not content:
                raise ValueError("缺少必需参数: session_id, role, content")

            # 添加到对话历史
            await self.conversation_history.add_message(
                session_id=session_id,
                role=role,
                content=content,
                agent_id=agent_id,
                images=images,
                metadata=metadata
            )

            # 更新统计
            self.stats["total_messages_stored"] += 1
            self.stats["last_access"] = datetime.now().isoformat()

            logger.debug(f"[MemoryNet] 添加对话: session={session_id}, role={role}")

            return Message(
                type=MessageType.RESPONSE,
                source="memory",
                target=message.source,
                content={
                    "action": "add_conversation",
                    "success": True,
                    "session_id": session_id
                }
            )

        except Exception as e:
            logger.error(f"[MemoryNet] 添加对话失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    async def _handle_get_conversation(self, message: Message) -> Message:
        """处理获取对话历史请求"""
        try:
            session_id = message.content.get("session_id")
            limit = message.content.get("limit", 20)

            if not session_id:
                raise ValueError("缺少必需参数: session_id")

            # 获取对话历史
            messages = await self.conversation_history.get_history(session_id, limit)

            # 更新统计
            self.stats["total_retrievals"] += 1
            self.stats["last_access"] = datetime.now().isoformat()

            logger.debug(f"[MemoryNet] 获取对话: session={session_id}, count={len(messages)}")

            return Message(
                type=MessageType.RESPONSE,
                source="memory",
                target=message.source,
                content={
                    "action": "get_conversation",
                    "session_id": session_id,
                    "messages": [
                        {
                            "role": m.role,
                            "content": m.content,
                            "timestamp": m.timestamp,
                            "images": m.images,
                            "agent_id": m.agent_id,
                            "metadata": m.metadata
                        }
                        for m in messages
                    ]
                }
            )

        except Exception as e:
            logger.error(f"[MemoryNet] 获取对话失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    async def _handle_add_memory(self, message: Message) -> Message:
        """处理添加 Undefined 记忆请求"""
        try:
            fact = message.content.get("fact")
            tags = message.content.get("tags", [])

            if not fact:
                raise ValueError("缺少必需参数: fact")

            # 添加记忆
            uuid = await self.undefined_memory.add(fact, tags)

            # 更新统计
            self.stats["total_memories_added"] += 1
            self.stats["last_access"] = datetime.now().isoformat()

            logger.debug(f"[MemoryNet] 添加记忆: uuid={uuid}")

            return Message(
                type=MessageType.RESPONSE,
                source="memory",
                target=message.source,
                content={
                    "action": "add_memory",
                    "success": True,
                    "uuid": uuid
                }
            )

        except Exception as e:
            logger.error(f"[MemoryNet] 添加记忆失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    async def _handle_search_memory(self, message: Message) -> Message:
        """处理搜索 Undefined 记忆请求"""
        try:
            keyword = message.content.get("keyword")
            limit = message.content.get("limit", 20)

            if not keyword:
                raise ValueError("缺少必需参数: keyword")

            # 搜索记忆
            memories = await self.undefined_memory.search(keyword, limit)

            # 更新统计
            self.stats["total_retrievals"] += 1
            self.stats["last_access"] = datetime.now().isoformat()

            logger.debug(f"[MemoryNet] 搜索记忆: keyword={keyword}, count={len(memories)}")

            return Message(
                type=MessageType.RESPONSE,
                source="memory",
                target=message.source,
                content={
                    "action": "search_memory",
                    "keyword": keyword,
                    "memories": [
                        {
                            "uuid": m.uuid,
                            "fact": m.fact,
                            "created_at": m.created_at,
                            "tags": m.tags
                        }
                        for m in memories
                    ]
                }
            )

        except Exception as e:
            logger.error(f"[MemoryNet] 搜索记忆失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    async def _handle_get_statistics(self, message: Message) -> Message:
        """处理获取统计信息请求"""
        try:
            # 获取完整统计
            system_stats = await self.memory_system.get_statistics()

            # 合并内部统计
            stats = {
                **system_stats,
                "memory_net": self.stats
            }

            return Message(
                type=MessageType.RESPONSE,
                source="memory",
                target=message.source,
                content={
                    "action": "get_statistics",
                    "statistics": stats
                }
            )

        except Exception as e:
            logger.error(f"[MemoryNet] 获取统计失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    async def _handle_export(self, message: Message) -> Message:
        """处理导出记忆数据请求"""
        try:
            output_dir = message.content.get("output_dir")

            # 导出数据
            export_files = await self.memory_system.export_all(
                Path(output_dir) if output_dir else None
            )

            logger.info(f"[MemoryNet] 导出完成: {len(export_files)} 个文件")

            return Message(
                type=MessageType.RESPONSE,
                source="memory",
                target=message.source,
                content={
                    "action": "export",
                    "success": True,
                    "export_files": export_files
                }
            )

        except Exception as e:
            logger.error(f"[MemoryNet] 导出失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="memory",
                target=message.source,
                content={"error": str(e)}
            )

    # ==================== 辅助方法 ====================

    async def get_recent_conversations(self, user_id: str = None, limit: int = 20) -> List[Dict]:
        """
        获取最近的对话历史（辅助方法）

        Args:
            user_id: 用户ID（用于生成session_id）
            limit: 限制数量

        Returns:
            对话列表
        """
        try:
            if not self.conversation_history:
                return []

            # 生成session_id（如果是QQ用户）
            if user_id:
                session_id = f"qq_{user_id}"
            else:
                # 没有user_id时，尝试获取最近的会话
                # 由于ConversationHistoryManager没有get_all_sessions方法，返回空列表
                return []

            # 获取该会话的历史
            messages = await self.conversation_history.get_history(session_id, limit=limit)

            # 转换为字典格式
            conversations = []
            for msg in messages:
                conversations.append({
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp,
                    'session_id': session_id
                })

            return conversations

        except Exception as e:
            logger.error(f"[MemoryNet] 获取对话历史失败: {e}")
            return []

    async def get_all_conversations(self) -> List[Dict]:
        """
        获取所有对话（辅助方法）

        注意：由于ConversationHistoryManager没有get_all_sessions方法，
        此方法目前只返回内存缓存中的对话

        Returns:
            所有对话列表
        """
        try:
            if not self.conversation_history:
                return []

            # 获取内存缓存中的所有会话
            all_conversations = []

            # ConversationHistoryManager有_memory_cache属性
            if hasattr(self.conversation_history, '_memory_cache'):
                for session_id, messages in self.conversation_history._memory_cache.items():
                    for msg in messages:
                        all_conversations.append({
                            'role': msg.role,
                            'content': msg.content,
                            'timestamp': msg.timestamp,
                            'session_id': session_id
                        })

            return all_conversations

        except Exception as e:
            logger.error(f"[MemoryNet] 获取所有对话失败: {e}")
            return []

    async def store(self, memory_data: Dict) -> None:
        """
        存储记忆（辅助方法）

        Args:
            memory_data: 记忆数据字典
        """
        try:
            memory_type = memory_data.get('type', 'conversation')

            if memory_type == 'conversation':
                # 添加到对话历史
                await self.conversation_history.add_message(
                    session_id=str(memory_data.get('session_id', 'default')),
                    role=memory_data.get('role', 'user'),
                    content=memory_data.get('content', ''),
                    agent_id=memory_data.get('agent_id'),
                    metadata=memory_data.get('metadata', {})
                )
            elif memory_type == 'undefined':
                # 添加到 Undefined 记忆
                await self.undefined_memory.add(
                    fact=memory_data.get('fact', ''),
                    tags=memory_data.get('tags', [])
                )

            logger.debug(f"[MemoryNet] 记忆已存储: {memory_type}")

        except Exception as e:
            logger.error(f"[MemoryNet] 存储记忆失败: {e}")

    async def search_undefined_memory(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索 Undefined 记忆（辅助方法）

        Args:
            query: 搜索查询
            limit: 限制数量

        Returns:
            记忆列表
        """
        try:
            if not self.undefined_memory:
                return []

            results = await self.undefined_memory.search(query, limit)
            return results

        except Exception as e:
            logger.error(f"[MemoryNet] 搜索记忆失败: {e}")
            return []

