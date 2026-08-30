"""
MIYA 知识库系统

支持:
- FAISS 向量检索
- BM25 稀疏检索
- RRF 混合检索
- 文档解析 (PDF, EPUB, TXT, URL)
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass
class Document:
    """文档"""

    doc_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    """检索结果"""

    doc_id: str
    content: str
    score: float
    metadata: Dict[str, Any]


# ==================== 向量存储 (FAISS) ====================


class VectorStore:
    """向量存储 (简化版)"""

    def __init__(self, dimension: int = 1536, metric: str = "cosine"):
        self.dimension = dimension
        self.metric = metric
        self._vectors: List[List[float]] = []
        self._ids: List[str] = []
        self._metadatas: List[Dict] = []
        self._contents: List[str] = []

    async def add(self, doc_id: str, vector: List[float], metadata: Dict, content: str):
        """添加向量"""
        self._ids.append(doc_id)
        self._vectors.append(vector)
        self._metadatas.append(metadata)
        self._contents.append(content)

    async def search(self, query_vector: List[float], top_k: int = 10) -> List[SearchResult]:
        """搜索"""
        if not self._vectors:
            return []

        # 简化余弦相似度计算
        scores = []
        for v in self._vectors:
            score = self._cosine_similarity(query_vector, v)
            scores.append(score)

        # 取 top_k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            results.append(
                SearchResult(
                    doc_id=self._ids[idx],
                    content=self._contents[idx],
                    score=scores[idx],
                    metadata=self._metadatas[idx],
                )
            )

        return results

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0
        return dot / (norm_a * norm_b)

    def save(self, path: str):
        """保存"""
        data = {
            "dimension": self.dimension,
            "ids": self._ids,
            "vectors": self._vectors,
            "metadatas": self._metadatas,
            "contents": self._contents,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str):
        """加载"""
        with open(path, "r") as f:
            data = json.load(f)
        self._ids = data["ids"]
        self._vectors = data["vectors"]
        self._metadatas = data["metadatas"]
        self._contents = data["contents"]
        self.dimension = data["dimension"]


# ==================== BM25 稀疏检索 ====================


class BM25SparseRetriever:
    """BM25 稀疏检索"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: List[str] = []
        self._doc_ids: List[str] = []
        self._metadatas: List[Dict] = []
        self._doc_freqs: Dict[str, int] = {}
        self._avgdl: float = 0

    async def add(self, doc_id: str, content: str, metadata: Dict):
        """添加文档"""
        self._doc_ids.append(doc_id)
        self._documents.append(content)
        self._metadatas.append(metadata)

        # 计算词频
        words = content.split()
        for word in set(words):
            self._doc_freqs[word] = self._doc_freqs.get(word, 0) + 1

        self._avgdl = sum(len(d.split()) for d in self._documents) / max(len(self._documents), 1)

    async def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """搜索"""
        if not self._documents:
            return []

        query_words = query.split()
        N = len(self._documents)

        scores = []
        for _doc_idx, doc in enumerate(self._documents):
            doc_words = doc.split()
            doc_len = len(doc_words)
            doc_word_freq = {}

            for word in doc_words:
                doc_word_freq[word] = doc_word_freq.get(word, 0) + 1

            score = 0
            for word in query_words:
                if word in doc_word_freq:
                    df = self._doc_freqs.get(word, 0)
                    if df == 0:
                        continue

                    tf = doc_word_freq[word]
                    idf = math.log((N - df + 0.5) / (df + 0.5) + 1)

                    tf_score = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl))
                    score += idf * tf_score

            scores.append(score)

        # 取 top_k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append(
                    SearchResult(
                        doc_id=self._doc_ids[idx],
                        content=self._documents[idx],
                        score=scores[idx],
                        metadata=self._metadatas[idx],
                    )
                )

        return results

    def save(self, path: str):
        data = {
            "k1": self.k1,
            "b": self.b,
            "doc_ids": self._doc_ids,
            "documents": self._documents,
            "metadatas": self._metadatas,
            "doc_freqs": self._doc_freqs,
            "avgdl": self._avgdl,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str):
        with open(path, "r") as f:
            data = json.load(f)
        self.k1 = data["k1"]
        self.b = data["b"]
        self._doc_ids = data["doc_ids"]
        self._documents = data["documents"]
        self._metadatas = data["metadatas"]
        self._doc_freqs = data["doc_freqs"]
        self._avgdl = data["avgdl"]


import math

# ==================== RRF 混合检索 ====================


class RankFusion:
    """RRF 混合检索"""

    def __init__(self, k: int = 60):
        self.k = k

    async def fuse(
        self,
        dense_results: List[SearchResult],
        sparse_results: List[SearchResult],
        top_k: int = 10,
    ) -> List[SearchResult]:
        """融合检索结果"""

        # 构建排名映射
        dense_ranks = {r.doc_id: idx + 1 for idx, r in enumerate(dense_results)}
        sparse_ranks = {r.doc_id: idx + 1 for idx, r in enumerate(sparse_results)}

        # 收集所有文档
        all_doc_ids = set(dense_ranks.keys()) | set(sparse_ranks.keys())

        # 计算 RRF 分数
        rrf_scores = {}
        for doc_id in all_doc_ids:
            score = 0

            # 稠密检索贡献
            if doc_id in dense_ranks:
                score += 1.0 / (self.k + dense_ranks[doc_id])

            # 稀疏检索贡献
            if doc_id in sparse_ranks:
                score += 1.0 / (self.k + sparse_ranks[doc_id])

            rrf_scores[doc_id] = score

        # 排序
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # 构建结果
        doc_map = {r.doc_id: r for r in dense_results + sparse_results}

        results = []
        for doc_id, score in sorted_docs:
            result = doc_map.get(doc_id)
            if result:
                results.append(
                    SearchResult(
                        doc_id=result.doc_id,
                        content=result.content,
                        score=score,
                        metadata=result.metadata,
                    )
                )

        return results


