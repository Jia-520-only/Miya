"""
AstrBot SubAgent
"""

from typing import Any, Dict, List, Optional


class SubAgent:
    """
    子代理

    独立的Agent实例，有自己的指令和工具集
    """

    def __init__(
        self,
        name: str,
        system_prompt: str = "",
        description: str = "",
        tools: Optional[List[str]] = None,
        provider_id: Optional[str] = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.description = description
        self.tools = tools or []
        self.provider_id = provider_id
        self._history: List[Dict[str, Any]] = []

    async def execute(self, task: str, context: Dict[str, Any]) -> str:
        """
        执行任务

        这个方法需要连接到实际的Provider来执行
        这里是一个简化的实现
        """
        self._history.append({"role": "user", "content": task})

        response = f"[{self.name}] 已接收任务: {task}\n"
        response += f"系统指令: {self.system_prompt[:100]}...\n"
        response += f"可用工具: {', '.join(self.tools) if self.tools else '无'}"

        self._history.append({"role": "assistant", "content": response})

        return response

    def get_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self._history

    def clear_history(self):
        """清空历史"""
        self._history.clear()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "description": self.description,
            "tools": self.tools,
            "provider_id": self.provider_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubAgent":
        """从字典创建"""
        return cls(
            name=data.get("name", ""),
            system_prompt=data.get("system_prompt", ""),
            description=data.get("description", ""),
            tools=data.get("tools", []),
            provider_id=data.get("provider_id"),
        )
