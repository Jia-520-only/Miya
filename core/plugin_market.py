"""
弥娅独立插件市场客户端
不依赖 AstrBot 核心，直接连接 AstrBot 插件市场 API
"""

import asyncio
import json
import logging
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import certifi

logger = logging.getLogger("Miya.PluginMarket")


PLUGIN_MARKET_URLS = [
    "https://api.soulter.top/astrbot/plugins",
]

PLUGIN_MARKET_FALLBACK = (
    "https://github.com/AstrBotDevs/AstrBot_Plugins_Collection/raw/refs/heads/main/plugin_cache_original.json"
)

PLUGIN_MD5_URL = "https://api.soulter.top/astrbot/plugins-md5"


@dataclass
class PluginInfo:
    """插件信息"""

    name: str
    description: str
    author: str
    version: str
    download_url: str
    homepage: str = ""
    tags: List[str] = None
    logo: str = ""
    astrbot_version: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class AstrBotPluginMarket:
    """AstrBot 插件市场客户端 - 独立实现"""

    def __init__(self, cache_dir: str = "data/plugin_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "plugins_market.json"
        self._md5_cache_file = self.cache_dir / "plugins_market_md5.json"

    async def get_plugin_list(self, force_refresh: bool = False, custom_url: Optional[str] = None) -> List[PluginInfo]:
        """获取插件市场列表

        Args:
            force_refresh: 强制刷新缓存
            custom_url: 自定义插件源 URL

        Returns:
            插件信息列表
        """
        if not force_refresh:
            cached_data = self._load_cache()
            if cached_data and self._is_cache_valid():
                logger.info("使用缓存的插件市场数据")
                return self._parse_plugins(cached_data)

        remote_data = await self._fetch_remote(custom_url)
        if remote_data:
            self._save_cache(remote_data)
            return self._parse_plugins(remote_data)

        cached_data = self._load_cache()
        if cached_data:
            logger.warning("使用过期缓存数据")
            return self._parse_plugins(cached_data)

        return []

    async def _fetch_remote(self, custom_url: Optional[str] = None) -> Optional[Dict]:
        """从远程获取插件数据"""
        urls = [custom_url] if custom_url else PLUGIN_MARKET_URLS
        urls.append(PLUGIN_MARKET_FALLBACK)

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        for url in urls:
            try:
                async with (
                    aiohttp.ClientSession(trust_env=True, connector=connector) as session,
                    session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response,
                ):
                    if response.status == 200:
                        try:
                            data = await response.json()
                        except aiohttp.ContentTypeError:
                            text = await response.text()
                            data = json.loads(text)

                        if data:
                            logger.info(f"成功获取插件市场数据: {len(data)} 个插件")
                            await self._update_md5()
                            return data

            except asyncio.TimeoutError:
                logger.warning(f"获取插件市场超时: {url}")
            except Exception as e:
                logger.warning(f"获取插件市场失败: {url}, {e}")

        return None

    async def _update_md5(self):
        """更新 MD5 缓存"""
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            async with (
                aiohttp.ClientSession(trust_env=True, connector=connector) as session,
                session.get(PLUGIN_MD5_URL, timeout=aiohttp.ClientTimeout(total=10)) as response,
            ):
                if response.status == 200:
                    md5_data = await response.json()
                    self._md5_cache_file.write_text(json.dumps(md5_data, ensure_ascii=False), encoding="utf-8")

        except Exception as e:
            logger.warning(f"更新 MD5 失败: {e}")

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache_file.exists():
            return False

        if not self._md5_cache_file.exists():
            return False

        try:
            current_md5 = self._load_current_md5()
            cached_md5 = json.loads(self._md5_cache_file.read_text(encoding="utf-8")).get("md5", "")
            return current_md5 == cached_md5
        except:
            return False

    def _load_current_md5(self) -> str:
        """加载当前缓存的 MD5"""
        try:
            cache_data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return cache_data.get("_meta", {}).get("md5", "")
        except:
            return ""

    def _load_cache(self) -> Optional[Dict]:
        """加载缓存"""
        if self._cache_file.exists():
            try:
                return json.loads(self._cache_file.read_text(encoding="utf-8"))
            except:
                pass
        return None

    def _save_cache(self, data: Dict):
        """保存缓存"""
        try:
            self._cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"保存插件缓存失败: {e}")

    def _parse_plugins(self, data: Dict) -> List[PluginInfo]:
        """解析插件数据"""
        plugins = []
        for name, info in data.items():
            if name.startswith("_"):
                continue

            try:
                plugin = PluginInfo(
                    name=name,
                    description=info.get("desc", ""),
                    author=info.get("author", "未知"),
                    version=info.get("tag_name", "1.0.0"),
                    download_url=info.get("download_url", ""),
                    homepage=info.get("homepage", ""),
                    tags=info.get("tags", []),
                    logo=info.get("logo", ""),
                    astrbot_version=info.get("astrbot_version", ""),
                )
                plugins.append(plugin)
            except Exception as e:
                logger.warning(f"解析插件 {name} 失败: {e}")

        return sorted(plugins, key=lambda x: x.name)

    async def download_plugin(self, plugin: PluginInfo, target_dir: Path) -> bool:
        """下载插件到目标目录

        Args:
            plugin: 插件信息
            target_dir: 目标目录

        Returns:
            是否成功
        """
        if not plugin.download_url:
            logger.error(f"插件 {plugin.name} 没有下载链接")
            return False

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        try:
            async with (
                aiohttp.ClientSession(trust_env=True, connector=connector) as session,
                session.get(plugin.download_url, timeout=aiohttp.ClientTimeout(total=120)) as response,
            ):
                if response.status == 200:
                    content = await response.read()

                    zip_path = target_dir / f"{plugin.name}.zip"
                    zip_path.write_bytes(content)

                    logger.info(f"插件 {plugin.name} 下载成功")
                    return True
                else:
                    logger.error(f"下载插件失败: {response.status}")

        except Exception as e:
            logger.error(f"下载插件 {plugin.name} 异常: {e}")

        return False


_market_instance: Optional[AstrBotPluginMarket] = None


def get_plugin_market() -> AstrBotPluginMarket:
    """获取插件市场单例"""
    global _market_instance
    if _market_instance is None:
        _market_instance = AstrBotPluginMarket()
    return _market_instance
