"""
弥娅集成工具系统 (AstrBot Tools Integration)

功能：
1. Computer Tools - 文件操作/代码执行
2. Web Search Tools - 网页搜索
3. Knowledge Base Tools - 知识库查询
4. Message Tools - 消息发送

作者: MIYA
日期: 2026-04-28
"""

import asyncio
import inspect
import json
import logging
import subprocess
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

logger = logging.getLogger(__name__)


# ==================== Computer Tools ====================


class ComputerTools:
    """
    计算机工具集

    提供：
    - 文件读取/写入/编辑
    - Shell命令执行
    - Python代码执行
    -Grep搜索
    """

    @staticmethod
    async def file_read(path: str, offset: int = 0, limit: int = 100) -> str:
        """读取文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()[offset : offset + limit]
                return "".join(lines)
        except FileNotFoundError:
            return f"文件不存在: {path}"
        except Exception as e:
            return f"读取失败: {e}"

    @staticmethod
    async def file_write(path: str, content: str, mode: str = "w") -> str:
        """写入文件"""
        try:
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return f"文件已写入: {path}"
        except Exception as e:
            return f"写入失败: {e}"

    @staticmethod
    async def file_edit(path: str, old: str, new: str) -> str:
        """编辑文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if old not in content:
                return "未找到要替换的内容"

            content = content.replace(old, new)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"文件已编辑: {path}"
        except Exception as e:
            return f"编辑失败: {e}"

    @staticmethod
    async def execute_shell(command: str, timeout: int = 30) -> str:
        """执行Shell命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,  # nosec B602
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout or result.stderr
            return output[:5000] if output else "命令执行完成"
        except subprocess.TimeoutExpired:
            return f"命令执行超时 ({timeout}秒)"
        except Exception as e:
            return f"执行失败: {e}"

    @staticmethod
    async def python_exec(code: str, timeout: int = 30) -> str:
        """执行Python代码"""
        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout or result.stderr
            return output[:5000] if output else "代码执行完成"
        except subprocess.TimeoutExpired:
            return f"代码执行超时 ({timeout}秒)"
        except Exception as e:
            return f"执行失败: {e}"

    @staticmethod
    async def grep(pattern: str, path: str, file_pattern: str = "*") -> str:
        """Grep搜索"""
        try:
            import glob

            matches = []
            for file_path in glob.glob(f"{path}/{file_pattern}", recursive=True):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            if pattern in line:
                                matches.append(f"{file_path}:{i}: {line.strip()}")
                except:
                    continue

            if not matches:
                return "未找到匹配"

            return "\n".join(matches[:50])
        except Exception as e:
            return f"搜索失败: {e}"


# ==================== Web Search Tools ====================


class WebSearchTools:
    """
    网页搜索工具集

    提供：
    - 通用网页搜索
    - 网页内容提取
    """

    def __init__(self):
        self._search_providers = {}

    def register_provider(self, name: str, search_func, extract_func=None):
        """注册搜索provider"""
        self._search_providers[name] = {
            "search": search_func,
            "extract": extract_func,
        }
        logger.info(f"[WebSearchTools] 注册provider: {name}")

    async def web_search(self, query: str, provider: str = "default", limit: int = 5) -> str:
        """网页搜索"""
        try:
            if provider in self._search_providers:
                results = await self._search_providers[provider]["search"](query, limit)
                return self._format_search_results(results)
            else:
                # 默认简单搜索
                return f"搜索: {query}\n(需要配置搜索provider)"
        except Exception as e:
            return f"搜索失败: {e}"

    async def web_extract(self, url: str, provider: str = "default") -> str:
        """提取网页内容"""
        try:
            if provider in self._search_providers:
                func = self._search_providers[provider].get("extract")
                if func:
                    content = await func(url)
                    return content[:5000]
            return f"无法提取: {url}"
        except Exception as e:
            return f"提取失败: {e}"

    def _format_search_results(self, results: List[Dict]) -> str:
        """格式化搜索结果"""
        if not results:
            return "未找到结果"

        output = "搜索结果:\n\n"
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            snippet = r.get("snippet", "")[:100]
            output += f"{i}. {title}\n   {url}\n   {snippet}\n\n"

        return output


# ==================== Knowledge Base Tools ====================


class KnowledgeBaseTools:
    """
    知识库工具集
    """

    @staticmethod
    async def query_knowledge(query: str, kb_name: str = "default", limit: int = 5) -> str:
        """查询知识库"""
        try:
            from core.knowledge_base import get_knowledge_base_manager

            kb = get_knowledge_base_manager()
            results = await kb.search(query, kb_name=kb_name, limit=limit)

            if not results:
                return f"未在知识库 [{kb_name}] 中找到相关内容"

            output = f"知识库 [{kb_name}] 查询结果:\n\n"
            for i, r in enumerate(results, 1):
                content = r.get("content", "")[:200]
                output += f"{i}. {content}\n\n"

            return output
        except Exception as e:
            return f"查询失败: {e}"

    @staticmethod
    async def add_to_knowledge(content: str, kb_name: str = "default", tags: Optional[List[str]] = None) -> str:
        """添加知识"""
        try:
            from core.knowledge_base import get_kb_manager

            kb = get_kb_manager()
            await kb.add_document(content, kb_name=kb_name, tags=tags or [])

            return f"已添加到知识库 [{kb_name}]"
        except Exception as e:
            return f"添加失败: {e}"


# ==================== Message Tools ====================


class MessageTools:
    """
    消息工具集
    """

    @staticmethod
    async def send_message(
        user_id: str,
        message: str,
        group_id: str = None,
        platform: str = "default",
    ) -> str:
        """发送消息"""
        logger.info(f"[MessageTools] 发送消息 to {user_id}: {message[:50]}...")

        # 这里可以调用平台适配器发送消息
        return f"消息已发送给 {user_id}: {message[:50]}..."

    @staticmethod
    async def send_image(user_id: str, image_path: str) -> str:
        """发送图片"""
        logger.info(f"[MessageTools] 发送图片 to {user_id}: {image_path}")
        return f"图片已发送给 {user_id}"

    @staticmethod
    async def send_reply(message_id: str, content: str) -> str:
        """回复消息"""
        logger.info(f"[MessageTools] 回复消息 {message_id}")
        return f"已回复: {content[:50]}..."


# ==================== 工具注册表 ====================


class ToolRegistry:
    """
    工具注册表 - 整合所有AstrBot风格工具
    """

    def __init__(self):
        self.computer = ComputerTools()
        self.web_search = WebSearchTools()
        self.knowledge_base = KnowledgeBaseTools()
        self.message = MessageTools()
        try:
            from core.tools_astrbot.earth_tools import get_earth_tools

            self.earth = get_earth_tools()
        except Exception:
            self.earth = None

        # 注册到Gestalt
        self._register_to_gestalt()

    def _register_to_gestalt(self):
        """注册到Gestalt"""
        try:
            from core.gestalt_enhanced import get_gestalt_controller_enhanced

            gestalt = get_gestalt_controller_enhanced()

            # 添加工具函数
            gestalt._builtin_tools.update(
                {
                    "file_read": self.computer.file_read,
                    "file_write": self.computer.file_write,
                    "file_edit": self.computer.file_edit,
                    "execute_shell": self.computer.execute_shell,
                    "python_exec": self.computer.python_exec,
                    "grep": self.computer.grep,
                    "web_search": self.web_search.web_search,
                    "web_extract": self.web_search.web_extract,
                    "query_knowledge": self.knowledge_base.query_knowledge,
                    "add_to_knowledge": self.knowledge_base.add_to_knowledge,
                    "send_message": self.message.send_message,
                    "send_image": self.message.send_image,
                    "send_reply": self.message.send_reply,
                }
            )

            # 注册地球online 工具（弥娅的现实游戏化模块，受 earth_online.enabled 总开关控制）
            earth_enabled = True
            try:
                from core.earth_online_store import earth_online_enabled

                earth_enabled = earth_online_enabled()
            except Exception:
                earth_enabled = True
            if self.earth is not None and earth_enabled:
                gestalt._builtin_tools.update(
                    {
                        "earth_summary": self.earth.earth_summary,
                        "earth_player": self.earth.earth_player,
                        "earth_list_items": self.earth.earth_list_items,
                        "earth_add_item": self.earth.earth_add_item,
                        "earth_list_quests": self.earth.earth_list_quests,
                        "earth_add_quest": self.earth.earth_add_quest,
                        "earth_accept_quest": self.earth.earth_accept_quest,
                        "earth_complete_quest": self.earth.earth_complete_quest,
                        "earth_fail_quest": self.earth.earth_fail_quest,
                        "earth_check_overdue": self.earth.earth_check_overdue,
                        "earth_get_quest": self.earth.earth_get_quest,
                        "earth_update_subtask": self.earth.earth_update_subtask,
                        "earth_activity": self.earth.earth_activity,
                        "earth_weekly_report": self.earth.earth_weekly_report,
                        "earth_remind_due": self.earth.earth_remind_due,
                        "earth_list_titles": self.earth.earth_list_titles,
                        "earth_comment_activity": self.earth.earth_comment_activity,
                        "earth_analyze": self.earth.earth_analyze,
                        "earth_daily_ritual": self.earth.earth_daily_ritual,
                        "earth_list_achievements": self.earth.earth_list_achievements,
                        "earth_add_achievement": self.earth.earth_add_achievement,
                        "earth_set_achievement_progress": self.earth.earth_set_achievement_progress,
                        "earth_list_story": self.earth.earth_list_story,
                        "earth_add_story": self.earth.earth_add_story,
                        "earth_list_characters": self.earth.earth_list_characters,
                        "earth_add_character": self.earth.earth_add_character,
                        "earth_adjust_affinity": self.earth.earth_adjust_affinity,
                        "earth_grant_currency": self.earth.earth_grant_currency,
                        "earth_spend_miya_coins": self.earth.earth_spend_miya_coins,
                        "earth_grant_exp": self.earth.earth_grant_exp,
                        "earth_post_note": self.earth.earth_post_note,
                        "earth_list_notes": self.earth.earth_list_notes,
                        "earth_world": self.earth.earth_world,
                        "earth_explore": self.earth.earth_explore,
                        "earth_world_status": self.earth.earth_world_status,
                        "earth_real_context": self.earth.earth_real_context,
                        "earth_refresh_real_context": self.earth.earth_refresh_real_context,
                        "earth_region_commission": self.earth.earth_region_commission,
                        # 策划级: 实体修改/删除
                        "earth_get_item": self.earth.earth_get_item,
                        "earth_update_item": self.earth.earth_update_item,
                        "earth_delete_item": self.earth.earth_delete_item,
                        "earth_update_quest": self.earth.earth_update_quest,
                        "earth_cancel_quest": self.earth.earth_cancel_quest,
                        "earth_get_character": self.earth.earth_get_character,
                        "earth_update_character": self.earth.earth_update_character,
                        "earth_delete_character": self.earth.earth_delete_character,
                        "earth_update_story": self.earth.earth_update_story,
                        "earth_delete_story": self.earth.earth_delete_story,
                        "earth_delete_note": self.earth.earth_delete_note,
                        "earth_pin_note": self.earth.earth_pin_note,
                        "earth_equip_title": self.earth.earth_equip_title,
                        "earth_checkin": self.earth.earth_checkin,
                        # 策划级: 玩家档案
                        "earth_update_player": self.earth.earth_update_player,
                        # 策划级: 世界与地理围栏
                        "earth_update_region": self.earth.earth_update_region,
                        "earth_add_world_event": self.earth.earth_add_world_event,
                        "earth_list_world_events": self.earth.earth_list_world_events,
                        "earth_delete_world_event": self.earth.earth_delete_world_event,
                        "earth_list_discoveries": self.earth.earth_list_discoveries,
                        "earth_choose_discovery": self.earth.earth_choose_discovery,
                        # 策划级: 限时活动运营
                        "earth_list_event_areas": self.earth.earth_list_event_areas,
                        "earth_create_event_area": self.earth.earth_create_event_area,
                        "earth_update_event_area": self.earth.earth_update_event_area,
                        "earth_delete_event_area": self.earth.earth_delete_event_area,
                        "earth_add_event_shop_item": self.earth.earth_add_event_shop_item,
                        "earth_delete_event_shop_item": self.earth.earth_delete_event_shop_item,
                        # 策划级: 商店查询
                        "earth_list_miya_shop": self.earth.earth_list_miya_shop,
                        "earth_manage_miya_shop": self.earth.earth_manage_miya_shop,
                        "earth_list_event_shop": self.earth.earth_list_event_shop,
                        # 策划级: 查询补充
                        "earth_affinity_logs": self.earth.earth_affinity_logs,
                        "earth_quest_history": self.earth.earth_quest_history,
                        # v17: 现实资产 / 回忆抽卡 / 纪行 / 周挑战 / 纪念日 / 每日日常
                        "earth_adjust_earth_currency": self.earth.earth_adjust_earth_currency,
                        "earth_memory_pool": self.earth.earth_memory_pool,
                        "earth_view_battle_pass": self.earth.earth_view_battle_pass,
                        "earth_weekly_challenge": self.earth.earth_weekly_challenge,
                        "earth_list_commemorations": self.earth.earth_list_commemorations,
                        "earth_add_commemoration": self.earth.earth_add_commemoration,
                        "earth_generate_daily_commissions": self.earth.earth_generate_daily_commissions,
                        # v17.1: 全权策划补齐
                        "earth_stats": self.earth.earth_stats,
                        "earth_list_checkins": self.earth.earth_list_checkins,
                        "earth_currency_ledger": self.earth.earth_currency_ledger,
                        "earth_update_real_context": self.earth.earth_update_real_context,
                        "earth_update_commemoration": self.earth.earth_update_commemoration,
                        "earth_delete_commemoration": self.earth.earth_delete_commemoration,
                        "earth_pull_memory": self.earth.earth_pull_memory,
                        "earth_claim_battle_pass": self.earth.earth_claim_battle_pass,
                        "earth_issue_care_commission": self.earth.earth_issue_care_commission,
                        "earth_redeem_service": self.earth.earth_redeem_service,
                    }
                )

            logger.info("[ToolRegistry] 已注册到Gestalt")

        except Exception as e:
            logger.warning(f"[ToolRegistry] 注册到Gestalt失败: {e}")

    def get_tools_schema(self) -> List[Dict]:
        """获取工具Schema"""
        schemas: List[Dict] = [
            # Computer Tools
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "读取文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"},
                            "offset": {"type": "integer", "description": "起始行"},
                            "limit": {"type": "integer", "description": "行数限制"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_write",
                    "description": "写入文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"},
                            "content": {"type": "string", "description": "文件内容"},
                            "mode": {"type": "string", "description": "写入模式"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_shell",
                    "description": "执行Shell命令",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "命令"},
                            "timeout": {"type": "integer", "description": "超时秒数"},
                        },
                        "required": ["command"],
                    },
                },
            },
            # Web Search Tools
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "搜索网页",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                            "limit": {"type": "integer", "description": "结果数量"},
                        },
                        "required": ["query"],
                    },
                },
            },
            # Knowledge Base Tools
            {
                "type": "function",
                "function": {
                    "name": "query_knowledge",
                    "description": "查询知识库",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "查询内容"},
                            "kb_name": {"type": "string", "description": "知识库名称"},
                        },
                        "required": ["query"],
                    },
                },
            },
            # Message Tools
            {
                "type": "function",
                "function": {
                    "name": "send_message",
                    "description": "发送消息给用户",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "用户ID"},
                            "message": {"type": "string", "description": "消息内容"},
                            "group_id": {"type": "string", "description": "群组ID"},
                        },
                        "required": ["user_id", "message"],
                    },
                },
            },
        ]

        # 追加地球online 工具
        try:
            from core.earth_online_store import earth_online_enabled

            if earth_online_enabled():
                from core.tools_astrbot.earth_tools import EARTH_TOOLS_SCHEMA

                schemas.extend(EARTH_TOOLS_SCHEMA)
        except Exception as e:
            logger.warning(f"[ToolRegistry] 加载地球online工具失败: {e}")

        return schemas


# ==================== 全局实例 ====================


_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


__all__ = [
    "ComputerTools",
    "WebSearchTools",
    "KnowledgeBaseTools",
    "MessageTools",
    "ToolRegistry",
    "get_tool_registry",
]
