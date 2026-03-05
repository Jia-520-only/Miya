"""LifeNet - LifeBook 记忆管理网络

LifeBook 功能的 QQ 机器人接口
- 日记记录与查询
- 层级总结（日/周/月/季/年）
- 节点管理（角色/阶段）
- 一键获取记忆上下文
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from memory.lifebook_manager import (
    LifeBookManager,
    MemoryLevel,
    NodeType,
    Node,
)

logger = logging.getLogger(__name__)


class LifeNet:
    """LifeBook 记忆网络
    
    提供 QQ 机器人接口访问 LifeBook 记忆系统
    """
    
    def __init__(self, base_dir: Optional[str] = None, ai_client=None):
        """初始化 LifeNet
        
        Args:
            base_dir: LifeBook 数据目录
            ai_client: AI 客户端（用于自动总结）
        """
        self.lifebook = LifeBookManager(base_dir=base_dir, ai_client=ai_client)
        logger.info("[LifeNet] LifeBook 记忆网络已启动")
    
    # ========== 日记相关 ==========
    
    async def add_diary(
        self,
        content: str,
        mood: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> str:
        """添加日记
        
        Args:
            content: 日记内容
            mood: 心情
            tags: 标签列表
        
        Returns:
            结果消息
        """
        try:
            date = datetime.now()
            title = f"{date.strftime('%Y年%m月%d日')} 日记"
            
            entry = self.lifebook.add_entry(
                level=MemoryLevel.DAILY,
                title=title,
                content=content,
                tags=tags or [],
                mood=mood,
            )
            
            logger.info(f"[LifeNet] 添加日记: {entry.entry_id}")
            return f"✅ 已记录日记: {title}\n{content[:100]}..."
        
        except Exception as e:
            logger.error(f"[LifeNet] 添加日记失败: {e}")
            return f"❌ 记录失败: {str(e)}"
    
    async def get_diary(self, date: Optional[str] = None) -> str:
        """获取日记
        
        Args:
            date: 日期（格式：YYYY-MM-DD），默认为今天
        
        Returns:
            日记内容
        """
        try:
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")
            
            entry = self.lifebook.get_entry(MemoryLevel.DAILY, date)
            
            if not entry:
                return f"📝 {date} 没有日记记录"
            
            result = f"## {entry.title}\n"
            if entry.mood:
                result += f"心情: {entry.mood}\n"
            if entry.tags:
                result += f"标签: {' '.join(entry.tags)}\n"
            result += f"\n{entry.content}"
            
            return result
        
        except Exception as e:
            logger.error(f"[LifeNet] 获取日记失败: {e}")
            return f"❌ 获取失败: {str(e)}"
    
    # ========== 节点管理 ==========
    
    async def create_character_node(
        self,
        name: str,
        description: str = "",
        tags: Optional[list] = None,
    ) -> str:
        """创建角色节点
        
        Args:
            name: 角色名称
            description: 描述
            tags: 标签
        
        Returns:
            结果消息
        """
        try:
            node = self.lifebook.create_node(
                name=name,
                node_type=NodeType.CHARACTER,
                tags=tags or [],
                description=description,
            )
            
            logger.info(f"[LifeNet] 创建角色节点: {node.node_id}")
            return f"✅ 已创建角色节点: {node.name}\n{node.description}"
        
        except Exception as e:
            logger.error(f"[LifeNet] 创建角色节点失败: {e}")
            return f"❌ 创建失败: {str(e)}"
    
    async def create_stage_node(
        self,
        name: str,
        description: str = "",
        tags: Optional[list] = None,
    ) -> str:
        """创建阶段节点
        
        Args:
            name: 阶段名称
            description: 描述
            tags: 标签
        
        Returns:
            结果消息
        """
        try:
            node = self.lifebook.create_node(
                name=name,
                node_type=NodeType.STAGE,
                tags=tags or [],
                description=description,
            )
            
            logger.info(f"[LifeNet] 创建阶段节点: {node.node_id}")
            return f"✅ 已创建阶段节点: {node.name}\n{node.description}"
        
        except Exception as e:
            logger.error(f"[LifeNet] 创建阶段节点失败: {e}")
            return f"❌ 创建失败: {str(e)}"
    
    async def list_nodes(
        self,
        node_type: Optional[str] = None,
    ) -> str:
        """列出节点
        
        Args:
            node_type: 节点类型（character/stage）
        
        Returns:
            节点列表
        """
        try:
            type_filter = None
            if node_type:
                if node_type == "character":
                    type_filter = NodeType.CHARACTER
                elif node_type == "stage":
                    type_filter = NodeType.STAGE
            
            nodes = self.lifebook.list_nodes(node_type=type_filter)
            
            if not nodes:
                return "📋 暂无节点记录"
            
            result = "## 节点列表\n\n"
            for node in nodes:
                node_type_name = "角色" if node.node_type == NodeType.CHARACTER else "阶段"
                result += f"### {node.name} ({node_type_name})\n"
                if node.description:
                    result += f"{node.description}\n"
                if node.tags:
                    result += f"标签: {' '.join(node.tags)}\n"
                result += "\n"
            
            return result
        
        except Exception as e:
            logger.error(f"[LifeNet] 列出节点失败: {e}")
            return f"❌ 获取失败: {str(e)}"
    
    async def get_node(self, name: str) -> str:
        """获取节点详情
        
        Args:
            name: 节点名称
        
        Returns:
            节点详情
        """
        try:
            # 通过名称查找节点
            node = None
            for n in self.lifebook._nodes.values():
                if n.name == name:
                    node = n
                    break
            
            if not node:
                return f"📝 未找到节点: {name}"
            
            result = f"## {node.name}\n\n"
            result += f"类型: {'角色节点' if node.node_type == NodeType.CHARACTER else '阶段节点'}\n"
            result += f"创建时间: {node.created_at}\n"
            if node.description:
                result += f"\n描述:\n{node.description}\n"
            if node.tags:
                result += f"\n标签: {' '.join(node.tags)}\n"
            if node.related_nodes:
                result += f"\n关联节点: {', '.join(node.related_nodes)}\n"
            
            # 查找相关记忆
            result += "\n## 相关记忆\n"
            for level in [MemoryLevel.DAILY, MemoryLevel.WEEKLY, MemoryLevel.MONTHLY]:
                entries = self.lifebook.search_entries(
                    keyword=name,
                    level=level,
                    limit=3,
                )
                if entries:
                    result += f"\n### {level.value} 记忆 ({len(entries)} 条)\n"
                    for entry in entries:
                        result += f"- {entry.title}\n"
            
            return result
        
        except Exception as e:
            logger.error(f"[LifeNet] 获取节点失败: {e}")
            return f"❌ 获取失败: {str(e)}"
    
    # ========== 层级总结 ==========
    
    async def add_summary(
        self,
        level: str,
        title: str,
        content: str,
        capsule: Optional[str] = None,
    ) -> str:
        """添加总结（周/月/季/年）
        
        Args:
            level: 层级（weekly/monthly/quarterly/yearly）
            title: 标题
            content: 内容
            capsule: 胶囊摘要
        
        Returns:
            结果消息
        """
        try:
            level_map = {
                "weekly": MemoryLevel.WEEKLY,
                "monthly": MemoryLevel.MONTHLY,
                "quarterly": MemoryLevel.QUARTERLY,
                "yearly": MemoryLevel.YEARLY,
            }
            
            memory_level = level_map.get(level)
            if not memory_level:
                return f"❌ 无效的层级: {level}"
            
            entry = self.lifebook.add_entry(
                level=memory_level,
                title=title,
                content=content,
                capsule=capsule,
            )
            
            logger.info(f"[LifeNet] 添加总结: {entry.entry_id} ({level})")
            return f"✅ 已记录{level}总结: {title}"
        
        except Exception as e:
            logger.error(f"[LifeNet] 添加总结失败: {e}")
            return f"❌ 记录失败: {str(e)}"
    
    async def get_summary(self, level: str, period: str) -> str:
        """获取总结
        
        Args:
            level: 层级（weekly/monthly/quarterly/yearly）
            period: 周期（如：2025-W03, 2025-01, 2025-Q1, 2025）
        
        Returns:
            总结内容
        """
        try:
            level_map = {
                "weekly": MemoryLevel.WEEKLY,
                "monthly": MemoryLevel.MONTHLY,
                "quarterly": MemoryLevel.QUARTERLY,
                "yearly": MemoryLevel.YEARLY,
            }
            
            memory_level = level_map.get(level)
            if not memory_level:
                return f"❌ 无效的层级: {level}"
            
            entry = self.lifebook.get_entry(memory_level, period)
            
            if not entry:
                return f"📝 {period} 没有总结记录"
            
            result = f"## {entry.title}\n"
            if entry.capsule:
                result += f"> {entry.capsule}\n\n"
            result += entry.content
            
            return result
        
        except Exception as e:
            logger.error(f"[LifeNet] 获取总结失败: {e}")
            return f"❌ 获取失败: {str(e)}"
    
    # ========== 一键获取记忆上下文 ==========
    
    async def get_memory_context(
        self,
        months_back: int = 1,
        include_nodes: bool = True,
    ) -> str:
        """一键获取记忆上下文
        
        Args:
            months_back: 回溯月数
            include_nodes: 是否包含节点信息
        
        Returns:
            记忆上下文
        """
        try:
            context = await self.lifebook.get_core_context(
                months_back=months_back,
                include_nodes=include_nodes,
            )
            
            logger.info(f"[LifeNet] 获取记忆上下文: {months_back}个月")
            return context
        
        except Exception as e:
            logger.error(f"[LifeNet] 获取记忆上下文失败: {e}")
            return f"❌ 获取失败: {str(e)}"
    
    # ========== 搜索功能 ==========
    
    async def search_memory(
        self,
        keyword: str,
        level: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """搜索记忆
        
        Args:
            keyword: 关键词
            level: 层级过滤
            limit: 结果数量限制
        
        Returns:
            搜索结果
        """
        try:
            level_filter = None
            if level:
                level_map = {
                    "daily": MemoryLevel.DAILY,
                    "weekly": MemoryLevel.WEEKLY,
                    "monthly": MemoryLevel.MONTHLY,
                    "quarterly": MemoryLevel.QUARTERLY,
                    "yearly": MemoryLevel.YEARLY,
                }
                level_filter = level_map.get(level)
            
            entries = self.lifebook.search_entries(
                keyword=keyword,
                level=level_filter,
                limit=limit,
            )
            
            if not entries:
                return f"🔍 未找到包含 '{keyword}' 的记忆"
            
            result = f"## 搜索结果: '{keyword}' ({len(entries)} 条)\n\n"
            for entry in entries:
                result += f"### {entry.title}\n"
                result += f"层级: {entry.level.value} | 时间: {entry.created_at}\n"
                result += f"{entry.content[:200]}...\n\n"
            
            return result
        
        except Exception as e:
            logger.error(f"[LifeNet] 搜索记忆失败: {e}")
            return f"❌ 搜索失败: {str(e)}"
