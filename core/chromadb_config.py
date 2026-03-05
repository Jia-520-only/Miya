"""
ChromaDB 配置和客户端管理
可选的向量数据库后端
"""
import logging
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ChromaDBConfig:
    """ChromaDB 配置"""
    persist_directory: str = "data/chromadb"
    collection_name: str = "miya_memories"
    embedding_function: Optional[str] = None  # 可选: "openai", "huggingface"


class MockChromaDBClient:
    """模拟 ChromaDB 客户端（用于回退）"""

    def __init__(self):
        self._collections = {}

    def get_or_create_collection(self, name: str):
        """获取或创建集合"""
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_vectors": sum(c.count() for c in self._collections.values())
        }

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return True


class MockCollection:
    """模拟 ChromaDB 集合"""

    def __init__(self, name: str):
        self.name = name
        self._data = []

    def add(self, ids: List[str], embeddings: List, metadatas: List[dict], documents: List[str]):
        """添加文档"""
        for i, (id_, emb, meta, doc) in enumerate(zip(ids, embeddings, metadatas, documents)):
            self._data.append({
                "id": id_,
                "embedding": emb,
                "metadata": meta,
                "document": doc
            })

    def query(self, query_embeddings: List, n_results: int = 5) -> dict:
        """查询文档"""
        # 简化处理：返回最近添加的
        results = {
            "ids": [],
            "embeddings": [],
            "metadatas": [],
            "documents": [],
            "distances": []
        }

        for item in self._data[-n_results:]:
            results["ids"].append(item["id"])
            results["embeddings"].append(item["embedding"])
            results["metadatas"].append(item["metadata"])
            results["documents"].append(item["document"])
            results["distances"].append(0.0)

        return results

    def count(self) -> int:
        """获取文档数量"""
        return len(self._data)

    def delete(self, ids: List[str]):
        """删除文档"""
        self._data = [d for d in self._data if d["id"] not in ids]


class ChromaDBClient:
    """ChromaDB 客户端包装器

    特点：
    - 支持自动回退到模拟模式
    - 持久化存储
    - 向量相似度搜索
    """

    def __init__(self, config: Optional[ChromaDBConfig] = None, use_mock: bool = False):
        self.config = config or ChromaDBConfig()
        self.use_mock = use_mock
        self._client = None

    async def connect(self) -> bool:
        """连接 ChromaDB"""
        if self.use_mock:
            logger.info("使用模拟 ChromaDB 客户端")
            self._client = MockChromaDBClient()
            return True

        try:
            import chromadb

            # 确保持久化目录存在
            persist_dir = Path(self.config.persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)

            # 创建客户端
            self._client = chromadb.PersistentClient(
                path=str(persist_dir)
            )

            logger.info(f"✅ ChromaDB 连接成功: {persist_dir}")
            return True

        except ImportError:
            logger.warning("ChromaDB 库未安装，使用模拟模式")
            self._client = MockChromaDBClient()
            return False
        except Exception as e:
            logger.warning(f"ChromaDB 连接失败: {e}，使用模拟模式")
            self._client = MockChromaDBClient()
            return False

    def get_or_create_collection(self, name: Optional[str] = None):
        """获取或创建集合"""
        if self._client is None:
            raise RuntimeError("ChromaDB 客户端未连接")

        collection_name = name or self.config.collection_name
        return self._client.get_or_create_collection(collection_name)

    async def disconnect(self):
        """断开连接"""
        # ChromaDB 不需要显式关闭
        self._client = None

    def get_stats(self) -> dict:
        """获取统计信息"""
        if self._client is None:
            return {"total_vectors": 0}

        return self._client.get_stats()

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return self._client is None or isinstance(self._client, MockChromaDBClient)


# 全局单例
_global_chromadb_client: Optional[ChromaDBClient] = None


async def get_chromadb_client(
    config: Optional[ChromaDBConfig] = None,
    use_mock: bool = False
) -> ChromaDBClient:
    """获取全局 ChromaDB 客户端（单例）"""
    global _global_chromadb_client

    if _global_chromadb_client is None:
        _global_chromadb_client = ChromaDBClient(config, use_mock)
        await _global_chromadb_client.connect()

    return _global_chromadb_client


def reset_chromadb_client():
    """重置 ChromaDB 客户端（主要用于测试）"""
    global _global_chromadb_client
    _global_chromadb_client = None
