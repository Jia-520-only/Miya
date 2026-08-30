"""
记忆系统初始化器
整合 Undefined 记忆、对话历史持久化、潮汐记忆
"""
import asyncio
import logging
from pathlib import Path
import os
from dotenv import load_dotenv

from core.conversation_history import get_conversation_history_manager, ConversationHistoryManager
from memory.undefined_memory import get_undefined_memory_adapter, UndefinedMemoryAdapter
from hub.memory_engine import MemoryEngine
from core.constants import Encoding

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv('config/.env')



class MemorySystemInitializer:
    """记忆系统初始化器

    统一管理所有记忆子系统：
    1. 对话历史持久化 (conversation_history.py)
    2. Undefined 手动记忆 (memory/undefined_memory.py)
    3. 潮汐记忆/梦境压缩 (hub/memory_engine.py)
    """

    def __init__(
        self,
        data_dir: Path = None,
        redis_client=None,
        milvus_client=None,
        neo4j_client=None
    ):
        self.data_dir = data_dir or Path("data")
        self.redis_client = redis_client
        self.milvus_client = milvus_client
        self.neo4j_client = neo4j_client

        # 记忆系统实例
        self.conversation_history: ConversationHistoryManager = None
        self.undefined_memory: UndefinedMemoryAdapter = None
        self.memory_engine: MemoryEngine = None

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
            logger.info("\n[1/3] 初始化对话历史持久化系统...")
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
            logger.info("\n[2/3] 初始化 Undefined 记忆系统...")
            self.undefined_memory = get_undefined_memory_adapter()
            await self.undefined_memory._load()

            memory_count = self.undefined_memory.count()
            logger.info(f"  [OK] 存储目录: {self.data_dir / 'memory'}")
            logger.info(f"  [OK] 手动记忆数量: {memory_count}")
            logger.info(f"  [OK] 存储文件: undefined_memory.json")

            # 3. 初始化潮汐记忆/梦境压缩引擎
            logger.info("\n[3/3] 初始化潮汐记忆/梦境压缩引擎...")
            self.memory_engine = MemoryEngine(
                redis_client=self.redis_client,
                milvus_client=self.milvus_client,
                neo4j_client=self.neo4j_client
            )

            # 检查数据库连接
            if self.redis_client:
                if hasattr(self.redis_client, 'is_mock_mode') and self.redis_client.is_mock_mode():
                    logger.info(f"  [OK] Redis: 模拟模式")
                else:
                    logger.info(f"  [OK] Redis: 已连接")

            if self.milvus_client:
                if hasattr(self.milvus_client, 'is_mock_mode') and self.milvus_client.is_mock_mode():
                    logger.info(f"  [OK] Milvus: 模拟模式")
                else:
                    logger.info(f"  [OK] Milvus: 已连接")

            if self.neo4j_client:
                if hasattr(self.neo4j_client, 'is_mock_mode') and self.neo4j_client.is_mock_mode():
                    logger.info(f"  [OK] Neo4j: 模拟模式")
                else:
                    logger.info(f"  [OK] Neo4j: 已连接")

            self._initialized = True

            logger.info("\n" + "=" * 50)
            logger.info("✅ 弥娅记忆系统初始化完成")
            logger.info("=" * 50)

            # 打印存储位置
            logger.info("\n数据存储位置:")
            logger.info(f"  • 对话历史: {self.data_dir / 'conversations'}")
            logger.info(f"  • 手动记忆: {self.data_dir / 'memory' / 'undefined_memory.json'}")
            redis_status = '已连接' if self.redis_client and not (hasattr(self.redis_client, 'is_mock_mode') and self.redis_client.is_mock_mode()) else '模拟模式'
            milvus_status = '已连接' if self.milvus_client and not (hasattr(self.milvus_client, 'is_mock_mode') and self.milvus_client.is_mock_mode()) else '模拟模式'
            neo4j_status = '已连接' if self.neo4j_client and not (hasattr(self.neo4j_client, 'is_mock_mode') and self.neo4j_client.is_mock_mode()) else '模拟模式'
            logger.info(f"  • Redis: {redis_status}")
            logger.info(f"  • Milvus: {milvus_status}")
            logger.info(f"  • Neo4j: {neo4j_status}")

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

    async def get_statistics(self) -> dict:
        """获取所有记忆系统的统计信息"""
        if not self._initialized:
            await self.initialize()

        stats = {
            "conversation_history": await self.conversation_history.get_statistics(),
            "undefined_memory": {
                "count": self.undefined_memory.count(),
                "file": str(self.data_dir / "memory" / "undefined_memory.json")
            },
            "tide_memory": {
                "count": len(self.memory_engine.tide_memory),
                "redis_available": self.redis_client is not None
            },
            "dream_memory": {
                "count": len(self.memory_engine.dream_memory),
                "milvus_available": self.milvus_client is not None
            }
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
                    output_dir / f"conversation_{session_id}_{timestamp}.json"
                )
                export_files[f"conversation_{session_id}"] = str(file_path)
        except Exception as e:
            logger.error(f"导出对话历史失败: {e}")

        # 2. 导出 Undefined 记忆
        try:
            import json
            undefined_file = output_dir / f"undefined_memory_{timestamp}.json"
            memories = await self.undefined_memory.get_all()
            with open(undefined_file, 'w', encoding=Encoding.UTF8) as f:
                json.dump([m.__dict__ for m in memories], f, ensure_ascii=False, indent=2)
            export_files["undefined_memory"] = str(undefined_file)
        except Exception as e:
            logger.error(f"导出 Undefined 记忆失败: {e}")

        logger.info(f"导出完成，共 {len(export_files)} 个文件到: {output_dir}")
        return export_files

    async def cleanup(self):
        """清理所有记忆系统"""
        if self.memory_engine:
            # 保存潮汐记忆
            if self.redis_client:
                self.memory_engine._save_tide_to_redis()

        logger.info("记忆系统已清理")


