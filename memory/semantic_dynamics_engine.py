"""
语义动力学引擎
负责记忆的语义分析和动态调整
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SemanticNode:
    """语义节点"""

    id: str
    content: str
    vector: List[float]
    connections: List[str] = field(default_factory=list)
    activation: float = 0.0
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())


class SemanticDynamicsEngine:
    """
    语义动力学引擎

    功能：
    1. 语义向量计算
    2. 记忆关联发现
    3. 语义相似度匹配
    4. 动态记忆激活
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        vector_cache=None,
    ):
        self.config = config or {
            "top_k": 10,
            "fuzzy_threshold": 0.85,
            "activation_decay": 0.95,
            "connection_threshold": 0.7,
        }
        self.vector_cache = vector_cache
        self.embedding_client = None
        self._semantic_graph: Dict[str, SemanticNode] = {}
        self._initialized = False

    def set_embedding_client(self, client):
        """设置嵌入客户端"""
        self.embedding_client = client

    async def initialize(self) -> bool:
        """初始化语义引擎"""
        self._initialized = True
        logger.info("语义动力学引擎初始化成功")
        return True

    async def compute_embedding(self, text: str) -> Optional[List[float]]:
        """计算文本嵌入向量"""
        if self.embedding_client is None:
            return self._generate_mock_vector(text)

        try:
            if hasattr(self.embedding_client, "encode"):
                return await self.embedding_client.encode(text)
            elif hasattr(self.embedding_client, "get_embedding"):
                return await self.embedding_client.get_embedding(text)
        except Exception as e:
            logger.warning(f"计算嵌入失败: {e}")

        return self._generate_mock_vector(text)

    def _generate_mock_vector(self, text: str) -> List[float]:
        """生成模拟向量"""
        import hashlib

        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        vector = []
        for i in range(384):
            vector.append(((hash_val >> i) & 1) * 2 - 1)
        norm = sum(x**2 for x in vector) ** 0.5
        return [x / norm for x in vector]

    async def find_similar(
        self,
        query: str,
        top_k: int = None,
        threshold: float = None,
    ) -> List[Dict]:
        """查找相似记忆"""
        if not self._initialized:
            await self.initialize()

        top_k = top_k or self.config.get("top_k", 10)
        threshold = threshold or self.config.get("fuzzy_threshold", 0.85)

        query_vector = await self.compute_embedding(query)
        if query_vector is None:
            return []

        if self.vector_cache and hasattr(self.vector_cache, "search"):
            try:
                results = await self.vector_cache.search(
                    query_vector=query_vector,
                    top_k=top_k,
                )
                return [r for r in results if r.get("distance", 0) >= threshold]
            except Exception as e:
                logger.warning(f"向量搜索失败: {e}")

        return []

    async def build_connections(self, memory_id: str, content: str) -> List[str]:
        """构建语义连接"""
        if not self._initialized:
            await self.initialize()

        vector = await self.compute_embedding(content)
        if vector is None:
            return []

        node = SemanticNode(
            id=memory_id,
            content=content,
            vector=vector,
        )

        connections = []
        threshold = self.config.get("connection_threshold", 0.7)

        for other_id, other_node in self._semantic_graph.items():
            if other_id == memory_id:
                continue

            similarity = self._cosine_similarity(vector, other_node.vector)
            if similarity >= threshold:
                connections.append(other_id)
                node.connections.append(other_id)
                other_node.connections.append(memory_id)

        self._semantic_graph[memory_id] = node
        return connections

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    async def activate(self, memory_id: str) -> float:
        """激活记忆"""
        if memory_id in self._semantic_graph:
            node = self._semantic_graph[memory_id]
            node.activation = 1.0
            node.last_accessed = datetime.now().isoformat()
            return 1.0
        return 0.0

    async def decay_activations(self) -> Dict[str, float]:
        """衰减所有记忆的激活值"""
        decay = self.config.get("activation_decay", 0.95)
        activated = {}

        for memory_id, node in self._semantic_graph.items():
            if node.activation > 0.1:
                node.activation *= decay
                activated[memory_id] = node.activation

        return activated

    async def get_hot_memories(self, limit: int = 10) -> List[Dict]:
        """获取热门记忆"""
        sorted_nodes = sorted(
            self._semantic_graph.items(),
            key=lambda x: x[1].activation,
            reverse=True,
        )

        return [
            {
                "id": node.id,
                "content": node.content[:100],
                "activation": node.activation,
                "connections": len(node.connections),
            }
            for _, node in sorted_nodes[:limit]
            if node.activation > 0.1
        ]

    async def analyze_memory_flow(
        self,
        memory_ids: List[str],
    ) -> Dict[str, Any]:
        """分析记忆流动"""
        if not memory_ids:
            return {"flow": [], "total_activation": 0}

        total_activation = 0.0
        flow = []

        for memory_id in memory_ids:
            if memory_id in self._semantic_graph:
                node = self._semantic_graph[memory_id]
                total_activation += node.activation
                flow.append(
                    {
                        "id": memory_id,
                        "content": node.content[:50],
                        "activation": node.activation,
                        "connections": node.connections,
                    }
                )

        return {
            "flow": flow,
            "total_activation": total_activation,
            "avg_activation": total_activation / len(memory_ids) if memory_ids else 0,
        }


def get_semantic_dynamics_engine(
    config: Optional[Dict] = None,
    vector_cache=None,
) -> SemanticDynamicsEngine:
    """获取语义动力学引擎实例"""
    return SemanticDynamicsEngine(config=config, vector_cache=vector_cache)
