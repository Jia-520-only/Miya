from __future__ import annotations

"""
弥娅插件市场 — 插件的发现、下载、评分

弥娅的「商店」— 佳可以从市场中浏览和安装社区分享的插件。
当前为本地市场模式，支持后续扩展到远程仓库。
"""

import hashlib
import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from plugin_sdk.core.registry import PluginRegistry, get_plugin_registry

logger = logging.getLogger("miya.plugin.market")

_MARKET_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "plugin_market"


@dataclass
class MarketEntry:
    """市场中的一个插件条目"""

    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    keywords: list[str] = field(default_factory=list)
    category: str = "utility"
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    install_size_mb: float = 0.0
    min_sdk_version: str = "1.0.0"
    last_updated: str = ""
    installed: bool = False
    installed_version: str = ""
    compatible: bool = True
    homepage: str = ""
    source_url: str = ""


class PluginMarket:
    """
    弥娅插件市场。

    功能:
      - 搜索/浏览插件
      - 安装/卸载
      - 评分
      - 与本地注册表同步状态
    """

    def __init__(self, registry: Optional[PluginRegistry] = None) -> None:
        self._registry = registry or get_plugin_registry()
        self._market_file = _MARKET_ROOT / "market_index.json"
        self._repos_dir = _MARKET_ROOT / "repos"
        self._market_file.parent.mkdir(parents=True, exist_ok=True)
        self._repos_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MarketEntry] = {}
        self._load_market()

    def _load_market(self) -> None:
        if self._market_file.exists():
            try:
                data = json.loads(self._market_file.read_text(encoding="utf-8"))
                for item in data.get("plugins", []):
                    entry = MarketEntry(**item)
                    self._entries[entry.plugin_id] = entry
                logger.info(f"[Market] 加载 {len(self._entries)} 个市场条目")
            except Exception as exc:
                logger.warning(f"[Market] 加载市场索引失败: {exc}")

    def _save_market(self) -> None:
        data = {
            "updated_at": datetime.now().isoformat(),
            "plugin_count": len(self._entries),
            "plugins": [
                {
                    "plugin_id": e.plugin_id,
                    "name": e.name,
                    "version": e.version,
                    "description": e.description,
                    "author": e.author,
                    "keywords": e.keywords,
                    "category": e.category,
                    "downloads": e.downloads,
                    "rating": e.rating,
                    "rating_count": e.rating_count,
                    "install_size_mb": e.install_size_mb,
                    "min_sdk_version": e.min_sdk_version,
                    "last_updated": e.last_updated,
                    "homepage": e.homepage,
                    "source_url": e.source_url,
                }
                for e in self._entries.values()
            ],
        }
        self._market_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _sync_installed_status(self) -> None:
        installed = set(self._registry.list_plugins())
        for entry in self._entries.values():
            if entry.plugin_id in installed:
                entry.installed = True
                meta = self._registry.get_metadata(entry.plugin_id)
                if meta:
                    entry.installed_version = meta.version
                    entry.compatible = meta.min_sdk_version <= entry.min_sdk_version

    # ---- 搜索 ----

    def search(
        self,
        query: str = "",
        category: str = "",
        sort_by: str = "downloads",
        limit: int = 20,
    ) -> list[MarketEntry]:
        self._sync_installed_status()
        results = list(self._entries.values())

        if query:
            q = query.lower()
            results = [
                e
                for e in results
                if q in e.name.lower() or q in e.description.lower() or any(q in k.lower() for k in e.keywords)
            ]

        if category:
            results = [e for e in results if e.category == category]

        if sort_by == "downloads":
            results.sort(key=lambda e: e.downloads, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda e: e.rating, reverse=True)
        elif sort_by == "name":
            results.sort(key=lambda e: e.name.lower())
        elif sort_by == "updated":
            results.sort(key=lambda e: e.last_updated, reverse=True)

        return results[:limit]

    def get_entry(self, plugin_id: str) -> Optional[MarketEntry]:
        self._sync_installed_status()
        return self._entries.get(plugin_id)

    def list_categories(self) -> list[str]:
        return sorted(set(e.category for e in self._entries.values()))

    # ---- 安装 ----

    async def install(self, plugin_id: str) -> dict[str, Any]:
        entry = self._entries.get(plugin_id)
        if entry is None:
            return {"success": False, "error": f"插件 {plugin_id} 不在市场中"}
        if entry.installed:
            return {
                "success": False,
                "error": f"插件 {plugin_id} 已安装 (v{entry.installed_version})",
            }

        repo_dir = self._repos_dir / plugin_id
        if not repo_dir.exists():
            return {
                "success": False,
                "error": f"插件 {plugin_id} 的本地仓库不存在: {repo_dir}",
            }

        plugin_root = _MARKET_ROOT.parent.parent / "plugins" / plugin_id
        plugin_root.mkdir(parents=True, exist_ok=True)

        try:
            for item in repo_dir.iterdir():
                dest = plugin_root / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            entry.downloads += 1
            entry.installed = True
            entry.installed_version = entry.version
            self._save_market()

            logger.info(f"[Market] 安装插件: {plugin_id} v{entry.version}")
            return {"success": True, "plugin_id": plugin_id, "version": entry.version}
        except Exception as exc:
            logger.error(f"[Market] 安装插件 {plugin_id} 失败: {exc}")
            return {"success": False, "error": str(exc)}

    async def uninstall(self, plugin_id: str) -> dict[str, Any]:
        entry = self._entries.get(plugin_id)
        if entry is None or not entry.installed:
            return {"success": False, "error": f"插件 {plugin_id} 未安装"}

        if plugin_id in self._registry._plugins:
            await self._registry.stop_plugin(plugin_id)
            self._registry.unregister(plugin_id)

        plugin_root = _MARKET_ROOT.parent.parent / "plugins" / plugin_id
        if plugin_root.exists():
            shutil.rmtree(plugin_root, ignore_errors=True)

        entry.installed = False
        entry.installed_version = ""
        self._save_market()

        logger.info(f"[Market] 卸载插件: {plugin_id}")
        return {"success": True, "plugin_id": plugin_id}

    async def update(self, plugin_id: str) -> dict[str, Any]:
        entry = self._entries.get(plugin_id)
        if entry is None:
            return {"success": False, "error": f"插件 {plugin_id} 不在市场中"}
        if not entry.installed:
            return {"success": False, "error": f"插件 {plugin_id} 未安装"}

        await self.uninstall(plugin_id)
        return await self.install(plugin_id)

    def rate(self, plugin_id: str, rating: float) -> dict[str, Any]:
        entry = self._entries.get(plugin_id)
        if entry is None:
            return {"success": False, "error": f"插件 {plugin_id} 不存在"}

        rating = max(0.0, min(5.0, float(rating)))
        total = entry.rating * entry.rating_count
        entry.rating_count += 1
        entry.rating = (total + rating) / entry.rating_count
        self._save_market()

        return {
            "success": True,
            "plugin_id": plugin_id,
            "new_rating": round(entry.rating, 1),
            "rating_count": entry.rating_count,
        }

    def add_to_market(self, entry: MarketEntry) -> bool:
        if entry.plugin_id in self._entries:
            logger.warning(f"[Market] 条目已存在: {entry.plugin_id}")
            return False
        entry.last_updated = datetime.now().isoformat()
        self._entries[entry.plugin_id] = entry
        self._save_market()
        logger.info(f"[Market] 添加市场条目: {entry.plugin_id}")
        return True

    def remove_from_market(self, plugin_id: str) -> bool:
        if plugin_id not in self._entries:
            return False
        del self._entries[plugin_id]
        self._save_market()
        return True


_market: Optional[PluginMarket] = None


def get_plugin_market(registry: Optional[PluginRegistry] = None) -> PluginMarket:
    global _market
    if _market is None:
        _market = PluginMarket(registry)
    return _market
