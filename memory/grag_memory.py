"""
弥娅 - GRAG知识图谱记忆管理器
整合NagaAgent记忆系统 + VCPToolBox浪潮RAG V3语义动力学
"""

import logging
import asyncio
import weakref
from typing import List, Dict, Optional, Tuple
from .quintuple_extractor import extract_quintuples_async
from .quintuple_graph import store_quintuples, query_graph_by_keywords, get_all_quintuples
from .semantic_dynamics_engine import SemanticDynamicsEngine, get_semantic_dynamics_engine
from .vector_cache import get_vector_cache_manager
from core.constants import NetworkTimeout

# AI名称常量
AI_NAME = "Miya"

logger = logging.getLogger(__name__)


class GRAGMemoryManager:
    """GRAG知识图谱记忆管理器（整合语义动力学）"""

    def __init__(self, config: Optional[Dict] = None, neo4j_client=None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.auto_extract = self.config.get('auto_extract', True)
        self.context_length = self.config.get('context_length', 20)
        self.similarity_threshold = self.config.get('similarity_threshold', 0.7)

        # Neo4j客户端
        self.neo4j_client = neo4j_client

        # NagaAgent: 五元组提取
        self.recent_context = []
        self.extraction_cache = set()
        self.active_tasks = set()

        # VCPToolBox: 语义动力学引擎
        self.semantic_dynamics = get_semantic_dynamics_engine(self.config)

        # 向量缓存管理器
        self.vector_cache = get_vector_cache_manager(self.config)

        if not self.enabled:
            logger.info("GRAG记忆系统已禁用")
            return

        try:
            logger.info("GRAG记忆系统初始化成功（整合语义动力学）")
        except Exception as e:
            logger.error(f"GRAG记忆系统初始化失败: {e}")
            self.enabled = False

    async def add_conversation_memory(self, user_input: str, ai_response: str) -> bool:
        """添加对话记忆到知识图谱"""
        if not self.enabled:
            return False
        try:
            # 拼接本轮内容
            conversation_text = f"用户: {user_input}\n{AI_NAME}: {ai_response}"
            logger.info(f"添加对话记忆: {conversation_text[:50]}...")

            # 更新recent_context（限制长度）
            self.recent_context.append(conversation_text)
            if len(self.recent_context) > self.context_length:
                self.recent_context = self.recent_context[-self.context_length:]

            # 异步提取五元组
            if self.auto_extract:
                try:
                    await self._extract_and_store_quintuples(conversation_text)
                except Exception as e:
                    logger.error(f"提取五元组失败: {e}")
                    # 如果失败，继续进行
                    pass

            return True
        except Exception as e:
            logger.error(f"添加对话记忆失败: {e}")
            return False

    async def _extract_and_store_quintuples(self, text: str) -> bool:
        """提取并存储五元组"""
        try:
            import hashlib
            text_hash = hashlib.sha256(text.encode()).hexdigest()

            if text_hash in self.extraction_cache:
                logger.debug(f"跳过已处理的文本: {text[:50]}...")
                return True

            logger.info(f"提取五元组: {text[:100]}...")
            
            # 添加超时保护
            try:
                quintuples = await asyncio.wait_for(
                    extract_quintuples_async(text), 
                    timeout=NetworkTimeout.API_REQUEST_TIMEOUT  # 30秒超时
                )
            except asyncio.TimeoutError:
                logger.warning("五元组提取超时，跳过本次提取")
                return False

            if not quintuples:
                logger.warning("未提取到五元组")
                return False

            logger.info(f"提取到 {len(quintuples)} 个五元组，准备存储")

            # 存储到Neo4j - 添加超时保护
            try:
                store_success = await asyncio.wait_for(
                    asyncio.to_thread(store_quintuples, quintuples),
                    timeout=15.0  # 15秒超时
                )
            except asyncio.TimeoutError:
                logger.warning("五元组存储超时，跳过本次存储")
                return False

            if store_success:
                self.extraction_cache.add(text_hash)
                logger.info("五元组存储成功")
                return True
            else:
                logger.error("五元组存储失败")
                return False

        except Exception as e:
            logger.error(f"提取和存储五元组失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def query_memory(self, question: str) -> Optional[str]:
        """查询记忆"""
        if not self.enabled:
            return None
            
        try:
            # 从Neo4j查询相关五元组
            quintuples = await asyncio.to_thread(query_graph_by_keywords, [question])
            
            if quintuples:
                # 格式化返回结果
                result_text = "相关知识：\n"
                for i, (subject, subject_type, predicate, obj, obj_type) in enumerate(quintuples[:5], 1):
                    result_text += f"{i}. {subject}({subject_type}) {predicate} {obj}({obj_type})\n"
                
                logger.info("从记忆中找到相关信息")
                return result_text
            return None
        except Exception as e:
            logger.error(f"查询记忆失败: {e}")
            return None
    
    async def get_relevant_memories(self, query: str, limit: int = 3) -> List[Tuple[str, str, str, str, str]]:
        """获取相关记忆（五元组格式）"""
        if not self.enabled:
            return []
            
        try:
            # 从Neo4j查询相关五元组
            quintuples = await asyncio.to_thread(query_graph_by_keywords, [query])
            
            # 限制返回数量
            return quintuples[:limit]
        except Exception as e:
            logger.error(f"获取相关记忆失败: {e}")
            return []
    
    def get_memory_stats(self) -> Dict:
        """获取记忆统计信息"""
        if not self.enabled:
            return {"enabled": False}
            
        try:
            all_quintuples = get_all_quintuples()
            
            return {
                "enabled": True,
                "total_quintuples": len(all_quintuples),
                "context_length": len(self.recent_context),
                "cache_size": len(self.extraction_cache),
                "active_tasks": len(self.active_tasks)
            }
        except Exception as e:
            logger.error(f"获取记忆统计失败: {e}")
            return {"enabled": False, "error": str(e)}
    
    async def clear_memory(self) -> bool:
        """清空记忆"""
        if not self.enabled:
            return False

        try:
            self.recent_context.clear()
            self.extraction_cache.clear()

            # 清空语义动力学缓存
            from .context_vector_manager import get_context_manager
            context_mgr = get_context_manager()
            context_mgr.clear()

            logger.info("记忆已清空")
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {e}")
            return False

    # ==================== 语义动力学接口 ====================

    async def process_conversation_with_semantic_dynamics(
        self,
        messages: List[Dict],
        enable_meta_thinking: bool = False,
        enable_semantic_groups: bool = True
    ):
        """
        使用语义动力学处理对话

        Args:
            messages: 消息列表
            enable_meta_thinking: 是否启用元思考链
            enable_semantic_groups: 是否启用语义组

        Returns:
            SemanticDynamicsResult: 语义动力学结果
        """
        if not self.enabled:
            return None

        try:
            await self.semantic_dynamics.initialize()

            result = await self.semantic_dynamics.process_conversation(
                messages=messages,
                enable_meta_thinking=enable_meta_thinking,
                enable_semantic_groups=enable_semantic_groups
            )

            logger.info(
                f"[GRAG] 语义动力学处理完成 - "
                f"召回{len(result.retrieved_memories)}条记忆, "
                f"激活{len(result.semantic_groups)}个语义组"
            )

            return result
        except Exception as e:
            logger.error(f"语义动力学处理失败: {e}")
            return None

    def set_embedding_func(self, func: callable):
        """设置嵌入函数"""
        self.semantic_dynamics.set_embedding_func(func)

    def set_retrieve_func(self, func: callable):
        """设置检索函数"""
        self.semantic_dynamics.set_retrieve_func(func)

    def set_ai_memo_func(self, func: callable):
        """设置AI记忆处理函数"""
        self.semantic_dynamics.set_ai_memo_func(func)

    async def save_caches(self):
        """保存所有缓存"""
        try:
            await self.vector_cache.save()
            logger.info("[GRAG] 缓存已保存")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")


# 全局记忆管理器实例
_grag_memory_manager: Optional[GRAGMemoryManager] = None


def get_grag_memory_manager() -> GRAGMemoryManager:
    """获取全局GRAG记忆管理器实例"""
    global _grag_memory_manager
    if _grag_memory_manager is None:
        _grag_memory_manager = GRAGMemoryManager()
    return _grag_memory_manager
