"""
弥娅向量索引 — FAISS 加速层

替代纯 Python 逐条余弦相似度计算，提供 O(log N) 级向量检索。
FAISS 不可用时自动回退到纯 Python 余弦计算。
"""

import importlib
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.info("[VectorIndex] FAISS 未安装，使用纯 Python 余弦回退")

FAISS_AVX2_AVAILABLE = False
if FAISS_AVAILABLE:
    try:
        importlib.import_module("faiss.swigfaiss_avx2")
        FAISS_AVX2_AVAILABLE = True
    except ImportError:
        pass

if FAISS_AVAILABLE:
    if FAISS_AVX2_AVAILABLE:
        logger.info("[VectorIndex] FAISS AVX2 加速已启用")
    else:
        logger.warning(
            "[VectorIndex] 当前 faiss 包未包含 AVX2 扩展，使用基础实现；可升级支持 AVX2 的 faiss 构建以加速检索"
        )


class VectorIndex:
    """FAISS 向量加速索引"""

    def __init__(self, dimension: int = 1024, persist_path: Optional[Path] = None):
        self.dimension = dimension
        self.persist_path = persist_path
        self._index = None
        self._id_map: Dict[int, str] = {}  # FAISS index pos → memory_id
        self._id_reverse: Dict[str, int] = {}  # memory_id → FAISS index pos
        self._count: int = 0
        self._dirty: bool = False
        self._last_save: float = time.time()

        if FAISS_AVAILABLE:
            self._init_faiss()
        else:
            self._vectors: Dict[str, np.ndarray] = {}

    def _init_faiss(self):
        self._index = faiss.IndexFlatIP(self.dimension)
        logger.info(f"[VectorIndex] FAISS IndexFlatIP 初始化，维度={self.dimension}")

    @property
    def count(self) -> int:
        return self._count

    def add(self, memory_id: str, vector: List[float]) -> bool:
        if not vector or len(vector) != self.dimension:
            logger.debug(f"[VectorIndex] 向量维度不匹配: {len(vector) if vector else 0} != {self.dimension}")
            return False

        vec = np.array(vector, dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(vec) if FAISS_AVAILABLE else None

        if FAISS_AVAILABLE:
            pos = self._count
            self._index.add(vec)
            self._id_map[pos] = memory_id
            self._id_reverse[memory_id] = pos
        else:
            self._vectors[memory_id] = vec.flatten()

        self._count += 1
        self._dirty = True
        return True

    def remove(self, memory_id: str) -> bool:
        if FAISS_AVAILABLE:
            if memory_id in self._id_reverse:
                del self._id_reverse[memory_id]
                return True
        else:
            if memory_id in self._vectors:
                del self._vectors[memory_id]
                self._count = len(self._vectors)
                return True
        return False

    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[Tuple[str, float]]:
        """向量相似度搜索，返回 [(memory_id, score), ...]"""
        if not query_vector or len(query_vector) != self.dimension:
            return []

        qvec = np.array(query_vector, dtype=np.float32).reshape(1, -1)

        if FAISS_AVAILABLE:
            return self._search_faiss(qvec, limit, threshold)
        else:
            return self._search_python(qvec, limit, threshold)

    def _search_faiss(
        self,
        qvec: np.ndarray,
        limit: int,
        threshold: float,
    ) -> List[Tuple[str, float]]:
        if self._count == 0:
            return []

        faiss.normalize_L2(qvec)
        k = min(limit * 3, self._count)
        distances, indices = self._index.search(qvec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0], strict=False):
            if idx < 0 or idx not in self._id_map:
                continue
            score = float(dist)
            if score >= threshold:
                results.append((self._id_map[idx], score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _search_python(
        self,
        qvec: np.ndarray,
        limit: int,
        threshold: float,
    ) -> List[Tuple[str, float]]:
        qvec_flat = qvec.flatten()
        qnorm = np.linalg.norm(qvec_flat)
        if qnorm == 0:
            return []

        scored = []
        for mid, vec in self._vectors.items():
            try:
                vnorm = np.linalg.norm(vec)
                if vnorm == 0:
                    continue
                similarity = float(np.dot(qvec_flat, vec) / (qnorm * vnorm))
                if similarity >= threshold:
                    scored.append((mid, similarity))
            except Exception:
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def persist(self) -> bool:
        """持久化 FAISS 索引到磁盘"""
        if not self.persist_path or not self._dirty:
            return False

        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)

            if FAISS_AVAILABLE and self._index is not None:
                faiss.write_index(self._index, str(self.persist_path))

            import json

            map_path = self.persist_path.with_suffix(".json")
            with open(map_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "id_map": self._id_map,
                        "id_reverse": self._id_reverse,
                        "count": self._count,
                    },
                    f,
                    ensure_ascii=False,
                )

            self._dirty = False
            self._last_save = time.time()
            logger.debug(f"[VectorIndex] 已持久化 {self._count} 个向量")
            return True
        except Exception as e:
            logger.warning(f"[VectorIndex] 持久化失败: {e}")
            return False

    def load(self) -> bool:
        """从磁盘加载 FAISS 索引"""
        if not self.persist_path or not self.persist_path.exists():
            return False

        try:
            if FAISS_AVAILABLE:
                self._index = faiss.read_index(str(self.persist_path))
            else:
                self._vectors.clear()

            import json

            map_path = self.persist_path.with_suffix(".json")
            if map_path.exists():
                with open(map_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._id_map = {int(k): v for k, v in data.get("id_map", {}).items()}
                    self._id_reverse = data.get("id_reverse", {})
                    self._count = data.get("count", 0)

            logger.info(f"[VectorIndex] 已加载 {self._count} 个向量")
            return True
        except Exception as e:
            logger.warning(f"[VectorIndex] 加载失败: {e}")
            return False


def get_vector_index(
    dimension: int = 4096,
    persist_path: Optional[Path] = None,
) -> VectorIndex:
    """获取向量索引单例"""
    if not hasattr(get_vector_index, "_instance"):
        get_vector_index._instance = VectorIndex(dimension, persist_path)  # type: ignore
    return get_vector_index._instance  # type: ignore


def reset_vector_index():
    """重置向量索引单例"""
    if hasattr(get_vector_index, "_instance"):
        del get_vector_index._instance  # type: ignore
