"""
Miya项目类型定义
统一项目中的所有类型定义，提高代码可维护性和类型安全性
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, NewType, Optional, TypedDict

# ==================== 基本类型别名 ====================
SessionID = NewType("SessionID", str)
MessageID = NewType("MessageID", str)
UserID = NewType("UserID", str)
TerminalType = Literal["cmd", "bash", "zsh", "powershell", "ssh"]


# ==================== 终端相关类型 ====================
class TerminalStatus(TypedDict):
    """终端状态信息"""

    id: SessionID
    name: str
    type: TerminalType
    status: Literal["running", "stopped", "error"]
    directory: str
    is_active: bool
    command_count: int
    output_count: int
    created_at: str
    last_activity: str


class CommandResult(TypedDict):
    """命令执行结果"""

    success: bool
    output: str
    error: str
    exit_code: int
    execution_time: float
    session_id: SessionID


# ==================== AI相关类型 ====================
@dataclass
class AIMessage:
    """AI消息"""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class AIRequest(TypedDict, total=False):
    """AI请求"""

    messages: list[AIMessage]
    model: str
    temperature: float
    max_tokens: Optional[int]
    top_p: Optional[float]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
    stream: bool


class AIResponse(TypedDict):
    """AI响应"""

    content: str
    usage: dict[str, int]
    finish_reason: str
    processing_time: float
    model: str


@dataclass
class AIConfig:
    """AI配置"""

    provider: Literal["openai", "claude", "deepseek", "zhipuai", "mock"]
    api_key: str
    model: str
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3


# ==================== 人格系统类型 ====================
class PersonalityForm(Enum):
    """人格形态"""

    NORMAL = "normal"
    BATTLE = "battle"
    MUSE = "muse"
    SINGER = "singer"
    GHOST = "ghost"


@dataclass
class PersonalityVector:
    """人格向量"""

    warmth: float = 0.85  # 温暖度 (0.0-1.0)
    logic: float = 0.75  # 逻辑性 (0.0-1.0)
    creativity: float = 0.8  # 创造力 (0.0-1.0)
    empathy: float = 0.9  # 同理心 (0.0-1.0)
    resilience: float = 0.8  # 韧性 (0.0-1.0)


# ==================== 记忆系统类型 ====================
class MemoryType(Enum):
    """记忆类型"""

    TIDE = "tide"  # 短期记忆
    COGNITIVE_SHORT = "cognitive_short"  # 认知短期记忆
    COGNITIVE_PINNED = "cognitive_pinned"  # 置顶记忆
    LIFEBOOK = "lifebook"  # 长期记忆
    SEMANTIC = "semantic"  # 语义记忆


@dataclass
class MemoryRecord:
    """记忆记录"""

    id: str
    content: str
    memory_type: MemoryType
    created_at: datetime
    accessed_at: datetime
    metadata: dict[str, Any]
    importance: float = 0.5  # 重要性 (0.0-1.0)


# ==================== 配置相关类型 ====================
class DatabaseConfig(TypedDict, total=False):
    """数据库配置"""

    host: str
    port: int
    database: str
    username: Optional[str]
    password: Optional[str]
    pool_size: int


class TerminalConfig(TypedDict, total=False):
    """终端配置"""

    max_terminals: int
    default_type: TerminalType
    command_timeout: int
    auto_cleanup: bool
    max_history: int


class WebConfig(TypedDict, total=False):
    """Web配置"""

    host: str
    port: int
    debug: bool
    cors_origins: list[str]
    api_prefix: str


# ==================== 错误处理类型 ====================
class ErrorCode(Enum):
    """错误代码"""

    # AI相关错误
    AI_SERVICE_UNAVAILABLE = "AI_001"
    AI_RATE_LIMIT = "AI_002"
    AI_INVALID_RESPONSE = "AI_003"
    AI_CONFIG_ERROR = "AI_004"

    # 终端相关错误
    TERMINAL_NOT_FOUND = "TERM_001"
    TERMINAL_EXECUTION_FAILED = "TERM_002"
    TERMINAL_CREATION_FAILED = "TERM_003"
    TERMINAL_TIMEOUT = "TERM_004"

    # 配置相关错误
    CONFIG_NOT_FOUND = "CONF_001"
    CONFIG_INVALID = "CONF_002"
    CONFIG_ENCRYPTION_ERROR = "CONF_003"

    # 网络相关错误
    NETWORK_TIMEOUT = "NET_001"
    NETWORK_CONNECTION_ERROR = "NET_002"

    # 系统错误
    SYSTEM_ERROR = "SYS_001"
    PERMISSION_DENIED = "PERM_001"


@dataclass
class AppError(Exception):
    """应用错误基类"""

    code: ErrorCode
    message: str
    details: Optional[dict[str, Any]] = None
    original_error: Optional[Exception] = None

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        result = {
            "error": self.code.value,
            "message": self.message,
            "type": self.__class__.__name__,
            "timestamp": datetime.now().isoformat(),
        }

        if self.details:
            result["details"] = self.details

        if self.original_error:
            result["original_error"] = str(self.original_error)

        return result


# ==================== 事件系统类型 ====================
@dataclass
class Event:
    """事件基类"""

    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class TerminalEvent(Event):
    """终端事件"""

    session_id: SessionID
    terminal_type: TerminalType
    command: Optional[str] = None
    result: Optional[CommandResult] = None


class AIEvent(Event):
    """AI事件"""

    model: str
    request_tokens: int
    response_tokens: int
    processing_time: float


# ==================== API响应类型 ====================
class APIResponse(TypedDict):
    """API响应"""

    success: bool
    data: Optional[Any]
    error: Optional[dict[str, Any]]
    timestamp: str
    request_id: Optional[str]


class PaginatedResponse(APIResponse):
    """分页响应"""

    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== 实用类型工具 ====================
def validate_type(obj: Any, expected_type: type, context: str = "") -> bool:
    """
    验证对象类型

    Args:
        obj: 要验证的对象
        expected_type: 期望的类型
        context: 上下文信息，用于错误提示

    Returns:
        验证是否通过
    """
    if not isinstance(obj, expected_type):
        if context:
            raise TypeError(f"{context}: 期望 {expected_type}, 实际得到 {type(obj)}")
        else:
            raise TypeError(f"期望 {expected_type}, 实际得到 {type(obj)}")
    return True


def optional_type(value: Any, expected_type: type) -> bool:
    """验证可选类型（允许None）"""
    if value is None:
        return True
    return isinstance(value, expected_type)
