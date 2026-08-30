"""
本地知识库存储引擎 — 基于 ChromaDB + embedding 模型

所有可配置项从 config/text_config.json 和 config/qq_config.yaml 读取，
不在代码中硬编码任何用户可见文本或配置值。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.config_utils import (
    get_api_key,
    get_knowledge_config,
    get_text_message,
)

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    from openai import AsyncOpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def _get_data_dir() -> Path:
    cfg_dir = get_knowledge_config("storage", default={}).get("data_dir", "")
    if cfg_dir:
        return Path(cfg_dir)
    return (
        Path(os.getenv("MIYA_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data")))
        / "knowledge"
    )


def _get_embedding_config() -> dict:
    cfg = get_knowledge_config("embedding", default={})
    return {
        "api_url": get_api_key("EMBEDDING_API_URL", get_api_key("OPENAI_API_BASE", "https://api.openai.com/v1")),
        "api_key": get_api_key("EMBEDDING_API_KEY") or get_api_key("OPENAI_API_KEY"),
        "model": os.getenv("EMBEDDING_MODEL", cfg.get("model_default", "text-embedding-3-small")),
    }


class KnowledgeStore:
    _instance: Optional[KnowledgeStore] = None

    def __init__(self):
        self._data_dir = _get_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._data_dir / get_knowledge_config("storage", default={}).get("index_file", "index.json")
        self._embed_config = _get_embedding_config()
        self._chroma_client: Any = None
        self._collection: Any = None
        self._openai_client: Any = None
        self._initialized = False

        self._default_category = get_knowledge_config("default_category", default="通用")
        self._collection_name = get_knowledge_config("collection_name", default="knowledge_base")
        self._max_embed_text = get_knowledge_config("embedding", default={}).get("max_text_length", 8000)
        self._max_chroma_doc = get_knowledge_config("chroma", default={}).get("max_doc_length", 4000)
        self._hnsw_space = get_knowledge_config("chroma", default={}).get("hnsw_space", "cosine")

    @classmethod
    def get_instance(cls) -> KnowledgeStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        if self._initialized:
            return

        if HAS_CHROMA and self._embed_config.get("api_key"):
            try:
                chroma_path = str(self._data_dir / "chromadb")
                self._chroma_client = await asyncio.to_thread(
                    lambda: chromadb.PersistentClient(
                        path=chroma_path,
                        settings=ChromaSettings(anonymized_telemetry=False),
                    )
                )
                self._collection = await asyncio.to_thread(
                    lambda: self._chroma_client.get_or_create_collection(
                        name=self._collection_name,
                        metadata={"hnsw:space": self._hnsw_space},
                    )
                )
                logger.info(f"[知识库] ChromaDB 初始化成功: {chroma_path}")
            except Exception as e:
                logger.warning(f"[知识库] ChromaDB 初始化失败，使用文件模式: {e}")
                self._chroma_client = None
                self._collection = None

        # 优先使用弥娅本地 EmbeddingClient，回退到 OpenAI
        # 注意：不在此处同步加载模型（SentenceTransformer 加载会阻塞事件循环）
        # 改为懒加载：首次调用 _get_embedding 时才初始化
        self._openai_client = None
        self._miya_embedder = None
        self._miya_embedder_init_attempted = False

        self._initialized = True

    async def _get_embedding(self, text: str) -> list[float]:
        text = text.strip()[: self._max_embed_text]

        # TODO: Miya 本地 embedder 懒加载会阻塞事件循环，暂时跳过
        # 后续改为 asyncio.to_thread 加载或复用已加载的全局实例
        # (embedder disabled via early return)
        if self._miya_embedder_init_attempted:
            self._miya_embedder_init_attempted = True
            try:
                from core.embedding_client import EmbeddingClient, EmbeddingProvider

                self._miya_embedder = EmbeddingClient(
                    provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
                    model="BAAI/bge-small-zh-v1.5",
                )
                await self._miya_embedder.initialize()
                logger.info("[知识库] 使用弥娅本地 embedding 模型")
            except Exception as e:
                logger.debug(f"[知识库] 弥娅 embedder 不可用: {e}")

        if self._miya_embedder is not None:
            try:
                result = await self._miya_embedder.embed([text])
                if isinstance(result, list) and result and isinstance(result[0], list):
                    return result[0]
                if isinstance(result, list) and result:
                    return list(result) if isinstance(result[0], (int, float)) else []
            except Exception as e:
                logger.debug(f"[知识库] 弥娅 embedder 失败: {e}")

        if self._openai_client is not None:
            try:
                resp = await self._openai_client.embeddings.create(
                    model=self._embed_config["model"],
                    input=text,
                )
                return resp.data[0].embedding
            except Exception as e:
                logger.error(f"[知识库] embedding 失败: {e}")

        return []

    def _read_index(self) -> dict:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"entries": {}, "categories": {}}
        return {"entries": {}, "categories": {}}

    def _write_index(self, index: dict) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._index_path)

    def _generate_id(self, title: str, content: str) -> str:
        raw = f"{title}:{content[:200]}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    async def add(self, content: str, title: str = "", category: str = "", source: str = "") -> str:
        await self.initialize()

        knowledge_id = self._generate_id(title, content)
        now = datetime.now(datetime.UTC).isoformat()
        cat = category or self._default_category

        entry = {
            "id": knowledge_id,
            "title": title or content[:60],
            "content": content,
            "category": cat,
            "source": source,
            "created_at": now,
            "updated_at": now,
        }

        index = self._read_index()
        index["entries"][knowledge_id] = entry
        if cat not in index["categories"]:
            index["categories"][cat] = []
        if knowledge_id not in index["categories"][cat]:
            index["categories"][cat].append(knowledge_id)
        self._write_index(index)

        if self._collection is not None:
            embedding = await self._get_embedding(content)
            if embedding:
                try:
                    await asyncio.to_thread(
                        lambda: self._collection.upsert(
                            ids=[knowledge_id],
                            embeddings=[embedding],
                            metadatas=[
                                {
                                    "title": title or content[:60],
                                    "category": cat,
                                    "source": source,
                                    "created_at": now,
                                }
                            ],
                            documents=[content[: self._max_chroma_doc]],
                        )
                    )
                except Exception as e:
                    logger.warning(f"[知识库] ChromaDB 写入失败: {e}")

        logger.info(f"[知识库] 添加: id={knowledge_id}")
        return knowledge_id

    async def delete(self, knowledge_id: str) -> bool:
        await self.initialize()
        index = self._read_index()
        if knowledge_id not in index["entries"]:
            return False

        entry = index["entries"].pop(knowledge_id)
        cat = entry.get("category", self._default_category)
        if cat in index["categories"] and knowledge_id in index["categories"][cat]:
            index["categories"][cat].remove(knowledge_id)
        self._write_index(index)

        if self._collection is not None:
            try:
                await asyncio.to_thread(lambda: self._collection.delete(ids=[knowledge_id]))
            except Exception as e:
                logger.warning(f"[知识库] ChromaDB 删除失败: {e}")

        logger.info(f"[知识库] 删除: id={knowledge_id}")
        return True

    async def update(self, knowledge_id: str, content: str = "", title: str = "", category: str = "") -> bool:
        await self.initialize()
        index = self._read_index()
        if knowledge_id not in index["entries"]:
            return False

        entry = index["entries"][knowledge_id]
        if content:
            entry["content"] = content
        if title:
            entry["title"] = title
        if category:
            old_cat = entry.get("category", self._default_category)
            if old_cat in index["categories"] and knowledge_id in index["categories"][old_cat]:
                index["categories"][old_cat].remove(knowledge_id)
            entry["category"] = category
            if category not in index["categories"]:
                index["categories"][category] = []
            if knowledge_id not in index["categories"][category]:
                index["categories"][category].append(knowledge_id)

        entry["updated_at"] = datetime.now(datetime.UTC).isoformat()
        self._write_index(index)

        if self._collection is not None and content:
            embedding = await self._get_embedding(content)
            if embedding:
                try:
                    await asyncio.to_thread(
                        lambda: self._collection.upsert(
                            ids=[knowledge_id],
                            embeddings=[embedding],
                            metadatas=[
                                {
                                    "title": entry["title"],
                                    "category": entry.get("category", self._default_category),
                                    "updated_at": entry["updated_at"],
                                }
                            ],
                            documents=[content[: self._max_chroma_doc]],
                        )
                    )
                except Exception as e:
                    logger.warning(f"[知识库] ChromaDB 更新失败: {e}")
        return True

    async def search_semantic(self, query: str, limit: int = 10, category: str = "") -> list[dict]:
        await self.initialize()
        results = []
        if self._collection is not None:
            embedding = await self._get_embedding(query)
            if embedding:
                try:
                    where_filter = {"category": category} if category else None
                    chroma_results = await asyncio.to_thread(
                        lambda: self._collection.query(
                            query_embeddings=[embedding],
                            n_results=limit,
                            where=where_filter,
                        )
                    )
                    ids = chroma_results.get("ids", [[]])[0]
                    distances = chroma_results.get("distances", [[]])[0]
                    metadatas = chroma_results.get("metadatas", [[]])[0]
                    documents = chroma_results.get("documents", [[]])[0]
                    index = self._read_index()
                    for i, kid in enumerate(ids):
                        entry = index["entries"].get(kid, {})
                        results.append(
                            {
                                "id": kid,
                                "title": entry.get(
                                    "title", metadatas[i].get("title", "") if i < len(metadatas) else ""
                                ),
                                "content": entry.get("content", documents[i] if i < len(documents) else ""),
                                "category": entry.get("category", ""),
                                "score": round(1.0 - distances[i], 4) if i < len(distances) else 0,
                                "method": "semantic",
                            }
                        )
                    return results
                except Exception as e:
                    logger.warning(f"[知识库] 语义搜索失败，回退到关键词搜索: {e}")
        return await self.search_keyword(query, limit, category)

    async def search_keyword(self, query: str, limit: int = 10, category: str = "") -> list[dict]:
        await self.initialize()
        index = self._read_index()
        results = []
        query_lower = query.lower()
        for kid, entry in index["entries"].items():
            if category and entry.get("category", self._default_category) != category:
                continue
            title = (entry.get("title") or "").lower()
            content = (entry.get("content") or "").lower()
            cat = (entry.get("category") or "").lower()
            score = 0
            if query_lower in title:
                score += 10
            for word in query_lower.split():
                if word in title:
                    score += 3
                if word in content:
                    score += 1
                if word in cat:
                    score += 2
            if query_lower in content:
                score += 5
            if score > 0:
                results.append(
                    {
                        "id": kid,
                        "title": entry.get("title", ""),
                        "content": entry.get("content", ""),
                        "category": entry.get("category", ""),
                        "score": score,
                        "method": "keyword",
                    }
                )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    async def list_entries(self, category: str = "", limit: int = 50) -> list[dict]:
        await self.initialize()
        index = self._read_index()
        entries = list(index["entries"].values())
        if category:
            entries = [e for e in entries if e.get("category") == category]
        entries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return entries[:limit]

    async def get_entry(self, knowledge_id: str) -> Optional[dict]:
        await self.initialize()
        index = self._read_index()
        return index["entries"].get(knowledge_id)

    async def list_categories(self) -> list[str]:
        await self.initialize()
        index = self._read_index()
        return sorted(index["categories"].keys())

    async def get_stats(self) -> dict:
        await self.initialize()
        index = self._read_index()
        total = len(index["entries"])
        categories = {c: len(ids) for c, ids in index["categories"].items()}
        chroma_count = 0
        if self._collection is not None:
            try:
                chroma_count = await asyncio.to_thread(lambda: self._collection.count())
            except Exception:
                pass
        return {
            "total_entries": total,
            "categories": categories,
            "chroma_entries": chroma_count,
            "has_embedding": self._miya_embedder is not None or self._openai_client is not None,
            "has_chroma": self._collection is not None,
        }


def get_knowledge_store() -> KnowledgeStore:
    return KnowledgeStore.get_instance()
