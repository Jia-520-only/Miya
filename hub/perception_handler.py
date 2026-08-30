"""
感知处理器 (Perception Handler)

职责：
1. 权限检查与修正
2. 终端工具优先级
3. 感知决策（如需要决策层处理）
4. 游戏模式助手优先级
5. 情感类/选择类工具优先级
6. 阻塞/选择级工具优先级
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PerceptionHandler:
    """
    感知处理器

    单一职责：处理现有模块及输入感知相关的复杂处理逻辑
    """

    def __init__(
        self,
        auth_subnet: Optional[Any] = None,
        onebot_client: Optional[Any] = None,
    ):
        """
        初始化感知处理器

        Args:
            auth_subnet: 权限子网
            onebot_client: OneBot客户端
        """
        self.auth_subnet = auth_subnet
        self.onebot_client = onebot_client

        logger.info("[感知处理器] 初始化完成")

    async def check_permission(self, perception: Dict) -> bool:
        """
        检查用户权限

        Args:
            perception: 感知数据

        Returns:
            是否有权限
        """
        user_id = perception.get("user_id")
        group_id = perception.get("group_id")
        message_type = perception.get("message_type", "group")

        # 管理员总是有权限
        if user_id and self.is_admin(user_id, group_id):
            return True

        # 权限子网检查
        if self.auth_subnet:
            try:
                from webnet.ToolNet.base import ToolContext

                context = ToolContext(
                    user_id=user_id, group_id=group_id, message_type=message_type, onebot_client=self.onebot_client
                )
                has_perm = await self.auth_subnet.check_permission(context)
                if not has_perm:
                    logger.warning(f"[感知处理器] 权限不足: user_id={user_id}, group_id={group_id}")
                return has_perm
            except Exception as e:
                logger.error(f"[感知处理器] 权限检查失败: {e}", exc_info=True)
                return False

        # 默认允许
        return True

    def is_admin(self, user_id: Optional[int], group_id: Optional[int]) -> bool:
        """
        检查是否是管理员

        Args:
            user_id: 用户ID
            group_id: 群号

        Returns:
            是否是管理员
        """
        # 这里可以实现管理员检查逻辑
        # 例如从配置文件或数据库读取管理员列表
        admin_list = self._load_admin_list()

        return bool(user_id and user_id in admin_list)

    def _load_admin_list(self) -> list:
        """
        加载管理员列表

        Returns:
            管理员ID列表
        """
        # 从配置文件加载
        try:
            config_file = Path("config/admins.json")
            if config_file.exists():
                import json

                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("admins", [])
        except Exception as e:
            logger.error(f"[感知处理器] 加载管理员列表失败: {e}", exc_info=True)

        # 返回默认管理员列表（空）
        return []

    async def prioritize_perception(self, perception: Dict) -> int:
        """
        感知优先级判断

        Args:
            perception: 感知数据

        Returns:
            优先级 (0=最低, 10=最高)
        """
        priority = 5  # 默认优先级

        # 情感类/选择类工具优先
        if self._is_emotion_or_choice_tool(perception):
            priority = 7

        # 阻塞/选择级工具优先
        if self._is_blocking_or_choice_tool(perception):
            priority = 6

        return priority

    def _is_emotion_or_choice_tool(self, perception: Dict) -> bool:
        """
        判断是否是情感类/选择类工具

        Args:
            perception: 感知数据

        Returns:
            是否是情感类/选择类工具
        """
        tool_name = perception.get("tool_name", "")
        emotion_tools = ["emote", "emotion", "mood", "choice", "select"]
        return any(tool in tool_name.lower() for tool in emotion_tools)

    def _is_blocking_or_choice_tool(self, perception: Dict) -> bool:
        """
        判断是否是阻塞/选择级工具

        Args:
            perception: 感知数据

        Returns:
            是否是阻塞/选择级工具
        """
        tool_name = perception.get("tool_name", "")
        blocking_tools = ["block", "pause", "wait", "confirm", "approve"]
        return any(tool in tool_name.lower() for tool in blocking_tools)

    async def enhance_perception(self, perception: Dict) -> Dict:
        """
        增强感知数据

        Args:
            perception: 原始感知数据

        Returns:
            增强后的感知数据
        """
        # 添加权限信息
        has_permission = await self.check_permission(perception)
        perception["has_permission"] = has_permission

        # 添加优先级
        priority = await self.prioritize_perception(perception)
        perception["priority"] = priority

        # 添加时间戳
        from datetime import datetime

        perception["timestamp"] = datetime.now().isoformat()

        # 添加来源信息
        user_id = perception.get("user_id")
        group_id = perception.get("group_id")
        perception["source"] = {
            "user_id": user_id,
            "group_id": group_id,
            "message_type": perception.get("message_type"),
        }

        return perception

    def get_handler_info(self) -> Dict[str, Any]:
        """
        获取处理器信息

        Returns:
            处理器信息
        """
        return {
            "name": "PerceptionHandler",
            "version": "1.0.0",
            "has_auth_subnet": self.auth_subnet is not None,
            "has_onebot_client": self.onebot_client is not None,
        }
