"""
ToolNet 子网路由器

> 将工具按功能分组到不同子网
> 提供统一的工具执行接口
>
> 子网分类：
> - BasicNet: 基础工具 (3个)
> - MessageNet: 消息工具 (4个)
> - GroupNet: 群管理工具 (5个)
> - MemoryNet: 记忆工具 (4个)
> - KnowledgeNet: 知识工具 (3个)
> - EntertainmentNet: 娱乐工具 (5个)
> - BilibiliNet: B站工具 (1个)
> - SchedulerNet: 定时任务 (3个)
> - CognitiveNet: 认知工具 (3个)
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from .registry import ToolRegistry, ToolContext


logger = logging.getLogger(__name__)


# 子网分类映射
SUBNET_CATEGORIES = {
    'BasicNet': [
        'get_current_time',
        'get_user_info',
        'python_interpreter',
    ],
    'MessageNet': [
        'send_message',
        'get_recent_messages',
        'send_text_file',
        'send_url_file',
    ],
    'GroupNet': [
        'get_member_list',
        'get_member_info',
        'find_member',
        'filter_members',
        'rank_members',
    ],
    'MemoryNet': [
        'memory_add',
        'memory_list',
        'memory_update',
        'memory_delete',
    ],
    'KnowledgeNet': [
        'knowledge_list',
        'knowledge_text_search',
        'knowledge_semantic_search',
    ],
    'CognitiveNet': [
        'get_profile',
        'search_profiles',
        'search_events',
    ],
    'BilibiliNet': [
        'bilibili_video',
    ],
    'SchedulerNet': [
        'create_schedule_task',
        'list_schedule_tasks',
        'delete_schedule_task',
    ],
    'EntertainmentNet': [
        'qq_like',
        'horoscope',
        'wenchang_dijun',
        'send_poke',
        'react_emoji',
    ],
}


@dataclass
class SubnetInfo:
    """子网信息"""
    name: str
    tool_count: int
    calls: int = 0
    success: int = 0
    failed: int = 0
    last_call: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.success / self.calls


class ToolSubnetRouter:
    """
    工具子网路由器

    负责将工具执行请求路由到正确的子网
    """

    def __init__(self, registry: ToolRegistry):
        """初始化路由器

        Args:
            registry: 工具注册表
        """
        self.registry = registry
        self.subnets: Dict[str, SubnetInfo] = {}
        self._init_subnets()
        logger.info(f"ToolSubnetRouter 已启动，管理 {len(self.subnets)} 个子网")

    def _init_subnets(self):
        """初始化子网分类"""
        for subnet_name, tool_names in SUBNET_CATEGORIES.items():
            self.subnets[subnet_name] = SubnetInfo(
                name=subnet_name,
                tool_count=len(tool_names)
            )
        logger.info(f"子网初始化完成: {self.subnets}")

    def get_subnet_for_tool(self, tool_name: str) -> Optional[str]:
        """获取工具所属子网"""
        for subnet_name, tool_names in SUBNET_CATEGORIES.items():
            if tool_name in tool_names:
                return subnet_name
        return None

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext
    ) -> str:
        """执行工具（自动路由到对应子网）

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果
        """
        subnet_name = self.get_subnet_for_tool(tool_name)

        if not subnet_name:
            return f"❌ 未找到工具: {tool_name}"

        # 更新统计
        subnet_info = self.subnets[subnet_name]
        subnet_info.calls += 1
        subnet_info.last_call = datetime.now()

        try:
            # 执行工具
            tool = self.registry.get_tool(tool_name)
            if not tool:
                subnet_info.failed += 1
                return f"❌ 工具未注册: {tool_name}"

            result = await tool.execute(args, context)

            subnet_info.success += 1
            return result

        except Exception as e:
            subnet_info.failed += 1
            logger.error(f"子网 {subnet_name} 执行工具 {tool_name} 失败: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    def get_all_tools_by_subnet(self) -> Dict[str, List[Dict[str, Any]]]:
        """按子网分组获取所有工具"""
        result = {}
        for subnet_name, tool_names in SUBNET_CATEGORIES.items():
            result[subnet_name] = []
            for tool_name in tool_names:
                tool = self.registry.get_tool(tool_name)
                if tool:
                    result[subnet_name].append({
                        'name': tool_name,
                        'config': tool.config if hasattr(tool, 'config') else {}
                    })
        return result

    def get_subnet_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有子网统计信息"""
        return {
            name: {
                'tool_count': info.tool_count,
                'total_calls': info.calls,
                'success_calls': info.success,
                'failed_calls': info.failed,
                'success_rate': info.success_rate,
                'last_call': info.last_call.isoformat() if info.last_call else None
            }
            for name, info in self.subnets.items()
        }
