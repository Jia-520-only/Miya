"""
AstrBot Agent Runner - 核心执行器

整合AstrBot的Agent执行能力
"""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .config import AgentConfig
from .context import AgentContext

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    AstrBot Agent 执行器

    提供:
    - 完整的工具调用能力
    - 上下文管理
    - Provider选择
    - 会话管理
    - 引用消息解析
    - 文件提取
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._provider = None
        self._tool_executor = None
        self._context: Optional[AgentContext] = None
        self._initialized = False

    async def initialize(self, provider: Any, tool_registry: Any):
        """初始化Agent"""
        try:
            self._provider = provider
            self._tool_executor = tool_registry
            self._initialized = True
            logger.info("[AgentRunner] 初始化完成")
        except Exception as e:
            logger.error(f"[AgentRunner] 初始化失败: {e}")

    async def execute(self, context: AgentContext, user_input: str, stream: bool = True) -> AsyncIterator[str] | str:
        """
        执行Agent

        Args:
            context: 执行上下文
            user_input: 用户输入
            stream: 是否流式输出
        """
        if not self._initialized:
            raise RuntimeError("AgentRunner未初始化")

        self._context = context

        try:
            messages = self._build_messages(context, user_input)
            tools = self._get_tools(context)

            if stream:
                return await self._execute_stream(messages, tools)
            else:
                return await self._execute_normal(messages, tools)
        except Exception as e:
            logger.error(f"[AgentRunner] 执行失败: {e}")
            return f"执行出错: {e}"

    def _build_messages(self, context: AgentContext, user_input: str) -> List[Dict]:
        """构建消息列表"""
        messages = []

        for msg in context.get_history():
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        messages.append({"role": "user", "content": user_input})

        return messages

    def _get_tools(self, context: AgentContext) -> List[Dict]:
        """获取工具列表"""
        tools = []

        for tool in context.tools:
            if hasattr(tool, "to_schema"):
                tools.append(tool.to_schema())
            elif isinstance(tool, dict):
                tools.append(tool)

        return tools

    async def _execute_stream(self, messages: List[Dict], tools: List[Dict]) -> AsyncIterator[str]:
        """流式执行"""
        if not self._provider:
            return

        try:
            async for chunk in self._provider.chat(messages=messages, tools=tools if tools else None, stream=True):
                yield chunk
        except Exception as e:
            logger.error(f"[AgentRunner] 流式执行失败: {e}")
            yield f"错误: {e}"

    async def _execute_normal(self, messages: List[Dict], tools: List[Dict]) -> str:
        """普通执行"""
        if not self._provider:
            return "Provider未初始化"

        try:
            response = await self._provider.chat(messages=messages, tools=tools if tools else None, stream=False)
            return response.get("content", "")
        except Exception as e:
            logger.error(f"[AgentRunner] 执行失败: {e}")
            return f"错误: {e}"

    async def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """执行工具"""
        if not self._tool_executor:
            return "工具执行器未初始化"

        try:
            if hasattr(self._tool_executor, "execute"):
                return await self._tool_executor.execute(tool_name, arguments)
            elif hasattr(self._tool_executor, "run_tool"):
                return await self._tool_executor.run_tool(tool_name, arguments)
            else:
                return "工具执行器不支持execute方法"
        except Exception as e:
            logger.error(f"[AgentRunner] 工具执行失败: {e}")
            return f"工具执行出错: {e}"

    async def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        tools = []
        if self._context:
            for tool in self._context.tools:
                if hasattr(tool, "name"):
                    tools.append(tool.name)
                elif isinstance(tool, dict):
                    tools.append(tool.get("name", ""))
        return tools

    def get_context(self) -> Optional[AgentContext]:
        """获取当前上下文"""
        return self._context


class AgentRunnerPool:
    """AgentRunner池，管理多个Runner实例"""

    def __init__(self):
        self._runners: Dict[str, AgentRunner] = {}
        self._default_config = AgentConfig()

    def create_runner(self, runner_id: str, config: Optional[AgentConfig] = None) -> AgentRunner:
        """创建Runner"""
        runner = AgentRunner(config or self._default_config)
        self._runners[runner_id] = runner
        return runner

    def get_runner(self, runner_id: str) -> Optional[AgentRunner]:
        """获取Runner"""
        return self._runners.get(runner_id)

    def remove_runner(self, runner_id: str):
        """移除Runner"""
        self._runners.pop(runner_id, None)

    def list_runners(self) -> List[str]:
        """列出所有Runner"""
        return list(self._runners.keys())


_agent_runner_pool: Optional[AgentRunnerPool] = None


def get_agent_runner_pool() -> AgentRunnerPool:
    """获取全局AgentRunner池"""
    global _agent_runner_pool
    if _agent_runner_pool is None:
        _agent_runner_pool = AgentRunnerPool()
    return _agent_runner_pool
