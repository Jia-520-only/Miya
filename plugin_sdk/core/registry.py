from __future__ import annotations

"""
弥娅插件注册表 — 插件的发现、加载、生命周期管理

三阶段加载:
  1. Discover  — 扫描 plugin_roots 发现所有插件
  2. Sort     — 拓扑排序解决依赖
  3. Load     — 按顺序初始化
"""

import asyncio
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from plugin_sdk.core.base import MiyaPlugin, PluginEntry, PluginMeta

logger = logging.getLogger("miya.plugin.registry")

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


class PluginRegistry:
    """
    弥娅插件注册表。

    单例模式，全局共享一个注册表实例。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, MiyaPlugin] = {}
        self._metadata: dict[str, PluginMeta] = {}
        self._plugin_roots: list[Path] = []
        self._load_order: list[str] = []
        self._started_count = 0

    # ---- 发现 ----

    def add_plugin_root(self, path: str | Path) -> None:
        p = Path(path).resolve()
        if p.exists() and p.is_dir() and p not in self._plugin_roots:
            self._plugin_roots.append(p)
            logger.info(f"[PluginRegistry] 添加插件根目录: {p}")

    def discover(self) -> list[Path]:
        """扫描所有 plugin_roots，发现插件目录"""
        candidates: list[Path] = []
        for root in self._plugin_roots:
            if not root.exists():
                continue
            for item in root.iterdir():
                if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("."):
                    if (
                        (item / "plugin.toml").exists()
                        or (item / "plugin.json").exists()
                        or (item / "plugin.yaml").exists()
                        or (item / "plugin.yml").exists()
                    ):
                        candidates.append(item)
        logger.info(f"[PluginRegistry] 发现 {len(candidates)} 个插件候选")
        return candidates

    # ---- 元数据 ----

    def scan_metadata(self, path: Path) -> Optional[PluginMeta]:
        """从插件目录读取元数据"""
        for manifest_name in ("plugin.toml", "plugin.json", "plugin.yaml", "plugin.yml"):
            manifest = path / manifest_name
            if not manifest.exists():
                continue

            try:
                if manifest_name.endswith((".yaml", ".yml")):
                    import yaml

                    with open(manifest, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                elif manifest_name.endswith(".json"):
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                else:  # toml
                    try:
                        import tomllib
                    except ImportError:
                        import tomli as tomllib
                    with open(manifest, "rb") as f:
                        data = tomllib.load(f)

                plugin_data = data.get("plugin", data)
                return PluginMeta(
                    plugin_id=plugin_data.get("plugin_id", path.name),
                    name=plugin_data.get("name", path.name),
                    version=str(plugin_data.get("version", "1.0.0")),
                    description=plugin_data.get("description", ""),
                    author=plugin_data.get("author", ""),
                    keywords=list(plugin_data.get("keywords", [])),
                    category=plugin_data.get("category", "utility"),
                    auto_start=plugin_data.get("auto_start", False),
                    permissions=list(plugin_data.get("permissions", [])),
                    dependencies=list(plugin_data.get("dependencies", [])),
                    homepage=plugin_data.get("homepage", ""),
                    source="local",
                )
            except Exception as exc:
                logger.warning(f"[PluginRegistry] 读取 {manifest} 失败: {exc}")

        return None

    # ---- 注册 ----

    def register(self, plugin: MiyaPlugin) -> bool:
        pid = plugin.meta.plugin_id
        if pid in self._plugins:
            logger.warning(f"[PluginRegistry] 插件 {pid} 已注册，跳过")
            return False
        self._plugins[pid] = plugin
        self._metadata[pid] = plugin.meta
        plugin.collect_entries()
        logger.info(f"[PluginRegistry] 注册插件: {pid} ({plugin.meta.name})")
        return True

    def unregister(self, plugin_id: str) -> bool:
        if plugin_id not in self._plugins:
            return False
        del self._plugins[plugin_id]
        self._metadata.pop(plugin_id, None)
        logger.info(f"[PluginRegistry] 注销插件: {plugin_id}")
        return True

    # ---- 拓扑排序 ----

    def resolve_dependencies(self) -> list[str]:
        """拓扑排序插件加载顺序"""
        adj: dict[str, list[str]] = {}
        indeg: dict[str, int] = {pid: 0 for pid in self._metadata}

        for pid, meta in self._metadata.items():
            adj.setdefault(pid, [])
            for dep in meta.dependencies:
                if dep in self._metadata:
                    adj.setdefault(dep, []).append(pid)
                    indeg[pid] = indeg.get(pid, 0) + 1
                else:
                    logger.warning(f"[PluginRegistry] 插件 {pid} 依赖 {dep} 未找到")

        queue = [pid for pid, d in indeg.items() if d == 0]
        order: list[str] = []

        while queue:
            pid = queue.pop(0)
            order.append(pid)
            for neighbor in adj.get(pid, []):
                indeg[neighbor] -= 1
                if indeg[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._metadata):
            missing = set(self._metadata) - set(order)
            logger.error(f"[PluginRegistry] 依赖循环检测到: {missing}")

        self._load_order = order
        return list(order)

    # ---- 生命周期 ----

    async def load_all(self) -> dict[str, bool]:
        """按依赖顺序加载所有插件"""
        self.resolve_dependencies()
        results: dict[str, bool] = {}

        for pid in self._load_order:
            if pid not in self._plugins:
                results[pid] = False
                continue
            plugin = self._plugins[pid]
            try:
                await plugin.on_startup()
                self._started_count += 1
                results[pid] = True
            except Exception as exc:
                logger.error(f"[PluginRegistry] 启动插件 {pid} 失败: {exc}")
                results[pid] = False

        return results

    async def shutdown_all(self) -> None:
        """反序关闭所有插件"""
        for pid in reversed(self._load_order):
            if pid in self._plugins:
                try:
                    await self._plugins[pid].on_shutdown()
                except Exception as exc:
                    logger.error(f"[PluginRegistry] 关闭插件 {pid} 失败: {exc}")
        self._started_count = 0

    async def start_plugin(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return False
        try:
            await plugin.on_startup()
            self._started_count += 1
            return True
        except Exception as exc:
            logger.error(f"[PluginRegistry] 启动插件 {plugin_id} 失败: {exc}")
            return False

    async def stop_plugin(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return False
        try:
            await plugin.on_shutdown()
            self._started_count = max(0, self._started_count - 1)
            return True
        except Exception as exc:
            logger.error(f"[PluginRegistry] 关闭插件 {plugin_id} 失败: {exc}")
            return False

    # ---- 查询 ----

    def get_plugin(self, plugin_id: str) -> Optional[MiyaPlugin]:
        return self._plugins.get(plugin_id)

    def get_metadata(self, plugin_id: str) -> Optional[PluginMeta]:
        return self._metadata.get(plugin_id)

    def list_plugins(self, category: str = "", keyword: str = "") -> list[PluginMeta]:
        result = list(self._metadata.values())
        if category:
            result = [m for m in result if m.category == category]
        if keyword:
            kw = keyword.lower()
            result = [
                m
                for m in result
                if kw in m.name.lower() or kw in m.description.lower() or any(kw in k.lower() for k in m.keywords)
            ]
        return result

    def get_all_entries(self) -> dict[str, list[PluginEntry]]:
        result: dict[str, list[PluginEntry]] = {}
        for pid, plugin in self._plugins.items():
            entries = list(plugin.collect_entries().values())
            if entries:
                result[pid] = entries
        return result

    def find_entry(self, name: str) -> Optional[tuple[MiyaPlugin, PluginEntry]]:
        for pid, plugin in self._plugins.items():
            entries = plugin.collect_entries()
            if name in entries:
                return plugin, entries[name]
        return None

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    @property
    def started_count(self) -> int:
        return self._started_count

    def health_check(self) -> dict:
        results = {}
        for pid, plugin in self._plugins.items():
            try:
                results[pid] = {
                    "healthy": plugin._started,
                    "entries": len(plugin.collect_entries()),
                }
            except Exception:
                results[pid] = {"healthy": False, "error": "check failed"}
        return results


_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
        _registry.add_plugin_root(_PLUGIN_ROOT / "plugins")
    return _registry
