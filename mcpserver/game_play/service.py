#!/usr/bin/env python3
"""
游戏陪玩 MCP 服务 — 弥娅的感知器入口

提供 start/stop/list_games/get_status。
画面分析自动注入弥娅主对话上下文（DecisionHub），无需手动调用。
"""

import json
import logging
from typing import Any, Optional

from core.game_play.engine import GamePlayEngine, get_game_play_engine

logger = logging.getLogger("game_play.service")


class GamePlayService:
    """游戏陪玩 MCP 服务"""

    def __init__(self):
        self.name = "game_play"
        self.description = "游戏陪玩感知器 — 画面自动注入弥娅主对话上下文"
        self.version = "1.0.0"
        self._engine: Optional[GamePlayEngine] = None

    async def _get_engine(self) -> GamePlayEngine:
        if self._engine is None:
            self._engine = get_game_play_engine()
            await self._engine.initialize()
        return self._engine

    async def handle_handoff(self, tool_call: dict[str, Any]) -> str:
        tool_name = str(tool_call.get("tool_name", "")).strip().lower()
        try:
            if tool_name == "start_game":
                return await self._start_game(tool_call)
            elif tool_name == "stop_game":
                return await self._stop_game(tool_call)
            elif tool_name == "get_status":
                return await self._get_status(tool_call)
            elif tool_name == "list_games":
                return await self._list_games(tool_call)
            else:
                return json.dumps(
                    {
                        "error": f"未知工具: {tool_name}",
                        "available": ["start_game", "stop_game", "get_status", "list_games"],
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.exception(f"[GamePlay] 异常: {tool_name}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    async def _start_game(self, call: dict[str, Any]) -> str:
        game_id = call.get("game_id")
        voice_enabled = _b(call.get("voice_enabled"), True)
        vision_enabled = _b(call.get("vision_enabled"), True)
        control_enabled = _b(call.get("control_enabled"), False)
        engine = await self._get_engine()
        result = await engine.start_game(
            game_id=game_id,
            voice_enabled=voice_enabled,
            vision_enabled=vision_enabled,
            control_enabled=control_enabled,
        )
        return json.dumps(result, ensure_ascii=False)

    async def _stop_game(self, call: dict[str, Any]) -> str:
        engine = await self._get_engine()
        result = await engine.stop_game()
        return json.dumps(result, ensure_ascii=False)

    async def _get_status(self, call: dict[str, Any]) -> str:
        engine = await self._get_engine()
        return json.dumps(engine.get_status(), ensure_ascii=False)

    async def _list_games(self, call: dict[str, Any]) -> str:
        engine = await self._get_engine()
        return json.dumps({"status": "success", "games": engine.list_games()}, ensure_ascii=False)


def _b(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "0", "no", "off")
    return bool(value)
