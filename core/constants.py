"""
弥娅系统统一常量定义

提供系统级别的常量定义，避免分散在各个模块中重复定义。
包括：日志级别、HTTP状态码、时间常量、游戏模式常量等。
"""
from enum import Enum


# ========== 日志级别 ==========
class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ========== HTTP 状态码 ==========
class HTTPStatus(int, Enum):
    """HTTP 状态码"""
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204

    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409

    INTERNAL_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


# ========== 时间常量（秒）==========
class TimeConstants:
    """时间常量（单位：秒）"""
    SECOND = 1
    MINUTE = 60
    HOUR = 60 * 60
    DAY = 24 * 60 * 60
    WEEK = 7 * 24 * 60 * 60
    MONTH = 30 * 24 * 60 * 60  # 近似值
    YEAR = 365 * 24 * 60 * 60  # 近似值


# ========== 游戏模式常量 ==========
class GameModeType(str, Enum):
    """游戏模式类型"""
    TRPG = "trpg"
    TAVERN = "tavern"
    CUSTOM = "custom"


class GameState(str, Enum):
    """游戏状态"""
    LOADING = "loading"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ========== 工具执行状态 ==========
class ToolExecutionStatus(str, Enum):
    """工具执行状态"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ========== 记忆类型 ==========
class MemoryType(str, Enum):
    """记忆类型"""
    CONVERSATION = "conversation"
    UNDEFINED = "undefined"
    TIDE = "tide"
    DREAM = "dream"
    GAME = "game"
    PROFILE = "profile"
    EVENT = "event"


# ========== 消息类型 ==========
class MessageType(str, Enum):
    """消息类型"""
    GROUP = "group"
    PRIVATE = "private"
    SYSTEM = "system"


# ========== 用户角色 ==========
class UserRole(str, Enum):
    """用户角色"""
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


# ========== 子网状态 ==========
class SubnetState(str, Enum):
    """子网状态"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


# ========== 工具权限 ==========
class ToolPermission(str, Enum):
    """工具权限"""
    PUBLIC = "public"  # 所有人可用
    ADMIN = "admin"    # 仅管理员
    SUPERADMIN = "superadmin"  # 仅超级管理员


# ========== 缓存过期时间（秒）==========
class CacheTTL:
    """缓存过期时间"""
    SHORT = 300          # 5分钟
    MEDIUM = 3600        # 1小时
    LONG = 86400         # 1天
    VERY_LONG = 604800   # 1周


# ========== 数据库配置常量 ==========
class DatabaseConfig:
    """数据库配置常量"""
    # Redis
    REDIS_DEFAULT_PORT = 6379
    REDIS_DEFAULT_DB = 0

    # Milvus
    MILVUS_DEFAULT_PORT = 19530
    MILVUS_DEFAULT_INDEX_TYPE = "IVF_FLAT"

    # Neo4j
    NEO4J_DEFAULT_PORT = 7687
    NEO4J_DEFAULT_HTTP_PORT = 7474

    # ChromaDB
    CHROMADB_DEFAULT_PORT = 8000


# ========== 性能限制常量 ==========
class PerformanceLimits:
    """性能限制常量"""
    # 工具执行
    TOOL_TIMEOUT = 480  # 工具执行超时时间（秒）
    TOOL_MAX_RETRIES = 3  # 工具最大重试次数

    # 内存
    MAX_MEMORY_MB = 512  # 最大内存使用（MB）

    # 并发
    MAX_CONCURRENT_TASKS = 10  # 最大并发任务数

    # 消息处理
    MAX_MESSAGE_LENGTH = 10000  # 最大消息长度
    MAX_HISTORY_LENGTH = 50    # 最大历史记录长度


# ========== 错误码 ==========
class ErrorCode:
    """错误码定义"""
    # 工具错误 (1000-1999)
    TOOL_NOT_FOUND = 1001
    TOOL_EXECUTION_FAILED = 1002
    TOOL_TIMEOUT = 1003
    TOOL_INVALID_PARAMS = 1004

    # 记忆错误 (2000-2999)
    MEMORY_NOT_FOUND = 2001
    MEMORY_SAVE_FAILED = 2002
    MEMORY_SEARCH_FAILED = 2003

    # 游戏错误 (3000-3999)
    GAME_NOT_FOUND = 3001
    GAME_ALREADY_EXISTS = 3002
    GAME_INVALID_STATE = 3003
    GAME_SAVE_FAILED = 3004

    # 权限错误 (4000-4999)
    PERMISSION_DENIED = 4001
    USER_NOT_FOUND = 4002

    # 系统错误 (5000-5999)
    INTERNAL_ERROR = 5001
    SERVICE_UNAVAILABLE = 5002


