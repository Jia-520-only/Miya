"""
统一知识库管理器 - Unified Knowledge Base Manager

整合弥娅原有知识库 + AstrBot 迁移知识库
===============================================
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("miya.unified.knowledge")


class UnifiedKnowledgeManager:
    """统一知识库管理器"""

    def __init__(self) -> None:
        self._knowledge_bases: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化知识库"""
        logger.info("[KnowledgeManager] 初始化知识库...")

        # 尝试加载 AstrBot 知识库
        try:
            from astrbot.core.knowledge_base.kb_mgr import (
                KnowledgeBaseManager as AstrBotKBMgr,
            )

            self._astrbots_kb = AstrBotKBMgr()
            logger.info("  ✅ AstrBot 知识库已加载")
        except ImportError as e:
            logger.warning(f"  ⚠ AstrBot 知识库不可用: {e}")
            self._astrbots_kb = None

        # 尝试加载 Miya 知识库
        try:
            from core.knowledge_base import KnowledgeBaseManager as MiyaKBMgr

            self._miya_kb = MiyaKBMgr()
            await self._miya_kb.initialize()
            logger.info("  ✅ Miya 知识库已加载")
        except ImportError as e:
            logger.warning(f"  ⚠ Miya 知识库不可用: {e}")
            self._miya_kb = None

        self._initialized = True

    async def create_knowledge_base(
        self,
        name: str,
        description: str = "",
        embedding_provider: str = "openai",
    ) -> Optional[Any]:
        """创建知识库"""
        # 优先使用 AstrBot (更强大)
        if self._astrbots_kb:
            try:
                kb = await self._astrbots_kb.create_kb(name, description, embedding_provider)
                self._knowledge_bases[name] = kb
                logger.info(f"[KnowledgeManager] 创建知识库 (AstrBot): {name}")
                return kb
            except Exception as e:
                logger.warning(f"AstrBot KB 创建失败，回退到 Miya: {e}")

        # 回退到 Miya
        if self._miya_kb:
            kb = await self._miya_kb.create_kb(name, embedding_provider)
            self._knowledge_bases[name] = kb
            logger.info(f"[KnowledgeManager] 创建知识库 (Miya): {name}")
            return kb

        return None

    async def search(
        self,
        query: str,
        kb_names: List[str],
        top_k: int = 5,
    ) -> List[Dict]:
        """搜索知识库"""
        results = []

        for kb_name in kb_names:
            kb = self._knowledge_bases.get(kb_name)
            if not kb:
                continue

            try:
                if hasattr(kb, "retrieve"):
                    kb_results = await kb.retrieve(query, top_k)
                    results.extend(kb_results)
            except Exception as e:
                logger.warning(f"搜索失败 {kb_name}: {e}")

        # 排序返回
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:top_k]

    async def add_document(
        self,
        kb_name: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """添加文档"""
        kb = self._knowledge_bases.get(kb_name)
        if not kb:
            return False

        try:
            if hasattr(kb, "add_document"):
                await kb.add_document(content, metadata)
                logger.info(f"[KnowledgeManager] 添加文档到 {kb_name}")
                return True
        except Exception as e:
            logger.error(f"添加文档失败: {e}")

        return False

    def list_knowledge_bases(self) -> List[Dict]:
        """列出知识库"""
        return [
            {
                "name": name,
                "type": "astrabot" if kb.__class__.__module__.startswith("astrbot") else "miya",
            }
            for name, kb in self._knowledge_bases.items()
        ]


# 全局实例
_knowledge_manager: Optional[UnifiedKnowledgeManager] = None


def get_knowledge_manager() -> UnifiedKnowledgeManager:
    """获取全局知识库管理器"""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = UnifiedKnowledgeManager()
    return _knowledge_manager


__all__ = [
    "UnifiedKnowledgeManager",
    "get_knowledge_manager",
]
