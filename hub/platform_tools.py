"""平台工具管理器

负责根据不同平台选择合适的工具集
"""

import logging
from typing import Dict, List

from core.unified_platform.platform_type import MiyaPlatform

logger = logging.getLogger(__name__)


class PlatformToolsManager:
    """平台工具管理器

    职责：
    - 根据平台类型选择合适的工具
    - 避免传递过多工具导致API超限
    - 管理平台特定的工具配置
    """

    # 核心工具 - 所有平台都需要
    CORE_TOOLS = [
        "get_current_time",
        "web_search",
        "tavily_search",
        "douyinhot",
        "weibohot",
        "baiduhot",
        "grok_search",
        # 通用资源搜索 + 浏览器 — 全平台通用
        "resource_find",
        "browse_web",
        # 视频下载
        "video_download",
        "download_file",
        # 跨平台文件发送（统一入口，图片与文件均走此工具）
        "send_platform_file",
        "list_data_files",
        # MusicNet — MIDI 作曲/编曲
        "midi_write",
        "midi_diff",
        "midi_batch_edit",
        "midi_query",
        "midi_inspect",
        "midi_play",
        "midi_render",
        # MCPNet — 全平台电脑操控
        "mcp_code_executor_execute",
        "mcp_web_search_search",
        "mcp_web_search_fetch",
        "mcp_screen_vision_look_screen",
        "mcp_screen_vision_screenshot",
        "mcp_filesystem_read_file",
        "mcp_filesystem_write_file",
        "mcp_filesystem_list_files",
        "mcp_filesystem_search_files",
        "mcp_art_service_generate_image",
        "mcp_art_service_list_providers",
        "mcp_art_service_get_gallery",
        # DSH 执行引擎 — 弥娅的「手」(DeepSeek Harness)
        "mcp_dsh_execute",
        "mcp_dsh_get_status",
        # 守护进程日志自检 — 弥娅查看后台终端运行状况
        "daemon_logs",
        # 一站式体检 — 平台/资源/任务/报错汇总
        "self_check",
        # 文件库 — 全平台文件存取
        "file_library_list",
        "file_library_search",
        "file_library_read",
        "file_library_stats",
        # 文件分析 — 全平台文件内容解析
        "analyze_file",
        "detect_file_type",
    ]

    # 地球online 工具 — 全平台通用 (弥娅随时查看/安排现实游戏化数据)
    EARTH_TOOLS = [
        "earth_summary",
        "earth_player",
        "earth_list_items",
        "earth_add_item",
        "earth_list_quests",
        "earth_add_quest",
        "earth_accept_quest",
        "earth_complete_quest",
        "earth_fail_quest",
        "earth_check_overdue",
        "earth_get_quest",
        "earth_update_subtask",
        "earth_activity",
        "earth_weekly_report",
        "earth_remind_due",
        "earth_list_titles",
        "earth_comment_activity",
        "earth_analyze",
        "earth_daily_ritual",
        "earth_list_achievements",
        "earth_add_achievement",
        "earth_set_achievement_progress",
        "earth_list_story",
        "earth_add_story",
        "earth_list_characters",
        "earth_add_character",
        "earth_adjust_affinity",
        "earth_grant_currency",
        "earth_spend_miya_coins",
        "earth_grant_exp",
        "earth_post_note",
        "earth_list_notes",
        "earth_world",
        "earth_explore",
        "earth_world_status",
        "earth_real_context",
        "earth_refresh_real_context",
        "earth_region_commission",
        # 策划级: 实体修改/删除
        "earth_get_item",
        "earth_update_item",
        "earth_delete_item",
        "earth_update_quest",
        "earth_cancel_quest",
        "earth_get_character",
        "earth_update_character",
        "earth_delete_character",
        "earth_update_story",
        "earth_delete_story",
        "earth_delete_note",
        "earth_pin_note",
        "earth_equip_title",
        "earth_checkin",
        # 策划级: 玩家档案
        "earth_update_player",
        # 策划级: 世界与地理围栏
        "earth_update_region",
        "earth_add_world_event",
        "earth_list_world_events",
        "earth_delete_world_event",
        "earth_list_discoveries",
        "earth_choose_discovery",
        # 策划级: 限时活动运营
        "earth_list_event_areas",
        "earth_create_event_area",
        "earth_update_event_area",
        "earth_delete_event_area",
        "earth_add_event_shop_item",
        "earth_delete_event_shop_item",
        # 策划级: 商店查询 + 弥娅商城货架管理
        "earth_list_miya_shop",
        "earth_list_event_shop",
        "earth_manage_miya_shop",
        # 策划级: 查询补充
        "earth_affinity_logs",
        "earth_quest_history",
        # v17: 现实资产 / 回忆抽卡 / 纪行 / 周挑战 / 纪念日 / 每日日常
        "earth_adjust_earth_currency",
        "earth_memory_pool",
        "earth_view_battle_pass",
        "earth_weekly_challenge",
        "earth_list_commemorations",
        "earth_add_commemoration",
        "earth_generate_daily_commissions",
        # v17.1: 全权策划补齐
        "earth_stats",
        "earth_list_checkins",
        "earth_currency_ledger",
        "earth_update_real_context",
        "earth_update_commemoration",
        "earth_delete_commemoration",
        "earth_pull_memory",
        "earth_claim_battle_pass",
        "earth_issue_care_commission",
        "earth_redeem_service",
    ]

    # 平台特定工具映射
    PLATFORM_TOOL_MAP = {
        "qq": [
            "send_message",
            "get_user_info",
            "qq_like",
            "send_poke",
            "react_emoji",
            "get_member_list",
            "get_member_info",
            "find_member",
            "memory_add",
            "memory_list",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # 搜索工具
            "web_search",
            "tavily_search",
            "douyinhot",
            "weibohot",
            "baiduhot",
            "grok_search",
            "crawl_webpage",
            # 信息查询
            "qq_level_query",
            "weather_query",
            # 跨端工具（从QQ控制终端）
            "execute_on_desktop",
            "send_to_desktop",
            "send_to_terminal",
            "terminal_command",
            "terminal_exec",
            "multi_terminal",
            # Terminal Ultra 工具
            "file_read",
            "file_write",
            "file_edit",
            "file_delete",
            "directory_tree",
            "code_execute",
            "project_analyze",
            # Git 工具
            "git_status",
            "git_diff",
            "git_log",
            "git_branch",
            "git_commit",
            "git_push",
            "git_pull",
            "git_checkout",
            "git_stash",
            # 搜索工具
            "file_grep",
            "file_glob",
            # 智能工具
            "project_context",
            "task_plan",
            "suggestions",
            # Skills 工具
            "list_skills",
            # 【格式塔】Agent 工具
            "group_file_downloader",
            "local_file_finder",
            "qq_file_reader",
            "qq_image_analyzer",
            "python_interpreter",
            "horoscope",
            "qq_like",
            "send_poke",
            "react_emoji",
            "wenchang_dijun",
            "baiduhot",
            "douyinhot",
            "qq_level_query",
            "weibohot",
            "crawl_webpage",
            "grok_search",
            "web_search",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # 飞书平台工具
        "lark": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # 文件库
            "file_library_list",
            "file_library_search",
            "file_library_read",
            "file_library_stats",
            # 文件分析
            "analyze_file",
            "detect_file_type",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # 钉钉平台工具
        "dingtalk": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # 企业微信工具
        "wecom": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # LINE平台工具
        "line": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # Discord平台工具
        "discord": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # Telegram平台工具
        "telegram": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # Slack平台工具
        "slack": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # KOOK平台工具
        "kook": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # 手机端 (mobile)
        "mobile": [
            "get_current_time",
            "web_search",
            "tavily_search",
            "baiduhot",
            "douyinhot",
            "weibohot",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            "mcp_dsh_execute",
            "mcp_dsh_get_status",
            "mcp_code_executor_execute",
            "mcp_screen_vision_look_screen",
            "mcp_screen_vision_screenshot",
            "mcp_filesystem_read_file",
            "mcp_filesystem_write_file",
            "mcp_filesystem_list_files",
            "mcp_filesystem_search_files",
            "mcp_art_service_generate_image",
            "mcp_art_service_list_providers",
            "mcp_art_service_get_gallery",
            "mcp_web_search_search",
            "mcp_web_search_fetch",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # Satori协议工具
        "satori": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # 微信开放平台
        "weixin_oc": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # 微信公众号
        "weixin_official_account": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        "weixin_ilink": [
            "send_message",
            "get_user_info",
            "memory_add",
            "memory_list",
            "web_search",
            "grok_search",
            "crawl_webpage",
            "baiduhot",
            "douyinhot",
            "weibohot",
            "weather_query",
            "python_interpreter",
            # 通用资源搜索 + 浏览器自动化 + 视频下载
            "resource_find",
            "browse_web",
            "video_download",
            "download_file",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # 文件库
            "file_library_list",
            "file_library_search",
            "file_library_read",
            "file_library_stats",
            # 文件分析
            "analyze_file",
            "detect_file_type",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        "terminal": [
            # DSH 执行引擎 — 弥娅的「手」
            "mcp_dsh_execute",
            "mcp_dsh_get_status",
            # 核心终端工具
            "terminal_command",
            "terminal_exec",
            "multi_terminal",
            "system_info",
            "environment_detector",
            # 跨端工具
            "send_to_qq",
            "send_to_desktop",
            "send_to_terminal",
            "execute_on_desktop",
            "sync_state",
            "qq_like",
            # 文件操作
            "file_read",
            "file_write",
            "file_edit",
            "file_delete",
            "directory_tree",
            "code_execute",
            "project_analyze",
            # Git 工具
            "git_status",
            "git_diff",
            "git_log",
            "git_branch",
            "git_commit",
            "git_push",
            "git_pull",
            "git_checkout",
            "git_stash",
            # 搜索工具
            "file_grep",
            "file_glob",
            # 代码理解
            "code_explain",
            "code_search_symbol",
            # 智能工具
            "project_context",
            "task_plan",
            "suggestions",
            # Agent 工具
            "code_explorer_agent",
            "code_reviewer_agent",
            "code_architect_agent",
            "terminal_agent",
            # Skills 工具
            "list_skills",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        # Desktop 平台使用与 QQ 相同的工具集（桌面端=超级管理员）
        # 复制 QQ 的工具列表，确保完全一致
        "desktop": [
            # 消息发送
            "send_message",
            "get_user_info",
            "qq_like",
            "send_poke",
            "react_emoji",
            "get_member_list",
            "get_member_info",
            "find_member",
            "memory_add",
            "memory_list",
            # 跨平台文件发送
            "send_platform_file",
            "list_data_files",
            # 搜索工具
            "web_search",
            "tavily_search",
            "douyinhot",
            "weibohot",
            "baiduhot",
            "grok_search",
            "crawl_webpage",
            # 信息查询
            "qq_level_query",
            "weather_query",
            # 跨端工具
            "execute_on_desktop",
            "send_to_desktop",
            "send_to_terminal",
            "terminal_command",
            "terminal_exec",
            "multi_terminal",
            # 文件操作
            "file_read",
            "file_write",
            "file_edit",
            "file_delete",
            "directory_tree",
            "code_execute",
            "project_analyze",
            # Git 工具
            "git_status",
            "git_diff",
            "git_log",
            "git_branch",
            "git_commit",
            "git_push",
            "git_pull",
            "git_checkout",
            "git_stash",
            # 搜索工具
            "file_grep",
            "file_glob",
            # 智能工具
            "project_context",
            "task_plan",
            "suggestions",
            # Skills 工具
            "list_skills",
            # Agent 工具
            "group_file_downloader",
            "local_file_finder",
            "qq_file_reader",
            "qq_image_analyzer",
            "python_interpreter",
            "ai_sing",
            "horoscope",
            "wenchang_dijun",
            "code_explorer_agent",
            "code_reviewer_agent",
            "code_architect_agent",
            "terminal_agent",
            # Mineradio 音乐播放器控制（MCP）
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
        "web": [
            "send_to_qq",
            "send_to_desktop",
            "send_to_terminal",
            "terminal_command",
            "terminal_exec",
            "file_read",
            "file_write",
            "file_edit",
            "file_delete",
            "directory_tree",
            "code_execute",
            "project_analyze",
            # Git 工具
            "git_status",
            "git_diff",
            "git_log",
            "git_branch",
            "git_commit",
            "git_push",
            "git_pull",
            "git_checkout",
            "git_stash",
            # 搜索工具
            "file_grep",
            "file_glob",
            # 智能工具
            "project_context",
            "task_plan",
            "suggestions",
            # Agent 工具
            "code_explorer_agent",
            "code_reviewer_agent",
            "code_architect_agent",
            "terminal_agent",
            # Skills 工具
            "list_skills",
            # Mineradio MCP
            "mcp_miya_mineradio_mineradio_get_status",
            "mcp_miya_mineradio_mineradio_play",
            "mcp_miya_mineradio_mineradio_pause",
            "mcp_miya_mineradio_mineradio_toggle_play",
            "mcp_miya_mineradio_mineradio_next",
            "mcp_miya_mineradio_mineradio_prev",
            "mcp_miya_mineradio_mineradio_seek",
            "mcp_miya_mineradio_mineradio_set_volume",
            "mcp_miya_mineradio_mineradio_toggle_mute",
            "mcp_miya_mineradio_mineradio_search",
            "mcp_miya_mineradio_mineradio_play_song",
            "mcp_miya_mineradio_mineradio_add_to_queue",
            "mcp_miya_mineradio_mineradio_clear_queue",
            "mcp_miya_mineradio_mineradio_get_queue",
            "mcp_miya_mineradio_mineradio_get_playlists",
            "mcp_miya_mineradio_mineradio_get_lyrics",
            "mcp_miya_mineradio_mineradio_set_mode",
            "mcp_miya_mineradio_mineradio_like_song",
            "mcp_miya_mineradio_mineradio_launch",
            "mcp_miya_mineradio_mineradio_health",
            "mcp_miya_mineradio_mineradio_get_playlist_tracks",
            "mcp_miya_mineradio_mineradio_play_list",
            "mcp_miya_mineradio_mineradio_unlike_song",
            "mcp_miya_mineradio_mineradio_create_playlist",
            "mcp_miya_mineradio_mineradio_shuffle_queue",
            "mcp_miya_mineradio_mineradio_remove_from_queue",
        ],
    }

    # 纯闲聊最小工具集 — 降低 prompt 体积，加速简单对话
    MINIMAL_CHAT_TOOLS = [
        "send_message",
        "qq_like",
        "send_poke",
        "react_emoji",
        "get_current_time",
        "get_user_info",
        "memory_add",
        "memory_list",
        "web_search",
        "weather_query",
    ]

    # QQ平台扩展工具
    QQ_EXTENDED_TOOLS = [
        "send_message",
        "get_user_info",
        "qq_like",
        "send_poke",
        "react_emoji",
        "get_member_list",
        "get_member_info",
        "find_member",
        "memory_add",
        "memory_list",
        "knowledge_text_search",
        "knowledge_semantic_search",
        "start_trpg",
        "roll_dice",
        "search_tavern_characters",
        # 跨端工具
        "execute_on_desktop",
        "send_to_desktop",
        "send_to_terminal",
        "terminal_command",
        # 搜索工具（新增）
        "web_search",
        "tavily_search",
        "douyinhot",
        "weibohot",
        "baiduhot",
        "grok_search",
        "crawl_webpage",
        # 通用资源搜索 + 浏览器自动化 + 视频下载
        "resource_find",
        "browse_web",
        "video_download",
        "download_file",
        # 信息查询
        "qq_level_query",
        "weather_query",
        # 【格式塔】Agent 工具
        "group_file_downloader",
        "local_file_finder",
        "qq_file_reader",
        "qq_image_analyzer",
        "python_interpreter",
        "horoscope",
        "wenchang_dijun",
        # 定时任务工具
        "create_schedule_task",
        "list_schedule_tasks",
        "delete_schedule_task",
        "update_schedule_task",
        "get_schedule_stats",
        # 新版知识库工具
        "add_knowledge",
        "search_knowledge",
        "delete_knowledge",
        # 新版认知侧写工具
        "get_profile",
        "search_profiles",
        "search_events",
        # B站/arXiv/GitHub 工具
        "bilibili_video",
        "arxiv_search",
        "github_repo",
        # 文件分析工具
        "analyze_file",
        "detect_file_type",
        # 群聊分析工具
        "group_analysis_member_structure",
        "group_analysis_member_activity",
        "group_analysis_inactive_risk",
        "group_analysis_message_mix",
    ]

    def __init__(self, tool_subnet):
        """
        初始化平台工具管理器

        Args:
            tool_subnet: ToolNet子网实例
        """
        self.tool_subnet = tool_subnet

    def get_platform_tools(self, platform: str) -> List[str]:
        """
        获取平台可用工具列表

        Args:
            platform: 平台类型

        Returns:
            工具名称列表
        """
        from hub.platform_adapters import get_adapter

        try:
            adapter = get_adapter(platform)
            return adapter._get_available_tools()
        except Exception as e:
            logger.error(f"[平台工具] 获取平台工具失败: {e}")
            return []

    def get_platform_specific_tools(self, platform: str) -> List[Dict]:
        """
        获取当前平台的工具 schema（优化版）

        只返回当前平台最常用的核心工具，避免过多工具导致API错误

        Args:
            platform: 平台类型 ('qq', 'terminal', 'desktop', 'web')

        Returns:
            工具 schema 列表
        """
        # 获取当前平台的工具
        selected_tools = self.PLATFORM_TOOL_MAP.get(platform, self.CORE_TOOLS)

        # 如果是 QQ 平台（含 aiocqhttp OneBot），添加更多常用工具
        if MiyaPlatform.is_qq(platform) or platform == MiyaPlatform.AIOCQHTTP.value:
            selected_tools = self.CORE_TOOLS + self.QQ_EXTENDED_TOOLS
            # QQ 聊天场景不需要屏幕视觉工具，移除避免 AI 混淆
            selected_tools = [
                t for t in selected_tools if t not in ("mcp_screen_vision_look_screen", "mcp_screen_vision_screenshot")
            ]

        # 地球online 工具 — 所有平台通用
        selected_tools = selected_tools + self.EARTH_TOOLS

        # 自检工具 — 所有平台通用（只读、轻量，让弥娅在任何平台都能体检/看日志）
        for _t in ("self_check", "daemon_logs"):
            if _t not in selected_tools:
                selected_tools.append(_t)

        # 从 tool_subnet 获取工具 schema
        try:
            all_schemas = self.tool_subnet.get_tools_schema()
            # 只返回在 selected_tools 列表中的工具
            platform_schemas = [s for s in all_schemas if s.get("function", {}).get("name") in selected_tools]

            logger.info(f"[平台工具] 平台 {platform} 使用 {len(platform_schemas)} 个工具")
            return platform_schemas

        except Exception as e:
            logger.warning(f"[平台工具] 获取平台工具失败: {e}，使用全部工具")
            return self.tool_subnet.get_tools_schema()

    def get_minimal_chat_tools(self) -> List[Dict]:
        """返回纯闲聊最小工具集，用于加速简单对话"""
        try:
            all_schemas = self.tool_subnet.get_tools_schema()
            minimal = [s for s in all_schemas if s.get("function", {}).get("name") in self.MINIMAL_CHAT_TOOLS]
            logger.debug(f"[平台工具] 闲聊精简: {len(minimal)} 个工具")
            return minimal
        except Exception:
            return []

    def is_creator(self, user_id: int, onebot_client) -> bool:
        """
        判断用户是否为造物主（超级管理员）

        Args:
            user_id: 用户ID
            onebot_client: OneBot客户端

        Returns:
            是否为造物主
        """
        if onebot_client and hasattr(onebot_client, "superadmin"):
            return user_id == onebot_client.superadmin
        return False
