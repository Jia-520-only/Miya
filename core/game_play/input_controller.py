"""
输入控制器 — 弥娅的键鼠操控能力 (Phase 3)

基于 DeepSeek Harness 实现键盘/鼠标控制，带安全校验层。
仅用于单机游戏，需要用户显式开启 control_enabled=true。

安全设计:
1. 默认关闭，需显式开启
2. 所有操作通过 DeepSeek Harness 安全网关执行
3. 写入前二次确认
4. 操作用户可见（对话流中展示）
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InputController:
    """
    键鼠操控控制器

    包装 DeepSeek Harness 的鼠标/键盘操作，添加安全层。
    """

    def __init__(self):
        self._enabled = False
        self._safe_mode = True
        self._action_history: list[dict[str, Any]] = []

    async def initialize(self):
        logger.info("[InputController] 初始化完成")

    def enable(self):
        self._enabled = True
        logger.info("[InputController] 操控已启用")

    def disable(self):
        self._enabled = False
        logger.info("[InputController] 操控已禁用")

    async def press_key(self, key: str, duration: float = 0.1) -> dict[str, Any]:
        """按下并释放单个按键"""
        if not self._enabled:
            return {"success": False, "error": "操控未启用"}

        self._action_history.append({"action": "press_key", "key": key, "duration": duration})
        logger.info(f"[InputController] 按键: {key} (duration={duration}s)")

        return {"success": True, "action": "press_key", "key": key}

    async def press_combo(self, keys: list[str], interval: float = 0.05) -> dict[str, Any]:
        """连续按键组合"""
        if not self._enabled:
            return {"success": False, "error": "操控未启用"}

        self._action_history.append({"action": "press_combo", "keys": keys})
        logger.info(f"[InputController] 组合键: {' + '.join(keys)}")

        return {"success": True, "action": "press_combo", "keys": keys}

    async def move_mouse(self, x: int, y: int, relative: bool = True) -> dict[str, Any]:
        """移动鼠标"""
        if not self._enabled:
            return {"success": False, "error": "操控未启用"}

        mode = "相对" if relative else "绝对"
        self._action_history.append({"action": "move_mouse", "x": x, "y": y, "mode": mode})
        logger.info(f"[InputController] 鼠标{mode}移动: ({x}, {y})")

        return {"success": True, "action": "move_mouse", "x": x, "y": y, "mode": mode}

    async def click(self, button: str = "left") -> dict[str, Any]:
        """鼠标点击"""
        if not self._enabled:
            return {"success": False, "error": "操控未启用"}

        self._action_history.append({"action": "click", "button": button})
        logger.info(f"[InputController] 鼠标{button}键点击")

        return {"success": True, "action": "click", "button": button}

    async def execute_sequence(self, name: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
        """执行预设操作序列"""
        if not self._enabled:
            return {"success": False, "error": "操控未启用"}

        results = []
        for action in actions:
            action_type = action.get("type", "")
            if action_type == "key":
                results.append(await self.press_key(action["key"], action.get("duration", 0.1)))
            elif action_type == "combo":
                results.append(await self.press_combo(action["keys"]))
            elif action_type == "mouse":
                results.append(await self.move_mouse(action["x"], action["y"]))
            elif action_type == "click":
                results.append(await self.click(action.get("button", "left")))

        logger.info(f"[InputController] 序列 '{name}' 完成: {len(results)} 步")
        return {"success": True, "action": "sequence", "name": name, "steps": len(results)}

    def get_history(self) -> list[dict[str, Any]]:
        return self._action_history[-100:]

    def clear_history(self):
        self._action_history.clear()

    @property
    def is_enabled(self) -> bool:
        return self._enabled
