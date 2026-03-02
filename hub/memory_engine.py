"""
潮汐记忆/梦境压缩
实现记忆的潮汐机制和梦境压缩
集成真实数据库客户端
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import heapq
import logging
import json

logger = logging.getLogger(__name__)


class MemoryEngine:
    """记忆引擎 - 支持真实数据库和模拟回退"""

    def __init__(self, redis_client=None, milvus_client=None, neo4j_client=None):
        # 潮汐记忆（短期）
        self.tide_memory = {}  # 记忆ID -> 内容
        self.tide_priority = []  # 优先级队列

        # 梦境压缩记忆（长期）
        self.dream_memory = {}
        self.dream_index = {}  # 关键词索引

        # 记忆元数据
        self.memory_metadata = {}

        # 数据库客户端
        self.redis_client = redis_client
        self.milvus_client = milvus_client
        self.neo4j_client = neo4j_client

        # 初始化状态
        self._initialize()

    def _initialize(self) -> None:
        """初始化记忆引擎"""
        # 尝试从Redis加载潮汐记忆
        if self.redis_client and not self.redis_client.is_mock_mode():
            self._load_tide_from_redis()
            logger.info("✅ 从Redis加载潮汐记忆")

        # 尝试从Milvus加载长期记忆统计
        if self.milvus_client and not self.milvus_client.is_mock_mode():
            stats = self.milvus_client.get_stats()
            logger.info(f"✅ Milvus长期记忆数量: {stats.get('total_vectors', 0)}")

        # 尝试从Neo4j加载知识图谱统计
        if self.neo4j_client and not self.neo4j_client.is_mock_mode():
            stats = self.neo4j_client.get_stats()
            logger.info(f"✅ Neo4j知识图谱: {stats.get('total_nodes', 0)}节点, "
                       f"{stats.get('total_relationships', 0)}关系")

    def _load_tide_from_redis(self) -> None:
        """从Redis加载潮汐记忆"""
        try:
            keys = self.redis_client.keys("tide:*")
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    memory_id = key.split(":")[-1]
                    self.tide_memory[memory_id] = data['content']
                    heapq.heappush(self.tide_priority, (-data['priority'], memory_id))
                    self.memory_metadata[memory_id] = data['metadata']
        except Exception as e:
            logger.error(f"从Redis加载潮汐记忆失败: {e}")

    def store_tide(self, memory_id: str, content: Dict, priority: float = 0.5,
                   ttl: int = 3600) -> None:
        """
        存储潮汐记忆

        Args:
            memory_id: 记忆ID
            content: 记忆内容
            priority: 优先级 (0-1)
            ttl: 生存时间（秒）
        """
        self.tide_memory[memory_id] = content
        heapq.heappush(self.tide_priority, (-priority, memory_id))

        metadata = {
            'type': 'tide',
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(seconds=ttl)).isoformat(),
            'priority': priority,
            'access_count': 0
        }

        self.memory_metadata[memory_id] = metadata

        # 存储到Redis
        if self.redis_client:
            try:
                self.redis_client.set(
                    f"tide:{memory_id}",
                    {
                        'content': content,
                        'metadata': metadata
                    },
                    ttl=ttl
                )
            except Exception as e:
                logger.error(f"存储潮汐记忆到Redis失败: {e}")

    def retrieve_tide(self, memory_id: str) -> Optional[Dict]:
        """检索潮汐记忆"""
        # 先从内存查找
        if memory_id not in self.tide_memory:
            # 尝试从Redis加载
            if self.redis_client:
                try:
                    data = self.redis_client.get(f"tide:{memory_id}")
                    if data:
                        self.tide_memory[memory_id] = data['content']
                        self.memory_metadata[memory_id] = data['metadata']
                        # 更新优先级队列
                        priority = data['metadata'].get('priority', 0.5)
                        heapq.heappush(self.tide_priority, (-priority, memory_id))
                except Exception as e:
                    logger.error(f"从Redis检索潮汐记忆失败: {e}")
                    return None
            else:
                return None

        # 检查是否过期
        metadata = self.memory_metadata.get(memory_id)
        if metadata:
            expires_at = datetime.fromisoformat(metadata['expires_at'])
            if datetime.now() > expires_at:
                self._expire_memory(memory_id)
                return None

        # 更新访问计数
        if metadata:
            metadata['access_count'] = metadata.get('access_count', 0) + 1

        return self.tide_memory.get(memory_id)

    def compress_to_dream(self, memory_id: str) -> None:
        """将潮汐记忆压缩为梦境记忆"""
        if memory_id not in self.tide_memory:
            return

        content = self.tide_memory[memory_id]
        compressed = self._compress_content(content)

        dream_id = f"dream_{memory_id}"
        self.dream_memory[dream_id] = compressed

        # 建立索引
        keywords = self._extract_keywords(content)
        for keyword in keywords:
            if keyword not in self.dream_index:
                self.dream_index[keyword] = []
            self.dream_index[keyword].append(dream_id)

        # 存储到Milvus（向量存储）
        if self.milvus_client and not self.milvus_client.is_mock_mode():
            try:
                # 这里需要嵌入向量，暂时用简化版本
                # 实际应该使用embedding模型生成向量
                import hashlib
                text = str(content)
                # 生成一个伪向量（实际应该用真实的embedding）
                vector_hash = hashlib.md5(text.encode()).digest()
                vector = [float(b) / 255.0 for b in vector_hash[:self.milvus_client.dimension]]

                self.milvus_client.insert(
                    vectors=[vector],
                    ids=[dream_id],
                    metadata=[{
                        'content': compressed.get('summary', ''),
                        'keywords': keywords,
                        'original_id': memory_id
                    }]
                )
                logger.info(f"✅ 存储梦境记忆到Milvus: {dream_id}")
            except Exception as e:
                logger.error(f"存储梦境记忆到Milvus失败: {e}")

        # 存储五元组到Neo4j
        if self.neo4j_client and 'text' in content:
            try:
                # 简化的五元组提取（实际应该用NLP）
                text = content['text']
                subject = "user"  # 简化
                predicate = "said"  # 简化
                obj = "something"  # 简化
                context = text[:100]  # 简化
                emotion = content.get('emotion', 'neutral')

                self.neo4j_client.create_memory_quintuple(
                    subject, predicate, obj, context, emotion
                )
                logger.info(f"✅ 存储记忆五元组到Neo4j: {dream_id}")
            except Exception as e:
                logger.error(f"存储记忆五元组到Neo4j失败: {e}")

        # 更新元数据
        if memory_id in self.memory_metadata:
            self.memory_metadata[memory_id]['compressed'] = True
            self.memory_metadata[memory_id]['dream_id'] = dream_id

    def search_dream(self, query: str, top_k: int = 10) -> List[Dict]:
        """在梦境记忆中搜索"""
        results = []

        # 1. 向量搜索（如果有Milvus）
        if self.milvus_client and not self.milvus_client.is_mock_mode():
            try:
                # 生成查询向量（简化）
                import hashlib
                vector_hash = hashlib.md5(query.encode()).digest()
                query_vector = [float(b) / 255.0 for b in vector_hash[:self.milvus_client.dimension]]

                # 搜索
                search_results = self.milvus_client.search(query_vector, top_k=top_k)

                for hit in search_results:
                    results.append({
                        'dream_id': hit['id'],
                        'content': {
                            'summary': hit['metadata'].get('content', ''),
                            'keywords': hit['metadata'].get('keywords', [])
                        },
                        'relevance': 1.0 / (1.0 + hit['distance']),  # 距离转相关性
                        'source': 'vector'
                    })
                logger.info(f"✅ 从Milvus检索到 {len(results)} 条记忆")
            except Exception as e:
                logger.error(f"Milvus搜索失败: {e}")

        # 2. 关键词搜索（如果向量搜索失败或补充）
        keywords = self._extract_keywords({'text': query})
        keyword_results = []

        for keyword in keywords:
            if keyword in self.dream_index:
                for dream_id in self.dream_index[keyword]:
                    if dream_id in self.dream_memory:
                        relevance = self._calculate_relevance(query, self.dream_memory[dream_id])
                        keyword_results.append({
                            'dream_id': dream_id,
                            'content': self.dream_memory[dream_id],
                            'relevance': relevance,
                            'source': 'keyword'
                        })

        # 合并结果
        all_results = results + keyword_results

        # 按相关性排序
        all_results.sort(key=lambda x: x['relevance'], reverse=True)

        # 去重
        seen_ids = set()
        final_results = []
        for r in all_results:
            if r['dream_id'] not in seen_ids:
                seen_ids.add(r['dream_id'])
                final_results.append(r)

        return final_results[:top_k]

    def search_by_emotion(self, emotion: str) -> List[Dict]:
        """按情绪搜索记忆（使用Neo4j）"""
        if self.neo4j_client and not self.neo4j_client.is_mock_mode():
            try:
                memories = self.neo4j_client.query_memory_by_emotion(emotion)
                logger.info(f"✅ 从Neo4j检索到 {len(memories)} 条情绪记忆")
                return memories
            except Exception as e:
                logger.error(f"按情绪搜索失败: {e}")

        return []

    def store_long_term(self, memory_id: str, content: Dict,
                        embedding: List[float] = None) -> None:
        """
        存储长期记忆（向量+知识图谱）

        Args:
            memory_id: 记忆ID
            content: 记忆内容
            embedding: 向量表示（可选）
        """
        # 存储向量
        if self.milvus_client:
            try:
                if embedding is None:
                    # 生成伪向量
                    import hashlib
                    text = str(content)
                    vector_hash = hashlib.md5(text.encode()).digest()
                    embedding = [float(b) / 255.0 for b in vector_hash[:self.milvus_client.dimension]]

                self.milvus_client.insert(
                    vectors=[embedding],
                    ids=[memory_id],
                    metadata=[content]
                )
                logger.info(f"✅ 存储长期记忆到Milvus: {memory_id}")
            except Exception as e:
                logger.error(f"存储长期记忆到Milvus失败: {e}")

        # 存储知识图谱
        if self.neo4j_client and 'text' in content:
            try:
                # 提取五元组（简化）
                text = content['text']
                subject = content.get('subject', 'user')
                predicate = content.get('predicate', 'expressed')
                obj = content.get('object', 'thought')
                context = text[:200]
                emotion = content.get('emotion', 'neutral')

                self.neo4j_client.create_memory_quintuple(
                    subject, predicate, obj, context, emotion
                )
                logger.info(f"✅ 存储知识图谱到Neo4j: {memory_id}")
            except Exception as e:
                logger.error(f"存储知识图谱到Neo4j失败: {e}")

    def _compress_content(self, content: Dict) -> Dict:
        """压缩记忆内容"""
        return {
            'original_id': content.get('id'),
            'summary': content.get('text', '')[:200],  # 简化为摘要
            'keywords': self._extract_keywords(content),
            'emotional_signature': content.get('emotion', {}),
            'compressed_at': datetime.now().isoformat()
        }

    def _extract_keywords(self, content: Dict) -> List[str]:
        """提取关键词"""
        text = content.get('text', '')
        # 简化实现：提取非停用词
        words = text.split()
        # 简单的停用词过滤
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [word for word in words if len(word) > 1 and word not in stopwords]
        return list(set(keywords))[:5]  # 返回前5个不重复关键词

    def _calculate_relevance(self, query: str, memory: Dict) -> float:
        """计算查询与记忆的相关性"""
        query_words = set(query.lower().split())
        memory_keywords = set(memory.get('keywords', []))

        if not query_words:
            return 0.0

        intersection = query_words & memory_keywords
        return len(intersection) / len(query_words)

    def _expire_memory(self, memory_id: str) -> None:
        """过期记忆清理"""
        if memory_id in self.tide_memory:
            del self.tide_memory[memory_id]

        # 从Redis删除
        if self.redis_client:
            try:
                self.redis_client.delete(f"tide:{memory_id}")
            except Exception as e:
                logger.error(f"从Redis删除记忆失败: {e}")

    def cleanup_expired(self) -> int:
        """清理所有过期记忆"""
        current_time = datetime.now()
        expired_ids = []

        for mid, meta in self.memory_metadata.items():
            if meta.get('type') == 'tide' and meta.get('expires_at'):
                expires_at = datetime.fromisoformat(meta['expires_at'])
                if current_time > expires_at:
                    expired_ids.append(mid)

        for mid in expired_ids:
            self._expire_memory(mid)
            if mid in self.memory_metadata:
                del self.memory_metadata[mid]

        if expired_ids:
            logger.info(f"🧹 清理了 {len(expired_ids)} 条过期记忆")

        return len(expired_ids)

    def get_memory_stats(self) -> Dict:
        """获取记忆统计"""
        stats = {
            'tide_count': len(self.tide_memory),
            'dream_count': len(self.dream_memory),
            'total_access': sum(
                m.get('access_count', 0)
                for m in self.memory_metadata.values()
            )
        }

        # 添加数据库统计
        if self.redis_client and not self.redis_client.is_mock_mode():
            stats['redis_mode'] = 'real'
            stats['redis_stats'] = self.redis_client.get_stats()
        else:
            stats['redis_mode'] = 'mock'

        if self.milvus_client and not self.milvus_client.is_mock_mode():
            stats['milvus_mode'] = 'real'
            stats['milvus_stats'] = self.milvus_client.get_stats()
        else:
            stats['milvus_mode'] = 'mock'

        if self.neo4j_client and not self.neo4j_client.is_mock_mode():
            stats['neo4j_mode'] = 'real'
            stats['neo4j_stats'] = self.neo4j_client.get_stats()
        else:
            stats['neo4j_mode'] = 'mock'

        return stats

    def clear_all(self) -> None:
        """清空所有记忆"""
        self.tide_memory.clear()
        self.tide_priority.clear()
        self.dream_memory.clear()
        self.dream_index.clear()
        self.memory_metadata.clear()

        # 清空数据库
        if self.redis_client:
            try:
                self.redis_client.flushdb()
                logger.info("🗑️ 已清空Redis")
            except Exception as e:
                logger.error(f"清空Redis失败: {e}")

        if self.milvus_client:
            try:
                self.milvus_client.drop_collection()
                self.milvus_client.create_collection()
                logger.info("🗑️ 已清空Milvus")
            except Exception as e:
                logger.error(f"清空Milvus失败: {e}")

        logger.info("🗑️ 已清空所有记忆")

    def export_memories(self) -> Dict:
        """导出所有记忆（用于备份）"""
        return {
            'tide_memory': self.tide_memory,
            'dream_memory': self.dream_memory,
            'memory_metadata': self.memory_metadata,
            'export_time': datetime.now().isoformat()
        }

    def import_memories(self, data: Dict) -> bool:
        """导入记忆（用于恢复）"""
        try:
            self.tide_memory = data.get('tide_memory', {})
            self.dream_memory = data.get('dream_memory', {})
            self.memory_metadata = data.get('memory_metadata', {})

            # 重建索引
            self.dream_index = {}
            for dream_id, memory in self.dream_memory.items():
                keywords = memory.get('keywords', [])
                for keyword in keywords:
                    if keyword not in self.dream_index:
                        self.dream_index[keyword] = []
                    self.dream_index[keyword].append(dream_id)

            logger.info(f"✅ 导入记忆成功: {len(self.tide_memory)}潮汐, {len(self.dream_memory)}梦境")
            return True
        except Exception as e:
            logger.error(f"导入记忆失败: {e}")
            return False
