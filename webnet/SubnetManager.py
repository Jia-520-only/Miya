"""
SubnetManager - 子网管理器

> 统一管理所有业务子网
> 提供工具路由和执行接口
>
> 子网架构：
> - BasicNet: 基础工具
> - MessageNet: 消息工具
> - GroupNet: 群管理工具
> - MemoryNet: 记忆工具
> - KnowledgeNet: 知识工具
> - EntertainmentNet: 娱乐工具
> - BilibiliNet: B站工具
> - SchedulerNet: 定时任务
> - CognitiveNet: 认知工具
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class SubnetStats:
    """子网统计信息"""
    subnet_name: str
    total_tools: int
    total_calls: int
    success_calls: int
    failed_calls: int
    last_call_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.success_calls / self.total_calls


class SubnetManager:
    """
    子网管理器

    负责管理所有业务子网，提供统一的工具执行接口
    """

    def __init__(self):
        self.subnets: Dict[str, Any] = {}
        self.tool_index: Dict[str, str] = {}  # tool_name -> subnet_name

    def register_subnet(self, subnet_name: str, subnet_instance: Any):
        """注册子网"""
        self.subnets[subnet_name] = subnet_instance
        logger.info(f"已注册子网: {subnet_name}")

        # 建立工具索引
        if hasattr(subnet_instance, 'tools'):
            for tool_name in subnet_instance.tools.keys():
                self.tool_index[tool_name] = subnet_name
            logger.info(f"  - 包含 {len(subnet_instance.tools)} 个工具")

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> str:
        """执行工具（路由到对应子网）

        Args:
            tool_name: 工具名称
            args: 工具参数
            user_id: 用户ID
            group_id: 群号
            message_type: 消息类型
            sender_name: 发送者名称

        Returns:
            执行结果字符串
        """
        # 查找工具所属子网
        subnet_name = self.tool_index.get(tool_name)
        if not subnet_name:
            return f"❌ 未找到工具: {tool_name}"

        subnet = self.subnets.get(subnet_name)
        if not subnet:
            return f"❌ 子网未初始化: {subnet_name}"

        # 调用子网执行
        try:
            return await subnet.execute_tool(
                tool_name=tool_name,
                args=args,
                user_id=user_id,
                group_id=group_id,
                message_type=message_type,
                sender_name=sender_name
            )
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具列表"""
        all_tools = []
        for subnet_name, subnet in self.subnets.items():
            if hasattr(subnet, 'get_tool_list'):
                tools = subnet.get_tool_list()
                all_tools.extend(tools)
            elif hasattr(subnet, 'tools'):
                for tool_name, tool in subnet.tools.items():
                    all_tools.append({
                        'name': tool_name,
                        'config': getattr(tool, 'config', {}),
                        'subnet': subnet_name
                    })
        return all_tools

    def get_stats(self) -> Dict[str, SubnetStats]:
        """获取所有子网统计信息"""
        stats = {}
        for subnet_name, subnet in self.subnets.items():
            if hasattr(subnet, 'get_stats'):
                subnet_stats = subnet.get_stats()
                stats[subnet_name] = SubnetStats(
                    subnet_name=subnet_name,
                    total_tools=subnet_stats.get('total_tools', 0),
                    total_calls=subnet_stats.get('total_calls', 0),
                    success_calls=subnet_stats.get('success_calls', 0),
                    failed_calls=subnet_stats.get('failed_calls', 0),
                    last_call_time=subnet_stats.get('last_call_time')
                )
            elif hasattr(subnet, 'config'):
                stats[subnet_name] = SubnetStats(
                    subnet_name=subnet_name,
                    total_tools=len(getattr(subnet, 'tools', {})),
                    total_calls=getattr(subnet.config, 'total_calls', 0),
                    success_calls=getattr(subnet.config, 'success_calls', 0),
                    failed_calls=getattr(subnet.config, 'failed_calls', 0),
                    last_call_time=getattr(subnet.config, 'last_call_time', None)
                )
        return stats

    def get_subnet_names(self) -> List[str]:
        """获取所有已注册的子网名称"""
        return list(self.subnets.keys())
