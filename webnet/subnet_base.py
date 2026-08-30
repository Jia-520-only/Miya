"""
弥娅子网基类（BaseSubnet）

定义统一的子网接口规范，确保所有子网实现一致性。
符合蛛网式分布式架构设计规范。
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.constants import LogLevel


logger = logging.getLogger(__name__)


@dataclass
class SubnetConfig:
    """子网配置基类"""
    subnet_name: str
    subnet_id: str
    version: str = "1.0.0"
    enabled: bool = True
    log_level: str = LogLevel.INFO

    # 核心组件引用
    onebot_client: Optional[Any] = None
    memory_engine: Optional[Any] = None
    cognitive_memory: Optional[Any] = None

    # 统计信息
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    last_call_time: Optional[datetime] = None


class BaseSubnet(ABC):
    """
    子网基类

    所有子网应继承此基类，实现统一的接口：
    - execute_tool: 执行工具
    - get_all_tools: 获取所有工具
    - get_stats: 获取统计信息
    - shutdown: 关闭子网
    - health_check: 健康检查
    """

    def __init__(self, config: Optional[SubnetConfig] = None):
        """初始化子网

        Args:
            config: 子网配置，如果未提供则使用默认配置
        """
        self.config = config or self._create_default_config()
        self.logger = logging.getLogger(self.config.subnet_name)

        # 工具存储
        self.tools: Dict[str, Any] = {}

        # 初始化工具
        self._init_tools()

        self.logger.info(
            f"{self.config.subnet_name} 子网已启动，已加载 {len(self.tools)} 个工具"
        )

    @abstractmethod
    def _create_default_config(self) -> SubnetConfig:
        """创建默认配置（子类必须实现）

        Returns:
            SubnetConfig 实例
        """
        pass

    @abstractmethod
    def _init_tools(self):
        """初始化工具（子类必须实现）

        子类应在此方法中加载所有工具并注册到 self.tools
        """
        pass

    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> str:
        """执行工具（子类必须实现）

        Args:
            tool_name: 工具名称
            args: 工具参数
            user_id: 用户ID
            group_id: 群号
            message_type: 消息类型 (group/private)
            sender_name: 发送者名称

        Returns:
            执行结果字符串
        """
        pass

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具信息（默认实现）

        子类可以重写此方法以提供自定义实现

        Returns:
            工具信息列表，每个元素包含：
            - name: 工具名称
            - config: 工具配置
            - subnet: 子网名称
        """
        return [
            {
                'name': name,
                'config': getattr(tool, 'config', {}),
                'subnet': self.config.subnet_name
            }
            for name, tool in self.tools.items()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取子网统计信息（默认实现）

        子类可以重写此方法以提供自定义实现

        Returns:
            统计信息字典，包含：
            - subnet_name: 子网名称
            - version: 版本号
            - total_tools: 工具总数
            - total_calls: 总调用次数
            - success_calls: 成功调用次数
            - failed_calls: 失败调用次数
            - success_rate: 成功率
            - last_call_time: 最后调用时间
        """
        success_rate = (
            self.config.success_calls / self.config.total_calls * 100
            if self.config.total_calls > 0
            else 0
        )

        return {
            'subnet_name': self.config.subnet_name,
            'version': self.config.version,
            'total_tools': len(self.tools),
            'total_calls': self.config.total_calls,
            'success_calls': self.config.success_calls,
            'failed_calls': self.config.failed_calls,
            'success_rate': f"{success_rate:.1f}%",
            'last_call_time': self.config.last_call_time
        }

    def health_check(self) -> bool:
        """健康检查（默认实现）

        子类可以重写此方法以提供自定义实现

        Returns:
            子网是否健康
        """
        return (
            self.config.enabled and
            len(self.tools) > 0
        )

    async def shutdown(self):
        """关闭子网（默认实现）

        子类可以重写此方法以提供自定义清理逻辑
        """
        self.logger.info(f"{self.config.subnet_name} 子网正在关闭...")
        self.tools.clear()
        self.logger.info(f"{self.config.subnet_name} 子网已关闭")

    def _record_success(self):
        """记录成功调用"""
        self.config.total_calls += 1
        self.config.success_calls += 1
        self.config.last_call_time = datetime.now()

    def _record_failure(self):
        """记录失败调用"""
        self.config.total_calls += 1
        self.config.failed_calls += 1
        self.config.last_call_time = datetime.now()


class ToolRegistrySubnet(BaseSubnet):
    """
    工具注册表子网（兼容旧实现）

    用于适配现有的基于 ToolRegistry 的子网实现
    """

    def __init__(self, tool_registry, config: Optional[SubnetConfig] = None):
        """初始化工具注册表子网

        Args:
            tool_registry: ToolRegistry 实例
            config: 子网配置
        """
        self.registry = tool_registry
        super().__init__(config)

    def _create_default_config(self) -> SubnetConfig:
        return SubnetConfig(
            subnet_name="ToolRegistrySubnet",
            subnet_id="subnet.tool_registry",
            version="1.0.0"
        )

    def _init_tools(self):
        """从 ToolRegistry 初始化工具"""
        self.tools = self.registry.tools

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> str:
        """执行工具"""
        from webnet.ToolNet.registry import ToolContext

        context = ToolContext(
            memory_engine=self.config.memory_engine,
            cognitive_memory=self.config.cognitive_memory,
            onebot_client=self.config.onebot_client,
            user_id=user_id,
            group_id=group_id,
            message_type=message_type,
            sender_name=sender_name
        )

        try:
            result = await self.registry.execute_tool(tool_name, args, context)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            self.logger.error(f"执行工具 {tool_name} 失败: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"