# ==================== 文档解析器 ====================


class DocumentParser:
    """文档解析器"""

    @staticmethod
    async def parse(file_path: str) -> str:
        """解析文档"""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".txt":
            return await DocumentParser._parse_txt(file_path)
        elif ext == ".pdf":
            return await DocumentParser._parse_pdf(file_path)
        elif ext == ".epub":
            return await DocumentParser._parse_epub(file_path)
        elif ext == ".md":
            return await DocumentParser._parse_txt(file_path)
        else:
            return await DocumentParser._parse_txt(file_path)

    @staticmethod
    async def _parse_txt(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    async def _parse_pdf(file_path: str) -> str:
        """解析 PDF (简化版)"""
        try:
            import PyPDF2

            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
            return text
        except Exception as e:
            logger.warning(f"PDF解析失败: {e}")
            return ""

    @staticmethod
    async def _parse_epub(file_path: str) -> str:
        """解析 EPUB (简化版)"""
        try:
            import epub_parser

            book = epub_parser.parse_file(file_path)
            return book.get_text()
        except Exception as e:
            logger.warning(f"EPUB解析失败: {e}")
            return ""


# ==================== 知识库管理器 ====================


class KnowledgeBaseManager:
    """知识库管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._vector_store = VectorStore()
        self._sparse_retriever = BM25SparseRetriever()
        self._rank_fusion = RankFusion()
        self._knowledge_bases: Dict[str, Dict] = {}
        self._initialized = True

        logger.info("[KnowledgeBaseManager] 初始化完成")

    async def create_knowledge_base(
        self,
        kb_id: str,
        name: str,
        description: str = "",
        embedding_model: str = "openai_embedding",
    ):
        """创建知识库"""
        self._knowledge_bases[kb_id] = {
            "id": kb_id,
            "name": name,
            "description": description,
            "embedding_model": embedding_model,
            "document_count": 0,
        }

        # 为这个知识库创建独立的存储
        os.makedirs(f"data/knowledge_base/{kb_id}", exist_ok=True)

        logger.info(f"[KnowledgeBaseManager] 创建知识库: {name}")

    async def add_document(
        self,
        kb_id: str,
        content: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ):
        """添加文档"""
        import uuid

        doc_id = str(uuid.uuid4())

        # 添加到向量存储
        if embedding:
            await self._vector_store.add(doc_id, embedding, metadata, content)

        # 添加到 BM25
        await self._sparse_retriever.add(doc_id, content, metadata)

        # 更新计数
        if kb_id in self._knowledge_bases:
            self._knowledge_bases[kb_id]["document_count"] += 1

        # 保存到文件
        doc_path = f"data/knowledge_base/{kb_id}/{doc_id}.json"
        os.makedirs(f"data/knowledge_base/{kb_id}", exist_ok=True)
        with open(doc_path, "w") as f:
            json.dump({"content": content, "metadata": metadata, "embedding": embedding}, f)

        logger.info(f"[KnowledgeBaseManager] 添加文档: {doc_id}")

    async def query(
        self,
        kb_id: str,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        method: str = "hybrid",
    ) -> List[SearchResult]:
        """查询知识库"""

        if method == "dense":
            # ���向量检索
            if query_embedding:
                return await self._vector_store.search(query_embedding, top_k)
        elif method == "sparse":
            # 仅 BM25
            return await self._sparse_retriever.search(query, top_k)
        else:
            # 混合检索 (RRF)
            dense_results = []
            if query_embedding:
                dense_results = await self._vector_store.search(query_embedding, top_k)

            sparse_results = await self._sparse_retriever.search(query, top_k)

            return await self._rank_fusion.fuse(dense_results, sparse_results, top_k)

    async def import_file(self, kb_id: str, file_path: str, metadata: Dict = None):
        """导入文件到知识库"""
        content = await DocumentParser.parse(file_path)

        embedding = None

        file_metadata = metadata or {}
        file_metadata["source_file"] = file_path

        await self.add_document(kb_id, content, file_metadata, embedding)

        logger.info(f"[KnowledgeBaseManager] 导入文件: {file_path}")

    def save(self, path: str):
        """将知识库状态持久化到文件"""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        data = {
            "knowledge_bases": self._knowledge_bases,
        }
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[KnowledgeBaseManager] 状态已保存到 {path}")

    def load(self, path: str):
        """从文件加载知识库状态"""
        if not os.path.exists(path):
            logger.warning(f"[KnowledgeBaseManager] 状态文件不存在: {path}")
            return
        with open(path, "r") as f:
            data = json.load(f)
        self._knowledge_bases = data.get("knowledge_bases", {})
        logger.info(f"[KnowledgeBaseManager] 状态已从 {path} 加载")

    def list_knowledge_bases(self) -> List[Dict]:
        """列出了知识库"""
        return list(self._knowledge_bases.values())

    def get_knowledge_base(self, kb_id: str) -> Optional[Dict]:
        return self._knowledge_bases.get(kb_id)


# 全局实例
_knowledge_base_manager = None


def get_knowledge_base_manager() -> KnowledgeBaseManager:
    global _knowledge_base_manager
    if _knowledge_base_manager is None:
        _knowledge_base_manager = KnowledgeBaseManager()
    return _knowledge_base_manager


__all__ = [
    "Document",
    "SearchResult",
    "VectorStore",
    "BM25SparseRetriever",
    "RankFusion",
    "DocumentParser",
    "KnowledgeBaseManager",
    "get_knowledge_base_manager",
]
