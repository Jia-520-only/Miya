"""
EntertainmentNet 子网基类

符合弥娅子网架构规范
"""
import logging
import asyncio
import httpx
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from core.constants import LogLevel
from .tools.qqlike import QQLike
from .tools.horoscope import Horoscope
from .tools.wenchang_dijun import WenchangDijun
from .tools.send_poke import SendPoke
from .tools.react_emoji import ReactEmoji


logger = logging.getLogger(__name__)


@dataclass
class EntertainmentConfig:
    """娱乐子网配置"""
    subnet_name: str = "EntertainmentNet"
    subnet_id: str = "subnet.entertainment"
    version: str = "1.0.0"
    enabled: bool = True
    log_level: str = LogLevel.INFO
    # 核心组件引用
    onebot_client: Any = None
    # 统计信息
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    last_call_time: Optional[datetime] = None


class EntertainmentSubnet:
    """
    EntertainmentNet 娱乐子网

    弥娅娱乐子网，符合蛛网式分布式架构：
    - 提供QQ娱乐功能
    - 支持星座运势查询
    - 支持占卜抽签
    - 提供统一的上下文管理
    """

    def __init__(
        self,
        onebot_client: Any = None,
        config: Optional[EntertainmentConfig] = None
    ):
        """初始化娱乐子网

        Args:
            onebot_client: OneBot 客户端
            config: 子网配置
        """
        self.config = config or EntertainmentConfig(
            onebot_client=onebot_client
        )

        # 初始化所有工具
        self.tools: Dict[str, Any] = {}
        self._init_tools()

        logger.info(f"EntertainmentNet 子网已启动 (v{self.config.version})")
        logger.info(f"已注册 {len(self.tools)} 个娱乐工具")

    def _init_tools(self):
        """初始化所有娱乐工具"""
        # 注册工具
        self.tools['qq_like'] = QQLike()
        self.tools['horoscope'] = Horoscope()
        self.tools['wenchang_dijun'] = WenchangDijun()
        self.tools['send_poke'] = SendPoke()
        self.tools['react_emoji'] = ReactEmoji()

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None
    ) -> str:
        """执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数
            user_id: 用户ID
            group_id: 群号
            message_type: 消息类型 (group/private)

        Returns:
            执行结果字符串
        """
        self.config.total_calls += 1

        if tool_name not in self.tools:
            self.config.failed_calls += 1
            return f"❌ 未找到工具: {tool_name}"

        tool = self.tools[tool_name]

        try:
            # 创建上下文
            context = {
                'onebot_client': self.config.onebot_client,
                'send_like_callback': getattr(self.config.onebot_client, 'send_like', None),
                'user_id': user_id,
                'group_id': group_id,
                'message_type': message_type
            }

            # 执行工具
            result = await tool.execute(args, context)

            self.config.success_calls += 1
            self.config.last_call_time = datetime.now()
            return result

        except Exception as e:
            self.config.failed_calls += 1
            logger.error(f"执行工具 {tool_name} 失败: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """获取所有工具列表

        Returns:
            工具信息列表
        """
        tool_list = []
        for tool_name, tool in self.tools.items():
            tool_list.append({
                'name': tool_name,
                'config': getattr(tool, 'config', {}),
                'subnet': 'EntertainmentNet'
            })
        return tool_list

    def get_stats(self) -> Dict[str, Any]:
        """获取子网统计信息

        Returns:
            统计信息字典
        """
        return {
            'subnet_name': self.config.subnet_name,
            'version': self.config.version,
            'total_tools': len(self.tools),
            'total_calls': self.config.total_calls,
            'success_calls': self.config.success_calls,
            'failed_calls': self.config.failed_calls,
            'success_rate': (
                self.config.success_calls / self.config.total_calls
                if self.config.total_calls > 0
                else 0
            ),
            'last_call_time': self.config.last_call_time
        }
