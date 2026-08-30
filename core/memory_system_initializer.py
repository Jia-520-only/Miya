"""
记忆系统初始化器
整合 Undefined 记忆、对话历史持久化、潮汐记忆
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

from core.constants import Encoding
from core.conversation_history import (
    ConversationHistoryManager,
    get_conversation_history_manager,
)
from core.memory_engine_shim import MemoryEngineShim as MemoryEngine
from memory.undefined_memory import UndefinedMemoryAdapter, get_undefined_memory_adapter

logger = logging.getLogger(__name__)

# 加载环境变量
import os as _os

if not _os.environ.get("_MIYA_DOTENV_LOADED"):
    load_dotenv("config/.env")


class MemorySystemInitializer:
    """记忆系统初始化器

    统一管理所有记忆子系统：
    1. 对话历史持久化 (conversation_history.py)
    2. Undefined 手动记忆 (memory/undefined_memory.py)
    3. 记忆引擎兼容层 (core/memory_engine_shim.py → memory/core.py V3.1)
    """

    def __init__(
        self,
        data_dir: Path = None,
    ):
        self.data_dir = data_dir or Path("data")

        self.conversation_history: ConversationHistoryManager = None
        self.undefined_memory: UndefinedMemoryAdapter = None
        self.memory_engine: MemoryEngine = None
        self.memory_bus = None

        self._initialized = False

    async def initialize(self) -> bool:
        """初始化所有记忆系统"""
        if self._initialized:
            logger.warning("记忆系统已初始化")
            return True

        try:
            logger.info("=" * 50)
            logger.info("开始初始化弥娅记忆系统")
            logger.info("=" * 50)

            # 1. 初始化对话历史持久化
            logger.info("\n[1/4] 初始化对话历史持久化系统...")
            self.conversation_history = await get_conversation_history_manager()

            # 检查数据目录
            history_data_dir = self.data_dir / "conversations"
            history_data_dir.mkdir(parents=True, exist_ok=True)

            stats = await self.conversation_history.get_statistics()
            logger.info(f"  [OK] 数据目录: {history_data_dir}")
            logger.info(f"  [OK] 已存储会话: {stats['total_sessions']}")
            logger.info(f"  [OK] 总消息数: {stats['total_messages']}")
            logger.info(f"  [OK] 每会话上限: {stats['max_messages_per_session']}")
            logger.info(f"  [OK] 内存缓存会话: {stats['cached_sessions']}")

            # 2. 初始化 Undefined 记忆系统
            logger.info("\n[2/4] 初始化 Undefined 记忆系统...")
            self.undefined_memory = get_undefined_memory_adapter()
            await self.undefined_memory._load()

            memory_count = self.undefined_memory.count()
            logger.info(f"  [OK] 存储目录: {self.data_dir / 'memory'}")
            logger.info(f"  [OK] 手动记忆数量: {memory_count}")
            logger.info("  [OK] 存储文件: undefined_memory.json")

            # 3. 初始化潮汐记忆/梦境压缩引擎
            logger.info("\n[3/4] 初始化潮汐记忆/梦境压缩引擎...")
            self.memory_engine = MemoryEngine()

            # 4. 初始化记忆总线 (MemoryBus) - 唯一记忆入口
            logger.info("\n[4/4] 初始化记忆总线 (MemoryBus)...")
            from memory.bus import get_memory_bus

            self.memory_bus = await get_memory_bus()
            logger.info(
                f"  [OK] MemoryBus 就绪，注入管线 Hooks: {self.memory_bus.injection_pipeline.stats()['total_hooks']}"
            )
            logger.info(f"  [OK] 存储后端: JSON + SQLite (FTS5 全文搜索)")

            self._initialized = True

            logger.info("\n" + "=" * 50)
            logger.info("✅ 弥娅记忆系统初始化完成")
            logger.info("=" * 50)

            # 打印存储位置
            logger.info("\n数据存储位置:")
            logger.info(f"  • 对话历史: {self.data_dir / 'conversations'}")
            logger.info(f"  • 手动记忆: {self.data_dir / 'memory' / 'undefined_memory.json'}")
            logger.info(f"  • SQLite: {self.data_dir / 'memory' / 'miya_memory.db'} (FTS5 全文搜索 + 向量检索)")

            return True

        except Exception as e:
            logger.error(f"记忆系统初始化失败: {e}", exc_info=True)
            return False

    async def get_conversation_history_manager(self) -> ConversationHistoryManager:
        """获取对话历史管理器"""
        if not self._initialized:
            await self.initialize()
        return self.conversation_history

    async def get_undefined_memory(self) -> UndefinedMemoryAdapter:
        """获取 Undefined 记忆适配器"""
        if not self._initialized:
            await self.initialize()
        return self.undefined_memory

    async def get_memory_engine(self) -> MemoryEngine:
        """获取记忆引擎"""
        if not self._initialized:
            await self.initialize()
        return self.memory_engine

    async def get_unified_memory(self):
        """获取统一记忆系统 (UnifiedMemoryManager)"""
        if not self._initialized:
            await self.initialize()
        from memory.undefined_memory import get_unified_memory_backend

        return await get_unified_memory_backend()

    async def get_statistics(self) -> dict:
        """获取所有记忆系统的统计信息"""
        if not self._initialized:
            await self.initialize()

        stats = {
            "conversation_history": await self.conversation_history.get_statistics(),
            "undefined_memory": {
                "count": self.undefined_memory.count(),
                "file": str(self.data_dir / "memory" / "undefined_memory.json"),
            },
            "tide_memory": {
                "count": len(self.memory_engine.tide_memory),
            },
            "dream_memory": {
                "count": len(self.memory_engine.dream_memory),
            },
        }

        return stats

    async def export_all(self, output_dir: Path = None) -> dict:
        """导出所有记忆数据

        Args:
            output_dir: 输出目录（可选）

        Returns:
            导出文件路径字典
        """
        if not self._initialized:
            await self.initialize()

        output_dir = output_dir or self.data_dir / "export"
        output_dir.mkdir(parents=True, exist_ok=True)

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_files = {}

        # 1. 导出对话历史
        try:
            session_ids = await self.conversation_history.get_all_session_ids()
            for session_id in session_ids:
                file_path = await self.conversation_history.export_session(
                    session_id,
                    output_dir / f"conversation_{session_id}_{timestamp}.json",
                )
                export_files[f"conversation_{session_id}"] = str(file_path)
        except Exception as e:
            logger.error(f"导出对话历史失败: {e}")

        # 2. 导出 Undefined 记忆
        try:
            import json

            undefined_file = output_dir / f"undefined_memory_{timestamp}.json"
            memories = await self.undefined_memory.get_all()
            with open(undefined_file, "w", encoding=Encoding.UTF8) as f:
                json.dump([m.__dict__ for m in memories], f, ensure_ascii=False, indent=2)
            export_files["undefined_memory"] = str(undefined_file)
        except Exception as e:
            logger.error(f"导出 Undefined 记忆失败: {e}")

        logger.info(f"导出完成，共 {len(export_files)} 个文件到: {output_dir}")
        return export_files

    async def cleanup(self):
        """清理所有记忆系统"""
        logger.info("记忆系统已清理")


# 全局单例
_global_initializer: MemorySystemInitializer = None


async def get_memory_system_initializer(
    data_dir: Path = None,
) -> MemorySystemInitializer:
    """获取全局记忆系统初始化器（单例）- JSON + SQLite 存储后端"""
    global _global_initializer

    logger.info("记忆系统就绪（JSON + SQLite，零外部数据库依赖）")
    if _global_initializer is None:
        _global_initializer = MemorySystemInitializer(
            data_dir=data_dir,
        )
        await _global_initializer.initialize()
    return _global_initializer


def reset_memory_system_initializer():
    """重置记忆系统初始化器（主要用于测试）"""
    global _global_initializer
    _global_initializer = None
