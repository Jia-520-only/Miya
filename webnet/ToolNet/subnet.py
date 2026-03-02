"""
ToolNet 子网基类

符合弥娅子网架构规范
"""
import logging
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .registry import ToolRegistry, ToolContext
from .subnet_router import ToolSubnetRouter


logger = logging.getLogger(__name__)


@dataclass
class SubnetConfig:
    """子网配置"""
    subnet_name: str = "ToolNet"
    subnet_id: str = "subnet.toolnet"
    version: str = "2.0.0"
    enabled: bool = True
    log_level: str = "INFO"
    # 核心组件引用
    memory_engine: Any = None
    cognitive_memory: Any = None
    onebot_client: Any = None
    scheduler: Any = None
    # 统计信息
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    last_call_time: Optional[datetime] = None


class ToolSubnet:
    """
    ToolNet 子网（路由中心）

    弥娅工具子网，符合蛛网式分布式架构：
    - 通过工具注册表管理所有工具
    - 支持工具路由到不同业务子网
    - 提供统一的上下文管理
    - 支持工具统计和监控
    
    子网分类：
    - BasicNet: 基础工具 (3个)
    - MessageNet: 消息工具 (4个)
    - GroupNet: 群管理工具 (5个)
    - MemoryNet: 记忆工具 (4个)
    - KnowledgeNet: 知识工具 (3个)
    - EntertainmentNet: 娱乐工具 (5个)
    - BilibiliNet: B站工具 (1个)
    - SchedulerNet: 定时任务 (3个)
    - CognitiveNet: 认知工具 (3个)
    """

    def __init__(
        self,
        memory_engine: Any = None,
        cognitive_memory: Any = None,
        onebot_client: Any = None,
        scheduler: Any = None,
        config: Optional[SubnetConfig] = None
    ):
        """初始化子网

        Args:
            memory_engine: 记忆引擎实例
            cognitive_memory: 认知记忆系统实例
            onebot_client: OneBot 客户端
            scheduler: 任务调度器
            config: 子网配置
        """
        self.config = config or SubnetConfig(
            memory_engine=memory_engine,
            cognitive_memory=cognitive_memory,
            onebot_client=onebot_client,
            scheduler=scheduler
        )

        # 工具注册表
        self.registry = ToolRegistry()

        # 加载所有工具
        self.registry.load_all_tools()

        # 初始化路由器
        self.router = ToolSubnetRouter(self.registry)

        logger.info(f"ToolNet 子网已启动 (v{self.config.version})")
        logger.info(f"已注册 {len(self.registry.tools)} 个工具")
        logger.info(f"已初始化 {len(self.router.subnets)} 个业务子网")

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> str:
        """执行工具

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
        self.config.total_calls += 1

        # 创建执行上下文
        context = ToolContext(
            memory_engine=self.config.memory_engine,
            cognitive_memory=self.config.cognitive_memory,
            onebot_client=self.config.onebot_client,
            scheduler=self.config.scheduler,
            user_id=user_id,
            group_id=group_id,
            message_type=message_type,
            sender_name=sender_name
        )

        # 通过路由器执行
        result = await self.router.execute_tool(tool_name, args, context)

        # 更新统计
        subnet_name = self.router.get_subnet_for_tool(tool_name)
        if subnet_name:
            subnet_info = self.router.subnets[subnet_name]
            if "✅" in result or "📚" in result:
                subnet_info.success += 1
            else:
                subnet_info.failed += 1

        if "✅" not in result and "📚" not in result:
            self.config.failed_calls += 1
        else:
            self.config.success_calls += 1

        self.config.last_call_time = datetime.now()
        return result

    def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """按子网分组获取所有工具"""
        return self.router.get_all_tools_by_subnet()

    def get_subnet_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有子网统计信息"""
        return self.router.get_subnet_stats()

    def get_stats(self) -> Dict[str, Any]:
        """获取工具子网统计信息"""
        return {
            'subnet_name': self.config.subnet_name,
            'version': self.config.version,
            'total_tools': len(self.registry.tools),
            'total_subnets': len(self.router.subnets),
            'total_calls': self.config.total_calls,
            'success_calls': self.config.success_calls,
            'failed_calls': self.config.failed_calls,
            'success_rate': (
                self.config.success_calls / self.config.total_calls
                if self.config.total_calls > 0
                else 0
            ),
            'last_call_time': self.config.last_call_time,
            'subnets': self.get_subnet_stats()
        }

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> str:
        """执行工具

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
        self.config.total_calls += 1

        # 创建执行上下文
        context = ToolContext(
            memory_engine=self.config.memory_engine,
            cognitive_memory=self.config.cognitive_memory,
            onebot_client=self.config.onebot_client,
            scheduler=self.config.scheduler,
            user_id=user_id,
            group_id=group_id,
            message_type=message_type,
            sender_name=sender_name
        )

        try:
            # 执行工具
            result = await self.registry.execute_tool(tool_name, args, context)

            self.config.success_calls += 1
            self.config.last_call_time = datetime.now()

            return result
        except Exception as e:
            self.config.failed_calls += 1
            logger.error(f"执行工具 {tool_name} 失败: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取所有工具的 OpenAI Function Calling 格式配置"""
        return self.registry.get_tools_schema()

    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self.registry.tools.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取子网统计信息"""
        success_rate = (
            self.config.success_calls / self.config.total_calls * 100
            if self.config.total_calls > 0 else 0
        )

        return {
            'subnet': self.config.subnet_name,
            'version': self.config.version,
            'total_tools': len(self.registry.tools),
            'total_calls': self.config.total_calls,
            'success_calls': self.config.success_calls,
            'failed_calls': self.config.failed_calls,
            'success_rate': f"{success_rate:.1f}%",
            'last_call': self.config.last_call_time.isoformat() if self.config.last_call_time else None
        }

    def health_check(self) -> bool:
        """健康检查"""
        return (
            len(self.registry.tools) > 0 and
            self.config.enabled
        )

    async def shutdown(self):
        """关闭子网"""
        logger.info("ToolNet 子网正在关闭...")
        # 清理资源
        self.registry.clear()
        logger.info("ToolNet 子网已关闭")
