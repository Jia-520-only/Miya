"""
跨端工具 - 让弥娅可以在不同终端之间发送消息和控制

使用方式：
- "把这个发到桌面提醒我" -> send_to_desktop
- "在桌面端打开火狐" -> send_command_to_desktop
- "同步设置到所有端" -> sync_state
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CrossTerminalResult:
    """跨端操作结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class CrossTerminalTools:
    """跨端工具集合"""

    def __init__(self, hub=None):
        self.hub = hub

    async def send_to_desktop(
        self,
        content: str,
        notification: bool = True
    ) -> str:
        """
        发送消息到桌面端

        使用场景：
        - "把这个发到桌面提醒我"
        - "在桌面上显示这条消息"
        - "提醒我XXX"
        """
        if not self.hub:
            return "❌ 跨端Hub未初始化，请确保桌面端已启动"

        try:
            from ..hub import TerminalType

            message_id = await self.hub.send_to_desktop(
                content=content,
                source_type=TerminalType.QQ,
                notification=notification
            )

            logger.info(f"[跨端工具] 消息已发送到桌面端: {message_id}")

            return f"✅ 已将消息发送到桌面端，消息ID: {message_id}"

        except Exception as e:
            logger.error(f"[跨端工具] 发送到桌面端失败: {e}")
            return f"❌ 发送到桌面端失败: {str(e)}"

    async def send_to_terminal(
        self,
        content: str
    ) -> str:
        """
        发送消息到终端
        """
        if not self.hub:
            return "❌ 跨端Hub未初始化"

        try:
            from ..hub import TerminalType

            message_id = await self.hub.send_to_terminal(
                content=content,
                source_type=TerminalType.QQ
            )

            return f"✅ 已将消息发送到终端，消息ID: {message_id}"

        except Exception as e:
            logger.error(f"[跨端工具] 发送到终端失败: {e}")
            return f"❌ 发送到终端失败: {str(e)}"

    async def send_to_qq(
        self,
        content: str,
        target_qq: str = ""
    ) -> str:
        """
        发送消息到QQ端
        """
        if not self.hub:
            return "❌ 跨端Hub未初始化"

        try:
            from ..hub import TerminalType

            message_id = await self.hub.send_to_qq(
                content=content,
                target_qq=target_qq,
                source_type=TerminalType.DESKTOP
            )

            return f"✅ 已将消息发送到QQ端，消息ID: {message_id}"

        except Exception as e:
            logger.error(f"[跨端工具] 发送到QQ失败: {e}")
            return f"❌ 发送到QQ失败: {str(e)}"

    async def send_to_web(
        self,
        content: str
    ) -> str:
        """
        发送消息到Web端
        """
        if not self.hub:
            return "❌ 跨端Hub未初始化"

        try:
            from ..hub import TerminalType

            message_id = await self.hub.send_to_web(
                content=content,
                source_type=TerminalType.DESKTOP
            )

            return f"✅ 已将消息发送到Web端，消息ID: {message_id}"

        except Exception as e:
            logger.error(f"[跨端工具] 发送到Web失败: {e}")
            return f"❌ 发送到Web失败: {str(e)}"

    async def execute_on_desktop(
        self,
        command: str
    ) -> str:
        """
        在桌面端执行命令

        使用场景：
        - "在桌面端打开火狐"
        - "让桌面端执行XXX"
        
        注意：如果桌面端未连接，系统会自动使用终端命令执行
        """
        if not self.hub:
            return "❌ 桌面端未连接，无法执行命令"

        try:
            from ..hub import TerminalType

            message_id = await self.hub.send_command(
                command=command,
                target_type=TerminalType.DESKTOP,
                source_type=TerminalType.QQ
            )

            logger.info(f"[跨端工具] 命令已发送到桌面端: {command}")

            return f"✅ 已在桌面端执行命令: {command}"

        except Exception as e:
            logger.error(f"[跨端工具] 桌面端执行失败: {e}")
            return f"❌ 桌面端执行失败: {str(e)}"

    async def sync_state(
        self,
        key: str,
        value: Any
    ) -> str:
        """
        同步状态到所有终端
        """
        if not self.hub:
            return "❌ 跨端Hub未初始化"

        try:
            await self.hub.set_state(key, value)

            return f"✅ 已将状态同步到所有端: {key}={value}"

        except Exception as e:
            logger.error(f"[跨端工具] 状态同步失败: {e}")
            return f"❌ 状态同步失败: {str(e)}"

    async def get_online_devices(self) -> str:
        """获取在线设备列表"""
        if not self.hub:
            return "❌ 跨端Hub未初始化"

        try:
            devices = await self.hub.get_online_devices()
            device_list = [
                {
                    "device_id": d.device_id,
                    "device_type": d.device_type.value,
                    "device_name": d.device_name,
                    "online": d.online
                }
                for d in devices
            ]

            return f"✅ 当前在线设备: {len(device_list)}个 - {device_list}"

        except Exception as e:
            logger.error(f"[跨端工具] 获取设备列表失败: {e}")
            return f"❌ 获取设备列表失败: {str(e)}"


# 工具注册信息
TOOL_DEFINITIONS = [
    {
        "name": "send_to_desktop",
        "description": """发送消息到桌面端。当用户说"把这个发到桌面"、"提醒我"、"在桌面上显示"时使用此工具。

支持的使用方式：
- "把这个发到桌面提醒我"
- "在桌面上显示XXX"
- "提醒我下午3点开会"
- "发送通知到桌面"

此工具会在桌面端弹出消息或通知。""",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要发送到桌面端的内容"
                },
                "notification": {
                    "type": "boolean",
                    "description": "是否以通知形式显示，默认true",
                    "default": True
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "execute_on_desktop",
        "description": """在桌面端执行命令。当用户说"在桌面端打开XXX"、"让桌面端执行XXX"时使用此工具。

支持的使用方式：
- "在桌面端打开火狐"
- "帮我打开桌面上的计算器"
- "执行桌面端命令"

注意：此工具发送命令到桌面端，由桌面端决定如何执行。""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要在桌面端执行的命令"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "sync_state",
        "description": """同步配置状态到所有终端。当用户说"同步设置"、"更新所有端"时使用。

此工具可以将桌面端修改的设置同步到QQ等其他端。""",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "设置项的键名"
                },
                "value": {
                    "type": "string",
                    "description": "设置项的值"
                }
            },
            "required": ["key", "value"]
        }
    }
]


# 全局实例
_cross_terminal_tools: Optional[CrossTerminalTools] = None


def get_cross_terminal_tools(hub=None) -> CrossTerminalTools:
    """获取跨端工具实例"""
    global _cross_terminal_tools
    if _cross_terminal_tools is None:
        _cross_terminal_tools = CrossTerminalTools(hub)
    return _cross_terminal_tools
