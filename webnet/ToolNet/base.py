"""
工具系统基础类

提供统一的基础类和接口，兼容旧版代码。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def resolve_platform_adapter(context: Any = None) -> Any:
    """解析工具执行时的平台适配器引用。

    优先从 context.platform_adapter 取，其次从全局 platform_context 取。
    返回 None 表示当前无平台上下文（如后台定时任务）。
    """
    adapter = getattr(context, "platform_adapter", None) if context is not None else None
    if adapter:
        return adapter
    try:
        from core.platform_context import get_current_platform_adapter

        return get_current_platform_adapter()
    except Exception:
        return None


@dataclass
class ToolContext:
    """工具执行上下文"""

    # OneBot 相关
    qq_net: Optional[Any] = None  # QQNet 实例
    onebot_client: Optional[Any] = None  # OneBot 客户端
    send_like_callback: Optional[Any] = None  # 点赞回调函数

    # 弥娅核心
    memory_engine: Optional[Any] = None  # 记忆引擎（兼容）
    unified_memory: Optional[Any] = None  # 统一记忆接口（新）
    memory_net: Optional[Any] = None  # MemoryNet 记忆系统
    emotion: Optional[Any] = None  # 情绪系统
    personality: Optional[Any] = None  # 人格系统
    scheduler: Optional[Any] = None  # 调度器
    lifenet: Optional[Any] = None  # LifeNet 记忆管理网络
    game_mode_adapter: Optional[Any] = None  # 游戏模式适配器

    # 运行时信息
    request_id: Optional[str] = None  # 请求ID
    group_id: Optional[int] = None  # 群号
    user_id: Optional[int] = None  # 用户ID
    message_type: Optional[str] = None  # 消息类型 (group/private)
    sender_name: Optional[str] = None  # 发送者名称
    is_at_bot: bool = False  # 是否@机器人
    at_list: list = field(default_factory=list)  # 消息中@的用户ID列表

    # 工具内部使用
    message_sent_this_turn: bool = field(default=False, init=False)

    # QQ 相关
    bot_qq: Optional[int] = None
    superadmin: Optional[int] = None  # 超级管理员 QQ

    # 图片数据（用于图片分析工具）
    image_data: Optional[bytes] = None  # 原始图片数据
    image_analysis: Optional[Dict] = None  # 图片分析结果

    # 平台适配器（用于跨平台文件发送等）
    platform_adapter: Optional[Any] = None  # 当前平台适配器实例

    # 平台原始用户 ID（未被规范化的，用于各平台 API 调用）
    platform_user_id: Optional[str] = None


class ToolRegistry:
    """工具注册表（兼容层）"""

    def __init__(self):
        """初始化工具注册表"""
        self.tools: Dict[str, Any] = {}
        self.logger = logging.getLogger("ToolRegistry")

    def register(self, name: str, tool: Any):
        """注册工具"""
        self.tools[name] = tool
        self.logger.debug(f"工具已注册: {name}")

    def get(self, name: str) -> Optional[Any]:
        """获取工具"""
        return self.tools.get(name)

    async def execute(self, name: str, context: ToolContext, **kwargs) -> Any:
        """执行工具"""
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"工具不存在: {name}")
        return await tool(context, **kwargs)


class BaseTool:
    """工具基类（兼容层）"""

    def __init__(self, name: str = None, description: str = ""):
        """
        初始化工具

        Args:
            name: 工具名称（兼容旧版，如果未提供则从 config 读取）
            description: 工具描述
        """
        if name is not None:
            self.name = name
            self.description = description
        else:
            # 兼容旧版：从 config 属性读取
            if hasattr(self, "config") and isinstance(self.config, property):
                config = self.config.fget(self)
                self.name = config.get("name", self.__class__.__name__)
                self.description = config.get("description", "")
            else:
                self.name = self.__class__.__name__
                self.description = description
        self.logger = logging.getLogger(f"Tool.{self.name}")

    async def execute(self, args: Dict, context: ToolContext) -> Any:
        """
        执行工具（子类必须实现）

        统一签名约定：execute(self, args: Dict, context: ToolContext) -> str
        所有工具一律使用此签名，不再混用 (context, **kwargs) 旧签名。

        Args:
            args: 工具参数字典
            context: 工具执行上下文

        Returns:
            执行结果
        """
        raise NotImplementedError(f"工具 {self.name} 必须实现 execute 方法")

    def __call__(self, context: ToolContext, **kwargs) -> Any:
        """
        工具调用接口（支持同步调用）

        Args:
            context: 工具上下文
            **kwargs: 其他参数

        Returns:
            执行结果
        """
        if asyncio.iscoroutinefunction(self.execute):
            # 如果是异步方法，需要在事件循环中运行
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，返回协程
                    return self.execute(context, **kwargs)
                else:
                    # 如果事件循环没有运行，直接运行
                    return loop.run_until_complete(self.execute(context, **kwargs))
            except RuntimeError:
                # 创建新的事件循环
                return asyncio.run(self.execute(context, **kwargs))
        else:
            # 同步方法直接调用
            return self.execute(context, **kwargs)


def tool(name: str, description: str = ""):
    """
    工具装饰器

    Args:
        name: 工具名称
        description: 工具描述

    Returns:
        装饰器函数
    """

    def decorator(func):
        """装饰器"""

        class DecoratedTool(BaseTool):
            def __init__(self):
                super().__init__(name, description)

            async def execute(self, context: ToolContext, **kwargs) -> Any:
                return await func(context, **kwargs)

        DecoratedTool.__name__ = func.__name__
        return DecoratedTool()

    return decorator
