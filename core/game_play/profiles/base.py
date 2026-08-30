"""
游戏 Profile 系统 — 通用游戏陪玩配置管理

结构:
- general.yaml   → 默认配置，所有游戏通用
- 游戏专属.yaml  → 可选覆盖/增强特定游戏

加载逻辑:
  get_profile(game_id) → 合并 general + game_id 专属
  get_profile(None)    → 只用 general
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class GameProfile:
    game_id: str
    game_name: str
    description: str = ""
    system_prompt: str = ""
    camera_strategy: dict[str, Any] = field(default_factory=dict)
    hotkeys: dict[str, str] = field(default_factory=dict)
    control_actions: dict[str, list[str]] = field(default_factory=dict)
    enabled: bool = True

    @property
    def adaptive_fps(self) -> dict[str, float]:
        return self.camera_strategy.get("adaptive_fps", {})

    @property
    def auto_speak(self) -> bool:
        return self.camera_strategy.get("auto_speak", True)

    @property
    def min_urgency_for_speak(self) -> int:
        return self.camera_strategy.get("min_urgency_for_speak", 3)

    @property
    def silence_scenes(self) -> list[str]:
        return self.camera_strategy.get("silence_scenes", [])

    @property
    def speak_cooldown(self) -> float:
        return self.camera_strategy.get("cooldown_between_speaks", 4.0)

    def get_fps_for_scene(self, scene: str) -> float:
        fps_map = self.adaptive_fps
        fps = fps_map.get(scene, fps_map.get("default", 2.0))
        if fps >= 999:
            return float("inf")
        return float(fps)

    def should_silence_scene(self, scene: str) -> bool:
        return scene in self.silence_scenes

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_name": self.game_name,
            "description": self.description,
            "camera_strategy": self.camera_strategy,
            "hotkeys": self.hotkeys,
            "control_actions": self.control_actions,
            "enabled": self.enabled,
        }


class GameProfileManager:
    """游戏配置档案管理器"""

    GENERAL_ID = "general"
    DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config" / "game_profiles"

    def __init__(self, profiles_dir: Optional[Path] = None):
        self._profiles_dir = profiles_dir or self.DEFAULT_PROFILES_DIR
        self._raw: dict[str, dict[str, Any]] = {}
        self.profiles: dict[str, GameProfile] = {}
        self._general: Optional[GameProfile] = None
        self._load_all()

    def _load_all(self):
        if not self._profiles_dir.exists():
            logger.warning(f"[ProfileManager] 目录不存在: {self._profiles_dir}")
            return

        for yaml_file in sorted(self._profiles_dir.glob("*.yaml")):
            try:
                self._load_file(yaml_file)
            except Exception as e:
                logger.error(f"[ProfileManager] 加载 {yaml_file.name} 失败: {e}")

        if self.GENERAL_ID in self._raw:
            self._general = self._build_profile(self._raw[self.GENERAL_ID])
            logger.info(f"[ProfileManager] 通用 Profile 就绪")

        for game_id, data in self._raw.items():
            if game_id == self.GENERAL_ID:
                continue
            profile = self._merge_with_general(data)
            if profile and profile.enabled:
                self.profiles[profile.game_id] = profile
                logger.info(f"[ProfileManager] 游戏专属: {profile.game_name} ({profile.game_id})")

        logger.info(f"[ProfileManager] 共 {len(self.profiles)} 个专属 + 1 通用 Profile")

    def _load_file(self, file_path: Path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return
        game_id = data.get("game_id", file_path.stem)
        self._raw[game_id] = data

    def _build_profile(self, data: dict[str, Any]) -> GameProfile:
        return GameProfile(
            game_id=data.get("game_id", ""),
            game_name=data.get("game_name", ""),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            camera_strategy=data.get("camera_strategy", {}) or {},
            hotkeys=data.get("hotkeys", {}) or {},
            control_actions=data.get("control_actions", {}) or {},
            enabled=data.get("enabled", True),
        )

    def _merge_with_general(self, data: dict[str, Any]) -> Optional[GameProfile]:
        if not self._general:
            return self._build_profile(data)

        import copy

        gen_data = self._raw.get(self.GENERAL_ID, {})

        merged_system = data.get("system_prompt", "")
        if not merged_system:
            merged_system = gen_data.get("system_prompt", "")

        merged_strategy = copy.deepcopy(gen_data.get("camera_strategy", {}) or {})
        for key, val in (data.get("camera_strategy", {}) or {}).items():
            if isinstance(val, dict) and isinstance(merged_strategy.get(key), dict):
                merged_strategy[key].update(val)
            else:
                merged_strategy[key] = val

        merged_hotkeys = copy.deepcopy(gen_data.get("hotkeys", {}) or {})
        merged_hotkeys.update(data.get("hotkeys", {}) or {})

        merged_actions = copy.deepcopy(gen_data.get("control_actions", {}) or {})
        merged_actions.update(data.get("control_actions", {}) or {})

        return GameProfile(
            game_id=data.get("game_id", ""),
            game_name=data.get("game_name", ""),
            description=data.get("description", ""),
            system_prompt=merged_system,
            camera_strategy=merged_strategy,
            hotkeys=merged_hotkeys,
            control_actions=merged_actions,
            enabled=data.get("enabled", True),
        )

    def get_profile(self, game_id: Optional[str] = None) -> Optional[GameProfile]:
        if game_id and game_id in self.profiles:
            return self.profiles[game_id]
        return self._general

    def list_profiles(self) -> list[dict[str, Any]]:
        profiles = [self._general.to_dict()] if self._general else []
        profiles.extend(p.to_dict() for p in self.profiles.values())
        return profiles

    def list_game_ids(self) -> list[str]:
        return list(self.profiles.keys())

    def reload(self):
        self._raw.clear()
        self.profiles.clear()
        self._general = None
        self._load_all()
