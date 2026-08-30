"""
统一Agent运行器 - 源自Undefined的Agent架构
为弥娅Agent提供统一的执行框架
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger("Miya.AgentRunner")


class AgentToolRegistry:
    """Agent工具注册表 - 发现并注册Agent专属工具"""

    def __init__(self, tools_dir: Path, agent_name: str):
        self.tools_dir = tools_dir
        self.agent_name = agent_name
        self._tools_schema: List[Dict] = []
        self._discover_tools()

    def _discover_tools(self):
        """发现工具目录下的所有工具"""
        if not self.tools_dir.exists():
            logger.warning(f"[Agent:{self.agent_name}] 工具目录不存在: {self.tools_dir}")
            return

        for tool_dir in self.tools_dir.iterdir():
            if not tool_dir.is_dir():
                continue

            handler_file = tool_dir / "handler.py"
            config_file = tool_dir / "config.json"

            if handler_file.exists() and config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)

                    # 从config.json提取工具schema
                    if "type" in config and "function" in config:
                        self._tools_schema.append(config)
                        logger.info(f"[Agent:{self.agent_name}] 发现工具: {tool_dir.name}")
                except Exception as e:
                    logger.warning(f"[Agent:{self.agent_name}] 加载工具失败 {tool_dir.name}: {e}")

    def get_tools_schema(self) -> List[Dict]:
        """获取工具Schema列表"""
        return self._tools_schema

    def get_tool_names(self) -> List[str]:
        """获取工具名称列表"""
        names = []
        for tool in self._tools_schema:
            func = tool.get("function", {})
            if func.get("name"):
                names.append(func["name"])
        return names


class AgentRunner:
    """统一Agent运行器"""

    def __init__(self, agent_name: str, agent_dir: Path):
        self.agent_name = agent_name
        self.agent_dir = agent_dir
        self.tools_dir = agent_dir / "tools"
        self.tool_registry = None

        if self.tools_dir.exists():
            self.tool_registry = AgentToolRegistry(self.tools_dir, agent_name)

    async def load_prompt(self) -> str:
        """加载Agent的prompt.md"""
        prompt_path = self.agent_dir / "prompt.md"
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"加载prompt失败: {e}")

        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """获取默认prompt"""
        defaults = {
            "info_agent": "你是一个信息查询助手，擅长回答各种问题，包括天气、新闻、搜索等。请用简洁、准确的方式回答用户的问题。",
            "entertainment_agent": "你是一个娱乐助手，擅长画画、占卜、游戏等。请用有趣、活泼的方式与用户互动。",
            "web_agent": "你是一个网络搜索助手，擅长搜索网页、获取信息。请帮用户找到需要的信息。",
            "file_analysis_agent": "你是一个文件分析助手，擅长分析各种文件。请帮用户理解文件内容。",
            "code_delivery_agent": "你是一个代码交付助手，擅长编写和运行代码。请帮用户完成任务。",
        }
        return defaults.get(self.agent_name, f"你是一个{self.agent_name}助手。")

    async def execute_tool(self, tool_name: str, args: Dict, context: Dict) -> str:
        """执行指定工具"""
        if not self.tool_registry:
            return "工具注册表未初始化"

        tools = self.tool_registry.get_tools_schema()
        for tool in tools:
            func = tool.get("function", {})
            if func.get("name") == tool_name:
                return await self._call_tool_handler(tool_name, args, context)

        return f"未找到工具: {tool_name}"

    async def _call_tool_handler(self, tool_name: str, args: Dict, context: Dict) -> str:
        """调用工具handler"""
        tool_dir = self.tools_dir / tool_name
        handler_file = tool_dir / "handler.py"

        if not handler_file.exists():
            return f"工具处理器不存在: {tool_name}"

        try:
            # 动态导入handler模块
            import sys

            sys.path.insert(0, str(self.agent_dir))

            handler_module = __import__(f"tools.{tool_name}.handler", fromlist=["execute"])

            if hasattr(handler_module, "execute"):
                return await handler_module.execute(args, context)
            else:
                return f"工具 {tool_name} 没有 execute 函数"
        except Exception as e:
            logger.error(f"执行工具失败 {tool_name}: {e}")
            return f"执行工具失败: {str(e)[:100]}"

    async def run(
        self,
        user_input: str,
        context: Dict,
        max_iterations: int = 20,
    ) -> str:
        """运行Agent主循环"""
        if not user_input.strip():
            return "请提供查询内容"

        logger.info(f"[Agent:{self.agent_name}] 开始处理: {user_input[:50]}...")

        # 加载prompt
        system_prompt = await self.load_prompt()

        # 获取可用工具
        tools = []
        if self.tool_registry:
            tools = self.tool_registry.get_tools_schema()

        if not tools:
            return f"[Agent:{self.agent_name}] 未找到可用工具，当前已配置的工具数为 0"

        # 获取 AI 客户端
        ai_client = context.get("ai_client")
        if not ai_client:
            return f"[Agent:{self.agent_name}] 未提供 AI 客户端，无法执行工具"

        # 构建消息 - 使用 AIMessage 格式
        from core.ai_client import AIMessage

        messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="user", content=user_input),
        ]

        try:
            # 调用 AI 客户端的 chat 方法
            result = await ai_client.chat(
                messages=messages,
                tools=tools,
                max_iterations=max_iterations,
                use_miya_prompt=False,  # Agent 使用自己的 prompt
            )

            logger.info(f"[Agent:{self.agent_name}] 执行完成")
            return result if result else f"[Agent:{self.agent_name}] 已处理完成"

        except Exception as e:
            logger.error(f"[Agent:{self.agent_name}] 执行失败: {e}")
            return f"[Agent:{self.agent_name}] 执行失败: {str(e)[:200]}"


async def run_agent_with_tools(
    agent_name: str,
    user_content: str,
    context: Dict,
    agent_dir: Path,
    max_iterations: int = 20,
    default_prompt: str = "",
) -> str:
    """统一入口 - 运行Agent"""
    runner = AgentRunner(agent_name, agent_dir)
    return await runner.run(user_content, context, max_iterations)
