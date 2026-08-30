"""
AgentHub - 统一的 Agent 调度中心
负责发现、管理和调度所有 Agent
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.AgentHub")


class AgentInfo:
    """Agent 信息封装"""

    def __init__(self, name: str, agent_dir: Path):
        self.name = name
        self.agent_dir = agent_dir
        self.prompt = ""
        self.tools: List[Dict] = []
        self._load()

    def _load(self):
        """加载 Agent 配置"""
        prompt_file = self.agent_dir / "prompt.md"
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                self.prompt = f.read()

        tools_dir = self.agent_dir / "tools"
        if tools_dir.exists():
            for tool_dir in tools_dir.iterdir():
                if not tool_dir.is_dir():
                    continue
                config_file = tool_dir / "config.json"
                if config_file.exists():
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            tool_config = json.load(f)
                            if "function" in tool_config:
                                self.tools.append(tool_config)
                    except Exception as e:
                        logger.warning(f"加载工具配置失败 {tool_dir.name}: {e}")

    def get_tools_schema(self) -> List[Dict]:
        """获取工具 schema"""
        return self.tools

    def get_tool_names(self) -> List[str]:
        """获取工具名称列表"""
        return [t.get("function", {}).get("name", "") for t in self.tools if t.get("function")]

    def to_choice_format(self) -> Dict:
        """转换为选择格式"""
        desc = self.prompt.split("\n")[0] if self.prompt else f"{self.name} Agent"
        return {
            "name": self.name,
            "description": desc[:100],
            "tools_count": len(self.tools),
            "tools": self.get_tool_names(),
        }


class AgentHub:
    """Agent 调度中心"""

    AGENT_DIR = Path(__file__).parent

    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self._discover_agents()

    def _discover_agents(self):
        """发现所有 Agent"""
        if not self.AGENT_DIR.exists():
            logger.warning(f"Agent 目录不存在: {self.AGENT_DIR}")
            return

        for agent_dir in self.AGENT_DIR.iterdir():
            if not agent_dir.is_dir():
                continue

            prompt_file = agent_dir / "prompt.md"
            if prompt_file.exists():
                agent_info = AgentInfo(agent_dir.name, agent_dir)
                self.agents[agent_dir.name] = agent_info
                logger.info(f"发现 Agent: {agent_dir.name} (工具数: {len(agent_info.tools)})")

    def list_agents(self) -> List[str]:
        """列出所有 Agent 名称"""
        return list(self.agents.keys())

    def get_agent(self, name: str) -> Optional[AgentInfo]:
        """获取指定 Agent"""
        return self.agents.get(name)

    def get_all_tools_schema(self) -> List[Dict]:
        """获取所有 Agent 的工具 Schema"""
        all_tools = []
        for agent in self.agents.values():
            all_tools.extend(agent.get_tools_schema())
        return all_tools

    async def execute_agent(
        self,
        agent_name: str,
        user_input: str,
        context: Any,
        max_iterations: int = 10,
    ) -> str:
        """执行指定的 Agent"""
        agent = self.get_agent(agent_name)
        if not agent:
            return f"未找到 Agent: {agent_name}"

        logger.info(f"[AgentHub] 调用 Agent: {agent_name}")

        from core.skills.agents.runner import AgentRunner

        runner = AgentRunner(agent_name, agent.agent_dir)

        # 增强用户输入，包含文件信息
        enhanced_input = user_input
        if context and isinstance(context, dict):
            files_list = context.get("files", [])
            file_segments = context.get("file_segments", [])
            if files_list or file_segments:
                file_info_parts = []
                for f in files_list:
                    if isinstance(f, dict):
                        file_info_parts.append(f.get("name", "文件"))
                    else:
                        file_info_parts.append(str(f))
                if file_info_parts:
                    enhanced_input = f"{user_input}\n\n[附加文件信息] 用户发送了以下文件: {', '.join(file_info_parts)}"
                    logger.info(f"[AgentHub] 文件信息已添加到输入: {file_info_parts}")

        # 构建消息

        # 执行 Agent - 传递完整 context
        return await runner.run(enhanced_input, context, max_iterations)

    def select_agent(self, user_input: str) -> Optional[str]:
        """根据用户输入选择合适的 Agent - 支持配置文件"""
        user_lower = user_input.lower()

        # 尝试从配置文件加载路由规则
        config_keywords = self._load_routing_config()

        if config_keywords:
            for agent_name, keywords in config_keywords.items():
                if any(kw in user_lower for kw in keywords):
                    logger.info(f"[AgentHub] 通过配置匹配 Agent: {agent_name}")
                    return agent_name
            return None

        # 回退到硬编码默认值
        agent_keywords = {
            "info_agent": [
                "天气",
                "热搜",
                "新闻",
                "查询",
                "搜索",
                "天气怎么样",
                "微博热搜",
                "抖音热搜",
                "百度热搜",
                "论文",
                "qq等级",
                "ping",
                "whois",
            ],
            "web_agent": [
                "搜索",
                "网络",
                "网页",
                "爬取",
                "链接",
                "网址",
                "查一下",
                "帮我找",
            ],
            "entertainment_agent": ["画图", "画画", "占卜", "游戏", "抽签", "运势"],
            "file_analysis_agent": ["分析", "文件", "解读", "PDF", "文档"],
            "code_delivery_agent": ["代码", "编程", "写代码", "开发", "程序"],
        }

        for agent_name, keywords in agent_keywords.items():
            if any(kw in user_lower for kw in keywords):
                return agent_name

        return None

    def _load_routing_config(self) -> Optional[Dict[str, List[str]]]:
        """从配置文件加载路由规则"""
        config_path = Path("config/agent_routing_config.json")
        if not config_path.exists():
            return None

        try:
            import json

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            routing = config.get("agent_routing", {})
            if not routing.get("enabled", True):
                return None

            rules = routing.get("routing_rules", {})
            result = {}
            for agent_name, rule in rules.items():
                result[agent_name] = rule.get("keywords", [])

            logger.info(f"[AgentHub] 已加载路由配置: {list(result.keys())}")
            return result
        except Exception as e:
            logger.warning(f"[AgentHub] 加载路由配置失败: {e}")
            return None


# 全局单例
_hub: Optional[AgentHub] = None


def get_agent_hub() -> AgentHub:
    """获取 AgentHub 单例"""
    global _hub
    if _hub is None:
        _hub = AgentHub()
    return _hub
