"""LifeBook 记忆管理系统

整合 LifeBook 的记忆管理逻辑：
- 日记 -> 周记 -> 月报 -> 季报 -> 年鉴 层级总结
- 角色节点、阶段节点管理
- 时间滚动记忆压缩
- 一键获取核心上下文
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MemoryLevel(Enum):
    """记忆层级"""
    DAILY = "daily"      # 日记
    WEEKLY = "weekly"    # 周记
    MONTHLY = "monthly"  # 月报
    QUARTERLY = "quarterly"  # 季报
    YEARLY = "yearly"    # 年鉴


class NodeType(Enum):
    """节点类型"""
    CHARACTER = "character"  # 角色节点
    STAGE = "stage"          # 阶段节点


@dataclass
class Node:
    """节点（角色/阶段）"""
    node_id: str
    name: str
    node_type: NodeType
    tags: List[str] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    related_nodes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    """记忆条目"""
    entry_id: str
    level: MemoryLevel
    title: str
    content: str
    created_at: str
    updated_at: str
    tags: List[str] = field(default_factory=list)
    mood: Optional[str] = None
    capsule: Optional[str] = None  # 给上层的胶囊摘要
    related_nodes: List[str] = field(default_factory=list)


class LifeBookManager:
    """LifeBook 记忆管理器
    
    功能：
    1. 记忆层级管理（日/周/月/季/年）
    2. 节点管理（角色节点、阶段节点）
    3. 时间滚动记忆压缩
    4. 一键获取核心上下文
    """
    
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        ai_client=None,
    ):
        """初始化 LifeBook 管理器
        
        Args:
            base_dir: 基础目录
            ai_client: AI 客户端（用于自动总结）
        """
        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent / "data" / "lifebook"
        else:
            self.base_dir = Path(base_dir)
        
        self.ai_client = ai_client
        
        # 目录结构
        self.daily_dir = self.base_dir / "daily"
        self.weekly_dir = self.base_dir / "weekly"
        self.monthly_dir = self.base_dir / "monthly"
        self.quarterly_dir = self.base_dir / "quarterly"
        self.yearly_dir = self.base_dir / "yearly"
        self.nodes_dir = self.base_dir / "nodes"
        
        # 初始化目录
        self._ensure_directories()
        
        # 节点缓存
        self._nodes: Dict[str, Node] = {}
        self._load_nodes()
    
    def _ensure_directories(self):
        """确保所有目录存在"""
        for dir_path in [
            self.base_dir, self.daily_dir, self.weekly_dir,
            self.monthly_dir, self.quarterly_dir, self.yearly_dir,
            self.nodes_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _load_nodes(self):
        """加载所有节点"""
        for node_file in self.nodes_dir.glob("*.json"):
            try:
                with open(node_file, "r", encoding=Encoding.UTF8) as f:
                    data = json.load(f)
                    node = Node(**data)
                    self._nodes[node.node_id] = node
            except Exception as e:
                logger.warning(f"加载节点失败 {node_file}: {e}")
        
        logger.info(f"[LifeBook] 已加载 {len(self._nodes)} 个节点")
    
    def _save_node(self, node: Node):
        """保存节点"""
        node_file = self.nodes_dir / f"{node.node_id}.json"
        with open(node_file, "w", encoding=Encoding.UTF8) as f:
            json.dump(node.__dict__, f, ensure_ascii=False, indent=2)
        
        self._nodes[node.node_id] = node
    
    def _entry_file(self, level: MemoryLevel, entry_id: str) -> Path:
        """获取条目文件路径"""
        level_dir = {
            MemoryLevel.DAILY: self.daily_dir,
            MemoryLevel.WEEKLY: self.weekly_dir,
            MemoryLevel.MONTHLY: self.monthly_dir,
            MemoryLevel.QUARTERLY: self.quarterly_dir,
            MemoryLevel.YEARLY: self.yearly_dir,
        }[level]
        
        return level_dir / f"{entry_id}.md"
    
    # ========== 节点管理 ==========
    
    def create_node(
        self,
        name: str,
        node_type: NodeType,
        tags: List[str] = None,
        description: str = "",
        related_nodes: List[str] = None,
    ) -> Node:
        """创建节点
        
        Args:
            name: 节点名称
            node_type: 节点类型
            tags: 标签
            description: 描述
            related_nodes: 关联节点ID
        
        Returns:
            创建的节点
        """
        node_id = f"{name}-{datetime.now().strftime('%Y-%m-%d')}"
        created_at = datetime.now().strftime("%Y-%m-%d")
        
        node = Node(
            node_id=node_id,
            name=name,
            node_type=node_type,
            tags=tags or [],
            description=description,
            created_at=created_at,
            related_nodes=related_nodes or [],
        )
        
        self._save_node(node)
        logger.info(f"[LifeBook] 创建节点: {node_id}")
        
        return node
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """获取节点"""
        return self._nodes.get(node_id)
    
    def list_nodes(
        self,
        node_type: Optional[NodeType] = None,
        tags: List[str] = None,
    ) -> List[Node]:
        """列出节点
        
        Args:
            node_type: 节点类型过滤
            tags: 标签过滤
        
        Returns:
            节点列表
        """
        nodes = list(self._nodes.values())
        
        if node_type:
            nodes = [n for n in nodes if n.node_type == node_type]
        
        if tags:
            nodes = [
                n for n in nodes
                if any(tag in n.tags for tag in tags)
            ]
        
        return nodes
    
    def update_node(
        self,
        node_id: str,
        **kwargs
    ) -> Optional[Node]:
        """更新节点"""
        node = self._nodes.get(node_id)
        if not node:
            return None
        
        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)
        
        self._save_node(node)
        return node
    
    # ========== 记忆条目管理 ==========
    
    def add_entry(
        self,
        level: MemoryLevel,
        title: str,
        content: str,
        tags: List[str] = None,
        mood: str = None,
        capsule: str = None,
        related_nodes: List[str] = None,
    ) -> MemoryEntry:
        """添加记忆条目
        
        Args:
            level: 记忆层级
            title: 标题
            content: 内容
            tags: 标签
            mood: 心情
            capsule: 胶囊摘要（给上层的摘要）
            related_nodes: 关联节点ID
        
        Returns:
            创建的记忆条目
        """
        now = datetime.now()
        entry_id = self._generate_entry_id(level, now)
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        
        entry = MemoryEntry(
            entry_id=entry_id,
            level=level,
            title=title,
            content=content,
            created_at=created_at,
            updated_at=created_at,
            tags=tags or [],
            mood=mood,
            capsule=capsule,
            related_nodes=related_nodes or [],
        )
        
        self._save_entry(entry)
        return entry
    
    def _generate_entry_id(self, level: MemoryLevel, date: datetime) -> str:
        """生成条目ID"""
        if level == MemoryLevel.DAILY:
            return date.strftime("%Y-%m-%d")
        elif level == MemoryLevel.WEEKLY:
            year = date.year
            week_num = date.isocalendar()[1]
            return f"{year}-W{week_num:02d}"
        elif level == MemoryLevel.MONTHLY:
            return date.strftime("%Y-%m")
        elif level == MemoryLevel.QUARTERLY:
            quarter = (date.month - 1) // 3 + 1
            return f"{date.year}-Q{quarter}"
        elif level == MemoryLevel.YEARLY:
            return str(date.year)
        else:
            return date.strftime("%Y%m%d%H%M%S")
    
    def _save_entry(self, entry: MemoryEntry):
        """保存记忆条目"""
        file_path = self._entry_file(entry.level, entry.entry_id)
        
        # Markdown 格式
        lines = [
            f"# {entry.title}",
            "",
            f"**时间:** {entry.created_at}",
            f"**层级:** {entry.level.value}",
        ]
        
        if entry.mood:
            lines.append(f"**心情:** {entry.mood}")
        
        if entry.tags:
            lines.append(f"**标签:** {' '.join(f'#{tag}' for tag in entry.tags)}")
        
        if entry.capsule:
            lines.append("")
            lines.append(f"> {entry.capsule}")
        
        lines.append("")
        lines.append(entry.content)
        
        # 关联节点
        if entry.related_nodes:
            lines.append("")
            lines.append("---")
            lines.append("## 关联节点")
            for node_id in entry.related_nodes:
                node = self._nodes.get(node_id)
                node_name = node.name if node else node_id
                lines.append(f"- [[{node_name}]]")
        
        with open(file_path, "w", encoding=Encoding.UTF8) as f:
            f.write("\n".join(lines))
        
        logger.info(f"[LifeBook] 保存记忆条目: {entry.entry_id} ({entry.level.value})")
    
    def get_entry(self, level: MemoryLevel, entry_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        file_path = self._entry_file(level, entry_id)
        if not file_path.exists():
            return None
        
        return self._parse_entry_file(file_path, level, entry_id)
    
    def _parse_entry_file(
        self,
        file_path: Path,
        level: MemoryLevel,
        entry_id: str
    ) -> Optional[MemoryEntry]:
        """解析记忆条目文件"""
        try:
            with open(file_path, "r", encoding=Encoding.UTF8) as f:
                content = f.read()
            
            # 提取元数据
            title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else entry_id
            
            time_match = re.search(r"^\*\*时间:\*\* (.+)$", content, re.MULTILINE)
            created_at = time_match.group(1) if time_match else ""
            
            mood_match = re.search(r"^\*\*心情:\*\* (.+)$", content, re.MULTILINE)
            mood = mood_match.group(1) if mood_match else None
            
            tags_match = re.search(r"^\*\*标签:\*\* (.+)$", content, re.MULTILINE)
            tags = []
            if tags_match:
                tags_str = tags_match.group(1)
                tags = [t.strip("#") for t in tags_str.split() if t.startswith("#")]
            
            # 提取胶囊
            capsule_match = re.search(r"^> (.+)$", content, re.MULTILINE)
            capsule = capsule_match.group(1) if capsule_match else None
            
            # 提取正文内容（去除元数据）
            body_match = re.search(r"^---$(.+)", content, re.MULTILINE | re.DOTALL)
            if body_match:
                body = body_match.group(1).strip()
            else:
                body = content
            
            # 提取关联节点
            related_nodes = []
            node_matches = re.findall(r"\[\[(.+?)\]\]", content)
            for node_name in node_matches:
                # 查找对应的节点ID
                for node_id, node in self._nodes.items():
                    if node.name == node_name:
                        related_nodes.append(node_id)
                        break
            
            return MemoryEntry(
                entry_id=entry_id,
                level=level,
                title=title,
                content=body,
                created_at=created_at,
                updated_at=created_at,
                tags=tags,
                mood=mood,
                capsule=capsule,
                related_nodes=related_nodes,
            )
        
        except Exception as e:
            logger.error(f"解析记忆条目失败 {file_path}: {e}")
            return None
    
    # ========== 时间滚动记忆回溯 ==========
    
    async def get_core_context(
        self,
        months_back: int = 1,
        include_nodes: bool = True,
    ) -> str:
        """一键获取核心上下文
        
        Args:
            months_back: 回溯月数
            include_nodes: 是否包含节点信息
        
        Returns:
            核心上下文文本
        """
        now = datetime.now()
        context_parts = []
        
        # 1. 年度总结（长期记忆）
        if months_back >= 12:
            yearly_entry = self._get_recent_entry(MemoryLevel.YEARLY, 1)
            if yearly_entry:
                context_parts.append(f"## 年度总结\n\n{yearly_entry.capsule or yearly_entry.title}")
        
        # 2. 季度总结
        if months_back >= 3:
            quarterly_entry = self._get_recent_entry(MemoryLevel.QUARTERLY, 1)
            if quarterly_entry:
                context_parts.append(f"## 季度总结\n\n{quarterly_entry.capsule or quarterly_entry.title}")
        
        # 3. 月度总结（中期记忆）
        for i in range(months_back):
            date = now - timedelta(days=30 * i)
            entry_id = date.strftime("%Y-%m")
            monthly_entry = self.get_entry(MemoryLevel.MONTHLY, entry_id)
            if monthly_entry:
                context_parts.append(f"## {monthly_entry.title}\n\n{monthly_entry.capsule or monthly_entry.content[:500]}")
        
        # 4. 周度总结（短期记忆）
        for i in range(4):
            date = now - timedelta(weeks=i)
            entry_id = self._generate_entry_id(MemoryLevel.WEEKLY, date)
            weekly_entry = self.get_entry(MemoryLevel.WEEKLY, entry_id)
            if weekly_entry:
                context_parts.append(f"## {weekly_entry.title}\n\n{weekly_entry.capsule or weekly_entry.content[:300]}")
        
        # 5. 最近日记
        for i in range(3):
            date = now - timedelta(days=i)
            entry_id = date.strftime("%Y-%m-%d")
            daily_entry = self.get_entry(MemoryLevel.DAILY, entry_id)
            if daily_entry:
                context_parts.append(f"## {daily_entry.title}\n\n{daily_entry.content[:200]}")
        
        # 6. 节点信息
        if include_nodes and self._nodes:
            context_parts.append("## 关键人物与阶段\n")
            for node in self._nodes.values():
                context_parts.append(f"- {node.name} ({node.node_type.value}): {node.description}")
        
        if context_parts:
            return "\n\n---\n\n".join(context_parts)
        else:
            return "暂无记忆记录"
    
    def _get_recent_entry(
        self,
        level: MemoryLevel,
        limit: int = 1,
    ) -> Optional[MemoryEntry]:
        """获取最近的记忆条目"""
        level_dir = {
            MemoryLevel.DAILY: self.daily_dir,
            MemoryLevel.WEEKLY: self.weekly_dir,
            MemoryLevel.MONTHLY: self.monthly_dir,
            MemoryLevel.QUARTERLY: self.quarterly_dir,
            MemoryLevel.YEARLY: self.yearly_dir,
        }[level]
        
        files = sorted(level_dir.glob("*.md"), reverse=True)
        
        for i, file_path in enumerate(files):
            if i >= limit:
                break
            entry_id = file_path.stem
            entry = self.get_entry(level, entry_id)
            if entry:
                return entry
        
        return None
    
    # ========== AI 自动总结 ==========
    
    async def generate_weekly_summary(
        self,
        start_date: Optional[datetime] = None,
    ) -> Optional[str]:
        """生成周度总结
        
        Args:
            start_date: 起始日期（默认为一周前）
        
        Returns:
            生成的周记内容
        """
        if not self.ai_client:
            logger.warning("[LifeBook] 未配置 AI 客户端，无法自动总结")
            return None
        
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        
        # 收集一周的日记
        daily_entries = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            entry_id = date.strftime("%Y-%m-%d")
            entry = self.get_entry(MemoryLevel.DAILY, entry_id)
            if entry:
                daily_entries.append(entry)
        
        if not daily_entries:
            return None
        
        # 构建提示词
        diaries_text = "\n\n".join([
            f"## {entry.title}\n{entry.content}"
            for entry in daily_entries
        ])
        
        prompt = f"""请基于以下日记，生成一周的总结，要求：
