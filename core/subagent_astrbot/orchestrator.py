"""
AstrBot Subagent Orchestrator
"""

import logging
from typing import Any, Dict, List, Optional

from .agent import SubAgent
from .config import SubAgentOrchestratorConfig

logger = logging.getLogger(__name__)


class SubAgentOrchestrator:
    """
    子代理编排器

    提供:
    - 子代理定义管理
    - 代理间切换
    - 工具共享
    """

    def __init__(self):
        self._agents: Dict[str, SubAgent] = {}
        self._config: Optional[SubAgentOrchestratorConfig] = None
        self._current_agent: Optional[str] = None

    async def load_from_config(self, config: Dict[str, Any]) -> bool:
        """从配置加载子代理"""
        try:
            self._config = SubAgentOrchestratorConfig()
            self._agents.clear()

            agents = config.get("agents", [])
            for agent_config in agents:
                if not isinstance(agent_config, dict):
                    continue
                if not agent_config.get("enabled", True):
                    continue

                name = agent_config.get("name", "").strip()
                if not name:
                    continue

                sub_agent = SubAgent(
                    name=name,
                    system_prompt=agent_config.get("system_prompt", ""),
                    description=agent_config.get("public_description", ""),
                    tools=agent_config.get("tools", []),
                    provider_id=agent_config.get("provider_id"),
                )
                self._agents[name] = sub_agent
                logger.info(f"[SubAgentOrchestrator] 加载子代理: {name}")

            return True
        except Exception as e:
            logger.error(f"[SubAgentOrchestrator] 加载配置失败: {e}")
            return False

    def list_agents(self) -> List[str]:
        """列出所有子代理"""
        return list(self._agents.keys())

    def get_agent(self, name: str) -> Optional[SubAgent]:
        """获取子代理"""
        return self._agents.get(name)

    def add_agent(self, agent: SubAgent) -> bool:
        """添加子代理"""
        if agent.name in self._agents:
            logger.warning(f"[SubAgentOrchestrator] 子代理已存在: {agent.name}")
            return False
        self._agents[agent.name] = agent
        return True

    def remove_agent(self, name: str) -> bool:
        """移除子代理"""
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    def switch_agent(self, name: str) -> bool:
        """切换当前代理"""
        if name in self._agents:
            self._current_agent = name
            return True
        return False

    def get_current_agent(self) -> Optional[SubAgent]:
        """获取当前代理"""
        if self._current_agent:
            return self._agents.get(self._current_agent)
        return None

    def get_handoff_tools(self) -> List[Dict[str, Any]]:
        """获取切换工具列表"""
        tools = []
        for name, agent in self._agents.items():
            tools.append(
                {
                    "name": f"handoff_to_{name}",
                    "description": f"切换到子代理: {name} - {agent.description}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "要交给子代理处理的任务",
                            }
                        },
                        "required": ["task"],
                    },
                }
            )
        return tools

    async def execute_handoff(self, agent_name: str, task: str, context: Dict[str, Any]) -> str:
        """执行代理切换"""
        agent = self.get_agent(agent_name)
        if not agent:
            return f"子代理不存在: {agent_name}"

        try:
            return await agent.execute(task, context)
        except Exception as e:
            logger.error(f"[SubAgentOrchestrator] 执行失败: {e}")
            return f"执行失败: {e}"


_orchestrator: Optional[SubAgentOrchestrator] = None


def get_orchestrator() -> SubAgentOrchestrator:
    """获取全局编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SubAgentOrchestrator()
    return _orchestrator
