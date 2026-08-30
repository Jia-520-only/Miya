"""
弥娅统一记忆系统 — 数据模型定义

包含枚举、MemoryItem、MemoryQuery、MemoryBackend 基类。
从 core.py (V3.1) 拆分，减少单文件体积。
"""

import hashlib
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Encoding:
    UTF8 = "utf-8"


# ==================== 枚举定义 ====================


class MemoryLevel(Enum):
    """记忆层级"""

    DIALOGUE = "dialogue"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    KNOWLEDGE = "knowledge"
    PINNED = "pinned"


class MemoryPriority(Enum):
    """记忆优先级"""

    LOW = 0.3
    NORMAL = 0.5
    HIGH = 0.7
    CRITICAL = 0.9


class MemorySource(Enum):
    """记忆来源"""

    DIALOGUE = "dialogue"  # 对话中自动存储
    AUTO_EXTRACT = "auto_extract"  # 自动提取
    MANUAL = "manual"  # 手动添加
    SYSTEM = "system"  # 系统生成
    IMPORTED = "imported"  # 导入
    ASSISTANT_SELF = "assistant_self"  # 弥娅自记忆（承诺、观点、建议等）


# ==================== 核心数据结构 ====================


@dataclass
class MemoryItem:
    """
    统一记忆数据项 - 整个系统的唯一数据结构

    所有记忆都是这个格式，没有任何例外！
    """

    # 唯一标识
    id: str = ""

    # 内容
    content: str = ""

    # 层级
    level: MemoryLevel = MemoryLevel.SHORT_TERM

    # 优先级
    priority: float = 0.5

    # 标签
    tags: List[str] = field(default_factory=list)

    # 用户关联
    user_id: str = "global"
    session_id: str = ""
    group_id: str = ""
    platform: str = "unknown"

    # 来源
    source: MemorySource = MemorySource.SYSTEM
    role: str = ""  # user/assistant

    # 对话详情
    event_type: str = ""  # 对话事件类型 (如"工作会议", "日常聊天", "学习讨论")
    location: str = ""  # 对话地点 (如"办公室", "咖啡馆", "线上")
    conversation_partner: str = ""  # 明确的对话对象
    emotional_tone: str = ""  # 情感基调 (如"愉快", "焦虑", "中性", "兴奋")
    significance: float = 0.5  # 主观重要性评分 (0-1)

    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None

    # 向量 (语义层)
    vector: Optional[List[float]] = None

    # 知识图谱 (图谱层)
    subject: str = ""
    predicate: str = ""
    obj: str = ""

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 访问统计
    access_count: int = 0
    last_accessed: Optional[str] = None

    # 状态
    is_pinned: bool = False  # 置顶
    is_archived: bool = False  # 归档

    def __post_init__(self):
        """初始化后处理"""
        if not self.id:
            self.id = self._generate_id()

        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def _generate_id(self) -> str:
        """生成唯一ID"""
        unique_str = f"{self.content}{self.user_id}{datetime.now().isoformat()}{uuid.uuid4().hex[:8]}"
        return hashlib.md5(unique_str.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data["level"] = self.level.value if isinstance(self.level, MemoryLevel) else self.level
        data["source"] = self.source.value if isinstance(self.source, MemorySource) else self.source
        if "metadata" in data and isinstance(data["metadata"], dict):
            data["metadata"] = self._serialize_dict(data["metadata"])
        return data

    def _serialize_dict(self, d: Dict) -> Dict:
        """递归序列化字典中的枚举"""
        result = {}
        for k, v in d.items():
            if isinstance(v, Enum):
                result[k] = v.value
            elif isinstance(v, dict):
                result[k] = self._serialize_dict(v)
            elif isinstance(v, list):
                result[k] = [self._serialize_value(item) for item in v]
            else:
                result[k] = v
        return result

    def _serialize_value(self, v):
        """序列化单个值"""
        if isinstance(v, Enum):
            return v.value
        elif isinstance(v, dict):
            return self._serialize_dict(v)
        elif isinstance(v, list):
            return [self._serialize_value(item) for item in v]
        return v

    @classmethod
    def from_dict(cls, data: Dict) -> Optional["MemoryItem"]:
        """从字典创建"""
        if not data:
            return None

        data = data.copy()

        if isinstance(data.get("level"), str):
            data["level"] = MemoryLevel(data["level"])
        if isinstance(data.get("source"), str):
            data["source"] = MemorySource(data["source"])

        data = {k: v for k, v in data.items() if v is not None}
        valid_fields = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**data)

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.level != MemoryLevel.SHORT_TERM:
            return False
        if not self.expires_at:
            return False
        try:
            return datetime.now() > datetime.fromisoformat(self.expires_at)
        except (ValueError, TypeError):
            return False

    def is_valid(self) -> bool:
        """检查是否有效"""
        if self.is_expired():
            return False
        if self.is_archived:
            return False
        return not (not self.content or len(self.content.strip()) < 1)

    def update_access(self):
        """更新访问统计"""
        if self.access_count is None:
            self.access_count = 0
        self.access_count += 1
        self.last_accessed = datetime.now().isoformat()

    def clone(self) -> "MemoryItem":
        """克隆记忆"""
        cloned = MemoryItem.from_dict(self.to_dict())
        if cloned is None:
            raise RuntimeError("Failed to clone memory item")
        return cloned


@dataclass
class MemoryQuery:
    """记忆查询条件"""

    # 文本搜索
    query: str = ""

    # 用户过滤
    user_id: Optional[str] = None
    # 多身份等价过滤（跨平台别名展开后使用，优先级高于 user_id）
    user_ids: Optional[List[str]] = None
    session_id: Optional[str] = None
    group_id: Optional[str] = None
    platform: Optional[str] = None

    # 层级过滤
    level: Optional[MemoryLevel] = None
    levels: Optional[List[MemoryLevel]] = None

    # 标签过滤
    tags: Optional[List[str]] = None
    any_tag: bool = False  # True: 任一匹配, False: 全部匹配

    # 优先级过滤
    priority: Optional[float] = None
    min_priority: float = 0.0
    max_priority: float = 1.0

    # 来源过滤
    source: Optional[MemorySource] = None

    # 时间过滤
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # 状态过滤
    include_archived: bool = False
    include_expired: bool = False
    is_pinned: Optional[bool] = None

    # 对话详情过滤
    event_type: Optional[str] = None
    location: Optional[str] = None
    conversation_partner: Optional[str] = None
    emotional_tone: Optional[str] = None
    min_significance: float = 0.0
    max_significance: float = 1.0

    # 分页
    limit: int = 20
    offset: int = 0

    # 排序
    sort_by: str = "priority"  # priority, created_at, updated_at, access_count
    sort_order: str = "desc"  # asc, desc


# ==================== 存储后端接口 ====================


class MemoryBackend:
    """记忆存储后端基类"""

    async def save(self, memory: MemoryItem) -> bool:
        raise NotImplementedError

    async def load(self, memory_id: str) -> Optional[MemoryItem]:
        raise NotImplementedError

    async def delete(self, memory_id: str) -> bool:
        raise NotImplementedError

    async def query(self, query: MemoryQuery) -> List[MemoryItem]:
        raise NotImplementedError

    async def close(self):
        pass
