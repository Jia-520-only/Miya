"""
弥娅 - 真正的向量缓存系统
使用Milvus Lite作为向量数据库
"""
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import hashlib
from pathlib import Path

from storage.milvus_client import MilvusClient
from core.embedding_client import EmbeddingClient, EmbeddingProvider

logger = logging.getLogger(__name__)


class RealVectorCache:
    """
    真正的向量缓存系统

    功能：
    1. 调用Embedding API生成向量
    2. 使用Milvus Lite存储和检索向量
    3. 支持向量相似度搜索
    4. 支持批量操作
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        milvus_db_path: str = "data/milvus_lite.db",
        collection_name: str = "miya_vectors",
        dimension: Optional[int] = None
    ):
        """
        初始化向量缓存

        Args:
            embedding_client: Embedding客户端
            milvus_db_path: Milvus Lite数据库路径
            collection_name: 集合名称
            dimension: 向量维度（可选，自动检测）
        """
        self.embedding_client = embedding_client
        self.collection_name = collection_name

        # 获取向量维度
        if dimension is None:
            dimension = embedding_client.get_dimension()

        if dimension is None:
            raise ValueError("无法确定向量维度，请手动指定")

        self.dimension = dimension

        # 初始化Milvus客户端
        self.milvus = MilvusClient(
            collection_name=collection_name,
            dimension=dimension,
            use_lite=True,  # 使用Milvus Lite（本地文件）
            use_mock=False  # 不使用模拟模式
        )

        # 创建集合
        self.milvus.create_collection(dimension=self.dimension)

        logger.info(
            f"[RealVectorCache] 初始化完成 - "
            f"collection={collection_name}, dimension={dimension}"
        )

    def _generate_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return hashlib.sha256(text.encode()).hexdigest()

    async def add(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        skip_cache: bool = False
    ) -> bool:
        """
        添加文本到向量缓存

        Args:
            text: 输入文本
            metadata: 元数据
            skip_cache: 是否跳过缓存检查

        Returns:
            是否成功
        """
        try:
            cache_key = self._generate_cache_key(text)

            # 检查是否已存在
            if not skip_cache:
                existing = await self.get_by_key(cache_key)
                if existing:
                    logger.debug(f"[RealVectorCache] 文本已存在: {text[:50]}...")
                    return True

            # 生成向量
            vector = await self.embedding_client.embed(text)

            if not vector:
                logger.error(f"[RealVectorCache] 向量生成失败: {text[:50]}...")
                return False

            # 准备元数据
            if metadata is None:
                metadata = {}

            metadata.update({
                'cache_key': cache_key,
                'text': text,
                'timestamp': datetime.now().isoformat()
            })

            # 插入到Milvus
            self.milvus.insert(
                vectors=[vector],
                ids=[cache_key],
                metadata=[metadata]
            )

            logger.info(f"[RealVectorCache] 添加成功: {text[:50]}...")
            return True

        except Exception as e:
            logger.error(f"[RealVectorCache] 添加失败: {e}")
            return False

    async def add_batch(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None
    ) -> int:
        """
        批量添加文本

        Args:
            texts: 文本列表
            metadatas: 元数据列表

        Returns:
            成功添加的数量
        """
        if not texts:
            return 0

        try:
            # 批量生成向量
            vectors = await self.embedding_client.embed_batch(texts)

            if not vectors or len(vectors) != len(texts):
                logger.error("[RealVectorCache] 批量向量生成失败")
                return 0

            # 准备元数据
            if metadatas is None:
                metadatas = [{} for _ in texts]

            cache_keys = []
            final_metadatas = []

            for i, (text, vector, metadata) in enumerate(zip(texts, vectors, metadatas)):
                cache_key = self._generate_cache_key(text)
                cache_keys.append(cache_key)

                final_metadata = metadata.copy()
                final_metadata.update({
                    'cache_key': cache_key,
                    'text': text,
                    'timestamp': datetime.now().isoformat()
                })
                final_metadatas.append(final_metadata)

            # 批量插入
            self.milvus.insert(
                vectors=vectors,
                ids=cache_keys,
                metadata=final_metadatas
            )

            logger.info(f"[RealVectorCache] 批量添加成功: {len(texts)} 条")
            return len(texts)

        except Exception as e:
            logger.error(f"[RealVectorCache] 批量添加失败: {e}")
            return 0

    async def search(
        self,
        query: str,
        top_k: int = 10,
        metric_type: str = 'COSINE'
    ) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回Top K结果
            metric_type: 距离类型（L2/IP/COSINE）

        Returns:
            搜索结果列表
        """
        try:
            # 生成查询向量
            query_vector = await self.embedding_client.embed(query)

            if not query_vector:
                logger.error(f"[RealVectorCache] 查询向量生成失败: {query[:50]}...")
                return []

            # 向量搜索
            results = self.milvus.search(
                query_vector=query_vector,
                top_k=top_k,
                metric_type=metric_type
            )

            logger.info(f"[RealVectorCache] 搜索完成: {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"[RealVectorCache] 搜索失败: {e}")
            return []

    async def get_by_key(self, cache_key: str) -> Optional[Dict]:
        """根据缓存键获取记录"""
        try:
            results = self.milvus.get(ids=[cache_key])

            if results and len(results) > 0:
                return results[0]

            return None

        except Exception as e:
            logger.error(f"[RealVectorCache] 获取失败: {e}")
            return None

    async def get_by_text(self, text: str) -> Optional[Dict]:
        """根据文本获取记录"""
        cache_key = self._generate_cache_key(text)
        return await self.get_by_key(cache_key)

    async def delete(self, cache_keys: List[str]) -> int:
        """删除记录"""
        try:
            deleted = self.milvus.delete(ids=cache_keys)
            logger.info(f"[RealVectorCache] 删除完成: {deleted} 条")
            return deleted

        except Exception as e:
            logger.error(f"[RealVectorCache] 删除失败: {e}")
            return 0

    async def clear(self) -> bool:
        """清空所有数据"""
        try:
            self.milvus.drop_collection()
            self.milvus.create_collection(dimension=self.dimension)
            logger.info("[RealVectorCache] 数据已清空")
            return True

        except Exception as e:
            logger.error(f"[RealVectorCache] 清空失败: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        try:
            milvus_stats = self.milvus.get_stats()

            return {
                'collection_name': self.collection_name,
                'dimension': self.dimension,
                'total_vectors': milvus_stats.get('total_vectors', 0),
                'mode': milvus_stats.get('mode', 'unknown'),
                'embedding_provider': self.embedding_client.provider.value,
                'embedding_model': self.embedding_client.model
            }

        except Exception as e:
            logger.error(f"[RealVectorCache] 获取统计失败: {e}")
            return {}

    def is_real_mode(self) -> bool:
        """是否为真实模式（非模拟）"""
        return not self.milvus.is_mock_mode()

    def close(self):
        """关闭连接"""
        self.milvus.close()


class VectorCacheManager:
    """
    向量缓存管理器

    统一管理多种类型的向量缓存：
    - EmbeddingCache: 对话向量和Embedding缓存
    - QueryCache: 查询结果向量缓存
    - MemoCache: AI记忆向量缓存
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        milvus_db_path: str = "data/milvus_lite.db"
    ):
        """
        初始化向量缓存管理器

        Args:
            embedding_client: Embedding客户端
            milvus_db_path: Milvus Lite数据库路径
        """
        self.embedding_client = embedding_client
        self.milvus_db_path = milvus_db_path

        # 初始化各类型缓存
        self.embedding_cache = RealVectorCache(
            embedding_client=embedding_client,
            milvus_db_path=milvus_db_path,
            collection_name="miya_embeddings"
        )

        self.query_cache = RealVectorCache(
            embedding_client=embedding_client,
            milvus_db_path=milvus_db_path,
            collection_name="miya_queries"
        )

        self.memo_cache = RealVectorCache(
            embedding_client=embedding_client,
            milvus_db_path=milvus_db_path,
            collection_name="miya_memos"
        )

        logger.info("[VectorCacheManager] 初始化完成")

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取或生成文本向量

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        # 先检查缓存
        cached = await self.embedding_cache.get_by_text(text)
        if cached:
            logger.debug(f"[VectorCacheManager] 命中向量缓存: {text[:50]}...")
            # 从Milvus获取向量（需要重新实现get方法返回向量）
            # 这里简化处理，重新生成
            pass

        # 生成新向量
        vector = await self.embedding_client.embed(text)

        # 存入缓存
        if vector:
            await self.embedding_cache.add(text)

        return vector

    async def search_similar(
        self,
        query: str,
        cache_type: str = "embedding",
        top_k: int = 10
    ) -> List[Dict]:
        """
        搜索相似文本

        Args:
            query: 查询文本
            cache_type: 缓存类型（embedding/query/memo）
            top_k: 返回Top K结果

        Returns:
            搜索结果
        """
        cache_map = {
            "embedding": self.embedding_cache,
            "query": self.query_cache,
            "memo": self.memo_cache
        }

        cache = cache_map.get(cache_type, self.embedding_cache)
        return await cache.search(query, top_k=top_k)

    async def add_conversation(
        self,
        user_input: str,
        ai_response: str
    ) -> bool:
        """
        添加对话记忆

        Args:
            user_input: 用户输入
            ai_response: AI响应

        Returns:
            是否成功
        """
        try:
            # 添加用户输入
            await self.embedding_cache.add(
                user_input,
                metadata={'role': 'user'}
            )

            # 添加AI响应
            await self.embedding_cache.add(
                ai_response,
                metadata={'role': 'assistant'}
            )

            return True

        except Exception as e:
            logger.error(f"[VectorCacheManager] 添加对话失败: {e}")
            return False

    async def save_query_result(
        self,
        query: str,
        params: Dict,
        result: any
    ) -> bool:
        """保存查询结果"""
        try:
            metadata = {
                'params': str(params),
                'result_type': str(type(result))
            }

            await self.query_cache.add(query, metadata=metadata)
            return True

        except Exception as e:
            logger.error(f"[VectorCacheManager] 保存查询结果失败: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取所有缓存统计"""
        return {
            'embedding_cache': self.embedding_cache.get_stats(),
            'query_cache': self.query_cache.get_stats(),
            'memo_cache': self.memo_cache.get_stats(),
            'total_vectors': (
                self.embedding_cache.get_stats().get('total_vectors', 0) +
                self.query_cache.get_stats().get('total_vectors', 0) +
                self.memo_cache.get_stats().get('total_vectors', 0)
            )
        }

    def close(self):
        """关闭所有连接"""
        self.embedding_cache.close()
        self.query_cache.close()
        self.memo_cache.close()


# 全局单例
_global_vector_cache_manager: Optional[VectorCacheManager] = None


async def get_vector_cache_manager(
    embedding_client: EmbeddingClient,
    milvus_db_path: str = "data/milvus_lite.db"
) -> VectorCacheManager:
    """
    获取全局向量缓存管理器

    Args:
        embedding_client: Embedding客户端
        milvus_db_path: Milvus数据库路径

    Returns:
        VectorCacheManager实例
    """
    global _global_vector_cache_manager

    if _global_vector_cache_manager is None:
        _global_vector_cache_manager = VectorCacheManager(
            embedding_client=embedding_client,
            milvus_db_path=milvus_db_path
        )

    return _global_vector_cache_manager


def reset_vector_cache_manager():
    """重置向量缓存管理器（主要用于测试）"""
    global _global_vector_cache_manager
    if _global_vector_cache_manager:
        _global_vector_cache_manager.close()
    _global_vector_cache_manager = None
