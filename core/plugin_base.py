"""插件基础类 - 弥娅插件系统核心

提供统一的插件接口：
- 基础插件类
- 工具注册
- 生命周期管理
- 配置管理
- 错误处理
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    enabled: bool = True
    metadata: Dict[str, Any] = None


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    author: str
    description: str
    category: str
    capabilities: List[str] = None
    dependencies: List[str] = None
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.dependencies is None:
            self.dependencies = []
        if self.config is None:
            self.config = {}


class BasePlugin(ABC):
    """基础插件类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = True
        self._initialized = False

        # 工具注册表
        self._tools: Dict[str, ToolDefinition] = {}

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """插件元数据（必须由子类实现）"""
        pass

    async def initialize(self) -> bool:
        """初始化插件"""
        if self._initialized:
            return True

        try:
            logger.info(f"[Plugin] 初始化插件: {self.metadata.name} v{self.metadata.version}")

            # 注册工具
            await self.register_tools()

            self._initialized = True
            logger.info(f"[Plugin] 插件初始化成功: {self.metadata.name}")
            return True

        except Exception as e:
            logger.error(f"[Plugin] 插件初始化失败 {self.metadata.name}: {e}")
            return False

    async def cleanup(self):
        """清理插件资源"""
        try:
            logger.info(f"[Plugin] 清理插件: {self.metadata.name}")
            self._tools.clear()
            self._initialized = False
        except Exception as e:
            logger.error(f"[Plugin] 插件清理失败 {self.metadata.name}: {e}")

    # ==================== 工具管理 ====================

    @abstractmethod
    async def register_tools(self):
        """注册工具（必须由子类实现）"""
        pass

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """注册单个工具"""
        if name in self._tools:
            logger.warning(f"[Plugin] 工具已存在，将被覆盖: {name}")

        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
            handler=handler,
            metadata=metadata or {}
        )

        self._tools[name] = tool
        logger.debug(f"[Plugin] 注册工具: {name}")

    def unregister_tool(self, name: str):
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.debug(f"[Plugin] 注销工具: {name}")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(name)

    def get_all_tools(self) -> List[ToolDefinition]:
        """获取所有工具"""
        return list(self._tools.values())

    async def execute_tool(self, name: str, **kwargs) -> Any:
        """执行工具"""
        tool = self._tools.get(name)

        if not tool:
            raise Exception(f"工具不存在: {name}")

        if not tool.enabled:
            raise Exception(f"工具已禁用: {name}")

        if not self.enabled:
            raise Exception(f"插件已禁用: {self.metadata.name}")

        try:
            logger.debug(f"[Plugin] 执行工具: {name}")
            result = await tool.handler(**kwargs)
            return result
        except Exception as e:
            logger.error(f"[Plugin] 工具执行失败 {name}: {e}")
            raise

    # ==================== 配置管理 ====================

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        return self.config.get(key, default)

    def set_config(self, key: str, value: Any):
        """设置配置"""
        self.config[key] = value
        logger.debug(f"[Plugin] 更新配置: {key}")

    # ==================== 生命周期钩子 ====================

    async def on_enable(self):
        """插件启用时调用"""
        logger.debug(f"[Plugin] 插件启用: {self.metadata.name}")

    async def on_disable(self):
        """插件禁用时调用"""
        logger.debug(f"[Plugin] 插件禁用: {self.metadata.name}")

    async def on_config_change(self, old_config: Dict[str, Any], new_config: Dict[str, Any]):
        """配置变更时调用"""
        logger.debug(f"[Plugin] 配置变更: {self.metadata.name}")


class BaseAgentPlugin(BasePlugin):
    """Agent插件基类（继承自基础插件类）"""

    @property
    def category(self) -> str:
        """插件类别"""
        return "agent"

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """
        处理Agent交接（MCP协议）

        Args:
            tool_call: 工具调用参数

        Returns:
            JSON字符串格式的结果
        """
        try:
            tool_name = tool_call.get("tool_name", "")
            message = tool_call.get("message", "")

            # 执行工具
            result = await self.execute_tool(tool_name, message=message, **tool_call)

            # 格式化为JSON响应
            return self._format_result(result)

        except Exception as e:
            logger.error(f"[Plugin] Agent交接处理失败: {e}")
            return self._format_error(str(e))

    def _format_result(self, result: Any) -> str:
        """格式化成功结果"""
        import json
        return json.dumps({
            "status": "success",
            "result": result
        }, ensure_ascii=False)

    def _format_error(self, error: str) -> str:
        """格式化错误结果"""
        import json
        return json.dumps({
            "status": "error",
            "message": error
        }, ensure_ascii=False)