# ========== 常用字符串常量 ==========
class CommonStrings:
    """常用字符串常量"""
    SUCCESS_PREFIX = "✅"
    ERROR_PREFIX = "❌"
    WARNING_PREFIX = "⚠️"
    INFO_PREFIX = "ℹ️"

    EMPTY_RESPONSE = ""
    UNKNOWN_ERROR = "未知错误"


# 特殊字符
SPECIAL_CHARS = {
    'at_bot': '@',
    'ellipsis': '…',
    'separator': '|',
}


# ========== 文件路径常量 ==========
class FilePath:
    """文件路径常量"""
    DATA_DIR = "data"
    LOGS_DIR = "logs"
    CONFIG_DIR = "config"
    PLUGINS_DIR = "plugin"
    TOOLS_DIR = "webnet"

    # 记忆数据
    MEMORY_DATA_DIR = f"{DATA_DIR}/memory_data"
    GAME_MEMORY_DIR = f"{DATA_DIR}/game_memory"

    # 配置文件
    ENV_FILE = f"{CONFIG_DIR}/.env"
    ENV_EXAMPLE_FILE = f"{CONFIG_DIR}/.env.example"


# ========== 编码常量 ==========
class Encoding:
    """编码常量"""
    UTF8 = "utf-8"


# ========== 网络超时常量 ==========
class NetworkTimeout:
    """网络超时常量"""
    # WebSocket
    WEBSOCKET_PING_INTERVAL = 20
    WEBSOCKET_PING_TIMEOUT = 480

    # API请求
    API_REQUEST_TIMEOUT = 30

    # Redis
    REDIS_CONNECT_TIMEOUT = 5

    # 记忆系统
    MEMORY_SEARCH_TIMEOUT = 30
    MEMORY_QUICK_SEARCH_TIMEOUT = 15
    QUINTUPLE_BASE_TIMEOUT = 600
    QUINTUPLE_RETRY_INCREMENT = 20

    # MLink
    MLINK_DEFAULT_TIMEOUT = 30
    MLINK_SHORT_TIMEOUT = 10

    # 其他
    AI_REQUEST_INTERVAL = 1.0
    HEARTBEAT_INTERVAL = 30


# ========== 限制常量 ==========
class Limits:
    """限制常量"""
    # 消息长度
    QQ_MAX_MESSAGE_LENGTH = 200
    QQ_MAX_API_COUNT = 500
    WEBSOCKET_MAX_MESSAGE_SIZE = 100 * 1024 * 1024  # 100MB

    # 历史记录
    CONVERSATION_MAX_MESSAGES_PER_SESSION = 200
    PERSONALITY_RESPONSE_HISTORY = 20
    TOOL_MONITOR_HISTORY_SIZE = 1000

    # 记忆系统
    COGNITIVE_MEMORY_MAX_SHORT_TERM = 20
    PROMPT_MEMORY_CONTEXT_COUNT = 5

    # 其他
    TOKEN_LIMIT_GAME_MODE = 100000
    TOKEN_LIMIT_HUB = 80000
    PERSONALITY_MAX_ADJUSTMENT = 0.05


# ========== 服务端口 ==========
class ServicePorts:
    """服务端口常量"""
    PC_UI_SERVER = 8888


# ========== 重试配置 ==========
class RetryConfig:
    """重试配置常量"""
    DEFAULT_MAX_RETRIES = 2
    TOOL_MAX_RETRIES = 3


# ========== 导出常量 ==========
__all__ = [
    # 日志级别
    'LogLevel',

    # HTTP 状态码
    'HTTPStatus',

    # 时间常量
    'TimeConstants',

    # 游戏模式
    'GameModeType',
    'GameState',

    # 工具执行
    'ToolExecutionStatus',

    # 记忆类型
    'MemoryType',

    # 消息类型
    'MessageType',

    # 用户角色
    'UserRole',

    # 子网状态
    'SubnetState',

    # 工具权限
    'ToolPermission',

    # 缓存
    'CacheTTL',

    # 数据库
    'DatabaseConfig',

    # 性能限制
    'PerformanceLimits',

    # 错误码
    'ErrorCode',

    # 常用字符串
    'CommonStrings',
    'SPECIAL_CHARS',

    # 文件路径
    'FilePath',

    # 编码
    'Encoding',

    # 网络超时
    'NetworkTimeout',

    # 限制
    'Limits',

    # 服务端口
    'ServicePorts',

    # 重试配置
    'RetryConfig',
]
