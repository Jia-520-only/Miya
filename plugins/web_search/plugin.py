from __future__ import annotations

"""
弥娅 Web Search 插件 — 浏览器使用能力示例

展示如何使用弥娅的 Browser Use Agent 通过插件封装浏览器搜索能力。
弥娅的决策中枢可以通过 action::tool_call 直接调用此插件。
"""

from typing import Any

from plugin_sdk.core.base import MiyaPlugin, miya_plugin, plugin_entry


@miya_plugin(
    plugin_id="miya_web_search",
    name="Web Search",
    version="1.0.0",
    description="让弥娅搜索互联网获取最新信息",
    keywords=["搜索", "查询", "web", "search"],
    category="knowledge",
    auto_start=True,
)
class WebSearchPlugin(MiyaPlugin):
    @plugin_entry(
        description="搜索互联网获取最新信息",
        keywords=["搜索", "查询", "search"],
        category="search",
        timeout=30.0,
    )
    async def search_web(self, query: str, max_results: int = 5) -> dict[str, Any]:
        try:
            from miya_senses.action.browser_use.adapter import BrowserUseExecutor

            executor = BrowserUseExecutor(enabled=True, default_timeout=30.0)
            result = await executor.execute(
                action_id="action::browser_search",
                params={"query": query, "engine": "默认搜索引擎"},
                context=f"搜索: {query}。请在搜索结果页面上提取前 {max_results} 条结果，用中文总结。",
            )

            if result.success:
                return {
                    "success": True,
                    "query": query,
                    "results": result.reply,
                    "session_key": result.session_key,
                }
            return {"success": False, "error": result.error}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @plugin_entry(
        description="读取当前网页内容",
        keywords=["读取", "阅读", "网页"],
        category="read",
        timeout=30.0,
    )
    async def read_webpage(self, url: str = "") -> dict[str, Any]:
        try:
            from miya_senses.action.browser_use.adapter import BrowserUseExecutor

            executor = BrowserUseExecutor(enabled=True, default_timeout=30.0)

            if url:
                await executor.execute(
                    action_id="action::browser_open",
                    params={"url": url},
                )

            result = await executor.execute(
                action_id="action::browser_read_page",
                params={"extract_type": "全文摘要"},
            )

            if result.success:
                return {
                    "success": True,
                    "url": url,
                    "content": result.reply,
                }
            return {"success": False, "error": result.error}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


@miya_plugin(
    plugin_id="miya_screen_companion",
    name="Screen Companion",
    version="1.0.0",
    description="屏幕感知陪伴 — 弥娅能看见佳在做什么并主动陪伴",
    keywords=["屏幕", "陪伴", "感知", "screen"],
    category="social",
    auto_start=True,
)
class ScreenCompanionPlugin(MiyaPlugin):
    @plugin_entry(
        description="查看佳当前在做什么",
        keywords=["屏幕", "观察", "look"],
        category="perception",
        timeout=15.0,
    )
    async def look_at_screen(self) -> dict[str, Any]:
        try:
            from miya_senses.sensors.screen_aware import get_screen_aware

            sa = get_screen_aware()
            if not sa.should_observe:
                last = sa.get_last_observation()
                if last:
                    return {
                        "success": True,
                        "activity": last.detected_activity,
                        "mood": last.mood_hint,
                        "apps": last.detected_apps,
                        "cached": True,
                    }
                return {"success": False, "error": "观察间隔未到且无缓存"}

            observation = await sa.observe()
            return {
                "success": True,
                "activity": observation.detected_activity,
                "description": observation.description,
                "mood": observation.mood_hint,
                "apps": observation.detected_apps,
                "attention_score": observation.attention_score,
                "proactive_score": observation.proactive_trigger_score,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @plugin_entry(
        description="获取佳的近期活动趋势",
        keywords=["趋势", "历史", "活动"],
        category="analytics",
    )
    async def get_activity_trend(self, count: int = 10) -> dict[str, Any]:
        try:
            from miya_senses.sensors.screen_aware import get_screen_aware

            sa = get_screen_aware()
            trend = sa.get_activity_trend()
            return {
                "success": True,
                "trend": trend[-count:],
                "total_observations": len(trend),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
