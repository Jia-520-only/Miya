"""Config Manager"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".miya" / "config.json"
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.config_path.exists():
            self._config = json.loads(self.config_path.read_text())

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self._config, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save()

    def delete(self, key: str):
        self._config.pop(key, None)
        self.save()

    def get_all(self) -> Dict[str, Any]:
        return self._config.copy()


_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager
