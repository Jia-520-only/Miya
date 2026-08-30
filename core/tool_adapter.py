"""
工具适配器 - 连接 AI 客户端和工具系统

架构升级：
1. 支持原生子网架构
2. 集成M-Link传输
3. 集成感知层预处理
4. 统一记忆系统接口
5. 支持工具降级机制
"""
import logging
from typing import Dict, Any, Optional, List
from webnet.tools.base import ToolContext


logger = logging.getLogger(__name__)


# 工具降级映射：当主工具失败时，自动尝试备选工具
# 格式：主工具名 -> [备选工具1, 备选工具2, ...]
TOOL_FALLBACK_MAP = {
    "execute_on_desktop": ["terminal_command", "multi_terminal"],
    "send_to_desktop": ["send_to_terminal"],
    "send_to_terminal": ["send_to_qq"],
    "send_to_qq": ["send_to_web"],
}


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
        context: Dict[str, Any],
        enable_fallback: bool = True
    ) -> str:
        """
        执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 上下文信息
            enable_fallback: 是否启用降级机制

        Returns:
            执行结果
        """
        if not self.tool_registry:
            logger.warning(f"工具注册表未设置，无法执行工具: {tool_name}")
            return f"错误：工具系统未初始化"

        # 准备过滤后的上下文
        filtered_context = self._prepare_tool_context(context)

        # 首先尝试执行主工具
        result = await self._do_execute_tool(tool_name, args, filtered_context)

        # 检查是否需要降级
        if enable_fallback and not self._is_success_result(result):
            fallback_tools = TOOL_FALLBACK_MAP.get(tool_name, [])
            for fallback_tool in fallback_tools:
                logger.info(f"[降级机制] 主工具 {tool_name} 失败，尝试降级工具: {fallback_tool}")
                try:
                    result = await self._do_execute_tool(fallback_tool, args, filtered_context)
                    if self._is_success_result(result):
                        logger.info(f"[降级机制] 降级工具 {fallback_tool} 执行成功")
                        # 添加降级提示
                        result += "\n\n[注: 由于跨端工具不可用，已使用替代方式执行]"
                        break
                except Exception as e:
                    logger.warning(f"[降级机制] 降级工具 {fallback_tool} 也失败: {e}")
                    continue
            else:
                # 所有工具都失败了
                if not self._is_success_result(result):
                    result += f"\n\n[注: 尝试了 {len(fallback_tools)} 个备选工具，均未能成功执行]"

        return result

    def _prepare_tool_context(self, context: Dict[str, Any]) -> ToolContext:
        """准备工具上下文"""
        # 添加额外上下文
        if self.life_subnet:
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

        return ToolContext(**filtered_context)

    def _is_success_result(self, result: str) -> bool:
        """判断工具执行是否成功"""
        if not result:
            return False
        # 失败的关键字
        failure_keywords = [
            "错误", "失败", "未找到", "不可用", "无法",
            "Error", "Failed", "Not Found", "Unavailable", "Cannot",
            "执行失败", "连接失败", "timeout", "Timeout"
        ]
        # 如果结果包含这些关键字，认为是失败的
        result_lower = result.lower()
        for keyword in failure_keywords:
            if keyword.lower() in result_lower and "降级" not in result:
                return False
        return True

    async def _do_execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        tool_context: ToolContext
    ) -> str:
        """
        执行单个工具

        Args:
            tool_name: 工具名称
            args: 工具参数
            tool_context: 工具上下文

        Returns:
            执行结果
        """
        try:
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