1. 提取本周的关键事件和情绪变化
2. 用一句话概括本周，作为"胶囊摘要"
3. 用温暖、理解的语言风格

日记内容：
{diaries_text}

请按以下格式输出：
## 标题
胶囊：一句话概括

## 本周回顾
[详细内容]
"""
        
        try:
            # 调用 AI 生成
            response = await self.ai_client.chat([{"role": "user", "content": prompt}])
            summary = response.get("content", "")
            
            # 保存周记
            week_num = start_date.isocalendar()[1]
            year = start_date.year
            entry_id = f"{year}-W{week_num:02d}"
            title = f"{year}年第{week_num}周总结"
            
            self.add_entry(
                level=MemoryLevel.WEEKLY,
                title=title,
                content=summary,
                capsule=self._extract_capsule(summary),
            )
            
            logger.info(f"[LifeBook] 生成周记: {entry_id}")
            return summary
        
        except Exception as e:
            logger.error(f"[LifeBook] 生成周记失败: {e}")
            return None
    
    def _extract_capsule(self, content: str) -> str:
        """从内容中提取胶囊摘要"""
        match = re.search(r"胶囊[:：]\s*(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""
    
    # ========== 搜索功能 ==========
    
    def search_entries(
        self,
        keyword: str,
        level: Optional[MemoryLevel] = None,
        tags: List[str] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """搜索记忆条目
        
        Args:
            keyword: 关键词
            level: 层级过滤
            tags: 标签过滤
            limit: 限制数量
        
        Returns:
            匹配的记忆条目列表
        """
        results = []
        
        # 确定搜索目录
        if level:
            level_dirs = {level}
        else:
            level_dirs = {
                MemoryLevel.DAILY, MemoryLevel.WEEKLY, MemoryLevel.MONTHLY,
                MemoryLevel.QUARTERLY, MemoryLevel.YEARLY,
            }
        
        for lv in level_dirs:
            level_dir = {
                MemoryLevel.DAILY: self.daily_dir,
                MemoryLevel.WEEKLY: self.weekly_dir,
                MemoryLevel.MONTHLY: self.monthly_dir,
                MemoryLevel.QUARTERLY: self.quarterly_dir,
                MemoryLevel.YEARLY: self.yearly_dir,
            }[lv]
            
            for file_path in level_dir.glob("*.md"):
                try:
                    entry = self._parse_entry_file(
                        file_path,
                        lv,
                        file_path.stem
                    )
                    if not entry:
                        continue
                    
                    # 关键词匹配
                    if keyword.lower() not in entry.content.lower() and \
                       keyword.lower() not in entry.title.lower():
                        continue
                    
                    # 标签匹配
                    if tags:
                        if not any(tag in entry.tags for tag in tags):
                            continue
                    
                    results.append(entry)
                    
                    if len(results) >= limit:
                        return results
                
                except Exception as e:
                    logger.warning(f"搜索失败 {file_path}: {e}")
        
        return results


# 导入 Enum
from enum import Enum
from core.constants import Encoding
