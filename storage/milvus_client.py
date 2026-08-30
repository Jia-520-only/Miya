"""
Milvus客户端 - 向量长期记忆
管理向量数据库存储和检索
支持真实Milvus连接和模拟回退模式
"""
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus客户端 - 支持真实连接、Milvus Lite和模拟回退"""

    def __init__(self, host: str = 'localhost', port: int = 19530,
                 collection_name: str = 'miya_memory',
                 dimension: int = 1536, use_lite: bool = True, use_mock: bool = None):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dimension = dimension
        self._use_lite = use_lite  # 是否优先使用 Milvus Lite
        self._use_mock = use_mock
        self._milvus_client = None
        self._collection = None
        self._is_lite = False

        # 模拟向量存储（回退模式）
        self._vectors = {}  # id -> (vector, metadata)
        self._ids = []

        # 尝试连接Milvus
        if not self._use_mock:
            self._connect_real()

    def _connect_real(self) -> bool:
        """尝试连接Milvus（优先尝试 Milvus Lite，再尝试远程 Milvus）"""
        try:
            from pymilvus import MilvusClient

            # 优先尝试 Milvus Lite（本地文件模式）
            if self._use_lite:
                try:
                    # 使用本地文件模式
                    lite_db_path = "data/milvus_lite.db"
                    self._milvus_client = MilvusClient(lite_db_path)
                    self._is_lite = True

                    # 检查集合是否存在
                    if self.collection_name in self._milvus_client.list_collections():
                        logger.info(f"✅ 已连接到 Milvus Lite (本地文件): {lite_db_path}")
                        logger.info(f"📊 使用现有集合: {self.collection_name}")
                    else:
                        logger.info(f"✅ 已连接到 Milvus Lite (本地文件): {lite_db_path}")
                        logger.info(f"📊 集合不存在，将自动创建: {self.collection_name}")

                    self._use_mock = False
                    return True
                except Exception as e:
                    logger.info(f"Milvus Lite 不可用: {e}，尝试远程 Milvus...")

            # 尝试远程 Milvus
            self._milvus_client = MilvusClient(
                uri=f"http://{self.host}:{self.port}"
            )
            self._is_lite = False

            # 检查集合是否存在
            if self.collection_name in self._milvus_client.list_collections():
                logger.info(f"✅ 已连接到远程Milvus: {self.host}:{self.port}")
                logger.info(f"📊 使用现有集合: {self.collection_name}")
            else:
                logger.info(f"✅ 已连接到远程Milvus: {self.host}:{self.port}")
                logger.info(f"📊 集合不存在，将自动创建: {self.collection_name}")

            self._use_mock = False
            return True
        except ImportError:
            logger.warning("⚠️ pymilvus包未安装，使用模拟模式")
            self._use_mock = True
            return False
        except Exception as e:
            logger.warning(f"⚠️ Milvus连接失败: {e}，使用模拟模式")
            self._use_mock = True
            return False

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return self._use_mock

    def connect(self) -> bool:
        """连接Milvus"""
        if self._use_mock:
            return True
        if self._milvus_client:
            try:
                # 测试连接
                self._milvus_client.list_collections()
                return True
            except Exception as e:
                logger.error(f"Milvus连接失败: {e}")
                return False
        return self._connect_real()

    def create_collection(self, dimension: int = None) -> bool:
        """
        创建集合

        Args:
            dimension: 向量维度
        """
        if dimension:
            self.dimension = dimension

        if self._use_mock:
            logger.info(f"模拟模式：创建集合 {self.collection_name}，维度: {self.dimension}")
            return True

        try:
            # 检查集合是否存在
            if self.collection_name not in self._milvus_client.list_collections():
                # 定义schema（兼容新版pymilvus）
                from pymilvus import MilvusClient

                # 删除旧集合（如果存在）
                try:
                    self._milvus_client.drop_collection(collection_name=self.collection_name)
                    logger.info(f"已删除旧集合: {self.collection_name}")
                except:
                    pass

                # 创建新集合
                self._milvus_client.create_collection(
                    collection_name=self.collection_name,
                    dimension=self.dimension,
                    metric_type="L2",
                    id_type="string",
                    max_length=65535  # 为varChar字段指定max_length
                )
                logger.info(f"创建Milvus集合成功: {self.collection_name} (维度: {self.dimension})")
            else:
                logger.info(f"集合已存在: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"创建Milvus集合失败: {e}")
            return False

    def insert(self, vectors: List[List[float]], ids: List[str] = None,
               metadata: List[Dict] = None) -> List[str]:
        """
        插入向量

        Returns:
            向量ID列表
        """
        if self._use_mock:
            return self._insert_mock(vectors, ids, metadata)

        try:
            # 确保集合存在
            if self.collection_name not in self._milvus_client.list_collections():
                self.create_collection()

            # 准备数据
            if ids is None:
                ids = [f"vec_{datetime.now().timestamp()}_{i}"
                       for i in range(len(vectors))]

            if metadata is None:
                metadata = [{} for _ in vectors]

            # 转换为numpy数组
            vectors_np = np.array(vectors, dtype=np.float32)

            # 序列化metadata
            metadata_str = [json.dumps(m, ensure_ascii=False) for m in metadata]

            # 插入数据
            data = [
                {"id": ids[i], "vector": vectors_np[i].tolist(), "metadata": metadata_str[i]}
                for i in range(len(vectors))
            ]

            self._milvus_client.insert(
                collection_name=self.collection_name,
                data=data
            )

            # 刷新以确保数据可搜索（Milvus Lite可能没有flush方法）
            try:
                if hasattr(self._milvus_client, 'flush'):
                    self._milvus_client.flush(self.collection_name)
            except:
                pass  # 忽略flush错误

            logger.info(f"✅ 插入 {len(vectors)} 个向量到Milvus")
            return ids

        except Exception as e:
            logger.error(f"Milvus insert失败: {e}")
            return self._insert_mock(vectors, ids, metadata)

    def _insert_mock(self, vectors: List[List[float]], ids: List[str] = None,
                   metadata: List[Dict] = None) -> List[str]:
        """模拟插入向量"""
        if ids is None:
            ids = [f"vec_mock_{len(self._ids) + i}_{datetime.now().timestamp()}"
                   for i in range(len(vectors))]

        if metadata is None:
            metadata = [{} for _ in vectors]

        for i, vector in enumerate(vectors):
            vector_id = ids[i]
            self._vectors[vector_id] = {
                'vector': vector,
                'metadata': metadata[i],
                'created_at': datetime.now().isoformat()
            }
            self._ids.append(vector_id)

        return ids

    def search(self, query_vector: List[float], top_k: int = 10,
               metric_type: str = 'L2') -> List[Dict]:
        """
        向量搜索

        Returns:
            搜索结果列表
        """
        if self._use_mock:
            return self._search_mock(query_vector, top_k, metric_type)

        try:
            # 搜索
            results = self._milvus_client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["metadata"]
            )

            # 解析结果
            formatted_results = []
            for hit in results[0]:
                formatted_results.append({
                    'id': hit['id'],
                    'distance': hit['distance'],
                    'metadata': json.loads(hit['entity'].get('metadata', '{}'))
                })

            logger.info(f"✅ Milvus搜索返回 {len(formatted_results)} 条结果")
            return formatted_results

        except Exception as e:
            logger.error(f"Milvus search失败: {e}")
            return self._search_mock(query_vector, top_k, metric_type)

    def _search_mock(self, query_vector: List[float], top_k: int = 10,
                   metric_type: str = 'L2') -> List[Dict]:
        """模拟向量搜索"""
        results = []

        for vector_id, data in self._vectors.items():
            stored_vector = data['vector']

            # 计算距离
            if metric_type == 'L2':
                distance = self._calculate_l2_distance(query_vector, stored_vector)
            elif metric_type == 'IP':
                distance = self._calculate_inner_product(query_vector, stored_vector)
            elif metric_type == 'COSINE':
                distance = self._calculate_cosine_distance(query_vector, stored_vector)
            else:
                distance = 0.0

            results.append({
                'id': vector_id,
                'distance': distance,
                'metadata': data['metadata']
            })

        # 排序并返回top_k
        if metric_type == 'IP':
            # 内积越大越好
            results.sort(key=lambda x: x['distance'], reverse=True)
        elif metric_type == 'COSINE':
            # 余弦距离越小越好
            results.sort(key=lambda x: x['distance'])
        else:
            # L2越小越好
            results.sort(key=lambda x: x['distance'])

        return results[:top_k]

    def _calculate_l2_distance(self, v1: List[float], v2: List[float]) -> float:
        """计算L2距离（欧氏距离）"""
        import math
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))

    def _calculate_inner_product(self, v1: List[float], v2: List[float]) -> float:
        """计算内积"""
        return sum(a * b for a, b in zip(v1, v2))

    def _calculate_cosine_distance(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦距离（1 - 余弦相似度）"""
        import math
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a ** 2 for a in v1))
        norm_b = math.sqrt(sum(b ** 2 for b in v2))

        if norm_a == 0 or norm_b == 0:
            return 1.0

        cosine_similarity = dot_product / (norm_a * norm_b)
        return 1.0 - cosine_similarity

    def delete(self, ids: List[str]) -> int:
        """
        删除向量

        Returns:
            删除的数量
        """
        if self._use_mock:
            return self._delete_mock(ids)

        try:
            self._milvus_client.delete(
                collection_name=self.collection_name,
                ids=ids
            )
            logger.info(f"✅ 删除 {len(ids)} 个向量")
            return len(ids)
        except Exception as e:
            logger.error(f"Milvus delete失败: {e}")
            return self._delete_mock(ids)

    def _delete_mock(self, ids: List[str]) -> int:
        """模拟删除向量"""
        deleted = 0
        for vector_id in ids:
            if vector_id in self._vectors:
                del self._vectors[vector_id]
                if vector_id in self._ids:
                    self._ids.remove(vector_id)
                deleted += 1

        return deleted

    def get(self, ids: List[str]) -> List[Dict]:
        """获取向量"""
        if self._use_mock:
            return self._get_mock(ids)

        try:
            results = []
            for vector_id in ids:
                # Milvus query
                query_results = self._milvus_client.query(
                    collection_name=self.collection_name,
                    filter=f"id == '{vector_id}'",
                    output_fields=["vector", "metadata"]
                )

                if query_results:
                    result = query_results[0]
                    results.append({
                        'id': result['id'],
                        'vector': result['vector'],
                        'metadata': json.loads(result.get('metadata', '{}'))
                    })

            return results
        except Exception as e:
            logger.error(f"Milvus get失败: {e}")
            return self._get_mock(ids)

    def _get_mock(self, ids: List[str]) -> List[Dict]:
        """模拟获取向量"""
        results = []
        for vector_id in ids:
            if vector_id in self._vectors:
                data = self._vectors[vector_id]
                results.append({
                    'id': vector_id,
                    'vector': data['vector'],
                    'metadata': data['metadata']
                })
        return results

    def update(self, ids: List[str], vectors: List[List[float]] = None,
               metadata: List[Dict] = None) -> int:
        """更新向量（Milvus不支持直接更新，需要删除后重新插入）"""
        if self._use_mock:
            return self._update_mock(ids, vectors, metadata)

        try:
            # Milvus不支持直接更新，需要删除后重新插入
            # 先获取原有数据
            existing_data = self.get(ids)

            if not existing_data:
                logger.warning(f"未找到向量: {ids}")
                return 0

            # 删除旧数据
            self.delete(ids)

            # 准备新数据
            new_vectors = []
            new_metadata = []

            for i, item in enumerate(existing_data):
                if vectors and i < len(vectors):
                    new_vectors.append(vectors[i])
                else:
                    new_vectors.append(item['vector'])

                if metadata and i < len(metadata):
                    # 合并metadata
                    new_meta = item['metadata'].copy()
                    new_meta.update(metadata[i])
                    new_metadata.append(new_meta)
                else:
                    new_metadata.append(item['metadata'])

            # 重新插入
            self.insert(new_vectors, ids, new_metadata)

            logger.info(f"✅ 更新 {len(ids)} 个向量")
            return len(ids)

        except Exception as e:
            logger.error(f"Milvus update失败: {e}")
            return self._update_mock(ids, vectors, metadata)

    def _update_mock(self, ids: List[str], vectors: List[List[float]] = None,
                   metadata: List[Dict] = None) -> int:
        """模拟更新向量"""
        updated = 0

        for i, vector_id in enumerate(ids):
            if vector_id in self._vectors:
                if vectors and i < len(vectors):
                    self._vectors[vector_id]['vector'] = vectors[i]
                if metadata and i < len(metadata):
                    self._vectors[vector_id]['metadata'].update(metadata[i])
                updated += 1

        return updated

    def count(self) -> int:
        """获取向量数量"""
        if self._use_mock:
            return len(self._vectors)

        try:
            # 获取集合统计信息
            stats = self._milvus_client.get_collection_stats(self.collection_name)
            return stats.get('row_count', 0)
        except Exception as e:
            logger.error(f"Milvus count失败: {e}")
            return len(self._vectors)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if self._use_mock:
            return {
                'mode': 'mock',
                'total_vectors': len(self._vectors),
                'collection_name': self.collection_name,
                'dimension': self.dimension
            }

        try:
            # 先检查集合是否存在
            collections = self._milvus_client.list_collections()
            if self.collection_name not in collections:
                logger.debug(f"集合 {self.collection_name} 不存在，返回 0")
                return {
                    'mode': 'real',
                    'total_vectors': 0,
                    'collection_name': self.collection_name,
                    'dimension': self.dimension
                }

            # 集合存在，获取统计信息
            stats = self._milvus_client.get_collection_stats(self.collection_name)
            return {
                'mode': 'real',
                'total_vectors': stats.get('row_count', 0),
                'collection_name': self.collection_name,
                'dimension': self.dimension
            }
        except Exception as e:
            logger.debug(f"Milvus get_stats失败: {e}")
            return {
                'mode': 'real',
                'total_vectors': len(self._vectors),
                'collection_name': self.collection_name,
                'dimension': self.dimension
            }

    def create_index(self, index_type: str = 'IVF_FLAT',
                     params: Dict = None) -> bool:
        """创建索引"""
        if self._use_mock:
            logger.info(f"📝 模拟模式：创建索引 {index_type}")
            return True

        try:
            # 默认索引参数
            if params is None:
                params = {
                    "nlist": 128,
                    "m": 16
                }

            # 创建索引
            self._milvus_client.create_index(
                collection_name=self.collection_name,
                index_params={
                    "index_type": index_type,
                    "metric_type": "L2",
                    "params": params
                }
            )

            logger.info(f"✅ 创建Milvus索引成功: {index_type}")
            return True
        except Exception as e:
            logger.error(f"创建Milvus索引失败: {e}")
            return False

    def drop_collection(self) -> bool:
        """删除集合"""
        if self._use_mock:
            self._vectors.clear()
            self._ids.clear()
            logger.info(f"🗑️ 模拟模式：删除集合 {self.collection_name}")
            return True

        try:
            self._milvus_client.drop_collection(self.collection_name)
            logger.info(f"🗑️ 删除Milvus集合成功: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"删除Milvus集合失败: {e}")
            self._vectors.clear()
            self._ids.clear()
            return False

    def close(self) -> None:
        """关闭连接"""
        if self._milvus_client:
            try:
                self._milvus_client.close()
                logger.info("Milvus连接已关闭")
            except Exception as e:
                logger.error(f"关闭Milvus连接失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
