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
from core.conversation_history import ConversationMessage

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

    async def search_all_conversations(self, query: str, limit: int = 20, 
                                    user_id: str = None) -> List[Dict]:
        """
        全局语义搜索 - 搜索所有会话中的相关对话（跨平台）

        Args:
            query: 搜索查询（关键词或语义）
            limit: 限制数量
            user_id: 当前用户ID（可选，用于优先排序）

        Returns:
            相关对话列表（按相关性排序）
        """
        try:
            if not self.conversation_history:
                return []

            # 获取所有会话ID
            session_ids = await self.conversation_history.get_all_session_ids()
            all_conversations = []
            query_lower = query.lower()

            # 遍历所有会话进行匹配
            for session_id in session_ids:
                messages = await self.conversation_history.get_history(session_id, limit=50)

                for msg in messages:
                    # 简单关键词匹配（未来可升级为语义搜索）
                    content_lower = msg.content.lower()

                    # 计算相关性分数
                    score = 0

                    # 1. 精确匹配（权重最高）
                    if query in msg.content:
                        score += 10

                    # 2. 关键词包含
                    keywords = query_lower.split()
                    for keyword in keywords:
                        if keyword in content_lower:
                            score += 3

                    # 3. 用户优先级
                    if user_id and f"qq_{user_id}" == session_id:
                        score += 2

                    # 4. 最近的对话权重更高
                    if score > 0:
                        all_conversations.append({
                            'role': msg.role,
                            'content': msg.content,
                            'timestamp': msg.timestamp,
                            'session_id': session_id,
                            'relevance_score': score
                        })

            # 按相关性排序
            all_conversations.sort(key=lambda x: x['relevance_score'], reverse=True)

            # 返回前N条
            return all_conversations[:limit]

        except Exception as e:
            logger.error(f"[MemoryNet] 全局搜索失败: {e}")
            return []

    async def get_cross_platform_memories(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取跨平台记忆 - 整合所有平台的相关记忆

        Args:
            user_id: 用户ID
            limit: 限制数量

        Returns:
            跨平台记忆列表
        """
        try:
            # 1. 获取当前用户的对话历史
            current_memories = await self.get_recent_conversations(user_id, limit=limit)

            # 2. 获取 Undefined 记忆（全局）
            undefined_memories = []
            if self.undefined_memory:
                # 获取所有手动记忆
                if hasattr(self.undefined_memory, 'get_all'):
                    all_undefined = await self.undefined_memory.get_all()
                    undefined_memories = all_undefined[:limit]
                else:
                    # 备用方法：搜索空关键词获取前几条
                    undefined_memories = await self.undefined_memory.search('', limit=limit)

            # 3. 整合记忆
            cross_platform_memories = []

            # 添加对话历史
            for mem in current_memories:
                # 创建副本避免修改原始数据
                new_mem = dict(mem) if isinstance(mem, dict) else {
                    'role': getattr(mem, 'role', 'user'),
                    'content': getattr(mem, 'content', ''),
                    'timestamp': getattr(mem, 'timestamp', ''),
                    'session_id': getattr(mem, 'session_id', '')
                }
                new_mem['source'] = 'conversation'
                new_mem['memory_type'] = 'dialogue'
                cross_platform_memories.append(new_mem)

            # 添加 Undefined 记忆
            for mem in undefined_memories:
                # 处理不同类型的记忆对象
                if hasattr(mem, 'fact'):
                    # SimpleMemory 对象
                    cross_platform_memories.append({
                        'role': 'system',
                        'content': mem.fact,
                        'timestamp': mem.created_at,
                        'session_id': 'undefined_global',
                        'uuid': mem.uuid,
                        'tags': mem.tags,
                        'source': 'undefined',
                        'memory_type': 'fact'
                    })
                else:
                    # 字典类型
                    cross_platform_memories.append({
                        'role': 'system',
                        'content': mem.get('fact', ''),
                        'timestamp': mem.get('created_at', ''),
                        'session_id': 'undefined_global',
                        'uuid': mem.get('uuid', ''),
                        'tags': mem.get('tags', []),
                        'source': 'undefined',
                        'memory_type': 'fact'
                    })

            # 4. 如果有记忆引擎，添加潮汐记忆
            if self.memory_system and hasattr(self.memory_system, 'memory_engine'):
                try:
                    engine = await self.memory_system.get_memory_engine()
                    if engine and hasattr(engine, 'retrieve_tide'):
                        # 尝试获取最近的潮汐记忆
                        tide_memory = engine.retrieve_tide(user_id)
                        if tide_memory:
                            cross_platform_memories.append({
                                'role': 'system',
                                'content': tide_memory.get('content', ''),
                                'timestamp': tide_memory.get('timestamp', ''),
                                'session_id': 'tide_memory',
                                'source': 'tide',
                                'memory_type': 'tide'
                            })
                            logger.debug("[MemoryNet] 已添加潮汐记忆")
                except Exception as e:
                    logger.debug(f"[MemoryNet] 获取潮汐记忆失败: {e}")

            logger.info(f"[MemoryNet] 跨平台记忆整合: {len(cross_platform_memories)} 条")

            return cross_platform_memories[:limit]

        except Exception as e:
            logger.error(f"[MemoryNet] 获取跨平台记忆失败: {e}")
            return []

    async def extract_and_store_important_info(self, content: str, user_id: str = None):
        """
        自动提取重要信息并保存到 Undefined 记忆

        Args:
            content: 对话内容
            user_id: 用户ID（可选）
        """
        try:
            # 简单规则提取（未来可使用 AI 智能提取）
            important_patterns = [
                # 个人信息
                (r'我是(.{1,10})', '用户身份'),
                (r'我叫(.{1,10})', '用户身份'),
                (r'我的名字是(.{1,10})', '用户身份'),

                # 偏好信息
                (r'我喜欢(.{1,30})', '偏好'),
                (r'我讨厌(.{1,30})', '偏好'),
                (r'我不喜欢(.{1,30})', '偏好'),

                # 重要事项
                (r'记住(.{1,50})', '重要事项'),
                (r'别忘了(.{1,50})', '重要事项'),
                (r'下次(.{1,50})', '重要事项'),

                # 工作/学习信息
                (r'我在(.{1,30})工作', '工作'),
                (r'我是(.{1,20})学生', '学生身份'),
                (r'我在学习(.{1,20})', '学习'),

                # 联系信息（脱敏）
                (r'我的电话是(.{11})', '联系方式'),
                (r'我的邮箱是([^\s]+)', '联系方式'),
            ]

            import re
            extracted_count = 0

            for pattern, tag in important_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    fact = match.strip()
                    if len(fact) > 1:  # 过滤过短的内容
                        await self.undefined_memory.add(fact, tags=[tag, 'auto_extracted'])
                        extracted_count += 1
                        logger.info(f"[MemoryNet] 自动提取记忆: {tag} - {fact}")

            if extracted_count > 0:
                logger.info(f"[MemoryNet] 自动提取了 {extracted_count} 条重要信息")

        except Exception as e:
            logger.error(f"[MemoryNet] 自动提取重要信息失败: {e}")

    # ==================== 潮汐记忆/知识图谱集成 ====================

    async def store_to_memory_engine(self, memory_data: Dict, memory_type: str = 'tide'):
        """
        存储到 MemoryEngine（潮汐记忆/知识图谱）

        Args:
            memory_data: 记忆数据
            memory_type: 记忆类型 ('tide' 或 'graph')
        """
        try:
            if not self.memory_system:
                logger.warning("[MemoryNet] MemoryEngine 未初始化")
                return

            engine = await self.memory_system.get_memory_engine()
            if not engine:
                logger.warning("[MemoryNet] MemoryEngine 不可用")
                return

            if memory_type == 'tide':
                # 存储到潮汐记忆
                memory_id = memory_data.get('memory_id', f"auto_{datetime.now().timestamp()}")
                content = memory_data.get('content', '')
                priority = memory_data.get('priority', 0.5)
                ttl = memory_data.get('ttl', 3600)

                engine.store_tide(
                    memory_id=memory_id,
                    content={'content': content, **memory_data.get('metadata', {})},
                    priority=priority,
                    ttl=ttl
                )
                logger.info(f"[MemoryNet] 已存储潮汐记忆: {memory_id}")

            elif memory_type == 'graph':
                # 存储到知识图谱（Neo4j）
                if self.memory_system.neo4j_client:
                    neo4j = self.memory_system.neo4j_client
                    subject = memory_data.get('subject')
                    predicate = memory_data.get('predicate')
                    obj = memory_data.get('object')
                    context = memory_data.get('context', '')
                    emotion = memory_data.get('emotion', 'neutral')

                    if all([subject, predicate, obj]):
                        rel_id = neo4j.create_memory_quintuple(
                            subject, predicate, obj, context, emotion
                        )
                        logger.info(f"[MemoryNet] 已存储知识图谱关系: {rel_id}")

        except Exception as e:
            logger.error(f"[MemoryNet] 存储到 MemoryEngine 失败: {e}")

    async def retrieve_from_memory_engine(self, memory_type: str = 'tide',
                                       query: str = None) -> List[Dict]:
        """
        从 MemoryEngine 检索记忆

        Args:
            memory_type: 记忆类型 ('tide' 或 'graph')
            query: 查询条件

        Returns:
            记忆列表
        """
        try:
            if not self.memory_system:
                return []

            engine = await self.memory_system.get_memory_engine()
            if not engine:
                return []

            results = []

            if memory_type == 'tide':
                # 检索潮汐记忆
                if query and isinstance(query, str):
                    memory = engine.retrieve_tide(query)
                    if memory:
                        results.append({
                            'type': 'tide',
                            'memory_id': query,
                            'content': memory,
                            'source': 'memory_engine'
                        })
                else:
                    # 获取所有潮汐记忆（通过优先级队列）
                    # 注意：这里简化处理，实际应该按优先级返回
                    logger.warning("[MemoryNet] 检索潮汐记忆需要 memory_id")

            elif memory_type == 'graph':
                # 检索知识图谱
                if query and isinstance(query, str):
                    # 按情绪检索
                    memories = self.memory_system.neo4j_client.query_memory_by_emotion(query)
                    for mem in memories:
                        results.append({
                            'type': 'graph',
                            'subject': mem['subject'],
                            'predicate': mem['predicate'],
                            'object': mem['object'],
                            'context': mem['context'],
                            'emotion': mem['emotion'],
                            'source': 'neo4j'
                        })

            return results

        except Exception as e:
            logger.error(f"[MemoryNet] 从 MemoryEngine 检索失败: {e}")
            return []

    async def compress_conversation_to_tide(self, session_id: str, 
                                         recent_count: int = 10):
        """
        将对话历史压缩为潮汐记忆

        Args:
            session_id: 会话ID
            recent_count: 保留的最近对话数
        """
        try:
            if not self.memory_system:
                return

            # 获取对话历史
            messages = await self.conversation_history.get_history(session_id, limit=100)

            if len(messages) <= recent_count:
                return  # 对话不够长，无需压缩

            # 最近的对话保留
            recent_messages = messages[-recent_count:]

            # 早期对话压缩
            old_messages = messages[:-recent_count]

            # 生成摘要
            import json
            summary = self._generate_conversation_summary(old_messages)

            # 存储到潮汐记忆
            memory_id = f"{session_id}_{int(datetime.now().timestamp())}"
            await self.store_to_memory_engine({
                'memory_id': memory_id,
                'content': summary,
                'metadata': {
                    'session_id': session_id,
                    'original_count': len(old_messages),
                    'compression_time': datetime.now().isoformat()
                },
                'priority': 0.3,  # 压缩记忆优先级较低
                'ttl': 7200  # 2小时TTL
            }, memory_type='tide')

            # 更新对话历史（只保留最近的）
            # 注意：这里需要实现一个截断方法
            logger.info(f"[MemoryNet] 已压缩对话 {session_id}: "
                       f"{len(old_messages)} 条 -> 1 条摘要")

        except Exception as e:
            logger.error(f"[MemoryNet] 压缩对话失败: {e}")

    def _generate_conversation_summary(self, messages: List) -> str:
        """
        生成对话摘要

        Args:
            messages: 消息列表

        Returns:
            摘要文本
        """
        try:
            # 简单摘要：提取关键信息
            summary_parts = []

            for msg in messages[:20]:  # 最多分析前20条
                if msg.role == 'user' and len(msg.content) > 10:
                    summary_parts.append(f"用户说: {msg.content[:50]}")

            return "\n".join(summary_parts) if summary_parts else "对话历史"

        except Exception as e:
            logger.error(f"[MemoryNet] 生成对话摘要失败: {e}")
            return "对话历史"