# 全局单例
_global_initializer: MemorySystemInitializer = None


async def get_memory_system_initializer(
    data_dir: Path = None,
    redis_client=None,
    milvus_client=None,
    neo4j_client=None
) -> MemorySystemInitializer:
    """获取全局记忆系统初始化器（单例）"""
    global _global_initializer

    # 自动初始化 Redis 客户端
    if redis_client is None:
        try:
            import redis
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))
            redis_password = os.getenv('REDIS_PASSWORD')

            # 创建 Redis 客户端
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )

            # 测试连接
            redis_client.ping()
            logger.info("已连接到 Redis")
        except Exception as e:
            logger.warning(f"Redis 连接失败,使用模拟模式: {e}")
            redis_client = None

    # 自动初始化 Neo4j 客户端
    if neo4j_client is None:
        try:
            from storage.neo4j_client import Neo4jClient
            neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
            neo4j_password = os.getenv('NEO4J_PASSWORD')
            neo4j_database = os.getenv('NEO4J_DATABASE', 'neo4j')

            if neo4j_password:
                neo4j_client = Neo4jClient(
                    uri=neo4j_uri,
                    user=neo4j_user,
                    password=neo4j_password,
                    database=neo4j_database
                )
                if neo4j_client.connect():
                    logger.info("已连接到 Neo4j")
                else:
                    logger.info("Neo4j 使用模拟模式")
                    neo4j_client = None
            else:
                logger.warning("未配置 Neo4j 密码,使用模拟模式")
        except Exception as e:
            logger.warning(f"Neo4j 连接失败,使用模拟模式: {e}")
            neo4j_client = None

    # 自动初始化 Milvus 客户端
    if milvus_client is None:
        try:
            from storage.milvus_client import MilvusClient
            milvus_host = os.getenv('MILVUS_HOST', 'localhost')
            milvus_port = int(os.getenv('MILVUS_PORT', 19530))
            milvus_collection = os.getenv('MILVUS_COLLECTION', 'miya_memory')
            milvus_dimension = int(os.getenv('MILVUS_DIMENSION', 1536))
            milvus_use_lite = os.getenv('MILVUS_USE_LITE', 'true').lower() == 'true'

            milvus_client = MilvusClient(
                host=milvus_host,
                port=milvus_port,
                collection_name=milvus_collection,
                dimension=milvus_dimension,
                use_lite=milvus_use_lite
            )
            if milvus_client.connect():
                if hasattr(milvus_client, '_is_lite') and milvus_client._is_lite:
                    logger.info("已连接到 Milvus Lite (本地模式)")
                else:
                    logger.info("已连接到 Milvus (远程模式)")
            else:
                logger.info("Milvus 使用模拟模式")
                milvus_client = None
        except Exception as e:
            logger.warning(f"Milvus 连接失败,使用模拟模式: {e}")
            milvus_client = None

    if _global_initializer is None:
        _global_initializer = MemorySystemInitializer(
            data_dir=data_dir,
            redis_client=redis_client,
            milvus_client=milvus_client,
            neo4j_client=neo4j_client
        )

    if not _global_initializer._initialized:
        await _global_initializer.initialize()

    return _global_initializer


def reset_memory_system_initializer():
    """重置记忆系统初始化器（主要用于测试）"""
    global _global_initializer
    _global_initializer = None
