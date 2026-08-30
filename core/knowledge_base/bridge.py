"""
Knowledge Base Bridge - 知识库桥接器

将 core/knowledge_base (新架构) 与 memory/core (旧系统) 连接
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("miya.knowledge_base.bridge")


class KnowledgeBaseBridge:
    """知识库桥接器"""

    def __init__(self) -> None:
        self._kbs: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化"""
        logger.info("[KBBridge] 初始化知识库桥接器...")
        self._initialized = True
        logger.info("[KBBridge] 已初始化")

    async def create_kb(
        self,
        name: str,
        embedding_provider: str = "openai",
        **kwargs,
    ) -> bool:
        """创建知识库"""
        try:
            logger.info(f"[KBBridge] 创建知识库: {name}")
            self._kbs[name] = {
                "name": name,
                "embedding_provider": embedding_provider,
                "doc_count": 0,
            }
            return True
        except Exception as e:
            logger.error(f"[KBBridge] 创建失败: {e}")
            return False

    async def add_document(
        self,
        kb_name: str,
        content: str,
        metadata: Dict | None = None,
    ) -> bool:
        """添加文档"""
        if kb_name not in self._kbs:
            logger.warning(f"[KBBridge] 知识库不存在: {kb_name}")
            return False

        try:
            self._kbs[kb_name]["doc_count"] += 1
            logger.debug(f"[KBBridge] 添加文档到 {kb_name}")
            return True
        except Exception as e:
            logger.error(f"[KBBridge] 添加失败: {e}")
            return False

    async def search(
        self,
        kb_names: List[str],
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """搜索"""
        results = []

        for kb_name in kb_names:
            if kb_name not in self._kbs:
                continue

            # 简化实现 - 返回空结果
            results.append(
                {
                    "kb_name": kb_name,
                    "content": f"知识库 {kb_name} 的相关文档...",
                    "score": 0.9,
                }
            )

        return results[:top_k]

    async def get_context(self, query: str, kb_names: List[str]) -> str:
        """获取检索上下文"""
        results = await self.search(kb_names, query)

        if not results:
            return ""

        lines = ["以下是相关的知识库内容,请参考这些信息回答用户的问题:\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"【知识 {i}】")
            lines.append(f"来源: {r['kb_name']}")
            lines.append(f"内容: {r['content']}")
            lines.append(f"相关度: {r['score']:.2f}")
            lines.append("")

        return "\n".join(lines)

    def list_kbs(self) -> List[Dict]:
        """列出知识库"""
        return [{"name": v["name"], "doc_count": v["doc_count"]} for v in self._kbs.values()]


# 全局实例
_kb_bridge: Optional[KnowledgeBaseBridge] = None


def get_kb_bridge() -> KnowledgeBaseBridge:
    """获取全局实例"""
    global _kb_bridge
    if _kb_bridge is None:
        _kb_bridge = KnowledgeBaseBridge()
    return _kb_bridge


# 便捷函数
async def search_knowledge(query: str, kb_names: List[str] = None) -> str:
    """搜索知识库"""
    bridge = get_kb_bridge()
    if kb_names is None:
        kb_names = [kb["name"] for kb in bridge.list_kbs()]
    return await bridge.get_context(query, kb_names)


__all__ = [
    "KnowledgeBaseBridge",
    "get_kb_bridge",
    "search_knowledge",
]
