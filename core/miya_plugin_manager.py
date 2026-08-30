"""
弥娅插件管理器
管理已安装的 AstrBot 插件
"""

import importlib.util
import json
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.PluginManager")


@dataclass
class InstalledPlugin:
    """已安装插件信息"""

    name: str
    description: str = ""
    author: str = ""
    version: str = ""
    enabled: bool = True
    installed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    path: str = ""
    module_name: str = ""
    entry_class: str = ""


class MiyaPluginManager:
    """弥娅插件管理器

    功能：
    1. 安装/卸载插件
    2. 启用/禁用插件
    3. 加载插件到系统
    4. 插件热重载
    """

    PLUGIN_DIR = Path("core/skills/miya_plugins")
    PLUGIN_CONFIG_FILE = "plugin_config.json"

    def __init__(self):
        self.PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        self._plugins: Dict[str, InstalledPlugin] = {}
        self._plugin_modules: Dict[str, Any] = {}
        self._load_plugin_config()

    def _get_config_path(self) -> Path:
        """获取插件配置文件路径"""
        return self.PLUGIN_DIR / self.PLUGIN_CONFIG_FILE

    def _load_plugin_config(self):
        """加载插件配置"""
        config_path = self._get_config_path()
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                for name, info in data.get("plugins", {}).items():
                    self._plugins[name] = InstalledPlugin(
                        name=name,
                        description=info.get("description", ""),
                        author=info.get("author", ""),
                        version=info.get("version", ""),
                        enabled=info.get("enabled", True),
                        installed_at=info.get("installed_at", ""),
                        path=info.get("path", ""),
                        module_name=info.get("module_name", ""),
                        entry_class=info.get("entry_class", ""),
                    )
                logger.info(f"已加载 {len(self._plugins)} 个插件配置")
            except Exception as e:
                logger.warning(f"加载插件配置失败: {e}")

    def _save_plugin_config(self):
        """保存插件配置"""
        config_path = self._get_config_path()
        data = {
            "plugins": {
                name: {
                    "description": p.description,
                    "author": p.author,
                    "version": p.version,
                    "enabled": p.enabled,
                    "installed_at": p.installed_at,
                    "path": p.path,
                    "module_name": p.module_name,
                    "entry_class": p.entry_class,
                }
                for name, p in self._plugins.items()
            }
        }
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def install(self, plugin_name: str, zip_path: Path) -> bool:
        """安装插件

        Args:
            plugin_name: 插件名称
            zip_path: 插件 ZIP 文件路径

        Returns:
            是否成功
        """
        try:
            extract_dir = self.PLUGIN_DIR / plugin_name

            if extract_dir.exists():
                shutil.rmtree(extract_dir)

            extract_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            plugin_info = await self._detect_plugin_info(plugin_name, extract_dir)

            self._plugins[plugin_name] = plugin_info
            self._save_plugin_config()

            os.remove(zip_path)

            logger.info(f"插件 {plugin_name} 安装成功")
            return True

        except Exception as e:
            logger.error(f"安装插件 {plugin_name} 失败: {e}")
            return False

    async def _detect_plugin_info(self, plugin_name: str, plugin_dir: Path) -> InstalledPlugin:
        """检测插件信息"""
        description = ""
        author = ""
        version = "1.0.0"
        module_name = ""
        entry_class = ""

        for py_file in plugin_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            content = py_file.read_text(encoding="utf-8")

            if "description" in content.lower() or "plugin" in content.lower():
                for line in content.split("\n"):
                    if "description" in line.lower() and "=" in line:
                        try:
                            desc = line.split("=")[1].strip().strip('"').strip("'")
                            if len(desc) > 10:
                                description = desc[:200]
                                break
                        except:
                            pass

        for py_file in plugin_dir.rglob("*.py"):
            if py_file.name.endswith("_plugin.py") or py_file.name == "plugin.py":
                module_name = f"core.skills.miya_plugins.{plugin_name}.{py_file.stem}"

                content = py_file.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if "class" in line and "Plugin" in line:
                        try:
                            entry_class = line.split("class")[1].split("(")[0].strip()
                            break
                        except:
                            pass
                break

        return InstalledPlugin(
            name=plugin_name,
            description=description,
            author=author,
            version=version,
            path=str(plugin_dir),
            module_name=module_name,
            entry_class=entry_class,
        )

    async def uninstall(self, plugin_name: str) -> bool:
        """卸载插件"""
        try:
            if plugin_name in self._plugins:
                del self._plugins[plugin_name]

            if plugin_name in self._plugin_modules:
                del self._plugin_modules[plugin_name]

            plugin_dir = self.PLUGIN_DIR / plugin_name
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)

            self._save_plugin_config()

            logger.info(f"插件 {plugin_name} 已卸载")
            return True

        except Exception as e:
            logger.error(f"卸载插件 {plugin_name} 失败: {e}")
            return False

    async def enable(self, plugin_name: str) -> bool:
        """启用插件"""
        if plugin_name in self._plugins:
            self._plugins[plugin_name].enabled = True
            self._save_plugin_config()
            logger.info(f"插件 {plugin_name} 已启用")
            return True
        return False

    async def disable(self, plugin_name: str) -> bool:
        """禁用插件"""
        if plugin_name in self._plugins:
            self._plugins[plugin_name].enabled = False
            self._save_plugin_config()
            logger.info(f"插件 {plugin_name} 已禁用")
            return True
        return False

    def get_installed_plugins(self) -> List[InstalledPlugin]:
        """获取已安装插件列表"""
        return list(self._plugins.values())

    def get_plugin(self, plugin_name: str) -> Optional[InstalledPlugin]:
        """获取指定插件"""
        return self._plugins.get(plugin_name)

    def is_enabled(self, plugin_name: str) -> bool:
        """检查插件是否启用"""
        plugin = self._plugins.get(plugin_name)
        return plugin.enabled if plugin else False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """重载插件"""
        if plugin_name in self._plugin_modules:
            try:
                mod = self._plugin_modules[plugin_name]
                importlib.reload(mod)
                logger.info(f"插件 {plugin_name} 已重载")
                return True
            except Exception as e:
                logger.error(f"重载插件 {plugin_name} 失败: {e}")
                return False
        return False


_manager_instance: Optional[MiyaPluginManager] = None


def get_plugin_manager() -> MiyaPluginManager:
    """获取插件管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MiyaPluginManager()
    return _manager_instance
