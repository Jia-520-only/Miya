"""
对话历史持久化系统
"""
import asyncio
import json
import logging
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """对话消息数据结构"""
    role: str  # user, assistant, system
    content: str
    timestamp: str
    session_id: str
    images: Optional[List[str]] = None
    agent_id: Optional[str] = None
    metadata: Optional[Dict] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.images is None:
            self.images = []


class ConversationHistoryManager:
    """对话历史持久化管理器

    特点：
    - JSON文件存储（简单可靠）
    - 按会话ID分组
    - 自动限制历史条数（防止文件过大）
    - 异步IO不阻塞主线程
    - 支持增量加载（避免内存爆炸）
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        max_messages_per_session: int = 200,
        max_memory_sessions: int = 100
    ):
        self.data_dir = data_dir or Path("data/conversations")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages_per_session = max_messages_per_session
        self.max_memory_sessions = max_memory_sessions

        # 会话历史缓存（内存中只保留最近的）
        self._memory_cache: Dict[str, List[ConversationMessage]] = {}
        self._loaded_sessions: set = set()

        # 统计信息
        self._session_counts: Dict[str, int] = {}

        # 保存任务跟踪（防止任务被销毁）
        self._save_tasks: Dict[str, asyncio.Task] = {}
        self._save_lock = asyncio.Lock()  # 防止并发保存

    def _get_session_file(self, session_id: str) -> Path:
        """获取会话历史文件路径"""
        # 使用session_id的hash避免文件名过长
        import hashlib
        hash_obj = hashlib.md5(session_id.encode('utf-8'))
        filename = f"session_{hash_obj.hexdigest()[:16]}.json"
        return self.data_dir / filename

    async def _load_session_from_disk(self, session_id: str) -> List[ConversationMessage]:
        """从磁盘加载会话历史"""
        file_path = self._get_session_file(session_id)

        if not file_path.exists():
            return []

        try:
            async with aiofiles.open(file_path, 'r', encoding=Encoding.UTF8) as f:
                content = await f.read()
                if not content or not content.strip():
                    return []
                data = json.loads(content)

            messages = [ConversationMessage(**m) for m in data]
            logger.debug(f"从磁盘加载会话 {session_id}: {len(messages)} 条消息")
            return messages

        except json.JSONDecodeError as e:
            logger.warning(f"会话历史文件JSON格式错误 {session_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"加载会话历史失败 {session_id}: {e}")
            return []

    async def _save_session_to_disk(self, session_id: str, messages: List[ConversationMessage]):
        """保存会话历史到磁盘"""
        file_path = self._get_session_file(session_id)

        # 使用锁防止并发保存
        async with self._save_lock:
            try:
                # 取消之前的保存任务（如果还在运行）
                if session_id in self._save_tasks:
                    old_task = self._save_tasks[session_id]
                    if not old_task.done():
                        old_task.cancel()
                        try:
                            await old_task
                        except asyncio.CancelledError:
                            pass

                data = [asdict(m) for m in messages]

                # 尝试使用 aiofiles 保存，失败则回退到同步保存
                try:
                    async with aiofiles.open(file_path, 'w', encoding=Encoding.UTF8) as f:
                        await f.write(json.dumps(data, ensure_ascii=False, indent=2))
                except RuntimeError:
                    # 如果事件循环已关闭，使用同步保存
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                self._session_counts[session_id] = len(messages)
                logger.debug(f"保存会话历史 {session_id}: {len(messages)} 条消息")

            except asyncio.CancelledError:
                logger.debug(f"保存任务被取消: {session_id}")
                # 尝试同步保存
                try:
                    data = [asdict(m) for m in messages]
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    logger.info(f"同步保存会话历史 {session_id}: {len(messages)} 条消息")
                except:
                    logger.error(f"同步保存失败: {session_id}")
            except Exception as e:
                logger.error(f"保存会话历史失败 {session_id}: {e}", exc_info=True)
                # 尝试同步保存作为最后手段
                try:
                    data = [asdict(m) for m in messages]
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    logger.info(f"同步保存会话历史 {session_id}: {len(messages)} 条消息")
                except:
                    pass

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """添加消息到会话历史

        Args:
            session_id: 会话ID
            role: 角色 (user, assistant, system)
            content: 消息内容
            agent_id: Agent ID（可选）
            images: 图片列表（可选）
            metadata: 元数据（可选）
        """
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            images=images,
            agent_id=agent_id,
            metadata=metadata or {}
        )

        # 确保会话已加载
        if session_id not in self._loaded_sessions:
            await self._ensure_session_loaded(session_id)

        # 添加消息
        self._memory_cache[session_id].append(message)

        # 限制数量
        if len(self._memory_cache[session_id]) > self.max_messages_per_session:
            self._memory_cache[session_id] = self._memory_cache[session_id][-self.max_messages_per_session:]

        # 创建保存任务并跟踪（避免任务被销毁）
        async def _save_with_cleanup():
            try:
                await self._save_session_to_disk(session_id, self._memory_cache[session_id])
            except Exception as e:
                logger.error(f"保存会话历史失败: {e}", exc_info=True)
            finally:
                # 清理任务引用
                self._save_tasks.pop(session_id, None)

        task = asyncio.create_task(_save_with_cleanup(), name=f"save_session_{session_id}")

        # 添加完成回调，确保任务完成时清理引用
        def _task_done(t: asyncio.Task):
            if t.exception():
                logger.error(f"会话保存任务异常: {t.exception()}", exc_info=t.exception())
            self._save_tasks.pop(session_id, None)

        task.add_done_callback(_task_done)

        self._save_tasks[session_id] = task

        logger.debug(f"添加消息到会话 {session_id}: {role} - {content[:50]}...")

    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[ConversationMessage]:
        """获取会话历史

        Args:
            session_id: 会话ID
            limit: 最大返回条数（可选）

        Returns:
            消息列表（按时间排序）
        """
        await self._ensure_session_loaded(session_id)

        messages = self._memory_cache.get(session_id, [])

        if limit:
            messages = messages[-limit:]

        return messages

    async def _ensure_session_loaded(self, session_id: str):
        """确保会话已加载到内存"""
        if session_id not in self._loaded_sessions:
            messages = await self._load_session_from_disk(session_id)
            self._memory_cache[session_id] = messages
            self._loaded_sessions.add(session_id)

            # 内存缓存限制
            if len(self._memory_cache) > self.max_memory_sessions:
                # 删除最久未使用的会话
                oldest_session = next(iter(self._memory_cache))
                del self._memory_cache[oldest_session]
                self._loaded_sessions.remove(oldest_session)
                logger.debug(f"内存缓存超限，移除会话: {oldest_session}")

    async def clear_session(self, session_id: str):
        """清空会话历史"""
        file_path = self._get_session_file(session_id)

        # 清空内存缓存
        if session_id in self._memory_cache:
            self._memory_cache[session_id].clear()

        # 删除磁盘文件
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"删除会话历史文件: {session_id}")
            except Exception as e:
                logger.error(f"删除会话历史文件失败 {session_id}: {e}")

        # 更新统计
        self._session_counts.pop(session_id, None)

    async def delete_session(self, session_id: str):
        """删除会话（包括历史文件）"""
        await self.clear_session(session_id)

        # 从缓存中移除
        if session_id in self._memory_cache:
            del self._memory_cache[session_id]
        if session_id in self._loaded_sessions:
            self._loaded_sessions.remove(session_id)

        logger.info(f"删除会话: {session_id}")

    async def get_all_session_ids(self) -> List[str]:
        """获取所有会话ID列表"""
        if not self.data_dir.exists():
            return []

        session_ids = []

        # 扫描数据目录
        for file_path in self.data_dir.glob("session_*.json"):
            # 尝试从文件名恢复session_id（这里简化处理）
            session_id = file_path.stem.replace("session_", "")
            session_ids.append(session_id)

        return session_ids

    async def get_statistics(self) -> Dict:
        """获取统计信息"""
        total_files = 0
        total_messages = 0

        if self.data_dir.exists():
            for file_path in self.data_dir.glob("session_*.json"):
                total_files += 1

                # 从缓存获取消息数
                # 这里简化处理，实际应该读取文件统计
                session_id = file_path.stem.replace("session_", "")
                total_messages += self._session_counts.get(session_id, 0)

        return {
            "total_sessions": total_files,
            "cached_sessions": len(self._memory_cache),
            "total_messages": total_messages,
            "max_messages_per_session": self.max_messages_per_session,
            "max_memory_sessions": self.max_memory_sessions
        }

    async def export_session(self, session_id: str, output_path: Optional[Path] = None) -> Path:
        """导出会话历史

        Args:
            session_id: 会话ID
            output_path: 输出文件路径（可选）

        Returns:
            导出文件路径
        """
        messages = await self.get_history(session_id)

        if output_path is None:
            output_path = self.data_dir / f"export_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "session_id": session_id,
            "export_time": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": [asdict(m) for m in messages]
        }

        async with aiofiles.open(output_path, 'w', encoding=Encoding.UTF8) as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

        logger.info(f"导出会话历史: {session_id} -> {output_path}")
        return output_path

    async def cleanup_old_sessions(self, days: int = 30):
        """清理旧的会话历史文件

        Args:
            days: 保留天数
        """
        if not self.data_dir.exists():
            return

        cutoff_time = datetime.now().timestamp() - (days * 86400)
        deleted_count = 0

        for file_path in self.data_dir.glob("session_*.json"):
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"删除旧会话历史: {file_path.name}")
            except Exception as e:
                logger.error(f"删除旧会话历史失败 {file_path}: {e}")

        logger.info(f"清理完成，删除 {deleted_count} 个旧会话历史文件")

    async def close(self):
        """关闭管理器，等待所有保存任务完成"""
        if self._save_tasks:
            logger.info(f"等待 {len(self._save_tasks)} 个保存任务完成...")

            # 等待所有任务完成或取消
            tasks = list(self._save_tasks.values())
            await asyncio.gather(*tasks, return_exceptions=True)

            self._save_tasks.clear()
            logger.info("所有保存任务已完成")

    async def flush(self):
        """立即刷新所有未完成的保存任务"""
        if self._save_tasks:
            logger.debug(f"刷新 {len(self._save_tasks)} 个未完成的保存任务")
            await asyncio.gather(*self._save_tasks.values(), return_exceptions=True)


# 全局单例
_global_manager: Optional[ConversationHistoryManager] = None


async def get_conversation_history_manager() -> ConversationHistoryManager:
    """获取全局对话历史管理器（单例）"""
    global _global_manager

    if _global_manager is None:
        _global_manager = ConversationHistoryManager()

    return _global_manager


def reset_conversation_history_manager():
    """重置管理器（主要用于测试）"""
    global _global_manager
    _global_manager = None


# 常量导入
from core.constants import Encoding
