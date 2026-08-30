"""LifeNet 子网 - LifeBook 功能的子网实现"""

import logging
from typing import Any, Dict, Optional

from webnet.life import LifeNet


logger = logging.getLogger(__name__)


class LifeSubnet:
    """LifeBook 记忆子网
    
    负责将 LifeBook 功能整合进弥娅网络系统
    """
    
    def __init__(self, base_dir: Optional[str] = None, ai_client=None):
        """初始化 Life 子网"""
        self.life = LifeNet(base_dir=base_dir, ai_client=ai_client)
        self.name = "LifeNet"
        self.description = "LifeBook 记忆管理网络"
    
    def get_name(self) -> str:
        return self.name
    
    def get_description(self) -> str:
        return self.description
    
    async def handle_message(
        self,
        message: str,
        context: Dict[str, Any] = None,
    ) -> Optional[str]:
        """处理消息（保留接口，暂不使用）
        
        LifeNet 通过工具函数接口提供服务，不处理普通消息
        """
        return None
    
    async def handle_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Any:
        """处理工具调用
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 调用上下文
        
        Returns:
            工具执行结果
        """
        try:
            # 日记相关
            if tool_name == "life_add_diary":
                return await self.life.add_diary(
                    content=args.get("content", ""),
                    mood=args.get("mood"),
                    tags=args.get("tags"),
                )
            
            elif tool_name == "life_get_diary":
                return await self.life.get_diary(
                    date=args.get("date"),
                )
            
            # 节点相关
            elif tool_name == "life_create_character_node":
                return await self.life.create_character_node(
                    name=args.get("name", ""),
                    description=args.get("description", ""),
                    tags=args.get("tags"),
                )
            
            elif tool_name == "life_create_stage_node":
                return await self.life.create_stage_node(
                    name=args.get("name", ""),
                    description=args.get("description", ""),
                    tags=args.get("tags"),
                )
            
            elif tool_name == "life_list_nodes":
                return await self.life.list_nodes(
                    node_type=args.get("node_type"),
                )
            
            elif tool_name == "life_get_node":
                return await self.life.get_node(
                    name=args.get("name", ""),
                )
            
            # 总结相关
            elif tool_name == "life_add_summary":
                return await self.life.add_summary(
                    level=args.get("level", ""),
                    title=args.get("title", ""),
                    content=args.get("content", ""),
                    capsule=args.get("capsule"),
                )
            
            elif tool_name == "life_get_summary":
                return await self.life.get_summary(
                    level=args.get("level", ""),
                    period=args.get("period", ""),
                )
            
            # 记忆上下文
            elif tool_name == "life_get_memory_context":
                return await self.life.get_memory_context(
                    months_back=args.get("months_back", 1),
                    include_nodes=args.get("include_nodes", True),
                )
            
            # 搜索
            elif tool_name == "life_search_memory":
                return await self.life.search_memory(
                    keyword=args.get("keyword", ""),
                    level=args.get("level"),
                    limit=args.get("limit", 5),
                )
            
            else:
                return f"❌ 未知的工具: {tool_name}"
        
        except Exception as e:
            logger.error(f"[LifeSubnet] 工具调用失败 {tool_name}: {e}")
            return f"❌ 执行失败: {str(e)}"
