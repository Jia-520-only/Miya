"""
工具适配器 - 连接 AI 客户端和工具系统

架构升级：
1. 支持原生子网架构
2. 集成M-Link传输
3. 集成感知层预处理
4. 统一记忆系统接口
"""
import logging
from typing import Dict, Any, Optional
from webnet.tools.base import ToolContext


logger = logging.getLogger(__name__)


class ToolAdapter:
    """
    工具适配器 - 执行工具调用

    支持两种模式：
    1. 兼容模式：使用传统的ToolRegistry
    2. 原生模式：使用M-Link子网架构
    """

    def __init__(self, enable_native: bool = True):
        """
        初始化工具适配器

        Args:
            enable_native: 是否启用原生M-Link模式
        """
        self.tool_registry: Optional[Any] = None
        self.life_subnet: Optional[Any] = None  # LifeNet实例
        self.unified_memory: Optional[Any] = None  # 统一记忆接口
        self.emotion_system: Optional[Any] = None  # 情绪系统

        self.enable_native = enable_native
        self.mlink_subnet: Optional[Any] = None  # M-Link子网

        self.logger = logging.getLogger("ToolAdapter")

    def set_tool_registry(self, registry: Any):
        """设置工具注册表"""
        self.tool_registry = registry
        self.logger.debug("工具注册表已设置")

    def set_life_subnet(self, life_subnet: Any):
        """设置LifeNet子网"""
        self.life_subnet = life_subnet
        self.logger.debug("LifeNet子网已设置")

    def set_unified_memory(self, unified_memory: Any):
        """设置统一记忆接口"""
        self.unified_memory = unified_memory
        self.logger.debug("统一记忆接口已设置")

    def set_emotion_system(self, emotion_system: Any):
        """设置情绪系统"""
        self.emotion_system = emotion_system
        self.logger.debug("情绪系统已设置")

    def enable_native_mode(
        self,
        tool_registry,
        emotion_system=None,
        memory_engine=None
    ):
        """
        启用原生M-Link模式

        Args:
            tool_registry: 工具注册表
            emotion_system: 情绪系统
            memory_engine: 记忆引擎
        """
        try:
            from webnet.ToolNet.mlink_subnet import MLinkToolSubnet

            self.mlink_subnet = MLinkToolSubnet(
                tool_registry=tool_registry,
                emotion_system=emotion_system,
                memory_engine=memory_engine,
                enable_perception=True,
                enable_mlink=True
            )

            self.enable_native = True
            self.logger.info("✅ 已启用原生M-Link模式")

        except Exception as e:
            self.logger.error(f"启用原生模式失败: {e}")
            self.enable_native = False

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 上下文信息

        Returns:
            执行结果
        """
        if not self.tool_registry:
            logger.warning(f"工具注册表未设置，无法执行工具: {tool_name}")
            return f"错误：工具系统未初始化"

        try:
            # 添加额外上下文
            context['lifenet'] = self.life_subnet
            if self.unified_memory:
                context['unified_memory'] = self.unified_memory

            # 过滤掉 ToolContext 不支持的参数
            # ToolContext 支持的字段: qq_net, onebot_client, send_like_callback,
            # memory_engine, unified_memory, memory_net, emotion, personality,
            # scheduler, lifenet, request_id, group_id, user_id, message_type,
            # sender_name, is_at_bot, at_list, game_mode, game_mode_manager,
            # game_mode_adapter, bot_qq, superadmin
            supported_fields = {
                'qq_net', 'onebot_client', 'send_like_callback',
                'memory_engine', 'unified_memory', 'memory_net', 'emotion',
                'personality', 'scheduler', 'lifenet', 'request_id',
                'group_id', 'user_id', 'message_type', 'sender_name',
                'is_at_bot', 'at_list', 'game_mode', 'game_mode_manager',
                'game_mode_adapter', 'bot_qq', 'superadmin'
            }
            filtered_context = {k: v for k, v in context.items() if k in supported_fields}

            # 创建工具上下文
            tool_context = ToolContext(**filtered_context)

            # 根据模式选择执行方式
            if self.enable_native and self.mlink_subnet:
                # 原生模式：使用M-Link子网
                result = await self.mlink_subnet.execute_tool(
                    tool_name,
                    args,
                    tool_context
                )
            else:
                # 兼容模式：直接调用注册表
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    logger.warning(f"未找到工具: {tool_name}")
                    return f"错误：未找到工具 '{tool_name}'"

                logger.info(f"执行工具: {tool_name}, 参数: {args}")
                result = await tool.execute(args, tool_context)
                logger.info(f"工具执行完成: {tool_name}")

            return result

        except Exception as e:
            logger.error(f"工具执行失败 {tool_name}: {e}", exc_info=True)
            return f"错误：工具执行失败 - {str(e)}"

    async def execute_tool_batch(
        self,
        tool_calls: list,
        context: Dict[str, Any]
    ) -> list:
        """
        批量执行工具

        Args:
            tool_calls: 工具调用列表
            context: 上下文信息

        Returns:
            结果列表
        """
        # 添加额外上下文
        context['lifenet'] = self.life_subnet
        if self.unified_memory:
            context['unified_memory'] = self.unified_memory

        # 过滤掉 ToolContext 不支持的参数
        supported_fields = {
            'qq_net', 'onebot_client', 'send_like_callback',
            'memory_engine', 'unified_memory', 'memory_net', 'emotion',
            'personality', 'scheduler', 'lifenet', 'request_id',
            'group_id', 'user_id', 'message_type', 'sender_name',
            'is_at_bot', 'at_list', 'game_mode', 'game_mode_manager',
            'game_mode_adapter', 'bot_qq', 'superadmin'
        }
        filtered_context = {k: v for k, v in context.items() if k in supported_fields}

        tool_context = ToolContext(**filtered_context)

        # 原生模式使用批量执行
        if self.enable_native and self.mlink_subnet:
            return await self.mlink_subnet.execute_tool_batch(tool_calls, tool_context)

        # 兼容模式逐个执行
        results = []
        for call in tool_calls:
            tool_name = call.get('tool_name')
            args = call.get('args', {})
            result = await self.execute_tool(tool_name, args, context)
            results.append(result)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self.enable_native and self.mlink_subnet:
            return self.mlink_subnet.get_stats()
        elif self.tool_registry:
            return {
                'mode': 'compatibility',
                'total_tools': len(self.tool_registry.tools)
            }
        else:
            return {'mode': 'uninitialized'}

    def health_check(self) -> bool:
        """健康检查"""
        if self.enable_native and self.mlink_subnet:
            return self.mlink_subnet.health_check()
        elif self.tool_registry:
            return len(self.tool_registry.tools) > 0
        return False


# 全局适配器实例
_adapter = None


def get_tool_adapter() -> ToolAdapter:
    """获取全局工具适配器实例"""
    global _adapter
    if _adapter is None:
        _adapter = ToolAdapter()
    return _adapter


def set_tool_adapter(adapter: ToolAdapter):
    """设置全局工具适配器"""
    global _adapter
    _adapter = adapter
