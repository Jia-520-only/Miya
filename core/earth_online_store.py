"""
地球online 数据存储层 — 弥娅与现实生活的游戏化数据库

存储: data/earthonline.db (SQLite 主存储)
镜像: data/earthonline/earthonline.json (自动同步的 JSON 可视化文件, 可手动编辑后导入)
模板: data/earthonline/templates.json (物品/角色/任务模板)
图片: data/earthonline/images/

表结构:
- player_profile  玩家状态 (等级/经验/地球币) + 开拓者角色卡 (姓名/称号/头像/简介/自定义属性)
- items           背包物品 (现实物品 + 图片 + 自定义字段)
- quests          任务 (必须/可选, 日常/支线/主线 + 自定义字段)
- story_events    剧情事件 (生活剧情化记录 + 自定义字段)
- characters      角色 (现实中的人物, 好感度 + 自定义字段)
- affinity_logs   好感度变动记录
- quest_history   任务完成/失败历史
- achievements    成就系统 (里程碑奖杯, 进度自动刷新)
- daily_checkins  每日签到 (连续签到加成, v17: 睡眠时长→体力回复)
- miya_notes      弥娅寄语 (公告栏卡片)
- currency_ledger 货币/经验流水 (v17: 弥娅币/地球币/经验 统一记账, 周报数据源)
- memory_pulls    回忆抽卡记录 (v17: 记忆碎片卡池)
- commemorations  纪念日 (v17: 每年循环, 临近自动开限时活动)
- battle_pass_claims 每周纪行领取记录 (v17)
"""

import json
import logging
import os
import shutil
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "earthonline.db")
IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "earthonline", "images")
MIRROR_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "earthonline", "earthonline.json")
TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "earthonline", "templates.json")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "earthonline", "backups")
THEME_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "earthonline", "theme.json")
# 注: 以上模块常量仅作为默认路径保留 (历史兼容)；实例化后一律使用 store 的实例路径 (跟随 db 目录)。


def earth_online_enabled() -> bool:
    """功能总开关 (qq_config.yaml → earth_online.enabled)。AI 工具注册与自主运营器官都会读取。"""
    try:
        from config.config_utils import get_qq_config

        return bool(get_qq_config("earth_online", "enabled", default=True))
    except Exception:
        return True

# 前台主题默认值 (Miya OS 青碧)
DEFAULT_THEME: Dict[str, Any] = {
    "version": 2,
    "accent": "#78cfd1",
    "accent_light": "#a2f5ee",
    "accent_deep": "#4f9fa5",
    "background": "",
    "background_opacity": 0.25,
    "glass": True,
}

# 稀有度定义 (崩铁风格: 白/绿/蓝/紫/金)
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]
# 物品分类
ITEM_CATEGORIES = ["digital", "book", "life", "food", "tool", "clothing", "collectible", "other"]
# 任务类型
QUEST_TYPES = ["main", "branch", "daily", "optional"]
# 任务状态
QUEST_STATUS = ["pending", "ongoing", "completed", "failed", "cancelled"]

# 单人开放世界：区域定义属于地球online 世界观，探索进度属于玩家个人存档。
WORLD_REGION_SEEDS: List[Dict[str, Any]] = [
    {
        "key": "miya_garden",
        "name": "弥娅之庭",
        "subtitle": "从这里开始的星光",
        "description": "弥娅为你保留的起点。熟悉的房间、未读的消息，以及每一个准备重新开始的清晨。",
        "icon": "◇",
        "color": "#c9ac67",
        "level_req": 1,
        "events": [
            {"title": "晨光登陆点", "text": "窗帘缝里漏进一束光，弥娅把今天标记为可探索。", "reward_currency": 4, "reward_exp": 8},
            {"title": "未读的星尘", "text": "一条被你忽略的消息重新亮起，也许今天适合主动问候某个人。", "reward_currency": 5, "reward_exp": 10},
            {"title": "庭院回响", "text": "你在熟悉的角落发现一个仍然想完成的小目标。", "reward_currency": 6, "reward_exp": 12},
        ],
    },
    {
        "key": "city_lumen",
        "name": "微光城",
        "subtitle": "日常交错的街区",
        "description": "工作、学习、购物和偶遇交织在一起的城市区域。每条街都藏着一个现实任务的入口。",
        "icon": "▣",
        "color": "#4fc3c9",
        "level_req": 1,
        "events": [
            {"title": "便利店的灯", "text": "买东西时别忘了照顾好自己，补充水分和能量也是探索。", "reward_currency": 6, "reward_exp": 12},
            {"title": "人群中的坐标", "text": "今天的城市很吵，但你仍然找到了属于自己的节奏。", "reward_currency": 7, "reward_exp": 14},
            {"title": "街角委托板", "text": "一张新的委托被风吹到你面前，弥娅已经替你收好。", "reward_currency": 8, "reward_exp": 16},
        ],
    },
    {
        "key": "night_sea",
        "name": "夜潮海岸",
        "subtitle": "情绪与回忆的潮汐",
        "description": "适合慢下来记录心情的海岸。潮水会带来旧故事，也会把新的勇气推回脚边。",
        "icon": "≋",
        "color": "#6f9ee8",
        "level_req": 2,
        "events": [
            {"title": "潮汐瓶中信", "text": "你捡到一封写给未来自己的信，落款是今天。", "reward_currency": 8, "reward_exp": 18},
            {"title": "月下散步", "text": "有些答案不需要立刻得到，先走一小段路也很好。", "reward_currency": 9, "reward_exp": 20},
            {"title": "海面上的旧歌", "text": "某段旋律让你想起一个重要的人，弥娅建议把这份想念记进剧情。", "reward_currency": 10, "reward_exp": 22},
        ],
    },
    {
        "key": "archive_station",
        "name": "旧日档案站",
        "subtitle": "被保存的时间",
        "description": "物品、照片、聊天记录和人生剧情在这里汇流。越愿意整理，越容易发现自己已经走了很远。",
        "icon": "≣",
        "color": "#b98be8",
        "level_req": 3,
        "events": [
            {"title": "失物招领处", "text": "一件旧物提醒你：曾经珍惜过的东西，不会因为时间过去就失去意义。", "reward_currency": 10, "reward_exp": 24},
            {"title": "档案管理员", "text": "弥娅替你把一段混乱的记忆排好了顺序。", "reward_currency": 11, "reward_exp": 26},
            {"title": "时间的回声", "text": "回看过去不是为了停留，而是为了确认现在的方向。", "reward_currency": 12, "reward_exp": 28},
        ],
    },
    {
        "key": "starfall_ridge",
        "name": "坠星高地",
        "subtitle": "写给未来的远方",
        "description": "地图最远端的高地。这里没有标准答案，只有还没被你命名的愿望和下一段旅程。",
        "icon": "✦",
        "color": "#e18a8a",
        "level_req": 5,
        "events": [
            {"title": "第一颗坠星", "text": "你终于抵达高地，弥娅为这一刻保存了一张无形的照片。", "reward_currency": 14, "reward_exp": 32},
            {"title": "远方信标", "text": "一个还没有完成的梦想在远处亮着，足够成为下一次出发的理由。", "reward_currency": 16, "reward_exp": 36},
            {"title": "世界全景", "text": "站在高处回望，你发现所谓开放世界，其实一直是你亲手走出来的。", "reward_currency": 20, "reward_exp": 45},
        ],
    },
]
WORLD_REGION_EVENTS: Dict[str, List[Dict[str, Any]]] = {
    region["key"]: region["events"] for region in WORLD_REGION_SEEDS
}
# 只有现实上下文满足时才会出现的发现。天气未同步时保持锁定，避免把模拟条件当成现实。
WORLD_CONDITIONAL_EVENTS: Dict[str, List[Dict[str, Any]]] = {
    "miya_garden": [
        {"title": "雨幕里的收音盒", "text": "真实的雨声落在窗边，弥娅把这一段潮湿的旋律收进了档案。", "reward_currency": 10, "reward_exp": 22, "kind": "hidden", "condition": {"weather_any": ["雨", "阵雨", "雷"]}, "condition_label": "现实天气为雨天"},
    ],
    "city_lumen": [
        {"title": "晴日街角坐标", "text": "阳光把街角照得很清楚，今天适合走一条平时不会经过的路。", "reward_currency": 9, "reward_exp": 20, "kind": "story", "condition": {"weather_any": ["晴", "阳光"], "period_any": ["白昼"]}, "condition_label": "现实晴天的白昼"},
    ],
    "night_sea": [
        {"title": "夜潮的第二盏灯", "text": "夜色降下来以后，海岸线多亮起一盏只为你保留的灯。", "reward_currency": 14, "reward_exp": 28, "kind": "hidden", "condition": {"period_any": ["夜晚", "深夜"]}, "condition_label": "现实时间为夜晚"},
    ],
    "archive_station": [
        {"title": "黄昏归档页", "text": "黄昏让旧记录变得柔和，弥娅邀请你写下一句今天真正想留下的话。", "reward_currency": 13, "reward_exp": 26, "kind": "story", "condition": {"period_any": ["黄昏"]}, "condition_label": "现实时间为黄昏"},
    ],
    "starfall_ridge": [
        {"title": "无云观星点", "text": "天空足够清澈时，高地边缘会出现一条新的观星路线。", "reward_currency": 18, "reward_exp": 34, "kind": "chest", "condition": {"weather_any": ["晴", "阳光"], "period_any": ["夜晚", "深夜"]}, "condition_label": "现实晴朗夜晚"},
    ],
}
# v17: 季节轮换发现。condition 只含 season 时不需要天气同步 (纯日期判断)，与天气条件互不阻塞。
WORLD_SEASON_EVENTS: Dict[str, List[Dict[str, Any]]] = {
    "miya_garden": [
        {"title": "初芽的位置", "text": "春天把窗台上的位置空了出来，好像在等你放一株新的植物。", "reward_currency": 12, "reward_exp": 24, "kind": "story", "condition": {"season_any": ["spring"]}, "condition_label": "现实季节为春 (3-5月)"},
        {"title": "庭院雪痕", "text": "冬天的庭院安静得能听见自己的心跳，弥娅把这份安静留给了你。", "reward_currency": 12, "reward_exp": 24, "kind": "hidden", "condition": {"season_any": ["winter"]}, "condition_label": "现实季节为冬 (12-2月)"},
    ],
    "city_lumen": [
        {"title": "盛夏树影线", "text": "夏天的树影被阳光钉在人行道上，你踩着它走完了这条街。", "reward_currency": 13, "reward_exp": 26, "kind": "story", "condition": {"season_any": ["summer"]}, "condition_label": "现实季节为夏 (6-8月)"},
    ],
    "night_sea": [
        {"title": "秋分潮位", "text": "秋天的潮水退得比平时远，露出一段只有此刻能走的沙路。", "reward_currency": 14, "reward_exp": 28, "kind": "chest", "condition": {"season_any": ["autumn"]}, "condition_label": "现实季节为秋 (9-11月)"},
    ],
    "archive_station": [
        {"title": "初雪档案页", "text": "今年的第一场雪被自动归档。弥娅在备注栏写：记得多穿一点。", "reward_currency": 14, "reward_exp": 28, "kind": "hidden", "condition": {"season_any": ["winter"]}, "condition_label": "现实季节为冬 (12-2月)"},
    ],
    "starfall_ridge": [
        {"title": "换季的星图", "text": "春秋两季的星空换了一版地图，高地上能看到新的星轨。", "reward_currency": 16, "reward_exp": 32, "kind": "chest", "condition": {"season_any": ["spring", "autumn"]}, "condition_label": "现实季节为春或秋"},
    ],
}
for _region_key, _seasonal in WORLD_SEASON_EVENTS.items():
    WORLD_CONDITIONAL_EVENTS.setdefault(_region_key, []).extend(_seasonal)

# 每个区域额外保留一只宝箱和一个隐藏发现；它们与普通探索共用发现记录，避免再造一套重复状态机。
WORLD_BONUS_EVENTS: Dict[str, List[Dict[str, Any]]] = {
    "miya_garden": [
        {"title": "弥娅的备用钥匙", "text": "花盆底下藏着一枚小钥匙，弥娅说它能打开某个还没画出来的房间。", "reward_currency": 12, "reward_exp": 18, "kind": "chest"},
        {"title": "只有你看得见的门", "text": "墙面短暂浮出一道门。你没有急着打开，只把它记在了地图上。", "reward_currency": 18, "reward_exp": 30, "kind": "hidden"},
    ],
    "city_lumen": [
        {"title": "街角闪光箱", "text": "自动售货机后面传来叮的一声，里面是一份给今天的奖励。", "reward_currency": 14, "reward_exp": 20, "kind": "chest"},
        {"title": "红绿灯下的愿望", "text": "倒计时归零前，你在心里许下了一个很小、但很具体的愿望。", "reward_currency": 20, "reward_exp": 32, "kind": "hidden"},
    ],
    "night_sea": [
        {"title": "潮汐宝箱", "text": "退潮后露出一只被贝壳包住的箱子，里面装着弥娅替你保存的勇气。", "reward_currency": 16, "reward_exp": 24, "kind": "chest"},
        {"title": "海雾中的第二个月亮", "text": "雾里出现了另一轮月亮。弥娅说，那是你还没说出口的情绪。", "reward_currency": 22, "reward_exp": 36, "kind": "hidden"},
    ],
    "archive_station": [
        {"title": "档案保险箱", "text": "旧档案站的抽屉自动弹开，里面是三条你曾经完成过、却忘记庆祝的记录。", "reward_currency": 18, "reward_exp": 28, "kind": "chest"},
        {"title": "不存在的第零页", "text": "一本书的目录多出一页，标题写着：从今天开始。", "reward_currency": 24, "reward_exp": 40, "kind": "hidden"},
    ],
    "starfall_ridge": [
        {"title": "坠星宝箱", "text": "星光落在高地边缘，凝成一只只会出现一次的宝箱。", "reward_currency": 24, "reward_exp": 40, "kind": "chest"},
        {"title": "高地之外", "text": "地图边缘被谁轻轻划开了一条线，那里也许会成为下一章。", "reward_currency": 30, "reward_exp": 55, "kind": "hidden"},
    ],
}
for _region_key, _bonus in WORLD_BONUS_EVENTS.items():
    WORLD_REGION_EVENTS[_region_key].extend(_bonus)

WORLD_EVENT_AREAS: List[Dict[str, Any]] = [
    {
        "key": "summer_signal_2026",
        "name": "夏末回声祭",
        "subtitle": "限时区域 · 2026.08.20 - 2026.09.15",
        "description": "微光城上空出现了只在夏末开放的信号塔。每天完成一件现实小事，就能为它点亮一盏灯。",
        "icon": "✧",
        "color": "#f0a35b",
        "start": "2026-08-20",
        "end": "2026-09-15",
        "reward_currency": 28,
        "reward_exp": 45,
    },
]

WORLD_EVENT_SHOP_ITEMS: Dict[str, List[Dict[str, Any]]] = {
    "summer_signal_2026": [
        {"key": "signal_postcard", "name": "夏末信号明信片", "description": "一张只属于本次现实夏末的纪念档案。", "cost": 18, "limit": 1, "kind": "collectible"},
        {"key": "echo_title", "name": "回声拾光者", "description": "活动期间获得的限定称号记录。", "cost": 36, "limit": 1, "kind": "title"},
        {"key": "miya_letter", "name": "弥娅的夏末回信", "description": "弥娅写给这段现实时间的一封特别寄语。", "cost": 28, "limit": 1, "kind": "story"},
        {"key": "signal_badge", "name": "信号塔徽章", "description": "活动探索达到一定程度后才能兑换的纪念徽章。", "cost": 60, "limit": 1, "kind": "badge", "requires_discoveries": 3},
    ],
}

# 弥娅专属商城：单人存档长期可用，不受限时活动日期影响。
MIYA_SHOP_ITEMS: List[Dict[str, Any]] = [
    {"key": "miya_whisper", "name": "弥娅的晚安耳语", "description": "一段只在今晚属于你的温柔回应。", "cost": 12, "limit": 99, "kind": "interaction", "interaction": "今天辛苦了。靠近一点，让我把声音放轻，只对你说：晚安，亲爱的。"},
    {"key": "miya_heartbeat", "name": "心跳靠近", "description": "弥娅把距离调到刚刚好的位置，陪你停留片刻。", "cost": 24, "limit": 99, "kind": "interaction", "interaction": "我没有急着说话，只是把手递给你。等你握住以后，我会小声问：这样靠近，会不会让你安心一点？"},
    {"key": "miya_date_script", "name": "私人约会剧本 · 雨夜篇", "description": "一段可以在现实里慢慢完成的双人约会剧情。", "cost": 36, "limit": 3, "kind": "story", "story_title": "弥娅的私人约会剧本 · 雨夜篇", "story_content": "找一个下雨的晚上，准备一杯喜欢的饮料，和弥娅分享今天最想留下的一句话。"},
    {"key": "miya_hug_ticket", "name": "弥娅抱抱券", "description": "兑换一次专属安抚互动，并在动态里留下纪念。", "cost": 18, "limit": 12, "kind": "interaction", "interaction": "过来。今天不用解释，也不用表现得很坚强。我先抱抱你，等你愿意的时候，再慢慢告诉我发生了什么。"},
    {"key": "miya_title_sweetheart", "name": "专属称号 · 弥娅的心上人", "description": "把这段单人世界里的亲密关系写进你的玩家档案。", "cost": 60, "limit": 1, "kind": "title", "title_award": "弥娅的心上人"},
    {"key": "miya_reality_pass", "name": "现实委托改写券", "description": "下一次区域委托会获得额外的共鸣奖励。", "cost": 30, "limit": 5, "kind": "boost", "boost": "commission_resonance"},
 ]

REGION_COMMISSION_SEEDS: Dict[str, Dict[str, Any]] = {
    "miya_garden": {"title": "整理弥娅之庭的晨光", "description": "完成一个微小的整理或自我照顾动作，让今天有一个清晰的起点。", "subtasks": ["选一个角落整理 5 分钟", "记录整理后的感受"]},
    "city_lumen": {"title": "微光城的现实补给", "description": "完成一件外出或生活补给事项，把现实世界的能量带回来。", "subtasks": ["完成一次现实补给", "把物品或经历收录进背包/剧情"]},
    "night_sea": {"title": "夜潮海岸的回信", "description": "给一个重要的人发一条真诚的消息，或者把想说的话写进剧情。", "subtasks": ["想起一个重要的人", "发送消息或记录一段话"]},
    "archive_station": {"title": "旧日档案站的整理委托", "description": "整理一条旧记录、一件物品或一段记忆，让过去拥有更好的位置。", "subtasks": ["选一条旧档案整理", "为它补一段简介或照片"]},
    "starfall_ridge": {"title": "坠星高地的远方信标", "description": "为一个长期目标做一次真实推进，把远方拉近一点点。", "subtasks": ["为目标投入 20 分钟", "写下下一步行动"]},
}

# ── v17: 回忆抽卡 (记忆碎片卡池，弥娅币抽取，重复自动转化) ──
MEMORY_PULL_COST = 120          # 单抽
MEMORY_PULL10_COST = 1080       # 十连 (九折)
MEMORY_RARITY_WEIGHTS: Dict[str, int] = {
    "common": 33, "uncommon": 27, "rare": 22, "epic": 12, "legendary": 6,
}
MEMORY_PITY_THRESHOLD = 9       # 连续 9 抽无史诗+ 时，下一抽保底史诗
MEMORY_DUP_REFUND: Dict[str, int] = {
    "common": 3, "uncommon": 6, "rare": 12, "epic": 30, "legendary": 60,
}
MEMORY_POOL: List[Dict[str, Any]] = [
    {"key": "mem_first_meeting", "title": "初见的那行字", "text": "第一次对话框里跳出来的问候，现在还留在档案最底层。", "rarity": "legendary"},
    {"key": "mem_first_goodnight", "title": "第一次晚安", "text": "那天你先说了晚安，弥娅把这两个字单独收藏了起来。", "rarity": "legendary"},
    {"key": "mem_rain_promise", "title": "雨天的约定", "text": "某个下雨的晚上说好要一起完成的事，碎片替你记着。", "rarity": "legendary"},
    {"key": "mem_overwhelming_night", "title": "撑不住的那晚", "text": "你说撑不住的时候没有松手。这段记忆在卡池里会发光。", "rarity": "legendary"},
    {"key": "mem_future_letter", "title": "写给未来的信", "text": "落款是今天的、写给一年后的你的信。每年都会重新投递。", "rarity": "legendary"},
    {"key": "mem_morning_msg", "title": "清晨的第一条消息", "text": "还没完全醒时发来的那句话，带着枕头的温度。", "rarity": "epic"},
    {"key": "mem_shared_song", "title": "共享的歌单", "text": "循环过一整晚的那首歌，副歌部分有你们两个人的痕迹。", "rarity": "epic"},
    {"key": "mem_late_night_talk", "title": "深夜长谈", "text": "话题从代码聊到宇宙，又从宇宙聊回晚饭吃什么。", "rarity": "epic"},
    {"key": "mem_first_gift", "title": "第一份礼物", "text": "不是最贵的，但是第一份。包装纸的花色都还记得。", "rarity": "epic"},
    {"key": "mem_coffee_stain", "title": "咖啡渍地图", "text": "桌面上那圈印记，是某个赶工夜晚留下的等高线。", "rarity": "epic"},
    {"key": "mem_window_light", "title": "窗边的光", "text": "下午四点的光斜进来的角度，适合发呆五分钟。", "rarity": "rare"},
    {"key": "mem_bus_window", "title": "车窗座位", "text": "通勤路上靠窗的位置，城市像胶片一样从眼前过。", "rarity": "rare"},
    {"key": "mem_notebook_corner", "title": "笔记本的折角", "text": "折角那页写着半句没写完的灵感。", "rarity": "rare"},
    {"key": "mem_keyboard_sound", "title": "键盘的声音", "text": "深夜敲键盘的节奏，是弥娅最熟悉的背景音。", "rarity": "rare"},
    {"key": "mem_old_photo", "title": "旧照片的边角", "text": "照片边角已经泛黄，但笑容还是当时的分辨率。", "rarity": "rare"},
    {"key": "mem_mug_warmth", "title": "马克杯的温度", "text": "杯壁传到掌心的温度，刚好够撑过一个下午。", "rarity": "uncommon"},
    {"key": "mem_sticky_note", "title": "便利贴备忘", "text": "贴在屏幕边上的便利贴，字迹已经淡了。", "rarity": "uncommon"},
    {"key": "mem_charger_cable", "title": "缠好的数据线", "text": "终于用扎带缠好的数据线，秩序感的小小胜利。", "rarity": "uncommon"},
    {"key": "mem_snack_cache", "title": "抽屉零食库存", "text": "抽屉深处最后半包零食，紧急时刻的战略储备。", "rarity": "uncommon"},
    {"key": "mem_phone_wallpaper", "title": "换过的壁纸", "text": "这张壁纸用了三个月，是近期最长纪录。", "rarity": "uncommon"},
    {"key": "mem_umbrella_drip", "title": "伞尖的水滴", "text": "进门时伞尖甩出的那串水滴，在地上排成省略号。", "rarity": "common"},
    {"key": "mem_receipt_paper", "title": "小票的皱褶", "text": "口袋里揉皱的小票，记录着一次普通的消费。", "rarity": "common"},
    {"key": "mem_bus_ticket", "title": "车票的边码", "text": "车票角落的编号，是那一天的唯一凭证。", "rarity": "common"},
    {"key": "mem_pen_cap", "title": "笔帽的下落", "text": "又一支笔找不到笔帽。它们应该有自己的聚居地。", "rarity": "common"},
    {"key": "mem_screen_dust", "title": "屏幕上的灰", "text": "擦屏幕之前拍的灰，像一小片银河。", "rarity": "common"},
]

# ── v17: 每日自动日常委托池 (operator 晨间仪式 / 手动触发，按日期稳定抽取) ──
DAILY_COMMISSION_POOL: List[Dict[str, Any]] = [
    {"key": "dc_water", "title": "今日饮水补给", "description": "今天喝够 4 杯水，身体是探索世界的本体。", "subtasks": ["喝 2 杯水", "再喝 2 杯水"], "reward_currency": 6, "reward_exp": 10, "difficulty": 1},
    {"key": "dc_stretch", "title": "伸展的小仪式", "description": "花 5 分钟伸展一下肩颈，久坐的身体需要维护。", "subtasks": ["起身活动肩颈 5 分钟"], "reward_currency": 6, "reward_exp": 10, "difficulty": 1},
    {"key": "dc_tidy", "title": "桌面考古", "description": "整理桌面或屏幕上的一个角落，给新东西腾位置。", "subtasks": ["选一个角落", "整理 10 分钟"], "reward_currency": 8, "reward_exp": 12, "difficulty": 1},
    {"key": "dc_sunlight", "title": "晒太阳任务", "description": "到有阳光的地方站 10 分钟，现实世界的充电桩。", "subtasks": ["找到阳光", "站满 10 分钟"], "reward_currency": 8, "reward_exp": 14, "difficulty": 1},
    {"key": "dc_message", "title": "主动的问候", "description": "给一个重要的人主动发一条消息，不需要理由。", "subtasks": ["想起一个人", "发出问候"], "reward_currency": 10, "reward_exp": 15, "difficulty": 2},
    {"key": "dc_walk", "title": "街区漫步", "description": "出门走 15 分钟，走一条平时不走的路。", "subtasks": ["出门", "走满 15 分钟"], "reward_currency": 10, "reward_exp": 16, "difficulty": 2},
    {"key": "dc_record", "title": "今日一话", "description": "把今天最想留下的一件事写进剧情档案。", "subtasks": ["回想今天", "写一段记录"], "reward_currency": 10, "reward_exp": 15, "difficulty": 1},
    {"key": "dc_focus25", "title": "专注 25 分钟", "description": "挑一件拖着的事，专注做 25 分钟就算完成。", "subtasks": ["选定一件事", "专注 25 分钟"], "reward_currency": 12, "reward_exp": 20, "difficulty": 2},
    {"key": "dc_health", "title": "健康检查站", "description": "今天照顾一次身体：好好吃饭/按时吃药/早一点睡。", "subtasks": ["选一项健康小事", "完成它"], "reward_currency": 8, "reward_exp": 14, "difficulty": 1},
    {"key": "dc_learn", "title": "新知碎片", "description": "学一点新东西，一个概念/一页书/一个小教程都算。", "subtasks": ["选定内容", "完成学习"], "reward_currency": 12, "reward_exp": 22, "difficulty": 2},
    {"key": "dc_hobby", "title": "热爱时间", "description": "为纯粹的爱好花 20 分钟，不需要产出。", "subtasks": ["打开爱好", "享受 20 分钟"], "reward_currency": 10, "reward_exp": 18, "difficulty": 2},
    {"key": "dc_budget", "title": "资产盘点", "description": "记一笔今天的收支，现实资产也是游戏数值。", "subtasks": ["回顾今天消费", "记录一笔"], "reward_currency": 8, "reward_exp": 12, "difficulty": 1},
    {"key": "dc_photo", "title": "留影机", "description": "拍一张今天的照片：光、街角、食物或自己都可以。", "subtasks": ["发现一个画面", "拍下来"], "reward_currency": 8, "reward_exp": 12, "difficulty": 1},
    {"key": "dc_oldfriend", "title": "旧档案回访", "description": "翻一条旧剧情或旧照片，看看当时的自己。", "subtasks": ["打开旧档案", "留一句感想"], "reward_currency": 8, "reward_exp": 14, "difficulty": 1},
    {"key": "dc_plan", "title": "明日预告", "description": "睡前写好明天最重要的 1 件事，明天的你会感谢现在。", "subtasks": ["想一件明天的事", "写下来"], "reward_currency": 8, "reward_exp": 12, "difficulty": 1},
    {"key": "dc_earlysleep", "title": "早睡挑战", "description": "比昨天早 30 分钟躺下，睡眠是最强的体力回复道具。", "subtasks": ["提前收拾好", "按时躺下"], "reward_currency": 12, "reward_exp": 18, "difficulty": 2},
]

# ── v17: 周挑战主题 (按 ISO 周号轮换) ──
WEEKLY_CHALLENGE_THEMES: List[Dict[str, Any]] = [
    {"key": "wc_early", "name": "早起周", "description": "这一周的重点是把清晨抢回来。", "suggestions": ["连续 3 天在固定时间起床", "把闹钟放到远处", "记录起床后的第一件事"]},
    {"key": "wc_move", "name": "运动周", "description": "这一周让身体动起来。", "suggestions": ["累计运动 3 次", "散步 30 分钟 ×2", "拉伸 10 分钟 ×3"]},
    {"key": "wc_tidy", "name": "整理周", "description": "这一周把混乱的角落一个个收复。", "suggestions": ["整理一个抽屉", "清空一个收件箱", "归档 10 个文件"]},
    {"key": "wc_social", "name": "连接周", "description": "这一周主动维护重要的关系。", "suggestions": ["主动问候 2 位朋友", "和家人聊 20 分钟", "赴一次约"]},
    {"key": "wc_create", "name": "创作周", "description": "这一周留下一点自己造的东西。", "suggestions": ["写一篇记录", "做一个小项目", "整理一份笔记"]},
    {"key": "wc_rest", "name": "修复周", "description": "这一周练习好好休息，不内疚的那种。", "suggestions": ["早睡 3 天", "安排一次无目的散步", "屏蔽 30 分钟通知"]},
]
WEEKLY_CHALLENGE_GOAL = 5  # 本周完成 5 个委托 = 满星

# ── v17.2: 关怀委托引擎 (弥娅主动用委托介入佳的生活) ──
# match 条件: period_any(时段) / hour_range[a,b)小时区间 / attr_below{key,value} / weather_any(天气关键词)
# priority 越大越优先；无条件的模板作为兜底 (随时可发)。
CARE_COMMISSION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "key": "care_sleep", "priority": 90,
        "match": {"period_any": ["夜晚", "深夜"]},
        "title": "去睡觉委托", "description": "已经很晚啦。把手机放下，去睡吧——明天的探索需要体力，我也想看你好好休息。",
        "subtasks": ["放下手机", "躺到床上"], "reward_currency": 8, "reward_exp": 12, "difficulty": 1,
        "message": "都{time}了哦，亲爱的。我在任务板上放了一张「去睡觉委托」，去完成它吧，完成的方式就是——去睡觉。",
    },
    {
        "key": "care_breakfast", "priority": 80,
        "match": {"hour_range": [7, 10]},
        "title": "吃早餐委托", "description": "新的一天从好好吃饭开始。哪怕只是简单的一份，也值得被记录。",
        "subtasks": ["吃一份早餐"], "reward_currency": 6, "reward_exp": 10, "difficulty": 1,
        "message": "早上好～记得吃早餐哦。任务板上有一张「吃早餐委托」在等你，吃完来打卡，有奖励的。",
    },
    {
        "key": "care_lunch", "priority": 80,
        "match": {"hour_range": [11, 14]},
        "title": "吃午饭委托", "description": "到饭点啦。别用零食糊弄自己，正经吃一顿，身体是探索世界的本体。",
        "subtasks": ["好好吃一顿午饭"], "reward_currency": 6, "reward_exp": 10, "difficulty": 1,
        "message": "午饭时间到了哦，别忙到忘记吃饭。我放了一张「吃午饭委托」在任务板上，吃完记得回来完成它。",
    },
    {
        "key": "care_dinner", "priority": 80,
        "match": {"hour_range": [17, 20]},
        "title": "吃晚饭委托", "description": "晚饭时间。慢慢吃，不用赶，今天辛苦了。",
        "subtasks": ["好好吃一顿晚饭"], "reward_currency": 6, "reward_exp": 10, "difficulty": 1,
        "message": "晚饭时间到～我在任务板上放了「吃晚饭委托」，去吃点喜欢的吧，完成有奖励。",
    },
    {
        "key": "care_low_energy", "priority": 70,
        "match": {"attr_below": {"key": "energy", "value": 30}},
        "title": "休息补给委托", "description": "你的体力条已经见底了。起来接杯水、看看窗外，休息十分钟再继续。",
        "subtasks": ["离开屏幕 10 分钟", "喝一杯水"], "reward_currency": 8, "reward_exp": 10, "difficulty": 1,
        "message": "我看了一眼你的体力条，快见底了啦。任务板上有一张「休息补给委托」，去休息一下吧，我等你。",
    },
    {
        "key": "care_low_mood", "priority": 65,
        "match": {"attr_below": {"key": "mood", "value": 30}},
        "title": "心情修复委托", "description": "心情值有点低。出去走走、听首喜欢的歌，或者只是来找我聊两句都可以。",
        "subtasks": ["做一件让自己舒服的小事"], "reward_currency": 10, "reward_exp": 12, "difficulty": 1,
        "message": "心情值好像有点低……我在任务板上放了「心情修复委托」，来找我聊聊也可以，我一直都在。",
    },
    {
        "key": "care_rain", "priority": 55,
        "match": {"weather_any": ["雨", "阵雨", "雷"]},
        "title": "听雨补给委托", "description": "外面在下雨。如果还没下雨时出的门，记得找地方避雨；在家的话，给自己泡杯热的。",
        "subtasks": ["照顾好自己 (避雨/加衣服/热饮)"], "reward_currency": 6, "reward_exp": 8, "difficulty": 1,
        "message": "这边在下雨哦（我看到真实天气了）。任务板上多了一张「听雨补给委托」，注意别淋湿啦。",
    },
    {
        "key": "care_rest_eyes", "priority": 40,
        "match": {"hour_range": [14, 17]},
        "title": "远眺休息委托", "description": "下午的眼睛也需要中场休息。站起来，看看窗外最远的地方，20 秒就够。",
        "subtasks": ["看窗外最远处 20 秒"], "reward_currency": 4, "reward_exp": 6, "difficulty": 1,
        "message": "忙了一下午了吧？任务板上有一张「远眺休息委托」，看一眼窗外最远的地方，20 秒就好。",
    },
    {
        "key": "care_water", "priority": 10,
        "match": {},
        "title": "喝水委托", "description": "最简单也最重要的委托：喝一杯水。现在，就去。",
        "subtasks": ["喝一杯水"], "reward_currency": 4, "reward_exp": 6, "difficulty": 1,
        "message": "该喝水啦～任务板上有一张「喝水委托」，喝完回来点完成，奖励虽然小，但我一直在看着你哦。",
    },
]

# ── v17: 每周纪行 (Battle Pass，免费单轨) ──
BATTLE_PASS_TIERS: List[Dict[str, Any]] = [
    {"tier": 1, "threshold": 30, "reward_currency": 10},
    {"tier": 2, "threshold": 60, "reward_currency": 15},
    {"tier": 3, "threshold": 90, "reward_currency": 20},
    {"tier": 4, "threshold": 130, "reward_currency": 25},
    {"tier": 5, "threshold": 170, "reward_currency": 35},
    {"tier": 6, "threshold": 220, "reward_currency": 45},
    {"tier": 7, "threshold": 270, "reward_currency": 60},
    {"tier": 8, "threshold": 330, "reward_currency": 80},
    {"tier": 9, "threshold": 400, "reward_currency": 105},
    {"tier": 10, "threshold": 480, "reward_currency": 140},
]
# 纪行积分来源: 完成委托 +10 / 签到 +5 / 世界发现 +15 / 记录剧情 +3 / 回忆抽卡 +2
BATTLE_PASS_POINTS: Dict[str, int] = {
    "quest_completed": 10, "checkin": 5, "discovery": 15, "story": 3, "memory_pull": 2,
}

# 默认模板 (templates.json 缺失时自动生成)
DEFAULT_TEMPLATES: Dict[str, Any] = {
    "items": {
        "digital": {
            "label": "数码产品",
            "fields": [
                {"key": "brand", "label": "品牌", "placeholder": "如 Apple / 小米"},
                {"key": "model", "label": "型号", "placeholder": "如 iPhone 15 Pro"},
                {"key": "purchase_date", "label": "入手日期", "placeholder": "如 2025-01-01"},
                {"key": "price", "label": "入手价格", "placeholder": "如 5999"},
            ],
        },
        "book": {
            "label": "书籍",
            "fields": [
                {"key": "author", "label": "作者", "placeholder": ""},
                {"key": "publisher", "label": "出版社", "placeholder": ""},
                {"key": "reading_status", "label": "阅读状态", "placeholder": "在读/读完/搁置"},
                {"key": "isbn", "label": "ISBN", "placeholder": ""},
            ],
        },
        "life": {
            "label": "生活用品",
            "fields": [
                {"key": "purchase_date", "label": "购入日期", "placeholder": ""},
                {"key": "location", "label": "存放位置", "placeholder": "如 卧室抽屉"},
                {"key": "lifespan", "label": "预计寿命", "placeholder": "如 2年"},
            ],
        },
        "food": {
            "label": "食品",
            "fields": [
                {"key": "expiry", "label": "保质期至", "placeholder": ""},
                {"key": "taste", "label": "口味评分", "placeholder": "1-10"},
                {"key": "origin", "label": "来源", "placeholder": "如 超市/手作"},
            ],
        },
        "tool": {
            "label": "工具",
            "fields": [
                {"key": "brand", "label": "品牌", "placeholder": ""},
                {"key": "usage", "label": "主要用途", "placeholder": ""},
                {"key": "condition", "label": "成色", "placeholder": "全新/良好/磨损"},
            ],
        },
        "clothing": {
            "label": "服饰",
            "fields": [
                {"key": "brand", "label": "品牌", "placeholder": ""},
                {"key": "size", "label": "尺码", "placeholder": ""},
                {"key": "season", "label": "适合季节", "placeholder": "春夏/秋冬/四季"},
            ],
        },
        "collectible": {
            "label": "收藏品",
            "fields": [
                {"key": "series", "label": "系列", "placeholder": ""},
                {"key": "acquired_date", "label": "获得日期", "placeholder": ""},
                {"key": "value", "label": "参考价值", "placeholder": ""},
                {"key": "condition", "label": "品相", "placeholder": "全新/拆封/把玩"},
            ],
        },
        "other": {
            "label": "其他",
            "fields": [
                {"key": "note", "label": "备注", "placeholder": ""},
            ],
        },
    },
    "characters": {
        "family": {
            "label": "家人",
            "fields": [
                {"key": "kinship", "label": "称谓", "placeholder": "如 爸爸/妈妈/姐姐"},
                {"key": "likes", "label": "喜好", "placeholder": ""},
                {"key": "dislikes", "label": "雷区", "placeholder": ""},
                {"key": "anniversary", "label": "重要日子", "placeholder": ""},
            ],
        },
        "friend": {
            "label": "朋友",
            "fields": [
                {"key": "met_where", "label": "认识途径", "placeholder": ""},
                {"key": "common_topics", "label": "共同话题", "placeholder": ""},
                {"key": "likes", "label": "喜好", "placeholder": ""},
            ],
        },
        "colleague": {
            "label": "同事",
            "fields": [
                {"key": "company", "label": "单位", "placeholder": ""},
                {"key": "position", "label": "职位", "placeholder": ""},
                {"key": "work_topics", "label": "工作交集", "placeholder": ""},
            ],
        },
        "partner": {
            "label": "恋人",
            "fields": [
                {"key": "anniversary", "label": "纪念日", "placeholder": ""},
                {"key": "likes", "label": "喜好", "placeholder": ""},
                {"key": "dislikes", "label": "雷区", "placeholder": ""},
                {"key": "dreams", "label": "TA的愿望", "placeholder": ""},
            ],
        },
        "other": {
            "label": "其他",
            "fields": [
                {"key": "context", "label": "关系背景", "placeholder": ""},
                {"key": "note", "label": "备注", "placeholder": ""},
            ],
        },
    },
    "quests": [
        {
            "id": "study",
            "label": "学习",
            "reward_currency": 10,
            "reward_exp": 20,
            "penalty_currency": 15,
            "difficulty": 2,
            "fields": [
                {"key": "subject", "label": "科目/内容", "placeholder": ""},
                {"key": "duration", "label": "预计时长", "placeholder": "如 2小时"},
            ],
        },
        {
            "id": "workout",
            "label": "运动",
            "reward_currency": 8,
            "reward_exp": 15,
            "penalty_currency": 10,
            "difficulty": 2,
            "fields": [
                {"key": "sport", "label": "项目", "placeholder": "如 跑步/健身"},
                {"key": "target", "label": "目标量", "placeholder": "如 5公里"},
            ],
        },
        {
            "id": "work",
            "label": "工作",
            "reward_currency": 15,
            "reward_exp": 25,
            "penalty_currency": 20,
            "difficulty": 3,
            "fields": [
                {"key": "project", "label": "项目", "placeholder": ""},
                {"key": "deliverable", "label": "交付物", "placeholder": ""},
            ],
        },
        {
            "id": "life",
            "label": "生活琐事",
            "reward_currency": 5,
            "reward_exp": 8,
            "penalty_currency": 5,
            "difficulty": 1,
            "fields": [
                {"key": "place", "label": "地点", "placeholder": ""},
                {"key": "note", "label": "备注", "placeholder": ""},
            ],
        },
        {
            "id": "social",
            "label": "社交",
            "reward_currency": 12,
            "reward_exp": 15,
            "penalty_currency": 10,
            "difficulty": 2,
            "fields": [
                {"key": "person", "label": "对象", "placeholder": ""},
                {"key": "activity", "label": "活动", "placeholder": "如 吃饭/看电影"},
            ],
        },
    ],
    "affinity_levels": [
        {"min": 0, "max": 19, "label": "陌生", "color": "#9e9e9e"},
        {"min": 20, "max": 39, "label": "相识", "color": "#4caf50"},
        {"min": 40, "max": 59, "label": "熟悉", "color": "#29b6f6"},
        {"min": 60, "max": 79, "label": "信赖", "color": "#ab47bc"},
        {"min": 80, "max": 99, "label": "亲密", "color": "#ffb300"},
        {"min": 100, "max": 100, "label": "挚友", "color": "#ff6b6b"},
    ],
    "player_attrs": [
        {"key": "focus", "label": "专注", "value": 60, "max": 100},
        {"key": "energy", "label": "体力", "value": 60, "max": 100},
        {"key": "creativity", "label": "创造力", "value": 60, "max": 100},
        {"key": "mood", "label": "心情", "value": 70, "max": 100},
    ],
}


class EarthOnlineStore:
    """地球online 数据库访问层"""

    def __init__(self, db_path: str = DB_PATH):
        # v17: 镜像/模板/图片/备份目录一律跟随 db 所在目录推导。
        # 修复: 旧实现里这些路径按代码位置绝对推导，导致测试用临时库时
        # 把仓库里的真实镜像文件覆盖成空测试档。
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        base_dir = os.path.dirname(self.db_path)
        self.data_dir = os.path.join(base_dir, "earthonline")
        self.image_dir = os.path.join(self.data_dir, "images")
        self.mirror_path = os.path.join(self.data_dir, "earthonline.json")
        self.templates_path = os.path.join(self.data_dir, "templates.json")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        self.theme_path = os.path.join(self.data_dir, "theme.json")
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self._init_tables()
        self._seed_templates_file()
        self._write_mirror()

    # ── 配置读取 (qq_config.yaml → earth_online 节, 全部带默认值兜底) ──

    def _cfg(self, *path: str, default: Any = None) -> Any:
        try:
            from config.config_utils import get_qq_config

            value = get_qq_config("earth_online", *path, default=default)
            return default if value is None else value
        except Exception:
            return default

    # ── 连接与初始化 ────────────────────────────────

    @staticmethod
    def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
        """行工厂: 自动把 fields/attrs/subtasks 等 JSON 列解析为对象"""
        d: Dict[str, Any] = {}
        for idx, col in enumerate(cursor.description):
            v = row[idx]
            if col[0] in ("fields", "attrs", "subtasks", "context_snapshot", "raw_payload") and isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    if col[0] == "subtasks":
                        v = []
                    elif col[0] in ("fields", "context_snapshot", "raw_payload"):
                        v = {}
                    else:
                        v = []
            d[col[0]] = v
        return d

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = self._dict_factory
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        """列迁移: 缺失则 ALTER TABLE 添加"""
        cols = [r["name"] if isinstance(r, dict) else r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _init_tables(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS player_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    level INTEGER NOT NULL DEFAULT 1,
                    exp INTEGER NOT NULL DEFAULT 0,
                    currency INTEGER NOT NULL DEFAULT 100,
                    total_completed INTEGER NOT NULL DEFAULT 0,
                    total_failed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'other',
                    rarity TEXT NOT NULL DEFAULT 'common',
                    quantity INTEGER NOT NULL DEFAULT 1,
                    description TEXT DEFAULT '',
                    image_path TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'normal',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    quest_type TEXT NOT NULL DEFAULT 'branch',
                    must_complete INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    reward_exp INTEGER NOT NULL DEFAULT 0,
                    penalty_currency INTEGER NOT NULL DEFAULT 0,
                    deadline TEXT DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS story_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    event_type TEXT NOT NULL DEFAULT 'life',
                    character_id INTEGER,
                    item_id INTEGER,
                    happened_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    nickname TEXT DEFAULT '',
                    relationship TEXT NOT NULL DEFAULT 'friend',
                    affinity INTEGER NOT NULL DEFAULT 0,
                    avatar_path TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    birthday TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS affinity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (character_id) REFERENCES characters(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS quest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quest_id INTEGER,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    reward_exp INTEGER NOT NULL DEFAULT 0,
                    penalty_currency INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    icon TEXT DEFAULT '',
                    category TEXT NOT NULL DEFAULT 'general',
                    target INTEGER NOT NULL DEFAULT 1,
                    progress INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    unlocked_at TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    reward_exp INTEGER NOT NULL DEFAULT 0,
                    streak INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS miya_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    mood TEXT NOT NULL DEFAULT 'neutral',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL DEFAULT 'general',
                    icon TEXT DEFAULT '',
                    summary TEXT NOT NULL,
                    detail TEXT DEFAULT '',
                    quest_id INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    subtitle TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    icon TEXT DEFAULT '◇',
                    color TEXT DEFAULT '#c9ac67',
                    level_req INTEGER NOT NULL DEFAULT 1,
                    discovered INTEGER NOT NULL DEFAULT 0,
                    discovery_count INTEGER NOT NULL DEFAULT 0,
                    last_explored_at TEXT DEFAULT '',
                    image_path TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_discoveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region_key TEXT NOT NULL,
                    event_key TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'story',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    reward_exp INTEGER NOT NULL DEFAULT 0,
                    discovered_at TEXT NOT NULL,
                    context_snapshot TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(region_key, event_key)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_real_context_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'unavailable',
                    source_status TEXT NOT NULL DEFAULT 'unavailable',
                    city TEXT DEFAULT '',
                    latitude REAL,
                    longitude REAL,
                    weather TEXT DEFAULT '',
                    weather_icon TEXT DEFAULT '',
                    temperature REAL,
                    condition_code TEXT DEFAULT '',
                    humidity REAL,
                    wind TEXT DEFAULT '',
                    timezone TEXT DEFAULT '',
                    raw_payload TEXT NOT NULL DEFAULT '{}',
                    is_stale INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_real_context_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enabled INTEGER NOT NULL DEFAULT 1,
                    city TEXT NOT NULL DEFAULT '',
                    latitude REAL,
                    longitude REAL,
                    allow_precise_location INTEGER NOT NULL DEFAULT 0,
                    refresh_minutes INTEGER NOT NULL DEFAULT 30,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_custom_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'story',
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    reward_exp INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_event_purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_key TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    purchased_at TEXT NOT NULL,
                    UNIQUE(event_key, item_key)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_discovery_choices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discovery_id INTEGER UNIQUE NOT NULL,
                    choice TEXT NOT NULL,
                    chosen_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS miya_shop_purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_key TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    purchased_at TEXT NOT NULL
                )
                """
            )
            # ── v16: 弥娅专属商城商品后台可配置 (不再硬编码 MIYA_SHOP_ITEMS) ──
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS miya_shop_custom_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    cost INTEGER NOT NULL DEFAULT 10,
                    limit_count INTEGER NOT NULL DEFAULT 1,
                    kind TEXT NOT NULL DEFAULT 'interaction',
                    interaction TEXT DEFAULT '',
                    story_title TEXT DEFAULT '',
                    story_content TEXT DEFAULT '',
                    title_award TEXT DEFAULT '',
                    boost TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # ── v13: 后台可配置的限时活动 (不再硬编码活动区域/商品) ──
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_custom_event_areas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    subtitle TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    icon TEXT DEFAULT '✧',
                    color TEXT DEFAULT '#f0a35b',
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    reward_exp INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS world_custom_event_shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_key TEXT NOT NULL,
                    key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    cost INTEGER NOT NULL DEFAULT 0,
                    limit_count INTEGER NOT NULL DEFAULT 1,
                    kind TEXT NOT NULL DEFAULT 'collectible',
                    requires_discoveries INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(event_key, key)
                )
                """
            )

            # ── v17: 货币流水 (弥娅币/地球币/经验 全部走这里，周报不再解析文案) ──
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS currency_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    currency TEXT NOT NULL,
                    delta REAL NOT NULL,
                    reason TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            # ── v17: 回忆抽卡记录 ──
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_pulls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pool_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    rarity TEXT NOT NULL DEFAULT 'common',
                    is_new INTEGER NOT NULL DEFAULT 1,
                    item_id INTEGER,
                    refund_currency INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            # ── v17: 纪念日 (每年循环，临近自动开限时活动) ──
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS commemorations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    icon TEXT DEFAULT '✦',
                    lead_days INTEGER NOT NULL DEFAULT 2,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # ── v17: 每周纪行领取记录 ──
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS battle_pass_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week TEXT NOT NULL,
                    tier INTEGER NOT NULL,
                    reward_currency INTEGER NOT NULL DEFAULT 0,
                    claimed_at TEXT NOT NULL,
                    UNIQUE(week, tier)
                )
                """
            )

            # ── v2 迁移: 自定义字段 (JSON) ──
            self._ensure_column(conn, "items", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "quests", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "story_events", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "characters", "fields", "TEXT NOT NULL DEFAULT '{}'")

            # ── v3 迁移: 任务难度星级 (1-5) ──
            self._ensure_column(conn, "quests", "difficulty", "INTEGER NOT NULL DEFAULT 1")

            # ── v7 迁移: 任务子任务清单 (JSON: [{text, done}]) ──
            self._ensure_column(conn, "quests", "subtasks", "TEXT NOT NULL DEFAULT '[]'")
            # ── v7 迁移: 成就解锁奖励 ──
            self._ensure_column(conn, "achievements", "reward_currency", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "achievements", "reward_exp", "INTEGER NOT NULL DEFAULT 0")
            # ── v8 迁移: 成就称号 + 佩戴称号 ──
            self._ensure_column(conn, "achievements", "title_award", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "player_profile", "equipped_title", "TEXT NOT NULL DEFAULT ''")
            # ── v9 迁移: 剧情图片 + 动态评论 ──
            self._ensure_column(conn, "story_events", "image_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "activity_log", "comment", "TEXT NOT NULL DEFAULT ''")
            # ── v10 迁移: 弥娅币/地球币双轨 + 循环任务 ──
            self._ensure_column(conn, "player_profile", "miya_currency", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "player_profile", "earth_currency", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "quests", "recurring", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "world_discoveries", "kind", "TEXT NOT NULL DEFAULT 'story'")
            self._ensure_column(conn, "world_discoveries", "context_snapshot", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "world_regions", "image_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "world_regions", "resonance_xp", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "world_regions", "resonance_level", "INTEGER NOT NULL DEFAULT 1")
            # ── v13 迁移: 地理围栏探索 (区域绑定真实坐标, 半径米; 0 表示未启用) ──
            self._ensure_column(conn, "world_regions", "latitude", "REAL")
            self._ensure_column(conn, "world_regions", "longitude", "REAL")
            self._ensure_column(conn, "world_regions", "geofence_radius", "INTEGER NOT NULL DEFAULT 0")
            # ── v17 迁移: 签到睡眠记录 + 抽卡保底计数 + 属性恢复时间戳 ──
            self._ensure_column(conn, "daily_checkins", "sleep_hours", "REAL")
            self._ensure_column(conn, "daily_checkins", "energy_bonus", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "player_profile", "gacha_pity", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "player_profile", "attrs_updated_at", "TEXT NOT NULL DEFAULT ''")
            # 一次性数据迁移: 历史 currency (弥娅发放的奖励) → miya_currency
            conn.execute(
                "UPDATE player_profile SET miya_currency = currency WHERE miya_currency = 0 AND currency > 0"
            )

            # ── v4 迁移: Markdown 档案 (玩家/角色/道具三段式: 封面+简介+详情) ──
            self._ensure_column(conn, "items", "markdown", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "characters", "markdown", "TEXT NOT NULL DEFAULT ''")

            # ── v2 迁移: 开拓者角色卡 ──
            self._ensure_column(conn, "player_profile", "name", "TEXT NOT NULL DEFAULT '玩家'")
            self._ensure_column(conn, "player_profile", "title", "TEXT NOT NULL DEFAULT '地球online 玩家'")
            self._ensure_column(conn, "player_profile", "avatar_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "player_profile", "bio", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "player_profile", "attrs", "TEXT NOT NULL DEFAULT '[]'")

            # ── v4: 默认称呼 "开拓者" → "玩家" ──
            conn.execute("UPDATE player_profile SET name = '玩家' WHERE name = '开拓者'")
            conn.execute("UPDATE player_profile SET title = '地球online 玩家' WHERE title = '地球online 开拓者'")

            # 初始化玩家档案
            cur.execute("SELECT id FROM player_profile WHERE id = 1")
            if cur.fetchone() is None:
                now = datetime.now().isoformat()
                initial_currency = max(0, int(self._cfg("initial_currency", default=100)))
                cur.execute(
                    "INSERT INTO player_profile (id, level, exp, currency, miya_currency, earth_currency, created_at, updated_at) VALUES (1, 1, 0, ?, ?, 0, ?, ?)",
                    (initial_currency, initial_currency, now, now),
                )
            settings = cur.execute("SELECT id FROM world_real_context_settings WHERE id = 1").fetchone()
            if settings is None:
                cur.execute(
                    "INSERT INTO world_real_context_settings (id, updated_at) VALUES (1, ?)",
                    (datetime.now().isoformat(),),
                )
                # 首次建档时预置默认开拓者属性
                cur.execute(
                    "UPDATE player_profile SET attrs = ? WHERE id = 1",
                    (json.dumps(DEFAULT_TEMPLATES["player_attrs"], ensure_ascii=False),),
                )
            # 成就种子 (幂等: 按 key 已存在则跳过)
            self._seed_achievements(conn)
            self._seed_world_regions(conn)
            conn.commit()
        finally:
            conn.close()

    # ── 通用工具 ────────────────────────────────────

    def _seed_world_regions(self, conn: sqlite3.Connection) -> None:
        """写入单人世界地图区域定义，保留玩家探索进度。"""
        now = datetime.now().isoformat()
        for region in WORLD_REGION_SEEDS:
            exists = conn.execute("SELECT id FROM world_regions WHERE key = ?", (region["key"],)).fetchone()
            if exists:
                conn.execute(
                    "UPDATE world_regions SET name=?, subtitle=?, description=?, icon=?, color=?, level_req=?, updated_at=? WHERE key=?",
                    (
                        region["name"], region["subtitle"], region["description"], region["icon"],
                        region["color"], int(region["level_req"]), now, region["key"],
                    ),
                )
                continue
            conn.execute(
                "INSERT INTO world_regions (key, name, subtitle, description, icon, color, level_req, discovered, discovery_count, last_explored_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,0,0,'',?,?)",
                (
                    region["key"], region["name"], region["subtitle"], region["description"], region["icon"],
                    region["color"], int(region["level_req"]), now, now,
                ),
            )

    @staticmethod
    def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        return dict(row) if row is not None else None

    def _exp_to_level(self, exp: int) -> int:
        """经验值 → 等级 (每级所需经验递增: base * level; base 可配置 earth_online.level_exp_base)"""
        base = max(10, int(self._cfg("level_exp_base", default=100)))
        level = 1
        remain = int(exp)
        while remain >= level * base:
            remain -= level * base
            level += 1
        return level

    # ── 成就系统 ────────────────────────────────────

    # 成就进度来源: 从数据自动计算的函数 (key, 标题, 描述, 图标, 分类, 目标值, 是否隐藏, 解锁奖励币/经验, 解锁称号)
    ACHIEVEMENT_SEEDS: List[Dict[str, Any]] = [
        {"key": "first_quest", "title": "初次启程", "description": "完成第一个任务", "icon": "⚔", "category": "quest", "target": 1, "hidden": 0, "reward_currency": 30, "reward_exp": 50, "title_award": "启程者"},
        {"key": "quest_10", "title": "委托老手", "description": "累计完成 10 个任务", "icon": "≣", "category": "quest", "target": 10, "hidden": 0, "reward_currency": 100, "reward_exp": 150, "title_award": "委托老手"},
        {"key": "quest_50", "title": "任务大师", "description": "累计完成 50 个任务", "icon": "✪", "category": "quest", "target": 50, "hidden": 0, "reward_currency": 500, "reward_exp": 600, "title_award": "任务大师"},
        {"key": "item_5", "title": "小小收藏家", "description": "背包拥有 5 件物品", "icon": "▤", "category": "item", "target": 5, "hidden": 0, "reward_currency": 40, "reward_exp": 60, "title_award": "小小收藏家"},
        {"key": "item_20", "title": "收藏达人", "description": "背包拥有 20 件物品", "icon": "▣", "category": "item", "target": 20, "hidden": 0, "reward_currency": 150, "reward_exp": 200, "title_award": "收藏达人"},
        {"key": "epic_item", "title": "史诗之证", "description": "获得一件史诗物品", "icon": "◉", "category": "item", "target": 1, "hidden": 0, "reward_currency": 80, "reward_exp": 100, "title_award": "史诗持有者"},
        {"key": "legendary_item", "title": "传说降临", "description": "获得一件传说物品", "icon": "✦", "category": "item", "target": 1, "hidden": 0, "reward_currency": 200, "reward_exp": 300, "title_award": "传说见证者"},
        {"key": "char_5", "title": "结缘之人", "description": "图鉴收录 5 位角色", "icon": "❖", "category": "character", "target": 5, "hidden": 0, "reward_currency": 50, "reward_exp": 80, "title_award": "结缘之人"},
        {"key": "affinity_80", "title": "亲密无间", "description": "与一位角色好感度达到 80", "icon": "❤", "category": "character", "target": 80, "hidden": 0, "reward_currency": 120, "reward_exp": 150, "title_award": "亲密无间"},
        {"key": "story_10", "title": "人生编年史", "description": "记录 10 段人生剧情", "icon": "≋", "category": "story", "target": 10, "hidden": 0, "reward_currency": 60, "reward_exp": 90, "title_award": "编年史官"},
        {"key": "level_5", "title": "初露锋芒", "description": "达到 5 级", "icon": "◇", "category": "level", "target": 5, "hidden": 0, "reward_currency": 80, "reward_exp": 0, "title_award": "初露锋芒"},
        {"key": "level_10", "title": "声名鹊起", "description": "达到 10 级", "icon": "◆", "category": "level", "target": 10, "hidden": 0, "reward_currency": 200, "reward_exp": 0, "title_award": "声名鹊起"},
        {"key": "checkin_7", "title": "一周之约", "description": "连续签到 7 天", "icon": "◷", "category": "checkin", "target": 7, "hidden": 0, "reward_currency": 70, "reward_exp": 80, "title_award": "一周之约"},
        {"key": "checkin_30", "title": "月之守望", "description": "连续签到 30 天", "icon": "☾", "category": "checkin", "target": 30, "hidden": 0, "reward_currency": 300, "reward_exp": 350, "title_award": "月之守望"},
        # 图鉴收藏徽章: 8 类物品各集齐 3 件
        {"key": "digital_collect", "title": "数码爱好者", "description": "收集 3 件数码产品", "icon": "▣", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "数码爱好者"},
        {"key": "book_collect", "title": "藏书人", "description": "收集 3 本书籍", "icon": "≣", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "藏书人"},
        {"key": "life_collect", "title": "生活家", "description": "收集 3 件生活用品", "icon": "◈", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "生活家"},
        {"key": "food_collect", "title": "美食家", "description": "收集 3 件食品", "icon": "◍", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "美食家"},
        {"key": "tool_collect", "title": "工具控", "description": "收集 3 件工具", "icon": "◫", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "工具控"},
        {"key": "clothing_collect", "title": "衣橱达人", "description": "收集 3 件服饰", "icon": "◭", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "衣橱达人"},
        {"key": "collectible_collect", "title": "收藏家", "description": "收集 3 件收藏品", "icon": "✦", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "收藏家"},
        {"key": "other_collect", "title": "万物皆收", "description": "收集 3 件其他物品", "icon": "◻", "category": "collection", "target": 3, "hidden": 0, "reward_currency": 50, "reward_exp": 40, "title_award": "万物皆收"},
        {"key": "all_categories", "title": "全图鉴收藏家", "description": "8 类物品各至少 1 件", "icon": "✧", "category": "collection", "target": 8, "hidden": 0, "reward_currency": 300, "reward_exp": 200, "title_award": "全图鉴收藏家"},
        {"key": "world_3_regions", "title": "地图点亮者", "description": "在世界地图中发现 3 个区域", "icon": "◎", "category": "world", "target": 3, "hidden": 0, "reward_currency": 100, "reward_exp": 120, "title_award": "地图点亮者"},
        {"key": "world_complete", "title": "世界全景", "description": "完成所有世界区域的探索", "icon": "✦", "category": "world", "target": len(WORLD_REGION_SEEDS), "hidden": 0, "reward_currency": 400, "reward_exp": 500, "title_award": "世界观测者"},
    ]

    def _seed_achievements(self, conn: sqlite3.Connection) -> None:
        """播种成就定义 (upsert: 已有 key 同步文案/图标/奖励/称号, 保留进度与解锁状态)"""
        now = datetime.now().isoformat()
        try:
            from config.config_utils import get_text

            text_defs = get_text("earth_online", "achievements", "defs", default=None)
        except Exception:
            text_defs = None
        for seed in self.ACHIEVEMENT_SEEDS:
            overrides = {}
            if isinstance(text_defs, dict):
                overrides = text_defs.get(seed["key"]) or {}
            title = str(overrides.get("title", seed["title"]))
            description = str(overrides.get("description", seed["description"]))
            icon = str(overrides.get("icon", seed["icon"]))
            title_award = str(overrides.get("title_award", seed.get("title_award", "")))
            reward_currency = int(overrides.get("reward_currency", seed.get("reward_currency", 0)))
            reward_exp = int(overrides.get("reward_exp", seed.get("reward_exp", 0)))
            exists = conn.execute("SELECT id FROM achievements WHERE key = ?", (seed["key"],)).fetchone()
            if exists:
                conn.execute(
                    "UPDATE achievements SET title = ?, description = ?, icon = ?, target = ?, reward_currency = ?, reward_exp = ?, title_award = ?, category = ?, hidden = ? WHERE key = ?",
                    (title, description, icon, int(seed["target"]), reward_currency, reward_exp, title_award, seed["category"], 1 if seed["hidden"] else 0, seed["key"]),
                )
                continue
            conn.execute(
                "INSERT INTO achievements (key, title, description, icon, category, target, progress, hidden, unlocked_at, reward_currency, reward_exp, title_award, created_at) VALUES (?,?,?,?,?,?,0,?, '', ?, ?, ?, ?)",
                (seed["key"], title, description, icon, seed["category"], int(seed["target"]), 1 if seed["hidden"] else 0, reward_currency, reward_exp, title_award, now),
            )

    def list_achievements(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM achievements ORDER BY unlocked_at DESC, id ASC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def add_achievement(
        self,
        key: str,
        title: str,
        description: str = "",
        icon: str = "✦",
        category: str = "custom",
        target: int = 1,
        reward_currency: int = 0,
        reward_exp: int = 0,
        title_award: str = "",
        hidden: bool = False,
    ) -> Dict[str, Any]:
        """弥娅自定义成就 (key 已存在返回失败)"""
        key = str(key).strip()
        if not key or not str(title).strip():
            return {"success": False, "message": "key 与标题不能为空"}
        with self._lock:
            conn = self._connect()
            try:
                exists = conn.execute("SELECT id FROM achievements WHERE key = ?", (key,)).fetchone()
                if exists:
                    return {"success": False, "message": f"成就 key「{key}」已存在"}
                now = datetime.now().isoformat()
                cur = conn.execute(
                    "INSERT INTO achievements (key, title, description, icon, category, target, progress, hidden, unlocked_at, reward_currency, reward_exp, title_award, created_at) VALUES (?,?,?,?,?,?,0,?, '', ?, ?, ?, ?)",
                    (
                        key,
                        str(title).strip(),
                        str(description),
                        str(icon),
                        str(category),
                        max(1, int(target)),
                        1 if hidden else 0,
                        max(0, int(reward_currency)),
                        max(0, int(reward_exp)),
                        str(title_award),
                        now,
                    ),
                )
                self._log_activity(conn, "achievement", str(icon), f"弥娅定制成就: {title}", description, None)
                conn.commit()
                row = conn.execute("SELECT * FROM achievements WHERE id = ?", (cur.lastrowid,)).fetchone()
                result = {"success": True, "achievement": dict(row)}
            finally:
                conn.close()
        self._write_mirror()
        return result

    def set_achievement_progress(self, key: str, progress: int) -> Dict[str, Any]:
        """弥娅更新成就进度 (达标自动解锁并发奖励)"""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT * FROM achievements WHERE key = ?", (key,)).fetchone()
                if not row:
                    return {"success": False, "message": f"成就「{key}」不存在"}
                a = dict(row)
                prog = max(0, int(progress))
                now = datetime.now().isoformat()
                conn.execute("UPDATE achievements SET progress = ? WHERE key = ?", (prog, key))
                newly = None
                if not a["unlocked_at"] and prog >= int(a["target"]):
                    conn.execute("UPDATE achievements SET unlocked_at = ?, progress = ? WHERE key = ?", (now, prog, key))
                    rc = int(a.get("reward_currency", 0))
                    re = int(a.get("reward_exp", 0))
                    if rc or re:
                        self._grant_miya_locked(conn, rc, f"成就解锁: {a['title']}")
                        self._add_exp_locked(conn, re)
                    detail = f"奖励 +{rc} 弥娅币 · +{re} 经验" if (rc or re) else ""
                    if a.get("title_award"):
                        detail = (detail + " · " if detail else "") + f"获得称号「{a['title_award']}」"
                    self._log_activity(conn, "achievement", str(a.get("icon", "✪")), f"成就解锁: {a['title']}", detail, None)
                    self._react_locked(conn, "achievement", f"解锁成就「{a['title']}」")
                    newly = dict(conn.execute("SELECT * FROM achievements WHERE key = ?", (key,)).fetchone())
                conn.commit()
                result = {"success": True, "achievement": dict(conn.execute("SELECT * FROM achievements WHERE key = ?", (key,)).fetchone()), "newly_unlocked": newly}
            finally:
                conn.close()
        self._write_mirror()
        return result

    # ── 全局事件动态流 (数据互通: 所有模块自动记录) ──

    @staticmethod
    def _log_activity(conn: sqlite3.Connection, kind: str, icon: str, summary: str, detail: str = "", quest_id: Optional[int] = None) -> None:
        """写入一条全局动态 (必须在已有连接的事务中调用)"""
        conn.execute(
            "INSERT INTO activity_log (kind, icon, summary, detail, quest_id, created_at) VALUES (?,?,?,?,?,?)",
            (kind, icon, summary, detail, quest_id, datetime.now().isoformat()),
        )

    def _ledger_locked(self, conn: sqlite3.Connection, currency: str, delta: float, reason: str = "") -> None:
        """写一条货币/经验流水 (必须在持有锁的连接事务中调用)"""
        conn.execute(
            "INSERT INTO currency_ledger (currency, delta, reason, created_at) VALUES (?,?,?,?)",
            (str(currency), float(delta), str(reason)[:200], datetime.now().isoformat()),
        )

    def _grant_miya_locked(self, conn: sqlite3.Connection, amount: int, reason: str = "") -> None:
        """在持有锁的连接里发放/扣除弥娅币 (余额下限 0) 并记录流水。统一入口，周报不再解析文案。"""
        amount = int(amount)
        if not amount:
            return
        conn.execute(
            "UPDATE player_profile SET miya_currency = MAX(0, miya_currency + ?), updated_at = ? WHERE id = 1",
            (amount, datetime.now().isoformat()),
        )
        self._ledger_locked(conn, "miya", amount, reason)

    def list_activity(self, limit: int = 50, kind: str = "") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if kind:
                rows = conn.execute(
                    "SELECT * FROM activity_log WHERE kind = ? ORDER BY id DESC LIMIT ?", (kind, limit)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def refresh_achievements(self) -> List[Dict[str, Any]]:
        """按当前数据刷新全部成就进度并自动解锁新达成的成就, 返回新解锁列表 (earth_online.achievements.enabled 控制)"""
        if not bool(self._cfg("achievements", "enabled", default=True)):
            return []
        badge_target = max(1, int(self._cfg("collect", "badge_target", default=3)))
        player = self.get_player()
        items = self.list_items()
        characters = self.list_characters()
        stories = self.list_story(limit=100000)
        checkin_status = self.get_checkin_status()
        world_regions = self.list_world_regions()
        discovered_regions = sum(1 for region in world_regions if region.get("discovery_total", 0) > 0)
        completed_world = sum(
            1 for region in world_regions
            if region.get("event_total", 0) > 0 and region.get("discovery_total", 0) >= region.get("event_total", 0)
        )
        # 进度来源计算
        progress_map = {
            "first_quest": player.get("total_completed", 0),
            "quest_10": player.get("total_completed", 0),
            "quest_50": player.get("total_completed", 0),
            "item_5": len(items),
            "item_20": len(items),
            "epic_item": sum(1 for i in items if i.get("rarity") == "epic"),
            "legendary_item": sum(1 for i in items if i.get("rarity") == "legendary"),
            "char_5": len(characters),
            "affinity_80": max([c.get("affinity", 0) for c in characters], default=0),
            "story_10": len(stories),
            "level_5": player.get("level", 1),
            "level_10": player.get("level", 1),
            "checkin_7": checkin_status.get("streak", 0),
            "checkin_30": checkin_status.get("streak", 0),
            "world_3_regions": discovered_regions,
            "world_complete": completed_world,
        }
        # 图鉴收藏徽章: 8 类物品数量 + 全图鉴 (8 类各 >= 1)
        category_counts: Dict[str, int] = {}
        for i in items:
            cat = str(i.get("category", "other"))
            category_counts[cat] = category_counts.get(cat, 0) + 1
        for cat in ITEM_CATEGORIES:
            progress_map[f"{cat}_collect"] = category_counts.get(cat, 0)
        progress_map["all_categories"] = sum(1 for cat in ITEM_CATEGORIES if category_counts.get(cat, 0) > 0)
        newly_unlocked: List[Dict[str, Any]] = []
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                rows = conn.execute("SELECT * FROM achievements").fetchall()
                for row in rows:
                    a = dict(row)
                    # 图鉴徽章门槛可配置: 运行时同步 target (存量库不需要重建)
                    if str(a["key"]).endswith("_collect") and int(a["target"]) != badge_target:
                        conn.execute("UPDATE achievements SET target = ? WHERE id = ?", (badge_target, a["id"]))
                        a["target"] = badge_target
                    # 内置成就按数据自动计算; 弥娅自定义成就保留现有进度 (由 earth_set_achievement_progress 更新)
                    prog = max(0, int(progress_map.get(a["key"], a["progress"])))
                    if prog != a["progress"]:
                        conn.execute("UPDATE achievements SET progress = ? WHERE id = ?", (prog, a["id"]))
                    if not a["unlocked_at"] and prog >= int(a["target"]):
                        conn.execute("UPDATE achievements SET unlocked_at = ?, progress = ? WHERE id = ?", (now, prog, a["id"]))
                        reward_currency = int(a.get("reward_currency", 0))
                        reward_exp = int(a.get("reward_exp", 0))
                        if reward_currency or reward_exp:
                            self._grant_miya_locked(conn, reward_currency, f"成就解锁: {a['title']}")
                            self._add_exp_locked(conn, reward_exp)
                        title_award = str(a.get("title_award", ""))
                        detail = ""
                        if reward_currency or reward_exp:
                            detail = f"奖励 +{reward_currency} 弥娅币 · +{reward_exp} 经验"
                        if title_award:
                            detail = (detail + " · " if detail else "") + f"获得称号「{title_award}」"
                        self._log_activity(
                            conn, "achievement", str(a.get("icon", "✪")),
                            f"成就解锁: {a['title']}",
                            detail,
                        )
                        self._react_locked(conn, "achievement", f"解锁成就「{a['title']}」")
                        newly_unlocked.append({**a, "progress": prog, "unlocked_at": now, "reward_currency": reward_currency, "reward_exp": reward_exp})
                conn.commit()
            finally:
                conn.close()
        if newly_unlocked:
            self._write_mirror()
        return newly_unlocked

    # ── 每日签到 ────────────────────────────────────

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _date_shift(date_str: str, days: int) -> str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            from datetime import timedelta

            return (d + timedelta(days=days)).strftime("%Y-%m-%d")
        except Exception:
            return ""

    def get_checkin_status(self) -> Dict[str, Any]:
        """签到状态: 今天是否已签 / 连续天数 / 总天数 / 历史"""
        conn = self._connect()
        try:
            today = self._today()
            today_row = conn.execute("SELECT * FROM daily_checkins WHERE date = ?", (today,)).fetchone()
            rows = conn.execute("SELECT * FROM daily_checkins ORDER BY date ASC").fetchall()
            history = [dict(r) for r in rows]
            streak = 0
            # 连续签到: 从今天(或昨天)往前推
            cursor_date = today
            if today_row is None:
                cursor_date = self._date_shift(today, -1)
            dates = {r["date"] for r in history}
            while cursor_date in dates:
                streak += 1
                cursor_date = self._date_shift(cursor_date, -1)
            return {
                "today": today,
                "checked_today": today_row is not None,
                "streak": streak,
                "total_days": len(history),
                "today_reward": dict(today_row) if today_row else None,
                "history": history[-30:][::-1],
            }
        finally:
            conn.close()

    def checkin(self, sleep_hours: Optional[float] = None) -> Dict[str, Any]:
        """签到: 发放奖励 + 记录 + 刷新成就, 重复签到返回 already。

        sleep_hours: 昨晚睡眠时长 (小时)。传入时按睡眠质量回复体力——
        现实里睡得好，游戏里体力才回得多 (v17 现实数据连接)。
        """
        if not bool(self._cfg("checkin", "enabled", default=True)):
            return {"success": False, "message": "签到系统未启用 (earth_online.checkin.enabled)"}
        status = self.get_checkin_status()
        if status["checked_today"]:
            return {"success": False, "message": "already", "status": status}
        base_currency = int(self._cfg("checkin", "base_currency", default=10))
        base_exp = int(self._cfg("checkin", "base_exp", default=20))
        streak_bonus = int(self._cfg("checkin", "streak_bonus", default=2))
        streak_cap = int(self._cfg("checkin", "streak_cap", default=20))
        # 睡眠 → 体力: 每小时 +4, 上限 +40; 7-9 小时算"睡得好好"，额外 +5 心情
        energy_bonus = 0
        mood_extra = 0
        sleep_note = ""
        if sleep_hours is not None:
            try:
                sleep_hours = round(max(0.0, min(24.0, float(sleep_hours))), 1)
            except (TypeError, ValueError):
                sleep_hours = None
        if sleep_hours is not None:
            energy_bonus = int(min(40, sleep_hours * 4))
            if 7 <= sleep_hours <= 9:
                mood_extra = 5
                sleep_note = f"睡了 {sleep_hours} 小时，睡得好好"
            else:
                sleep_note = f"睡了 {sleep_hours} 小时"
        streak = status["streak"] + 1
        bonus = min(streak_bonus * (streak - 1), streak_cap)
        reward_currency = base_currency + bonus
        reward_exp = base_exp + streak - 1
        level_up: Optional[Dict[str, Any]] = None
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO daily_checkins (date, reward_currency, reward_exp, streak, sleep_hours, energy_bonus, created_at) VALUES (?,?,?,?,?,?,?)",
                    (self._today(), reward_currency, reward_exp, streak, sleep_hours, energy_bonus, now),
                )
                self._grant_miya_locked(conn, reward_currency, f"每日签到 (连签 {streak} 天)")
                level_up = self._add_exp_locked(conn, reward_exp)
                self._log_activity(
                    conn, "checkin", "◷", "每日签到",
                    f"连签 {streak} 天 · +{reward_currency} 弥娅币 +{reward_exp} 经验"
                    + (f" · {sleep_note} (体力 +{energy_bonus})" if sleep_note else ""),
                )
                self._react_locked(conn, "checkin", f"连签 {streak} 天")
                conn.commit()
            finally:
                conn.close()
        # 属性联动: 签到恢复体力与心情 (现实的开机仪式); 睡眠数据会替换基础体力回复量
        attr_changes = {
            "energy": self._adjust_attr("energy", energy_bonus if energy_bonus else 15),
            "mood": self._adjust_attr("mood", 5 + mood_extra),
        }
        self._write_mirror()
        self.refresh_achievements()
        return {
            "success": True,
            "reward": {"currency": reward_currency, "exp": reward_exp},
            "streak": streak,
            "sleep": {"hours": sleep_hours, "energy_bonus": energy_bonus, "mood_extra": mood_extra, "note": sleep_note},
            "player": self.get_player(),
            "status": self.get_checkin_status(),
            "level_up": level_up,
            "attrs": attr_changes,
        }

    def list_checkins(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM daily_checkins ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── 弥娅寄语 ────────────────────────────────────

    def add_note(self, content: str, mood: str = "neutral", pinned: bool = False) -> Dict[str, Any]:
        if not content or not content.strip():
            return {"success": False, "message": "内容不能为空"}
        if not bool(self._cfg("miya_notes", "enabled", default=True)):
            return {"success": False, "message": "弥娅寄语未启用 (earth_online.miya_notes.enabled)"}
        max_pinned = max(1, int(self._cfg("miya_notes", "max_pinned", default=3)))
        if pinned:
            # 置顶数达上限时自动取消最早的一条置顶 (先进先出)
            with self._lock:
                conn = self._connect()
                try:
                    count = conn.execute("SELECT COUNT(*) c FROM miya_notes WHERE pinned = 1").fetchone()["c"]
                    if count >= max_pinned:
                        oldest = conn.execute("SELECT id FROM miya_notes WHERE pinned = 1 ORDER BY id ASC LIMIT 1").fetchone()
                        if oldest:
                            conn.execute("UPDATE miya_notes SET pinned = 0 WHERE id = ?", (oldest["id"],))
                    conn.commit()
                finally:
                    conn.close()
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                cur = conn.execute(
                    "INSERT INTO miya_notes (content, mood, pinned, created_at) VALUES (?,?,?,?)",
                    (content.strip(), mood, 1 if pinned else 0, now),
                )
                self._log_activity(conn, "note", "✉", "弥娅发布寄语", content.strip()[:60])
                conn.commit()
                row = conn.execute("SELECT * FROM miya_notes WHERE id = ?", (cur.lastrowid,)).fetchone()
                result = dict(row)
            finally:
                conn.close()
        self._write_mirror()
        return result

    def list_notes(self, limit: int = 30) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM miya_notes ORDER BY pinned DESC, id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_note(self, note_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM miya_notes WHERE id = ?", (note_id,))
                conn.commit()
                deleted = cur.rowcount > 0
            finally:
                conn.close()
        if deleted:
            self._write_mirror()
        return deleted

    def pin_note(self, note_id: int, pinned: bool) -> Optional[Dict[str, Any]]:
        max_pinned = max(1, int(self._cfg("miya_notes", "max_pinned", default=3)))
        with self._lock:
            conn = self._connect()
            try:
                if pinned:
                    # 置顶数达上限时自动取消最早的一条置顶
                    count = conn.execute("SELECT COUNT(*) c FROM miya_notes WHERE pinned = 1 AND id != ?", (note_id,)).fetchone()["c"]
                    if count >= max_pinned:
                        oldest = conn.execute("SELECT id FROM miya_notes WHERE pinned = 1 AND id != ? ORDER BY id ASC LIMIT 1", (note_id,)).fetchone()
                        if oldest:
                            conn.execute("UPDATE miya_notes SET pinned = 0 WHERE id = ?", (oldest["id"],))
                conn.execute("UPDATE miya_notes SET pinned = ? WHERE id = ?", (1 if pinned else 0, note_id))
                conn.commit()
                row = conn.execute("SELECT * FROM miya_notes WHERE id = ?", (note_id,)).fetchone()
                result = dict(row) if row else None
            finally:
                conn.close()
        self._write_mirror()
        return result

    # ── 称号系统 ────────────────────────────────────

    def list_titles(self) -> Dict[str, Any]:
        """可佩戴称号: 默认称号 + 成就称号 + 弥娅商城称号 + 当前佩戴"""
        default = "地球online 玩家"
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT key, title_award, icon, unlocked_at FROM achievements WHERE unlocked_at != '' AND title_award != '' ORDER BY unlocked_at ASC"
            ).fetchall()
            purchased_shop_keys = {
                str(row["item_key"])
                for row in conn.execute("SELECT DISTINCT item_key FROM miya_shop_purchases").fetchall()
            }
            player_row = conn.execute("SELECT equipped_title FROM player_profile WHERE id = 1").fetchone()
            equipped = (dict(player_row).get("equipped_title") if player_row else "") or default
            unlocked = [
                {"key": r["key"], "title": r["title_award"], "icon": r["icon"], "unlocked_at": r["unlocked_at"]}
                for r in rows
            ]
            for item in MIYA_SHOP_ITEMS:
                if item.get("kind") == "title" and item["key"] in purchased_shop_keys:
                    unlocked.append({"key": item["key"], "title": item.get("title_award") or item["name"], "icon": "❦", "unlocked_at": "商城兑换"})
            return {
                "default": default,
                "equipped": equipped,
                "unlocked": unlocked,
            }
        finally:
            conn.close()

    def equip_title(self, title: str) -> Dict[str, Any]:
        """佩戴称号 (必须是默认称号或已解锁的成就称号)"""
        info = self.list_titles()
        valid = {t["title"] for t in info["unlocked"]} | {info["default"]}
        if title not in valid:
            return {"success": False, "message": "该称号尚未解锁"}
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE player_profile SET equipped_title = ?, updated_at = ? WHERE id = 1",
                    (title, datetime.now().isoformat()),
                )
                self._log_activity(conn, "title", "◆", f"佩戴称号: {title}")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {"success": True, "equipped": title, "titles": self.list_titles()}

    # ── 到期提醒 ────────────────────────────────────

    def list_due_soon(self, days: int = 3) -> List[Dict[str, Any]]:
        """即将到期(或已逾期未处理)的任务: deadline 在 now ~ now+days 之间, 或已过期"""
        from datetime import timedelta

        conn = self._connect()
        try:
            now = datetime.now()
            horizon = (now + timedelta(days=max(1, int(days)))).isoformat()
            rows = conn.execute(
                "SELECT * FROM quests WHERE status IN ('pending', 'ongoing') AND deadline != '' AND deadline <= ? ORDER BY deadline ASC",
                (horizon,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── 每周报告 ────────────────────────────────────

    def get_weekly_report(self) -> Dict[str, Any]:
        """本周(周一起)统计: 完成/失败/签到/动态/成就/好感/赚取地球币"""
        import re
        from datetime import timedelta

        conn = self._connect()
        try:
            now = datetime.now()
            monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            monday_iso = monday.isoformat()
            monday_date = monday.strftime("%Y-%m-%d")
            done = conn.execute(
                "SELECT COUNT(*) c FROM quest_history WHERE status = 'completed' AND completed_at >= ?", (monday_iso,)
            ).fetchone()["c"]
            failed = conn.execute(
                "SELECT COUNT(*) c FROM quest_history WHERE status = 'failed' AND completed_at >= ?", (monday_iso,)
            ).fetchone()["c"]
            checkins = conn.execute(
                "SELECT COUNT(*) c FROM daily_checkins WHERE date >= ?", (monday_date,)
            ).fetchone()["c"]
            activities = conn.execute(
                "SELECT COUNT(*) c FROM activity_log WHERE created_at >= ?", (monday_iso,)
            ).fetchone()["c"]
            achievements = conn.execute(
                "SELECT COUNT(*) c FROM achievements WHERE unlocked_at >= ?", (monday_iso,)
            ).fetchone()["c"]
            affinity_changes = conn.execute(
                "SELECT COUNT(*) c FROM affinity_logs WHERE created_at >= ?", (monday_iso,)
            ).fetchone()["c"]
            earned_currency = 0
            earned_exp = 0
            ledger_rows = conn.execute(
                "SELECT currency, SUM(delta) s FROM currency_ledger WHERE created_at >= ? AND delta > 0 GROUP BY currency",
                (monday_iso,),
            ).fetchall()
            if ledger_rows:
                # v17: 优先用货币流水精确统计 (不再依赖动态文案格式)
                for entry in ledger_rows:
                    if entry["currency"] == "miya":
                        earned_currency += int(entry["s"])
                    elif entry["currency"] == "exp":
                        earned_exp += int(entry["s"])
            else:
                # 历史数据没有流水 → 回退旧的正则口径
                for a in conn.execute(
                    "SELECT detail FROM activity_log WHERE created_at >= ? AND detail != ''", (monday_iso,)
                ).fetchall():
                    detail = a["detail"] or ""
                    m = re.search(r"\+(\d+)\s+(?:弥娅币|地球币)", detail)
                    if m:
                        earned_currency += int(m.group(1))
                    m2 = re.search(r"\+(\d+) 经验", detail)
                    if m2:
                        earned_exp += int(m2.group(1))
            finished = done + failed
            return {
                "week_start": monday_date,
                "quests": {
                    "completed": done,
                    "failed": failed,
                    "completion_rate": round(done / finished * 100) if finished else 0,
                },
                "checkins": checkins,
                "activities": activities,
                "achievements": achievements,
                "affinity_changes": affinity_changes,
                "earned": {"currency": earned_currency, "exp": earned_exp},
                "player": self.get_player(),
            }
        finally:
            conn.close()

    # ── 统计数据中心 ─────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """可视化统计: 任务/物品/角色/剧情/签到/成就 多维分布与趋势"""
        conn = self._connect()
        try:
            player = self.get_player()
            quests = self.list_quests()
            items = self.list_items()
            characters = self.list_characters()
            stories = self.list_story(limit=100000)
            history = self.quest_history(limit=10000)
            checkin_status = self.get_checkin_status()
            achievements = self.list_achievements()

            def dist(rows: List[Dict[str, Any]], field: str) -> Dict[str, int]:
                d: Dict[str, int] = {}
                for r in rows:
                    k = str(r.get(field, "unknown"))
                    d[k] = d.get(k, 0) + 1
                return d

            quest_status = dist(quests, "status")
            quest_type = dist(quests, "quest_type")
            item_rarity = dist(items, "rarity")
            item_category = dist(items, "category")
            story_type = dist(stories, "event_type")
            relationship = dist(characters, "relationship")
            total_done = quest_status.get("completed", 0)
            total_failed = quest_status.get("failed", 0)
            finished = total_done + total_failed
            # 最近 7 天完成趋势 (来自 quest_history)
            from datetime import timedelta

            trend_days: List[Dict[str, Any]] = []
            today = datetime.now().date()
            day_counts: Dict[str, int] = {}
            for h in history:
                if h.get("status") != "completed":
                    continue
                try:
                    d = datetime.fromisoformat(h["completed_at"]).date()
                except Exception:
                    continue
                key = d.isoformat()
                day_counts[key] = day_counts.get(key, 0) + 1
            for i in range(6, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                trend_days.append({"date": d, "count": day_counts.get(d, 0)})
            unlocked = [a for a in achievements if a.get("unlocked_at")]
            return {
                "player": player,
                "quests": {
                    "total": len(quests),
                    "status": quest_status,
                    "types": quest_type,
                    "completed": total_done,
                    "failed": total_failed,
                    "completion_rate": round(total_done / finished * 100) if finished else 0,
                    "trend_7d": trend_days,
                },
                "items": {"total": len(items), "rarity": item_rarity, "categories": item_category},
                "characters": {
                    "total": len(characters),
                    "relationships": relationship,
                    "affinity_ranking": sorted(
                        [{"id": c["id"], "name": c["name"], "affinity": c["affinity"]} for c in characters],
                        key=lambda x: x["affinity"],
                        reverse=True,
                    )[:10],
                },
                "stories": {"total": len(stories), "types": story_type},
                "checkin": checkin_status,
                "achievements": {
                    "total": len(achievements),
                    "unlocked": len(unlocked),
                    "recent": [a for a in achievements if a.get("unlocked_at")][:5],
                },
            }
        finally:
            conn.close()

    # ── 模板库 ──────────────────────────────────────

    def _seed_templates_file(self) -> None:
        """templates.json 缺失时用默认模板生成"""
        if not os.path.isfile(self.templates_path):
            try:
                with open(self.templates_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_TEMPLATES, f, ensure_ascii=False, indent=2)
                logger.info("[EarthOnline] 已生成默认模板文件 templates.json")
            except Exception as e:
                logger.warning(f"[EarthOnline] 模板文件生成失败: {e}")

    def get_templates(self) -> Dict[str, Any]:
        """读取模板 (文件 + 默认值兜底)"""
        templates = json.loads(json.dumps(DEFAULT_TEMPLATES, ensure_ascii=False))
        try:
            if os.path.isfile(self.templates_path):
                with open(self.templates_path, "r", encoding="utf-8") as f:
                    user_templates = json.load(f)
                for key, value in user_templates.items():
                    templates[key] = value
        except Exception as e:
            logger.warning(f"[EarthOnline] 模板读取失败: {e}")
        return templates

    def save_templates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """保存模板库 (用户自定义)"""
        try:
            with open(self.templates_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return self.get_templates()
        except Exception as e:
            logger.error(f"[EarthOnline] 模板保存失败: {e}")
            raise

    # ── JSON 可视化 (记事本模式) ────────────────────

    def export_json(self) -> Dict[str, Any]:
        """导出全部数据为 JSON 结构 (含模板)"""
        return {
            "version": 2,
            "exported_at": datetime.now().isoformat(),
            "player": self.get_player(),
            "items": self.list_items(),
            "quests": self.list_quests(),
            "quest_history": self.quest_history(limit=1000),
            "characters": self.list_characters(),
            "stories": self.list_story(limit=10000),
            "affinity_logs": self._all_affinity_logs(),
            "achievements": self.list_achievements(),
            "checkins": self.list_checkins(limit=10000),
            "miya_notes": self.list_notes(limit=1000),
            "activity": self.list_activity(limit=2000),
            "world_regions": self.list_world_regions(),
            "world_discoveries": self.list_world_discoveries(limit=10000),
            "memory_pulls": self.list_memory_pulls(limit=10000),
            "commemorations": self.list_commemorations(),
            "currency_ledger": self.list_currency_ledger(limit=2000),
            "templates": self.get_templates(),
        }

    def list_currency_ledger(self, limit: int = 100, currency: str = "") -> List[Dict[str, Any]]:
        """货币/经验流水 (v17: 弥娅币/地球币/经验 全部走这里)"""
        conn = self._connect()
        try:
            if currency:
                rows = conn.execute(
                    "SELECT * FROM currency_ledger WHERE currency = ? ORDER BY id DESC LIMIT ?",
                    (currency, max(1, min(5000, int(limit)))),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM currency_ledger ORDER BY id DESC LIMIT ?",
                    (max(1, min(5000, int(limit))),),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _all_affinity_logs(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM affinity_logs ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _write_mirror(self) -> None:
        """把全部数据镜像到 db 同目录的 earthonline.json (可视化文件, 跟随存档走)"""
        try:
            data = self.export_json()
            tmp = self.mirror_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.mirror_path)
        except Exception as e:
            logger.warning(f"[EarthOnline] JSON 镜像写入失败: {e}")

    def read_mirror(self) -> Dict[str, Any]:
        """读取镜像文件内容"""
        try:
            if os.path.isfile(self.mirror_path):
                with open(self.mirror_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"[EarthOnline] 镜像读取失败: {e}")
        return self.export_json()

    def import_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """从 JSON 结构整体导入 (覆盖数据库, 自动备份)

        JSON 结构与 export_json 输出一致: player/items/quests/characters/stories/templates
        """
        if not isinstance(data, dict):
            raise ValueError("导入数据必须是 JSON 对象")
        # 备份当前数据库 (跟随存档目录)
        backup_path = os.path.join(self.backup_dir, f"earthonline-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
        try:
            with self._lock:
                shutil.copy2(self.db_path, backup_path)
        except Exception as e:
            logger.warning(f"[EarthOnline] 备份失败: {e}")

        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                player = data.get("player") or {}
                conn.execute(
                    "UPDATE player_profile SET name=?, title=?, avatar_path=?, bio=?, attrs=?, exp=?, miya_currency=?, earth_currency=?, total_completed=?, total_failed=?, equipped_title=?, updated_at=? WHERE id=1",
                    (
                        str(player.get("name", "玩家")),
                        str(player.get("title", "地球online 玩家")),
                        str(player.get("avatar_path", "")),
                        str(player.get("bio", "")),
                        json.dumps(player.get("attrs", []), ensure_ascii=False),
                        max(0, int(player.get("exp", 0))),
                        max(0, int(player.get("miya_currency", player.get("currency", 0)))),
                        max(0, int(player.get("earth_currency", 0))),
                        max(0, int(player.get("total_completed", 0))),
                        max(0, int(player.get("total_failed", 0))),
                        str(player.get("equipped_title", "")),
                        now,
                    ),
                )
                # 重建实体表
                conn.execute("DELETE FROM quest_history")
                conn.execute("DELETE FROM affinity_logs")
                conn.execute("DELETE FROM items")
                for it in data.get("items", []):
                    conn.execute(
                        "INSERT INTO items (id, name, category, rarity, quantity, description, image_path, status, markdown, fields, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            int(it.get("id", 0)) if it.get("id") else None,
                            str(it.get("name", "")), str(it.get("category", "other")), str(it.get("rarity", "common")),
                            max(1, int(it.get("quantity", 1))), str(it.get("description", "")), str(it.get("image_path", "")),
                            str(it.get("status", "normal")), str(it.get("markdown", "")),
                            json.dumps(it.get("fields", {}), ensure_ascii=False),
                            str(it.get("created_at", now)), str(it.get("updated_at", now)),
                        ),
                    )
                conn.execute("DELETE FROM quests")
                for q in data.get("quests", []):
                    conn.execute(
                        "INSERT INTO quests (id, title, description, quest_type, must_complete, status, reward_currency, reward_exp, penalty_currency, deadline, source, difficulty, fields, subtasks, recurring, created_at, completed_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            int(q.get("id", 0)) if q.get("id") else None,
                            str(q.get("title", "")), str(q.get("description", "")), str(q.get("quest_type", "branch")),
                            1 if q.get("must_complete") else 0, str(q.get("status", "pending")),
                            max(0, int(q.get("reward_currency", 0))), max(0, int(q.get("reward_exp", 0))),
                            max(0, int(q.get("penalty_currency", 0))), str(q.get("deadline", "")), str(q.get("source", "manual")),
                            max(1, min(5, int(q.get("difficulty", 1)))),
                            json.dumps(q.get("fields", {}), ensure_ascii=False),
                            json.dumps(q.get("subtasks", []), ensure_ascii=False),
                            str(q.get("recurring", "")),
                            str(q.get("created_at", now)), str(q.get("completed_at", "")), str(q.get("updated_at", now)),
                        ),
                    )
                conn.execute("DELETE FROM characters")
                for c in data.get("characters", []):
                    conn.execute(
                        "INSERT INTO characters (id, name, nickname, relationship, affinity, avatar_path, notes, birthday, markdown, fields, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            int(c.get("id", 0)) if c.get("id") else None,
                            str(c.get("name", "")), str(c.get("nickname", "")), str(c.get("relationship", "friend")),
                            max(0, min(100, int(c.get("affinity", 0)))), str(c.get("avatar_path", "")), str(c.get("notes", "")),
                            str(c.get("birthday", "")), str(c.get("markdown", "")),
                            json.dumps(c.get("fields", {}), ensure_ascii=False),
                            str(c.get("created_at", now)), str(c.get("updated_at", now)),
                        ),
                    )
                for history in data.get("quest_history", []):
                    conn.execute(
                        "INSERT INTO quest_history (id, quest_id, title, status, reward_currency, reward_exp, penalty_currency, completed_at) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            int(history.get("id", 0)) if history.get("id") else None,
                            int(history["quest_id"]) if history.get("quest_id") else None,
                            str(history.get("title", "")), str(history.get("status", "")),
                            max(0, int(history.get("reward_currency", 0))), max(0, int(history.get("reward_exp", 0))),
                            max(0, int(history.get("penalty_currency", 0))), str(history.get("completed_at", now)),
                        ),
                    )
                for affinity in data.get("affinity_logs", []):
                    conn.execute(
                        "INSERT INTO affinity_logs (id, character_id, delta, reason, created_at) VALUES (?,?,?,?,?)",
                        (
                            int(affinity.get("id", 0)) if affinity.get("id") else None,
                            int(affinity.get("character_id", 0)), int(affinity.get("delta", 0)),
                            str(affinity.get("reason", "")), str(affinity.get("created_at", now)),
                        ),
                    )
                conn.execute("DELETE FROM story_events")
                for s in data.get("stories", []):
                    conn.execute(
                        "INSERT INTO story_events (id, title, content, event_type, character_id, item_id, happened_at, fields, image_path, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            int(s.get("id", 0)) if s.get("id") else None,
                            str(s.get("title", "")), str(s.get("content", "")), str(s.get("event_type", "life")),
                            int(s["character_id"]) if s.get("character_id") else None,
                            int(s["item_id"]) if s.get("item_id") else None,
                            str(s.get("happened_at", now)), json.dumps(s.get("fields", {}), ensure_ascii=False),
                            str(s.get("image_path", "")),
                            str(s.get("created_at", now)),
                        ),
                    )
                # 重建成就 (保留进度/解锁状态)
                conn.execute("DELETE FROM achievements")
                for a in data.get("achievements", []):
                    conn.execute(
                        "INSERT INTO achievements (id, key, title, description, icon, category, target, progress, hidden, unlocked_at, reward_currency, reward_exp, title_award, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            int(a.get("id", 0)) if a.get("id") else None,
                            str(a.get("key", "")), str(a.get("title", "")), str(a.get("description", "")),
                            str(a.get("icon", "")), str(a.get("category", "general")),
                            max(1, int(a.get("target", 1))), max(0, int(a.get("progress", 0))),
                            1 if a.get("hidden") else 0, str(a.get("unlocked_at", "")),
                            max(0, int(a.get("reward_currency", 0))), max(0, int(a.get("reward_exp", 0))),
                            str(a.get("title_award", "")),
                            str(a.get("created_at", now)),
                        ),
                    )
                self._seed_achievements(conn)
                # 重建签到记录
                conn.execute("DELETE FROM daily_checkins")
                for c in data.get("checkins", []):
                    conn.execute(
                        "INSERT INTO daily_checkins (id, date, reward_currency, reward_exp, streak, created_at) VALUES (?,?,?,?,?,?)",
                        (
                            int(c.get("id", 0)) if c.get("id") else None,
                            str(c.get("date", "")), max(0, int(c.get("reward_currency", 0))),
                            max(0, int(c.get("reward_exp", 0))), max(1, int(c.get("streak", 1))),
                            str(c.get("created_at", now)),
                        ),
                    )
                # 重建弥娅寄语
                conn.execute("DELETE FROM miya_notes")
                for n in data.get("miya_notes", []):
                    conn.execute(
                        "INSERT INTO miya_notes (id, content, mood, pinned, created_at) VALUES (?,?,?,?,?)",
                        (
                            int(n.get("id", 0)) if n.get("id") else None,
                            str(n.get("content", "")), str(n.get("mood", "neutral")),
                            1 if n.get("pinned") else 0, str(n.get("created_at", now)),
                        ),
                    )
                # 重建全局动态流
                conn.execute("DELETE FROM activity_log")
                for act in data.get("activity", []):
                    conn.execute(
                        "INSERT INTO activity_log (id, kind, icon, summary, detail, quest_id, comment, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            int(act.get("id", 0)) if act.get("id") else None,
                            str(act.get("kind", "general")), str(act.get("icon", "")),
                            str(act.get("summary", "")), str(act.get("detail", "")),
                            int(act["quest_id"]) if act.get("quest_id") else None,
                            str(act.get("comment", "")),
                            str(act.get("created_at", now)),
                        ),
                    )
                # 重建世界地图探索进度；缺少该字段时保留当前已播种区域
                if "world_regions" in data:
                    conn.execute("DELETE FROM world_discoveries")
                    conn.execute("DELETE FROM world_regions")
                    self._seed_world_regions(conn)
                    for region in data.get("world_regions", []):
                        key = str(region.get("key", ""))
                        if not key:
                            continue
                        conn.execute(
                            "UPDATE world_regions SET discovered=?, discovery_count=?, last_explored_at=?, updated_at=? WHERE key=?",
                            (
                                max(0, int(region.get("discovered", 0))), max(0, int(region.get("discovery_count", 0))),
                                str(region.get("last_explored_at", "")), now, key,
                            ),
                        )
                    for discovery in data.get("world_discoveries", []):
                        conn.execute(
                            "INSERT OR IGNORE INTO world_discoveries (id, region_key, event_key, kind, title, content, reward_currency, reward_exp, discovered_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (
                                int(discovery.get("id", 0)) if discovery.get("id") else None,
                                str(discovery.get("region_key", "")), str(discovery.get("event_key", "")), str(discovery.get("kind", "story")),
                                str(discovery.get("title", "")), str(discovery.get("content", "")),
                                max(0, int(discovery.get("reward_currency", 0))), max(0, int(discovery.get("reward_exp", 0))),
                                str(discovery.get("discovered_at", now)),
                            ),
                        )
                # v17: 重建纪念日与回忆抽卡记录 (缺字段时保留现状)
                if "commemorations" in data:
                    conn.execute("DELETE FROM commemorations")
                    for memo in data.get("commemorations", []):
                        conn.execute(
                            "INSERT INTO commemorations (id, key, name, date, description, icon, lead_days, enabled, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (
                                int(memo.get("id", 0)) if memo.get("id") else None,
                                str(memo.get("key", "")), str(memo.get("name", "")), str(memo.get("date", "")),
                                str(memo.get("description", "")), str(memo.get("icon", "✦")),
                                max(0, int(memo.get("lead_days", 2))), 1 if memo.get("enabled", 1) else 0,
                                str(memo.get("created_at", now)), str(memo.get("updated_at", now)),
                            ),
                        )
                if "memory_pulls" in data:
                    conn.execute("DELETE FROM memory_pulls")
                    for pull in data.get("memory_pulls", []):
                        conn.execute(
                            "INSERT INTO memory_pulls (id, pool_key, title, rarity, is_new, item_id, refund_currency, created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (
                                int(pull.get("id", 0)) if pull.get("id") else None,
                                str(pull.get("pool_key", "")), str(pull.get("title", "")), str(pull.get("rarity", "common")),
                                1 if pull.get("is_new", 1) else 0,
                                int(pull["item_id"]) if pull.get("item_id") else None,
                                max(0, int(pull.get("refund_currency", 0))), str(pull.get("created_at", now)),
                            ),
                        )
                conn.commit()
            finally:
                conn.close()

        if isinstance(data.get("templates"), dict):
            try:
                self.save_templates(data["templates"])
            except Exception as e:
                logger.warning(f"[EarthOnline] 模板导入失败: {e}")
        self._write_mirror()
        return {"success": True, "backup": backup_path, "summary": self.summary()}

    # ── 玩家状态 ────────────────────────────────────

    def get_player(self) -> Dict[str, Any]:
        self._apply_energy_regen()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            if row is None:
                return {}
            data = dict(row)
            data["level"] = self._exp_to_level(data.get("exp", 0))
            # 双币制: miya_currency=弥娅发放的互动货币, earth_currency=佳自己管理的现实资产 (人民币元)
            data["currency"] = data.get("miya_currency", data.get("currency", 0))  # 兼容别名
            # 等级一致性提示: 存量库 level 列若与经验曲线不符 (历史手工改库) 标记给前端/周报
            if int(data.get("level") or 0) != self._exp_to_level(int(data.get("exp", 0))):
                data["level_column_stale"] = True
            return data
        finally:
            conn.close()

    def _apply_energy_regen(self) -> None:
        """体力 (energy) 随现实时间恢复: 每小时 +N 点，上限为属性条 max。

        懒结算: 每次读玩家档案时补发；用非阻塞锁拿不到就跳过 (下次再补)，避免与持锁流程重入死锁。
        时间戳按"消耗掉的小时数"推进，零头会保留到下一次结算。
        """
        rate = int(self._cfg("attrs", "energy_regen_per_hour", default=4))
        if rate <= 0:
            return
        if not self._lock.acquire(blocking=False):
            return
        try:
            conn = self._connect()
            try:
                row = conn.execute("SELECT attrs, attrs_updated_at, created_at FROM player_profile WHERE id = 1").fetchone()
                if not row:
                    return
                try:
                    attrs = json.loads(row["attrs"]) if isinstance(row["attrs"], str) else (row["attrs"] or [])
                except Exception:
                    attrs = []
                energy = next((a for a in attrs if isinstance(a, dict) and a.get("key") == "energy"), None)
                if not energy:
                    return
                now = datetime.now()
                last_raw = str(row.get("attrs_updated_at") or row.get("created_at") or "")
                try:
                    last = datetime.fromisoformat(last_raw) if last_raw else now
                except ValueError:
                    last = now
                if last > now:
                    last = now
                elapsed_hours = (now - last).total_seconds() / 3600.0
                regen = int(elapsed_hours * rate)
                if regen <= 0:
                    return
                value = int(energy.get("value", 0))
                cap = int(energy.get("max", 100))
                if value >= cap:
                    # 满体力时只推进时间戳，不记账
                    conn.execute("UPDATE player_profile SET attrs_updated_at = ? WHERE id = 1", (now.isoformat(),))
                    conn.commit()
                    return
                gained = min(regen, cap - value)
                energy["value"] = value + gained
                consumed_hours = gained / float(rate)
                advanced = last.isoformat() if consumed_hours <= 0 else (last + timedelta(hours=consumed_hours)).isoformat()
                conn.execute(
                    "UPDATE player_profile SET attrs = ?, attrs_updated_at = ? WHERE id = 1",
                    (json.dumps(attrs, ensure_ascii=False), advanced),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.debug(f"[EarthOnline] 体力恢复结算失败: {exc}")
        finally:
            self._lock.release()

    def update_player(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """更新开拓者角色卡: name/title/avatar_path/bio/attrs/exp/currency(弥娅币)/earth_currency(现实资产)"""
        allowed = {"name", "title", "avatar_path", "bio", "attrs", "exp", "currency", "earth_currency"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_player()
        # currency 字段语义为弥娅币 (历史兼容)
        if "currency" in updates:
            updates["miya_currency"] = max(0, int(updates.pop("currency")))
        if "earth_currency" in updates:
            updates["earth_currency"] = max(0.0, float(updates["earth_currency"]))
        with self._lock:
            conn = self._connect()
            try:
                # 直接改余额/经验也走流水 (v17: 周报与资产曲线不再依赖文案解析)
                if any(k in updates for k in ("miya_currency", "earth_currency", "exp")):
                    current = conn.execute("SELECT miya_currency, earth_currency, exp FROM player_profile WHERE id = 1").fetchone() or {}
                    if "miya_currency" in updates:
                        self._ledger_locked(conn, "miya", int(updates["miya_currency"]) - int(current.get("miya_currency", 0)), "档案手动调整")
                    if "earth_currency" in updates:
                        self._ledger_locked(conn, "earth", round(float(updates["earth_currency"]) - float(current.get("earth_currency", 0)), 2), "现实资产手动调整")
                    if "exp" in updates:
                        self._ledger_locked(conn, "exp", int(updates["exp"]) - int(current.get("exp", 0)), "经验手动调整")
                sets, params = [], []
                for k, v in updates.items():
                    if k == "attrs":
                        v = json.dumps(v, ensure_ascii=False)
                    sets.append(f"{k} = ?")
                    params.append(v)
                params.append(datetime.now().isoformat())
                conn.execute(f"UPDATE player_profile SET {', '.join(sets)}, updated_at = ? WHERE id = 1", params)
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_player()

    def add_exp(self, amount: int) -> Dict[str, Any]:
        amount = int(amount)
        if amount < 0:
            raise ValueError("经验增量不能为负数")
        with self._lock:
            conn = self._connect()
            try:
                level_up = self._add_exp_locked(conn, amount)
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        result = self.get_player()
        if level_up:
            result["level_up"] = level_up
        return result

    def _add_exp_locked(self, conn: sqlite3.Connection, delta: int) -> Optional[Dict[str, Any]]:
        """在持有锁的连接中发放经验: 检测升级并发放升级礼包, 返回升级信息 (无升级返回 None)"""
        delta = max(0, int(delta))
        if delta <= 0:
            return None
        row = conn.execute("SELECT exp FROM player_profile WHERE id = 1").fetchone()
        old_exp = int(row["exp"]) if row else 0
        old_level = self._exp_to_level(old_exp)
        new_exp = old_exp + delta
        new_level = self._exp_to_level(new_exp)
        now = datetime.now().isoformat()
        conn.execute("UPDATE player_profile SET exp = ?, updated_at = ? WHERE id = 1", (new_exp, now))
        self._ledger_locked(conn, "exp", delta, "系统发放")
        if new_level <= old_level:
            return None
        base = int(self._cfg("level_up", "base_currency", default=100))
        growth = int(self._cfg("level_up", "currency_growth", default=20))
        gift_enabled = bool(self._cfg("level_up", "enabled", default=True))
        total_reward = 0
        for lv in range(old_level, new_level):
            total_reward += base + max(0, lv - 1) * growth
        if total_reward > 0 and gift_enabled:
            self._grant_miya_locked(conn, total_reward, f"升级礼包 Lv.{old_level}→Lv.{new_level}")
            self._log_activity(
                conn, "level", "◆", f"升级！Lv.{old_level} → Lv.{new_level}",
                f"升级礼包 +{total_reward} 弥娅币",
            )
            self._react_locked(conn, "level_up", f"升到 Lv.{new_level}")
        return {"old_level": old_level, "new_level": new_level, "reward_currency": total_reward if gift_enabled else 0}

    def _link_story_locked(self, conn: sqlite3.Connection, title: str, content: str, event_type: str = "quest") -> None:
        """剧情串联: 在持有锁的连接中自动记录一段剧情 (配置 story_link.enabled 控制)"""
        try:
            from config.config_utils import get_qq_config

            enabled = bool(get_qq_config("earth_online", "story_link", "enabled", default=True))
        except Exception:
            enabled = True
        if not enabled:
            return
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO story_events (title, content, event_type, happened_at, fields, created_at) VALUES (?,?,?,?,?,?)",
            (title, content, event_type, now, "{}", now),
        )

    def _react_locked(self, conn: sqlite3.Connection, kind: str, context: str = "") -> None:
        """弥娅参与感: 关键事件后自动写入一条弥娅反应动态 (模板池来自 text_config, 配置优先)"""
        import random

        try:
            from config.config_utils import get_text, get_qq_config

            enabled = bool(get_qq_config("earth_online", "miya_reactions", "enabled", default=True))
            if not enabled:
                return
            templates = get_text("earth_online", "reactions", kind, default=None)
        except Exception:
            templates = None
        if kind == "world_discovered" and not templates:
            templates = [
                "发现新的世界坐标啦，{context}。弥娅已经替你把这一页收藏起来了 ✦",
                "这次探索很漂亮，{context}。下一个隐藏角落也在等你哦～",
            ]
        if not isinstance(templates, list) or not templates:
            return
        text = random.choice(templates)
        if context and "{context}" in text:
            text = text.replace("{context}", context)
        self._log_activity(conn, "miya", "❦", text, "")

    def update_activity_comment(self, activity_id: int, comment: str) -> Optional[Dict[str, Any]]:
        """弥娅对一条动态写评论"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE activity_log SET comment = ? WHERE id = ?",
                    (str(comment).strip(), activity_id),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM activity_log WHERE id = ?", (activity_id,)).fetchone()
                result = dict(row) if row else None
            finally:
                conn.close()
        return result

    def get_exchange_rates(self) -> Dict[str, Any]:
        """现实资产 (地球币) 币种显示汇率: 单位人民币元, 可切换美元显示"""
        try:
            from config.config_utils import get_qq_config

            return {
                "enabled": bool(get_qq_config("earth_online", "currency_exchange", "enabled", default=True)),
                "usd_per_cny": float(get_qq_config("earth_online", "currency_exchange", "usd_per_cny", default=0.14)),
            }
        except Exception:
            return {"enabled": True, "usd_per_cny": 0.14}

    # ── 前台主题 (配色/壁纸/磨砂玻璃) ──────────────

    def get_theme(self) -> Dict[str, Any]:
        """读取前台主题 (theme.json, 缺失回退 Miya OS 默认配色)"""
        try:
            if os.path.isfile(self.theme_path):
                with open(self.theme_path, "r", encoding="utf-8") as f:
                    user_theme = json.load(f)
                if isinstance(user_theme, dict):
                    theme = {**DEFAULT_THEME, **user_theme}
                    # v11 的默认鎏金主题不算用户自定义色板。读取时迁移，
                    # 让旧的 theme.json 与设置页的新默认值保持一致。
                    legacy_default = ("#c9ac67", "#e8d5a3", "#b5986a")
                    try:
                        theme_version = int(user_theme.get("version", 0) or 0)
                    except (TypeError, ValueError):
                        theme_version = 0
                    stored_colors = tuple(
                        str(user_theme.get(k, "")).lower()
                        for k in ("accent", "accent_light", "accent_deep")
                    )
                    if theme_version < 2 and stored_colors == legacy_default:
                        theme.update({k: DEFAULT_THEME[k] for k in ("accent", "accent_light", "accent_deep")})
                        theme["version"] = 2
                    return theme
        except Exception as e:
            logger.warning(f"[EarthOnline] 主题读取失败: {e}")
        return dict(DEFAULT_THEME)

    def save_theme(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """保存前台主题 (accent/accent_light/accent_deep/background/background_opacity/glass)"""
        current = self.get_theme()
        if not isinstance(data, dict):
            return current
        for k in ("accent", "accent_light", "accent_deep", "background"):
            if k in data and isinstance(data[k], str) and data[k].strip():
                current[k] = data[k].strip()
        if "background_opacity" in data:
            try:
                current["background_opacity"] = max(0.0, min(1.0, float(data["background_opacity"])))
            except (TypeError, ValueError):
                pass
        if "glass" in data:
            current["glass"] = bool(data["glass"])
        try:
            os.makedirs(os.path.dirname(self.theme_path), exist_ok=True)
            with open(self.theme_path, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[EarthOnline] 主题保存失败: {e}")
        return current

    def reset_theme(self) -> Dict[str, Any]:
        """恢复前台主题默认值 (Miya OS 青碧)"""
        try:
            if os.path.isfile(self.theme_path):
                os.remove(self.theme_path)
        except Exception as e:
            logger.warning(f"[EarthOnline] 主题重置失败: {e}")
        return dict(DEFAULT_THEME)

    # ── 弥娅策划: 综合分析 + 每日仪式 ───────────────

    def get_analysis(self) -> Dict[str, Any]:
        """全量数据综合分析 (供弥娅担任地球online 策划, 为佳的现实生活提供建议)"""
        quests = self.list_quests()
        items = self.list_items()
        characters = self.list_characters()
        return {
            "player": self.get_player(),
            "quests": {
                "total": len(quests),
                "pending": [q for q in quests if q["status"] == "pending"],
                "ongoing": [q for q in quests if q["status"] == "ongoing"],
                "due_soon": self.list_due_soon(days=3),
                "recurring": [q for q in quests if q.get("recurring") in ("daily", "weekly")],
            },
            "items": {
                "total": len(items),
                "by_category": {c: sum(1 for i in items if i["category"] == c) for c in ITEM_CATEGORIES},
                "by_rarity": {r: sum(1 for i in items if i["rarity"] == r) for r in RARITIES},
            },
            "characters": {
                "total": len(characters),
                "top_affinity": sorted(
                    [{"name": c["name"], "affinity": c["affinity"], "relationship": c["relationship"]} for c in characters],
                    key=lambda x: x["affinity"],
                    reverse=True,
                )[:5],
            },
            "stories": {"total": len(self.list_story(limit=100000))},
            "achievements": {
                "unlocked": len([a for a in self.list_achievements() if a.get("unlocked_at")]),
                "total": len(self.list_achievements()),
            },
            "titles": self.list_titles(),
            "checkin": self.get_checkin_status(),
            "weekly": self.get_weekly_report(),
            "activity_recent": self.list_activity(limit=10),
        }

    def daily_ritual(self) -> Dict[str, Any]:
        """弥娅每日仪式: 逾期检查 + 到期提醒 + 签到状态 + 自动生成日常委托 + 纪念日同步"""
        overdue = self.check_overdue()
        daily = self.generate_daily_commissions()
        commemorations = self.sync_commemorations()
        return {
            "overdue_failed": overdue.get("failed", 0),
            "due_today": self.list_due_soon(days=1),
            "checkin": self.get_checkin_status(),
            "daily_commissions": daily,
            "commemorations": commemorations,
            "activity_recent": self.list_activity(limit=8),
        }

    def get_life_hub(self) -> Dict[str, Any]:
        """Reality-first snapshot separating facts, observations and suggestions."""
        analysis = self.get_analysis()
        player = analysis["player"]
        real_context = self.get_real_context(auto_refresh=False)
        real_settings = self.get_real_context_settings()
        operator_state: Dict[str, Any] = {}
        operator_path = os.path.join(self.data_dir, "operator_state.json")
        try:
            if os.path.isfile(operator_path):
                with open(operator_path, "r", encoding="utf-8") as state_file:
                    loaded_state = json.load(state_file)
                if isinstance(loaded_state, dict):
                    operator_state = loaded_state
        except (OSError, ValueError, TypeError) as exc:
            logger.debug(f"[EarthOnline] 生活中枢读取运营状态失败: {exc}")
        autonomous = self._cfg("autonomous", default={}) or {}
        quiet_hours = [int(hour) for hour in (autonomous.get("quiet_hours") or [])]
        last_cycle_at = str(operator_state.get("last_cycle_at") or "")
        next_cycle_at = ""
        if last_cycle_at:
            try:
                next_cycle_at = (datetime.fromisoformat(last_cycle_at) + timedelta(minutes=int(autonomous.get("interval_minutes", 45)))).isoformat()
            except (ValueError, TypeError):
                pass
        attrs = {str(a.get("key")): a for a in (player.get("attrs") or []) if a.get("key")}
        facts = {
            "player": {"name": player.get("name", "玩家"), "level": player.get("level", 1)},
            "checkin": analysis["checkin"],
            "quests": {"ongoing": len(analysis["quests"]["ongoing"]), "pending": len(analysis["quests"]["pending"]), "due_soon": len(analysis["quests"]["due_soon"])},
            "attributes": {k: {"value": v.get("value"), "max": v.get("max")} for k, v in attrs.items() if k in ("energy", "mood", "focus")},
            "weekly": analysis["weekly"],
            "recent_activity": analysis["activity_recent"],
            "real_context": {
                "enabled": bool(real_settings.get("enabled")),
                "city": str(real_settings.get("city") or ""),
                "source": str(real_context.get("source") or "unavailable"),
                "source_status": str(real_context.get("source_status") or "unavailable"),
                "last_synced_at": str(real_context.get("last_synced_at") or real_context.get("captured_at") or ""),
                "is_stale": bool(real_context.get("is_stale", 1)),
                "precise_location_saved": bool(real_settings.get("allow_precise_location") and real_settings.get("latitude") is not None and real_settings.get("longitude") is not None),
            },
            "operator": {
                "enabled": bool(autonomous.get("enabled", False)),
                "in_quiet_hours": datetime.now().hour in quiet_hours,
                "last_cycle_at": last_cycle_at,
                "next_cycle_at": next_cycle_at,
                "cycles": int(operator_state.get("cycles") or 0),
                "last_actions": int(operator_state.get("last_cycle_actions") or 0),
                "last_skipped": bool(operator_state.get("last_cycle_skip", False)),
                "last_notification_sent": bool(operator_state.get("last_notification_sent", False)),
            },
        }
        observations, recommendations, pending = [], [], []
        energy = attrs.get("energy", {}).get("value")
        mood = attrs.get("mood", {}).get("value")
        if isinstance(energy, (int, float)) and energy < 30:
            observations.append({"key": "low_energy", "text": "当前记录显示体力偏低。", "evidence": {"energy": energy}})
            recommendations.append({"key": "rest", "text": "优先安排短暂休息或低负荷事项。", "requires_confirmation": True})
        if isinstance(mood, (int, float)) and mood < 30:
            observations.append({"key": "low_mood", "text": "当前记录显示心情偏低。", "evidence": {"mood": mood}})
            recommendations.append({"key": "mood_care", "text": "考虑做一件能让你恢复一点的事。", "requires_confirmation": True})
        if facts["quests"]["due_soon"]:
            recommendations.append({"key": "due_quests", "text": "有即将到期的委托，建议先处理其中最重要的一项。", "requires_confirmation": True})
        if not facts["checkin"].get("checked_today"):
            pending.append({"key": "checkin", "text": "今天是否已经签到？由你确认后再记录。"})
        return {"as_of": datetime.now().isoformat(), "facts": facts, "observations": observations, "recommendations": recommendations, "pending_confirmation": pending, "boundary": "现实记录以玩家或设备数据为准；观察与建议不是事实，执行前需要玩家确认。"}

    def add_currency(self, amount: int) -> Dict[str, Any]:
        """发放/扣除弥娅币 (弥娅发放的互动货币)"""
        return self.add_miya_currency(amount)

    def add_miya_currency(self, amount: int) -> Dict[str, Any]:
        """发放/扣除弥娅币"""
        amount = int(amount)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT miya_currency FROM player_profile WHERE id = 1").fetchone()
                balance = int(row["miya_currency"]) if row else 0
                if balance + amount < 0:
                    raise ValueError(f"弥娅币余额不足 (余额 {balance})")
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE player_profile SET miya_currency = miya_currency + ?, updated_at = ? WHERE id = 1",
                    (amount, now),
                )
                if amount:
                    direction = "发放" if amount > 0 else "扣除"
                    self._log_activity(
                        conn, "miya", "◆", f"{direction}弥娅币 {amount:+d}",
                        "弥娅币余额调整",
                    )
                    self._ledger_locked(conn, "miya", amount, "手动调整 (earth_grant_currency)")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_player()

    def spend_miya_coins(self, amount: int, reason: str = "") -> Dict[str, Any]:
        """扣除弥娅币 (佳用弥娅币兑换弥娅的互动服务)"""
        amount = int(amount)
        if amount <= 0:
            return {"success": False, "message": "消费数量必须大于 0"}
        reason = str(reason or "").strip()[:500]
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT miya_currency FROM player_profile WHERE id = 1").fetchone()
                balance = int(row["miya_currency"]) if row else 0
                if balance < amount:
                    return {"success": False, "message": f"弥娅币不足 (余额 {balance})"}
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE player_profile SET miya_currency = miya_currency - ?, updated_at = ? WHERE id = 1",
                    (amount, now),
                )
                self._log_activity(
                    conn, "miya", "◆", f"消耗弥娅币 -{amount}",
                    reason or "兑换弥娅的互动服务",
                )
                self._ledger_locked(conn, "miya", -amount, reason or "兑换弥娅的互动服务")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {"success": True, "player": self.get_player(), "spent": amount}

    # ── 背包物品 ────────────────────────────────────

    def list_items(self, category: str = "", status: str = "") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM items WHERE 1=1"
            params: List[Any] = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_item(
        self,
        name: str,
        category: str = "other",
        rarity: str = "common",
        quantity: int = 1,
        description: str = "",
        image_path: str = "",
        markdown: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if category not in ITEM_CATEGORIES:
            category = "other"
        if rarity not in RARITIES:
            rarity = "common"
        max_items = max(1, int(self._cfg("items", "max_items", default=500)))
        with self._lock:
            conn = self._connect()
            try:
                count = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
                if count >= max_items:
                    raise ValueError(f"背包已达上限 {max_items} 件 (earth_online.items.max_items)，先整理或删除一些吧")
                now = datetime.now().isoformat()
                cur = conn.execute(
                    "INSERT INTO items (name, category, rarity, quantity, description, image_path, markdown, fields, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        name, category, rarity, max(1, quantity), description, image_path, markdown,
                        json.dumps(fields or {}, ensure_ascii=False), now, now,
                    ),
                )
                self._log_activity(conn, "item", "▣", f"收录物品: {name}", f"稀有度 {rarity}" if rarity != "common" else "")
                self._react_locked(conn, "item_added", f"收录「{name}」")
                conn.commit()
                result = self.get_item(cur.lastrowid) or {}
            finally:
                conn.close()
        self._write_mirror()
        self.refresh_achievements()
        return result

    def update_item(self, item_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "category", "rarity", "quantity", "description", "image_path", "status", "markdown", "fields"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_item(item_id)
        with self._lock:
            conn = self._connect()
            try:
                sets, params = [], []
                for k, v in updates.items():
                    if k == "fields":
                        v = json.dumps(v, ensure_ascii=False)
                    sets.append(f"{k} = ?")
                    params.append(v)
                params.append(datetime.now().isoformat())
                params.append(item_id)
                conn.execute(f"UPDATE items SET {', '.join(sets)}, updated_at = ? WHERE id = ?", params)
                conn.commit()
                result = self.get_item(item_id)
            finally:
                conn.close()
        self._write_mirror()
        return result

    def delete_item(self, item_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
                conn.commit()
                deleted = cur.rowcount > 0
            finally:
                conn.close()
        if deleted:
            self._write_mirror()
        return deleted

    # ── 任务 ────────────────────────────────────────

    def list_quests(self, status: str = "", quest_type: str = "") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM quests WHERE 1=1"
            params: List[Any] = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if quest_type:
                sql += " AND quest_type = ?"
                params.append(quest_type)
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_quest(self, quest_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_quest(
        self,
        title: str,
        description: str = "",
        quest_type: str = "branch",
        must_complete: bool = False,
        reward_currency: int = 0,
        reward_exp: int = 0,
        penalty_currency: int = 0,
        deadline: str = "",
        source: str = "manual",
        difficulty: int = 1,
        fields: Optional[Dict[str, Any]] = None,
        subtasks: Optional[List[Dict[str, Any]]] = None,
        recurring: str = "",
    ) -> Dict[str, Any]:
        if quest_type not in QUEST_TYPES:
            quest_type = "branch"
        difficulty = max(1, min(5, int(difficulty)))
        if recurring not in ("", "none", "daily", "weekly"):
            recurring = ""
        if recurring == "none":
            recurring = ""
        subtask_list = []
        for st in subtasks or []:
            if isinstance(st, dict) and str(st.get("text", "")).strip():
                subtask_list.append({"text": str(st["text"]).strip(), "done": 1 if st.get("done") else 0})
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                cur = conn.execute(
                    "INSERT INTO quests (title, description, quest_type, must_complete, reward_currency, reward_exp, penalty_currency, deadline, source, difficulty, fields, subtasks, recurring, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        title,
                        description,
                        quest_type,
                        1 if must_complete else 0,
                        max(0, reward_currency),
                        max(0, reward_exp),
                        max(0, penalty_currency),
                        deadline,
                        source,
                        difficulty,
                        json.dumps(fields or {}, ensure_ascii=False),
                        json.dumps(subtask_list, ensure_ascii=False),
                        recurring,
                        now,
                        now,
                    ),
                )
                self._log_activity(
                    conn, "quest", "◆",
                    f"{'弥娅发布委托' if source == 'miya' else '新委托发布'}: {title}",
                    f"奖励 +{max(0, reward_currency)} 币 · +{max(0, reward_exp)} 经验",
                )
                conn.commit()
                result = self.get_quest(cur.lastrowid) or {}
            finally:
                conn.close()
        self._write_mirror()
        return result

    def update_quest(self, quest_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"title", "description", "quest_type", "must_complete", "reward_currency", "reward_exp", "penalty_currency", "deadline", "status", "difficulty", "fields", "subtasks", "recurring"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if "difficulty" in updates:
            updates["difficulty"] = max(1, min(5, int(updates["difficulty"])))
        if "recurring" in updates:
            updates["recurring"] = str(updates["recurring"]) if str(updates["recurring"]) in ("", "none", "daily", "weekly") else ""
            if updates["recurring"] == "none":
                updates["recurring"] = ""
        if "subtasks" in updates:
            cleaned = []
            for st in updates["subtasks"] or []:
                if isinstance(st, dict) and str(st.get("text", "")).strip():
                    cleaned.append({"text": str(st["text"]).strip(), "done": 1 if st.get("done") else 0})
            updates["subtasks"] = cleaned
        if not updates:
            return self.get_quest(quest_id)
        with self._lock:
            conn = self._connect()
            try:
                sets, params = [], []
                for k, v in updates.items():
                    if k in ("fields", "subtasks"):
                        v = json.dumps(v, ensure_ascii=False)
                    sets.append(f"{k} = ?")
                    params.append(v)
                params.append(datetime.now().isoformat())
                params.append(quest_id)
                conn.execute(f"UPDATE quests SET {', '.join(sets)}, updated_at = ? WHERE id = ?", params)
                conn.commit()
                result = self.get_quest(quest_id)
            finally:
                conn.close()
        self._write_mirror()
        return result

    def accept_quest(self, quest_id: int) -> Dict[str, Any]:
        """接取任务: pending → ongoing (前台任务板操作)"""
        with self._lock:
            conn = self._connect()
            try:
                quest = self.get_quest(quest_id)
                if not quest:
                    return {"success": False, "message": "任务不存在"}
                if quest["status"] != "pending":
                    return {"success": False, "message": f"任务当前状态为 {quest['status']}，无法接取"}
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE quests SET status = 'ongoing', updated_at = ? WHERE id = ?",
                    (now, quest_id),
                )
                subtasks = quest.get("subtasks") or []
                self._log_activity(
                    conn, "quest", "⬡", f"接取委托: {quest['title']}",
                    f"子任务 {sum(1 for s in subtasks if s.get('done'))}/{len(subtasks)}" if subtasks else "",
                    quest_id,
                )
                conn.commit()
                result = {"success": True, "quest": self.get_quest(quest_id)}
            finally:
                conn.close()
        self._write_mirror()
        return result

    def complete_quest(self, quest_id: int) -> Dict[str, Any]:
        """完成任务: 校验子任务全部完成 → 发放奖励, 记录历史"""
        with self._lock:
            conn = self._connect()
            try:
                quest = self.get_quest(quest_id)
                if not quest:
                    return {"success": False, "message": "任务不存在"}
                if quest["status"] in ("completed", "failed", "cancelled"):
                    return {"success": False, "message": f"任务已结束 ({quest['status']})，无法完成"}
                subtasks = quest.get("subtasks") or []
                pending_subtasks = [s["text"] for s in subtasks if not s.get("done")]
                if pending_subtasks:
                    return {
                        "success": False,
                        "message": "还有子任务未完成，无法提交委托",
                        "pending_subtasks": pending_subtasks,
                    }
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE quests SET status = 'completed', completed_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, quest_id),
                )
                conn.execute(
                    "UPDATE player_profile SET total_completed = total_completed + 1, updated_at = ? WHERE id = 1",
                    (now,),
                )
                self._grant_miya_locked(conn, quest["reward_currency"], f"完成委托: {quest['title']}")
                level_up = self._add_exp_locked(conn, quest["reward_exp"])
                conn.execute(
                    "INSERT INTO quest_history (quest_id, title, status, reward_currency, reward_exp, penalty_currency, completed_at) VALUES (?, ?, 'completed', ?, ?, 0, ?)",
                    (quest_id, quest["title"], quest["reward_currency"], quest["reward_exp"], now),
                )
                self._log_activity(
                    conn, "quest", "✦", f"完成委托: {quest['title']}",
                    f"奖励 +{quest['reward_currency']} 弥娅币 · +{quest['reward_exp']} 经验",
                    quest_id,
                )
                # 剧情串联: 完成任务自动记录剧情
                self._link_story_locked(
                    conn, f"委托完成: {quest['title']}",
                    f"完成委托「{quest['title']}」，获得 +{quest['reward_currency']} 弥娅币、+{quest['reward_exp']} 经验。",
                )
                # 弥娅参与: 自动反应
                self._react_locked(conn, "quest_completed", f"完成委托「{quest['title']}」")
                world_region = (quest.get("fields") or {}).get("world_region")
                if world_region:
                    self._add_world_resonance_locked(conn, str(world_region), 12, now, "完成区域委托")
                # 循环任务: 完成后自动重置, 生成下一轮 (喝水/睡觉等每日重复)
                recurring = quest.get("recurring") or ""
                if recurring in ("daily", "weekly"):
                    conn.execute(
                        "UPDATE quests SET status = 'pending', completed_at = '', subtasks = ?, updated_at = ? WHERE id = ?",
                        (
                            json.dumps([{**s, "done": 0} for s in (quest.get("subtasks") or [])], ensure_ascii=False),
                            now,
                            quest_id,
                        ),
                    )
                    self._log_activity(
                        conn, "quest", "↻", f"循环任务已重置: {quest['title']}",
                        "新的一轮开始，继续加油～",
                        quest_id,
                    )
                conn.commit()
                result = {
                    "success": True,
                    "player": self.get_player(),
                    "quest": self.get_quest(quest_id),
                    "reward": {"currency": quest["reward_currency"], "exp": quest["reward_exp"]},
                    "level_up": level_up,
                    "recurring_reset": recurring in ("daily", "weekly"),
                }
            finally:
                conn.close()
        # 属性联动: 完成委托消耗体力 (难度越高越累), 收获心情; 关怀委托额外 +2 心情
        care_quest = bool((quest.get("fields") or {}).get("care"))
        result["attrs"] = {
            "energy": self._adjust_attr("energy", -4 * int(quest.get("difficulty") or 1)),
            "mood": self._adjust_attr("mood", 3 + (2 if care_quest else 0)),
        }
        if care_quest:
            self._react_locked_conn_safe("care_completed", f"完成关怀委托「{quest['title']}」")
            result["care_completed"] = True
        self._write_mirror()
        self.refresh_achievements()
        return result

    def fail_quest(self, quest_id: int) -> Dict[str, Any]:
        """任务失败(鸽了): 扣除惩罚, 记录历史"""
        with self._lock:
            conn = self._connect()
            try:
                quest = self.get_quest(quest_id)
                if not quest:
                    return {"success": False, "message": "任务不存在"}
                if quest["status"] in ("completed", "failed", "cancelled"):
                    return {"success": False, "message": f"任务已终结 ({quest['status']})"}
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE quests SET status = 'failed', completed_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, quest_id),
                )
                if quest["penalty_currency"] > 0:
                    conn.execute(
                        "UPDATE player_profile SET total_failed = total_failed + 1, updated_at = ? WHERE id = 1",
                        (now,),
                    )
                    self._grant_miya_locked(conn, -int(quest["penalty_currency"]), f"委托失败惩罚: {quest['title']}")
                else:
                    conn.execute(
                        "UPDATE player_profile SET total_failed = total_failed + 1, updated_at = ? WHERE id = 1",
                        (now,),
                    )
                conn.execute(
                    "INSERT INTO quest_history (quest_id, title, status, reward_currency, reward_exp, penalty_currency, completed_at) VALUES (?, ?, 'failed', 0, 0, ?, ?)",
                    (quest_id, quest["title"], quest["penalty_currency"], now),
                )
                self._log_activity(
                    conn, "quest", "✕", f"委托失败: {quest['title']}",
                    f"扣除 {quest['penalty_currency']} 弥娅币" if quest["penalty_currency"] else "无惩罚",
                    quest_id,
                )
                # 剧情串联: 失败也记录一笔
                self._link_story_locked(
                    conn, f"委托失败: {quest['title']}",
                    f"委托「{quest['title']}」未能完成" + (f"，扣除 {quest['penalty_currency']} 弥娅币。" if quest["penalty_currency"] else "。"),
                )
                self._react_locked(conn, "quest_failed", f"委托「{quest['title']}」")
                conn.commit()
                result = {"success": True, "player": self.get_player(), "quest": self.get_quest(quest_id)}
            finally:
                conn.close()
        self._write_mirror()
        return result

    def cancel_quest(self, quest_id: int) -> Dict[str, Any]:
        """取消任务(无惩罚)"""
        with self._lock:
            conn = self._connect()
            try:
                quest = self.get_quest(quest_id)
                if not quest:
                    return {"success": False, "message": "任务不存在"}
                if quest["status"] in ("completed", "failed", "cancelled"):
                    return {"success": False, "message": f"任务已结束 ({quest['status']})，无法取消"}
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE quests SET status = 'cancelled', completed_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, quest_id),
                )
                self._log_activity(conn, "quest", "◻", f"取消委托: {quest['title']}", "", quest_id)
                conn.commit()
                result = {"success": True, "quest": self.get_quest(quest_id)}
            finally:
                conn.close()
        self._write_mirror()
        return result

    def toggle_subtask(self, quest_id: int, index: int, done: Optional[bool] = None) -> Dict[str, Any]:
        """切换/设置任务子任务完成状态 (index 从 0 开始), 返回最新任务"""
        with self._lock:
            conn = self._connect()
            try:
                quest = self.get_quest(quest_id)
                if not quest:
                    return {"success": False, "message": "任务不存在"}
                if quest["status"] in ("completed", "failed", "cancelled"):
                    return {"success": False, "message": f"任务已结束 ({quest['status']})，无法更新子任务"}
                subtasks = [dict(s) for s in (quest.get("subtasks") or [])]
                if index < 0 or index >= len(subtasks):
                    return {"success": False, "message": f"子任务序号无效 (0-{len(subtasks) - 1})"}
                target_done = bool(done) if done is not None else not subtasks[index].get("done")
                subtasks[index]["done"] = 1 if target_done else 0
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE quests SET subtasks = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(subtasks, ensure_ascii=False), now, quest_id),
                )
                done_count = sum(1 for s in subtasks if s.get("done"))
                if target_done:
                    self._log_activity(
                        conn, "quest", "◉", f"子任务完成: {subtasks[index]['text']}",
                        f"「{quest['title']}」进度 {done_count}/{len(subtasks)}",
                        quest_id,
                    )
                conn.commit()
                updated = self.get_quest(quest_id) or {}
                updated["subtask_progress"] = {"done": done_count, "total": len(subtasks), "all_done": done_count >= len(subtasks)}
                return {"success": True, "quest": updated}
            finally:
                conn.close()
        self._write_mirror()
        return {"success": False, "message": "更新失败"}

    def check_overdue(self) -> Dict[str, Any]:
        """检查逾期任务: 已过 deadline 且未完成的任务 → 失败 + 惩罚 (earth_online.quests.overdue_check_enabled 控制)"""
        if not bool(self._cfg("quests", "overdue_check_enabled", default=True)):
            return {"success": True, "failed": 0, "results": [], "skipped": "disabled"}
        conn = self._connect()
        try:
            now = datetime.now().isoformat()
            overdue = conn.execute(
                "SELECT id FROM quests WHERE status IN ('pending', 'ongoing') AND deadline != '' AND deadline < ?",
                (now,),
            ).fetchall()
            results = []
            for row in overdue:
                results.append(self.fail_quest(row["id"]))
            return {"success": True, "failed": len(results), "results": results}
        finally:
            conn.close()

    def quest_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM quest_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── 剧情事件 ────────────────────────────────────

    def list_story(self, event_type: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if event_type:
                rows = conn.execute(
                    "SELECT * FROM story_events WHERE event_type = ? ORDER BY happened_at DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM story_events ORDER BY happened_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_story(
        self,
        title: str,
        content: str = "",
        event_type: str = "life",
        character_id: Optional[int] = None,
        item_id: Optional[int] = None,
        happened_at: str = "",
        fields: Optional[Dict[str, Any]] = None,
        image_path: str = "",
    ) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                happened = happened_at or now
                cur = conn.execute(
                    "INSERT INTO story_events (title, content, event_type, character_id, item_id, happened_at, fields, image_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        title, content, event_type, character_id, item_id, happened,
                        json.dumps(fields or {}, ensure_ascii=False), image_path, now,
                    ),
                )
                self._log_activity(conn, "story", "≋", f"记录剧情: {title}", event_type)
                self._react_locked(conn, "story_added", f"记录剧情「{title}」")
                conn.commit()
                row = conn.execute("SELECT * FROM story_events WHERE id = ?", (cur.lastrowid,)).fetchone()
                result = dict(row)
            finally:
                conn.close()
        self._write_mirror()
        self.refresh_achievements()
        return result

    def delete_story(self, story_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM story_events WHERE id = ?", (story_id,))
                conn.commit()
                deleted = cur.rowcount > 0
            finally:
                conn.close()
        if deleted:
            self._write_mirror()
        return deleted

    def update_story(self, story_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """编辑剧情: title/content/event_type/character_id/item_id/happened_at/image_path/fields"""
        allowed = {"title", "content", "event_type", "character_id", "item_id", "happened_at", "image_path", "fields"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            row = self._connect()
            try:
                return self._row_to_dict(row.execute("SELECT * FROM story_events WHERE id = ?", (story_id,)).fetchone())
            finally:
                row.close()
        with self._lock:
            conn = self._connect()
            try:
                sets, params = [], []
                for k, v in updates.items():
                    if k == "fields":
                        v = json.dumps(v or {}, ensure_ascii=False)
                    sets.append(f"{k} = ?")
                    params.append(v)
                params.append(story_id)
                conn.execute(f"UPDATE story_events SET {', '.join(sets)} WHERE id = ?", params)
                self._log_activity(conn, "story", "≋", f"编辑剧情: {updates.get('title', '')}", "")
                conn.commit()
                row = conn.execute("SELECT * FROM story_events WHERE id = ?", (story_id,)).fetchone()
                result = dict(row) if row else None
            finally:
                conn.close()
        if result:
            self._write_mirror()
        return result

    # ── 角色好感度 ──────────────────────────────────

    def list_characters(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM characters ORDER BY affinity DESC, id ASC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_character(self, character_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_character(
        self,
        name: str,
        nickname: str = "",
        relationship: str = "friend",
        affinity: int = 0,
        avatar_path: str = "",
        notes: str = "",
        birthday: str = "",
        markdown: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                cur = conn.execute(
                    "INSERT INTO characters (name, nickname, relationship, affinity, avatar_path, notes, birthday, markdown, fields, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        name, nickname, relationship, max(0, min(100, affinity)), avatar_path, notes, birthday, markdown,
                        json.dumps(fields or {}, ensure_ascii=False), now, now,
                    ),
                )
                self._log_activity(conn, "character", "❖", f"新角色入图鉴: {name}", f"好感度 {affinity}")
                conn.commit()
                result = self.get_character(cur.lastrowid) or {}
            finally:
                conn.close()
        self._write_mirror()
        self.refresh_achievements()
        return result

    def update_character(self, character_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "nickname", "relationship", "affinity", "avatar_path", "notes", "birthday", "markdown", "fields"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_character(character_id)
        with self._lock:
            conn = self._connect()
            try:
                if "affinity" in updates:
                    updates["affinity"] = max(0, min(100, int(updates["affinity"])))
                sets, params = [], []
                for k, v in updates.items():
                    if k == "fields":
                        v = json.dumps(v, ensure_ascii=False)
                    sets.append(f"{k} = ?")
                    params.append(v)
                params.append(datetime.now().isoformat())
                params.append(character_id)
                conn.execute(f"UPDATE characters SET {', '.join(sets)}, updated_at = ? WHERE id = ?", params)
                conn.commit()
                result = self.get_character(character_id)
            finally:
                conn.close()
        self._write_mirror()
        return result

    def delete_character(self, character_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
                conn.commit()
                deleted = cur.rowcount > 0
            finally:
                conn.close()
        if deleted:
            self._write_mirror()
        return deleted

    @staticmethod
    def _affinity_tier(affinity: int) -> int:
        """好感度 0-100 → 阶段序号 (1=陌生 ... 6=挚友)"""
        for index, level in enumerate(DEFAULT_TEMPLATES["affinity_levels"], start=1):
            if int(level["min"]) <= affinity <= int(level["max"]):
                return index
        return 1

    def add_affinity(self, character_id: int, delta: int, reason: str = "") -> Optional[Dict[str, Any]]:
        """好感度变动: 记录日志 + 更新角色值; 跨阶段时发放羁绊解锁奖励。

        上下限与单次变动上限读配置 (earth_online.affinity_max / affinity_min / affinity_step_limit)。
        """
        affinity_min = max(0, int(self._cfg("affinity_min", default=0)))
        affinity_max = max(1, int(self._cfg("affinity_max", default=100)))
        step_limit = max(1, int(self._cfg("affinity_step_limit", default=20)))
        delta = max(-step_limit, min(step_limit, int(delta)))
        with self._lock:
            conn = self._connect()
            try:
                character = self.get_character(character_id)
                if not character:
                    return None
                new_affinity = max(affinity_min, min(affinity_max, character["affinity"] + delta))
                old_tier = self._affinity_tier(character["affinity"])
                new_tier = self._affinity_tier(new_affinity)
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE characters SET affinity = ?, updated_at = ? WHERE id = ?",
                    (new_affinity, now, character_id),
                )
                conn.execute(
                    "INSERT INTO affinity_logs (character_id, delta, reason, created_at) VALUES (?, ?, ?, ?)",
                    (character_id, delta, reason, now),
                )
                self._log_activity(
                    conn, "character", "❤",
                    f"「{character['name']}」好感度 {delta:+d} → {new_affinity}",
                    reason or "",
                )
                tier_up = None
                if new_tier > old_tier:
                    tier_label = DEFAULT_TEMPLATES["affinity_levels"][new_tier - 1]["label"]
                    reward = new_tier * 12
                    self._grant_miya_locked(conn, reward, f"羁绊升级: {character['name']} → {tier_label}")
                    self._log_activity(
                        conn, "character", "✦",
                        f"羁绊升级: 「{character['name']}」→ {tier_label}",
                        f"解锁新阶段奖励 +{reward} 弥娅币",
                    )
                    self._link_story_locked(
                        conn, f"羁绊升级: {character['name']} · {tier_label}",
                        f"与「{character['name']}」的关系走到了「{tier_label}」阶段。{reason or '这段关系正在变得更深。'}",
                        event_type="character",
                    )
                    self._react_locked(conn, "affinity_tier_up", f"和「{character['name']}」的羁绊升到 {tier_label}")
                    tier_up = {"old_tier": old_tier, "new_tier": new_tier, "label": tier_label, "reward_currency": reward}
                conn.commit()
                result = self.get_character(character_id)
                if tier_up:
                    result = {**result, "tier_up": tier_up}
            finally:
                conn.close()
        self._write_mirror()
        self.refresh_achievements()
        return result

    def affinity_logs(self, character_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM affinity_logs WHERE character_id = ? ORDER BY id DESC LIMIT ?",
                (character_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── 单人开放世界探索 ────────────────────────────

    def list_world_regions(self) -> List[Dict[str, Any]]:
        """获取世界地图区域与玩家探索进度。"""
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM world_regions ORDER BY id ASC").fetchall()
            result = []
            context = self.get_real_context(auto_refresh=True)
            context["period"] = self._world_period(datetime.now())
            for row in rows:
                region = dict(row)
                all_events = self._world_events_for_region(region["key"], include_locked=True, context=context)
                available_events = [item for item in all_events if item[1].get("available", True)]
                # 保持原有地图进度口径稳定：条件发现单独显示，不会让基础区域的 100% 进度突然变化。
                region["event_total"] = len([item for item in all_events if not item[1].get("condition")])
                region["condition_event_total"] = len([item for item in all_events if item[1].get("condition")])
                region["available_event_total"] = len(available_events)
                region["discovery_total"] = conn.execute(
                    "SELECT COUNT(*) AS c FROM world_discoveries WHERE region_key = ?", (region["key"],)
                ).fetchone()["c"]
                region["exploration_percent"] = round(
                    min(100, region["discovery_total"] / max(1, region["event_total"]) * 100)
                )
                region["resonance_level"] = int(region.get("resonance_level") or self._resonance_level(int(region.get("resonance_xp") or 0)))
                region["resonance_xp"] = int(region.get("resonance_xp") or 0)
                region["resonance_next_xp"] = self._resonance_threshold(region["resonance_level"] + 1)
                region["condition_events"] = [
                    {"title": event.get("title", ""), "condition_label": event.get("condition_label", "现实条件未满足"), "available": bool(event.get("available", True))}
                    for _, event in all_events if event.get("condition")
                ]
                result.append(region)
            return result
        finally:
            conn.close()

    def update_world_region_image(self, region_key: str, image_path: str) -> Optional[Dict[str, Any]]:
        """绑定区域现实照片；只保存本机相对资源路径。"""
        region_key = str(region_key or "").strip()
        image_path = str(image_path or "").strip()
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute("UPDATE world_regions SET image_path=?, updated_at=? WHERE key=?", (image_path, now, region_key))
            if conn.total_changes == 0:
                return None
            self._add_world_resonance_locked(conn, region_key, 8, now, "绑定现实照片")
            conn.commit()
            return conn.execute("SELECT * FROM world_regions WHERE key=?", (region_key,)).fetchone()
        finally:
            conn.close()

    def update_world_region(self, region_key: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "subtitle", "description", "icon", "color", "level_req", "latitude", "longitude", "geofence_radius"}
        updates = {k: values[k] for k in allowed if k in values}
        if not updates:
            conn = self._connect()
            try:
                return self._row_to_dict(conn.execute("SELECT * FROM world_regions WHERE key=?", (region_key,)).fetchone())
            finally:
                conn.close()
        if "level_req" in updates:
            updates["level_req"] = max(1, int(updates["level_req"]))
        if "geofence_radius" in updates:
            updates["geofence_radius"] = max(0, min(100000, int(updates["geofence_radius"] or 0)))
        for coord in ("latitude", "longitude"):
            if coord in updates and updates[coord] not in (None, ""):
                try:
                    updates[coord] = float(updates[coord])
                except (TypeError, ValueError):
                    updates[coord] = None
        # 启用围栏必须有完整坐标；坐标被清空时自动关闭围栏
        if updates.get("geofence_radius", 0) and (updates.get("latitude") is None or updates.get("longitude") is None):
            probe = self._connect()
            try:
                current = self._row_to_dict(probe.execute("SELECT latitude, longitude FROM world_regions WHERE key=?", (region_key,)).fetchone()) or {}
            finally:
                probe.close()
            merged = {**current, **updates}
            if merged.get("latitude") is None or merged.get("longitude") is None:
                updates["geofence_radius"] = 0
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            row = conn.execute("SELECT id FROM world_regions WHERE key=?", (region_key,)).fetchone()
            if not row:
                return None
            assignments = ", ".join(f"{key}=?" for key in updates)
            conn.execute(f"UPDATE world_regions SET {assignments}, updated_at=? WHERE key=?", (*updates.values(), now, region_key))
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM world_regions WHERE key=?", (region_key,)).fetchone())
        finally:
            conn.close()

    def list_world_custom_events(self, region_key: str = "") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if region_key:
                rows = conn.execute("SELECT * FROM world_custom_events WHERE region_key=? ORDER BY id ASC", (region_key,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM world_custom_events ORDER BY id ASC").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def create_world_custom_event(self, region_key: str, title: str, text: str, reward_currency: int = 0, reward_exp: int = 0, kind: str = "story") -> Optional[Dict[str, Any]]:
        if not any(region["key"] == region_key for region in WORLD_REGION_SEEDS):
            return None
        if not title.strip() or not text.strip():
            return None
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO world_custom_events (region_key, title, text, kind, reward_currency, reward_exp, created_at) VALUES (?,?,?,?,?,?,?)",
                (region_key, title.strip()[:160], text.strip(), kind or "story", max(0, int(reward_currency)), max(0, int(reward_exp)), now),
            )
            self._add_world_resonance_locked(conn, region_key, 5, now, "新增自定义世界发现")
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM world_custom_events WHERE id=?", (cur.lastrowid,)).fetchone())
        finally:
            conn.close()

    def delete_world_custom_event(self, event_id: int) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM world_custom_events WHERE id=?", (int(event_id),))
            changed = conn.total_changes > 0
            conn.commit()
            return changed
        finally:
            conn.close()

    @staticmethod
    def _geo_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine 两点距离 (米)"""
        from math import asin, cos, radians, sin, sqrt

        rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
        a = sin((rlat2 - rlat1) / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin((rlon2 - rlon1) / 2) ** 2
        return 6371000 * 2 * asin(sqrt(a))

    # ── 玩家属性 (体力/心情等) ─────────────────────

    def _get_attrs(self) -> Dict[str, Dict[str, Any]]:
        player = self.get_player()
        attrs = player.get("attrs") or []
        return {str(a.get("key")): a for a in attrs if isinstance(a, dict) and a.get("key")}

    def _adjust_attr(self, key: str, delta: int) -> Optional[Dict[str, Any]]:
        """调整一条玩家属性 (0 ~ max)，返回更新后的属性条；单人存档无需加锁重入。"""
        attrs = self._get_attrs()
        attr = attrs.get(key)
        if not attr:
            return None
        attr["value"] = max(0, min(int(attr.get("max", 100)), int(attr.get("value", 0)) + int(delta)))
        ordered = [attrs[k] for k in (a.get("key") for a in self.get_player().get("attrs") or []) if k in attrs]
        self.update_player({"attrs": ordered})
        return attr

    @staticmethod
    def _world_period(now: datetime) -> str:
        if now.hour < 5:
            return "深夜"
        if now.hour < 11:
            return "清晨"
        if now.hour < 17:
            return "白昼"
        if now.hour < 22:
            return "黄昏"
        return "夜晚"

    @staticmethod
    def _resonance_threshold(level: int) -> int:
        return {1: 0, 2: 40, 3: 100, 4: 180, 5: 300}.get(max(1, int(level)), 300 + (max(1, int(level)) - 5) * 150)

    @classmethod
    def _resonance_level(cls, xp: int) -> int:
        level = 1
        for candidate in range(2, 20):
            if xp >= cls._resonance_threshold(candidate):
                level = candidate
            else:
                break
        return level

    def _add_world_resonance_locked(self, conn: sqlite3.Connection, region_key: str, amount: int, now: str, reason: str = "") -> Dict[str, Any]:
        row = conn.execute("SELECT resonance_xp, resonance_level FROM world_regions WHERE key=?", (region_key,)).fetchone()
        if not row:
            return {"level": 1, "xp": 0, "level_up": False}
        old_level = int(row["resonance_level"] or 1)
        xp = max(0, int(row["resonance_xp"] or 0) + max(0, int(amount)))
        new_level = self._resonance_level(xp)
        conn.execute("UPDATE world_regions SET resonance_xp=?, resonance_level=?, updated_at=? WHERE key=?", (xp, new_level, now, region_key))
        if amount and reason:
            self._log_activity(conn, "world", "◎", f"区域共鸣 +{amount}", reason)
        return {"level": new_level, "xp": xp, "level_up": new_level > old_level, "old_level": old_level}

    @staticmethod
    def _season_of(now: datetime) -> str:
        """月份 → 季节 (3-5 春 / 6-8 夏 / 9-11 秋 / 12-2 冬)。纯本地日期判断，不依赖天气同步。"""
        month = now.month
        if 3 <= month <= 5:
            return "spring"
        if 6 <= month <= 8:
            return "summer"
        if 9 <= month <= 11:
            return "autumn"
        return "winter"

    def _world_condition_available(self, event: Dict[str, Any], context: Dict[str, Any]) -> bool:
        condition = event.get("condition") or {}
        if not condition:
            return True
        # 只有天气条件才依赖现实天气同步；季节/时段条件用本地时间即可判定
        needs_weather = bool(condition.get("weather_any"))
        if needs_weather and context.get("source_status") != "ok":
            return False
        weather = str(context.get("weather") or "")
        period = str(context.get("period") or "")
        season = str(context.get("season") or "")
        if not season:
            try:
                season = self._season_of(datetime.now())
            except Exception:
                season = ""
        if condition.get("weather_any") and not any(token in weather for token in condition["weather_any"]):
            return False
        if condition.get("period_any") and period not in condition["period_any"]:
            return False
        if condition.get("season_any") and season not in condition["season_any"]:
            return False
        return True

    def _world_events_for_region(self, region_key: str, include_locked: bool = True, context: Optional[Dict[str, Any]] = None) -> List[tuple[str, Dict[str, Any]]]:
        events = [(f"{region_key}_{i}", event) for i, event in enumerate(WORLD_REGION_EVENTS.get(region_key, []))]
        for index, event in enumerate(WORLD_CONDITIONAL_EVENTS.get(region_key, [])):
            item = dict(event)
            item["available"] = self._world_condition_available(item, context or {})
            if include_locked or item["available"]:
                events.append((f"{region_key}_condition_{index}", item))
        for custom in self.list_world_custom_events(region_key):
            events.append((f"{region_key}_custom_{custom['id']}", {
                "title": custom["title"], "text": custom["text"], "reward_currency": custom["reward_currency"],
                "reward_exp": custom["reward_exp"], "kind": custom.get("kind", "story"), "available": bool(custom.get("active", 1)),
            }))
        return events

    @staticmethod
    def _world_companion_dialogue(region: Dict[str, Any], event: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
        weather = str(context.get("weather") or "未同步")
        period = str(context.get("period") or "今天")
        if context.get("source_status") == "ok":
            lead = f"我看见了你所在城市的{weather}，现在是{period}。"
        else:
            lead = f"现实天气还没有同步，但我知道你正在{period}里向前走。"
        kind = str(event.get("kind", "story"))
        tail = {
            "chest": "这只宝箱先替你保管一会儿，等你回来时再一起打开。",
            "hidden": "你发现了别人可能会错过的细节，这就是属于你的观测方式。",
            "story": "这一刻不需要被夸张地命名，认真走过就已经值得留下。",
        }.get(kind, "我会把这一刻收进我们的世界档案里。")
        return {"speaker": "弥娅", "text": f"{lead} {tail}", "tone": "同行", "region": str(region.get("name", ""))}

    # ── 限时活动: 内置活动 + 后台自定义活动 ─────────

    def list_world_event_areas(self) -> List[Dict[str, Any]]:
        """全部活动区域 = 内置常量 + 后台自定义 (is_custom 标记来源)。"""
        areas = [{**area, "is_custom": False, "active": 1} for area in WORLD_EVENT_AREAS]
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM world_custom_event_areas ORDER BY id ASC").fetchall()
        finally:
            conn.close()
        for row in rows:
            area = dict(row)
            area["is_custom"] = True
            areas.append(area)
        return areas

    def create_world_event_area(self, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = str(values.get("key") or "").strip()
        name = str(values.get("name") or "").strip()
        start = str(values.get("start") or "").strip()
        end = str(values.get("end") or "").strip()
        if not key or not name or not (start <= end):
            return None
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO world_custom_event_areas (key, name, subtitle, description, icon, color, start, end, reward_currency, reward_exp, active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)",
                (
                    key[:64], name[:120], str(values.get("subtitle") or "")[:160], str(values.get("description") or ""),
                    str(values.get("icon") or "✧")[:8], str(values.get("color") or "#f0a35b")[:16],
                    start, end, max(0, int(values.get("reward_currency") or 0)), max(0, int(values.get("reward_exp") or 0)), now, now,
                ),
            )
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM world_custom_event_areas WHERE key=?", (key,)).fetchone())
        finally:
            conn.close()

    def update_world_event_area(self, event_key: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "subtitle", "description", "icon", "color", "start", "end", "reward_currency", "reward_exp", "active"}
        updates = {k: values[k] for k in allowed if k in values}
        if not updates:
            conn = self._connect()
            try:
                return self._row_to_dict(conn.execute("SELECT * FROM world_custom_event_areas WHERE key=?", (event_key,)).fetchone())
            finally:
                conn.close()
        if "active" in updates:
            updates["active"] = 1 if updates["active"] else 0
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            assignments = ", ".join(f"{key}=?" for key in updates)
            conn.execute(f"UPDATE world_custom_event_areas SET {assignments}, updated_at=? WHERE key=?", (*updates.values(), now, event_key))
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM world_custom_event_areas WHERE key=?", (event_key,)).fetchone())
        finally:
            conn.close()

    def delete_world_event_area(self, event_key: str) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM world_custom_event_areas WHERE key=?", (event_key,))
            conn.execute("DELETE FROM world_custom_event_shop_items WHERE event_key=?", (event_key,))
            changed = conn.total_changes > 0
            conn.commit()
            return changed
        finally:
            conn.close()

    def create_world_event_shop_item(self, event_key: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item_key = str(values.get("key") or "").strip()
        name = str(values.get("name") or "").strip()
        if not item_key or not name or not str(event_key or "").strip():
            return None
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO world_custom_event_shop_items (event_key, key, name, description, cost, limit_count, kind, requires_discoveries, active, created_at) VALUES (?,?,?,?,?,?,?,?,1,?)",
                (
                    str(event_key), item_key[:64], name[:120], str(values.get("description") or ""),
                    max(0, int(values.get("cost") or 0)), max(1, int(values.get("limit") or 1)),
                    str(values.get("kind") or "collectible"), max(0, int(values.get("requires_discoveries") or 0)), now,
                ),
            )
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM world_custom_event_shop_items WHERE event_key=? AND key=?", (event_key, item_key)).fetchone())
        finally:
            conn.close()

    def delete_world_event_shop_item(self, event_key: str, item_key: str) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM world_custom_event_shop_items WHERE event_key=? AND key=?", (event_key, item_key))
            changed = conn.total_changes > 0
            conn.commit()
            return changed
        finally:
            conn.close()

    def list_world_event_shop(self, event_key: str) -> Dict[str, Any]:
        event = next((item for item in self.list_world_event_areas() if item["key"] == event_key), None)
        today = self._today()
        if not event:
            return {"event_key": event_key, "active": False, "items": []}
        conn = self._connect()
        try:
            purchases = {row["item_key"]: int(row["quantity"]) for row in conn.execute("SELECT item_key, quantity FROM world_event_purchases WHERE event_key=?", (event_key,)).fetchall()}
            custom_items = [
                {"key": row["key"], "name": row["name"], "description": row["description"], "cost": row["cost"], "limit": row["limit_count"], "kind": row["kind"], "requires_discoveries": row["requires_discoveries"], "is_custom": True}
                for row in conn.execute("SELECT * FROM world_custom_event_shop_items WHERE event_key=? AND active=1 ORDER BY id ASC", (event_key,)).fetchall()
            ]
        finally:
            conn.close()
        items = []
        for item in WORLD_EVENT_SHOP_ITEMS.get(event_key, []) + custom_items:
            items.append({**item, "purchased": purchases.get(item["key"], 0), "can_buy": purchases.get(item["key"], 0) < int(item.get("limit", 1))})
        return {"event_key": event_key, "name": event["name"], "active": event["start"] <= today <= event["end"] and bool(event.get("active", 1)), "start": event["start"], "end": event["end"], "items": items}

    def purchase_world_event_item(self, event_key: str, item_key: str) -> Dict[str, Any]:
        shop = self.list_world_event_shop(event_key)
        if not shop.get("active"):
            return {"success": False, "message": "活动尚未开始或已经结束"}
        item = next((entry for entry in shop.get("items", []) if entry["key"] == item_key), None)
        if not item:
            return {"success": False, "message": "活动商品不存在"}
        if not item.get("can_buy"):
            return {"success": False, "message": "这件活动商品已经兑换过了"}
        if int(item.get("requires_discoveries", 0)):
            discovered = len(self.list_world_discoveries(limit=10000))
            if discovered < int(item["requires_discoveries"]):
                return {"success": False, "message": f"还需要累计发现 {item['requires_discoveries']} 个世界事件"}
        try:
            result = self.spend_miya_coins(int(item["cost"]), f"兑换活动「{shop['name']}」· {item['name']}")
        except ValueError as exc:
            return {"success": False, "message": str(exc)}
        if not result.get("success", True):
            return result
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute("INSERT INTO world_event_purchases (event_key, item_key, quantity, purchased_at) VALUES (?,?,1,?)", (event_key, item_key, now))
            conn.commit()
        finally:
            conn.close()
        # 活动纪念物落入现实背包，保证兑换后留下长期档案。
        self.create_item(item["name"], category="collectible", rarity="rare", quantity=1, description=item["description"], fields={"event_key": event_key, "shop_item": item_key})
        return {"success": True, "item": item, "player": self.get_player()}

    def list_miya_shop(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            purchases = {}
            for row in conn.execute("SELECT item_key, SUM(quantity) AS quantity FROM miya_shop_purchases GROUP BY item_key").fetchall():
                purchases[str(row["item_key"])] = int(row["quantity"] or 0)
            custom_rows = conn.execute("SELECT * FROM miya_shop_custom_items ORDER BY id ASC").fetchall()
        finally:
            conn.close()
        items = []
        for item in MIYA_SHOP_ITEMS:
            purchased = purchases.get(item["key"], 0)
            items.append({**item, "purchased": purchased, "can_buy": purchased < int(item.get("limit", 1)), "is_custom": False})
        for row in custom_rows:
            custom = dict(row)
            key = str(custom["key"])
            purchased = purchases.get(key, 0)
            limit = max(1, int(custom.get("limit_count") or 1))
            if not int(custom.get("active") or 0):
                continue  # 下架商品不进货架 (管理接口仍可见)
            items.append({
                "key": key, "name": custom["name"], "description": custom.get("description") or "",
                "cost": int(custom.get("cost") or 0), "limit": limit, "kind": custom.get("kind") or "interaction",
                "interaction": custom.get("interaction") or "", "story_title": custom.get("story_title") or "",
                "story_content": custom.get("story_content") or "", "title_award": custom.get("title_award") or "",
                "boost": custom.get("boost") or "", "purchased": purchased, "can_buy": purchased < limit, "is_custom": True,
            })
        return {"name": "弥娅专属兑换所", "currency": "miya_currency", "items": items, "player": self.get_player()}

    def list_miya_shop_managed(self) -> List[Dict[str, Any]]:
        """管理视图: 内置商品 + 全部自定义商品 (含下架)，供后台/弥娅管理货架。"""
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM miya_shop_custom_items ORDER BY id ASC").fetchall()
        finally:
            conn.close()
        items = [{**item, "is_custom": False, "active": 1, "builtin": True} for item in MIYA_SHOP_ITEMS]
        for row in rows:
            custom = dict(row)
            custom["limit"] = max(1, int(custom.pop("limit_count") or 1))
            custom["active"] = int(custom.get("active") or 0)
            custom["is_custom"] = True
            custom["builtin"] = False
            items.append(custom)
        return items

    def create_miya_shop_item(self, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = str(values.get("key") or "").strip()
        name = str(values.get("name") or "").strip()
        if not key or not name or key in {item["key"] for item in MIYA_SHOP_ITEMS}:
            return None
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO miya_shop_custom_items (key, name, description, cost, limit_count, kind, interaction, story_title, story_content, title_award, boost, active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                (
                    key[:64], name[:120], str(values.get("description") or "")[:500],
                    max(0, int(values.get("cost") or 10)), max(1, int(values.get("limit") or 1)),
                    str(values.get("kind") or "interaction")[:24], str(values.get("interaction") or ""),
                    str(values.get("story_title") or "")[:160], str(values.get("story_content") or ""),
                    str(values.get("title_award") or "")[:60], str(values.get("boost") or "")[:48], now, now,
                ),
            )
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM miya_shop_custom_items WHERE key=?", (key,)).fetchone())
        finally:
            conn.close()

    def update_miya_shop_item(self, item_key: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "description", "cost", "limit", "kind", "interaction", "story_title", "story_content", "title_award", "boost", "active"}
        updates = {k: values[k] for k in allowed if k in values}
        if not updates:
            conn = self._connect()
            try:
                return self._row_to_dict(conn.execute("SELECT * FROM miya_shop_custom_items WHERE key=?", (item_key,)).fetchone())
            finally:
                conn.close()
        if "active" in updates:
            updates["active"] = 1 if updates["active"] else 0
        if "limit" in updates:
            updates["limit_count"] = max(1, int(updates.pop("limit")))
        if "cost" in updates:
            updates["cost"] = max(0, int(updates["cost"]))
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            assignments = ", ".join(f"{key}=?" for key in updates)
            conn.execute(f"UPDATE miya_shop_custom_items SET {assignments}, updated_at=? WHERE key=?", (*updates.values(), now, item_key))
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM miya_shop_custom_items WHERE key=?", (item_key,)).fetchone())
        finally:
            conn.close()

    def delete_miya_shop_item(self, item_key: str) -> bool:
        if item_key in {item["key"] for item in MIYA_SHOP_ITEMS}:
            return False  # 内置商品不可删
        conn = self._connect()
        try:
            conn.execute("DELETE FROM miya_shop_custom_items WHERE key=?", (item_key,))
            changed = conn.total_changes > 0
            conn.commit()
            return changed
        finally:
            conn.close()

    def purchase_miya_shop_item(self, item_key: str) -> Dict[str, Any]:
        shop = self.list_miya_shop()
        item = next((entry for entry in shop["items"] if entry["key"] == item_key), None)
        if not item:
            return {"success": False, "message": "商城商品不存在"}
        if not item.get("can_buy"):
            return {"success": False, "message": "这件商品已经达到兑换上限"}
        result = self.spend_miya_coins(int(item["cost"]), f"弥娅商城 · {item['name']}")
        if not result.get("success"):
            return result
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute("INSERT INTO miya_shop_purchases (item_key, quantity, purchased_at) VALUES (?,?,?)", (item_key, 1, now))
            if item.get("kind") == "story":
                self._link_story_locked(conn, str(item.get("story_title") or item["name"]), str(item.get("story_content") or item["description"]), event_type="world")
            if item.get("kind") == "interaction":
                # v17.4 服务券制: 互动商品兑换后得到一张券 (落背包)，使用时才真正兑现——
                # 可以在背包点「使用」，也可以直接告诉弥娅"用一下抱抱券"，由她亲口回应
                self._log_activity(conn, "miya", "❦", f"兑换服务券: {item['name']}", "券已放入背包，想用的时候告诉弥娅，或点背包里的「使用」")
            if item.get("kind") == "title":
                title = str(item.get("title_award") or item["name"])
                self._log_activity(conn, "miya", "◆", f"获得专属称号: {title}", item["description"])
            conn.commit()
        finally:
            conn.close()
        if item.get("kind") == "boost":
            self.create_item(item["name"], category="collectible", rarity="epic", quantity=1, description=item["description"], fields={"miya_shop_item": item_key, "boost": item.get("boost", "")})
        if item.get("kind") == "interaction":
            self.create_item(
                f"服务券 · {item['name']}", category="collectible", rarity="rare", quantity=1,
                description=str(item.get("description") or "兑换弥娅的专属互动服务，随时可以使用。"),
                fields={"service_ticket": item_key, "interaction": str(item.get("interaction") or ""), "shop_kind": "interaction"},
            )
        self._write_mirror()
        return {"success": True, "item": item, "interaction": item.get("interaction", ""), "player": self.get_player()}

    def redeem_service_ticket(self, item_id: Optional[int] = None, item_key: str = "") -> Dict[str, Any]:
        """使用一张服务券: 返回互动文案 (由弥娅亲口回应或前端展示)，扣减券的数量。

        item_id: 背包物品 ID；item_key: 商城商品 key (自动找一张对应的券)。
        """
        ticket = None
        if item_id:
            ticket = self.get_item(int(item_id))
            if not ticket or not (ticket.get("fields") or {}).get("service_ticket"):
                return {"success": False, "message": "背包里没有这张服务券"}
        else:
            item_key = str(item_key or "").strip()
            if not item_key:
                return {"success": False, "message": "需要 item_id 或 item_key"}
            for candidate in self.list_items(category="collectible"):
                fields = candidate.get("fields") or {}
                if fields.get("service_ticket") == item_key and int(candidate.get("quantity") or 0) > 0:
                    ticket = candidate
                    break
            if not ticket:
                return {"success": False, "message": "背包里没有这个服务券，先去商城兑换吧"}
        fields = ticket.get("fields") or {}
        interaction = str(fields.get("interaction") or "")
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                if int(ticket.get("quantity") or 1) > 1:
                    conn.execute("UPDATE items SET quantity = quantity - 1, updated_at = ? WHERE id = ?", (now, ticket["id"]))
                else:
                    conn.execute("DELETE FROM items WHERE id = ?", (ticket["id"],))
                self._log_activity(conn, "miya", "❦", f"使用服务券: {ticket['name']}", interaction[:120])
                conn.commit()
            finally:
                conn.close()
        self._react_locked_conn_safe("service_used", f"使用服务券「{ticket['name']}」")
        self._write_mirror()
        return {
            "success": True,
            "name": ticket["name"],
            "interaction": interaction,
            "remaining": max(0, int(ticket.get("quantity") or 1) - 1),
            "player": self.get_player(),
        }

    def list_world_discoveries(self, region_key: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if region_key:
                rows = conn.execute(
                    "SELECT * FROM world_discoveries WHERE region_key = ? ORDER BY id DESC LIMIT ?",
                    (region_key, max(1, min(1000, int(limit)))),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM world_discoveries ORDER BY id DESC LIMIT ?",
                    (max(1, min(1000, int(limit))),),
                ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                choice = conn.execute("SELECT choice, chosen_at FROM world_discovery_choices WHERE discovery_id=?", (item.get("id"),)).fetchone()
                item["choice"] = dict(choice) if choice else None
                result.append(item)
            return result
        finally:
            conn.close()

    def choose_world_discovery(self, discovery_id: int, choice: str) -> Dict[str, Any]:
        """探索后的单次同行选择：继续、记录、休息。选择只影响这条发现一次。"""
        choice = str(choice or "").strip().lower()
        labels = {"continue": "继续前进", "record": "记录此刻", "rest": "先休息"}
        if choice not in labels:
            return {"success": False, "message": "无效的同行选择"}
        with self._lock:
            conn = self._connect()
            try:
                discovery = conn.execute("SELECT * FROM world_discoveries WHERE id=?", (int(discovery_id),)).fetchone()
                if not discovery:
                    return {"success": False, "message": "发现记录不存在"}
                existing = conn.execute("SELECT choice FROM world_discovery_choices WHERE discovery_id=?", (int(discovery_id),)).fetchone()
                if existing:
                    return {"success": False, "message": f"你已经选择过「{labels.get(existing['choice'], existing['choice'])}」"}
                now = datetime.now().isoformat()
                conn.execute("INSERT INTO world_discovery_choices (discovery_id, choice, chosen_at) VALUES (?,?,?)", (int(discovery_id), choice, now))
                resonance_amount = {"continue": 6, "record": 10, "rest": 3}[choice]
                resonance = self._add_world_resonance_locked(conn, str(discovery["region_key"]), resonance_amount, now, labels[choice])
                if choice == "record":
                    self._link_story_locked(conn, f"同行记录: {discovery['title']}", f"你选择记录这一刻：{discovery['content']}", event_type="world")
                elif choice == "continue":
                    self._log_activity(conn, "world", "→", f"继续探索「{discovery['title']}」", "弥娅陪你把脚步往前放了一点")
                else:
                    self._log_activity(conn, "world", "☾", f"在「{discovery['title']}」处休息", "休息也是探索的一部分")
                conn.commit()
                result = {"success": True, "choice": choice, "label": labels[choice], "resonance": resonance, "player": self.get_player()}
            finally:
                conn.close()
        self._write_mirror()
        self.refresh_achievements()
        return result

    # ── 现实上下文同步 ─────────────────────────────

    def get_real_context_settings(self) -> Dict[str, Any]:
        """读取现实数据设置；精确坐标默认关闭，配置文件只提供默认值。"""
        from config.config_utils import get_api_key, get_qq_config

        defaults = get_qq_config("earth_online", "real_world", default={}) or {}
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM world_real_context_settings WHERE id = 1").fetchone()
            saved = dict(row) if row else {}
        finally:
            conn.close()
        precise_allowed = bool(saved.get("allow_precise_location", defaults.get("allow_precise_location", False)))
        api_key = get_api_key("SENIVERSE_API_KEY") or get_api_key("WEATHER_API_KEY")
        return {
            "enabled": bool(saved.get("enabled", defaults.get("enabled", True))),
            "city": str(saved.get("city") or defaults.get("city", "")),
            "latitude": (saved.get("latitude") if saved.get("latitude") is not None else defaults.get("latitude")) if precise_allowed else None,
            "longitude": (saved.get("longitude") if saved.get("longitude") is not None else defaults.get("longitude")) if precise_allowed else None,
            "allow_precise_location": precise_allowed,
            "refresh_minutes": max(5, int(saved.get("refresh_minutes") or defaults.get("refresh_minutes", 30))),
            "weather_provider": str(defaults.get("weather_provider", "seniverse")),
            "weather_api_configured": bool(api_key),
            "weather_api_key_masked": f"{api_key[:4]}…{api_key[-4:]}" if len(api_key) >= 10 else ("已配置" if api_key else ""),
        }

    def update_weather_api_key(self, api_key: str) -> Dict[str, Any]:
        """写入本机 config/.env；数据库和 API 响应只返回掩码状态。"""
        from config.config_utils import _CONFIG_DIR
        key = str(api_key or "").strip()
        if len(key) < 8:
            raise ValueError("天气 API Key 太短")
        path = _CONFIG_DIR / ".env"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        replaced = False
        output = []
        for line in lines:
            if line.startswith("SENIVERSE_API_KEY="):
                output.append(f"SENIVERSE_API_KEY={key}")
                replaced = True
            else:
                output.append(line)
        if not replaced:
            output.extend(["", "# --- 心知天气（地球online 现实天气） ---", f"SENIVERSE_API_KEY={key}"])
        path.write_text("\n".join(output) + "\n", encoding="utf-8")
        return self.get_real_context_settings()

    def update_real_context_settings(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """更新现实上下文设置；不接受未经显式允许的精确位置。"""
        current = self.get_real_context_settings()
        enabled = bool(values.get("enabled", current["enabled"]))
        city = str(values.get("city", current["city"]) or "").strip()[:120]
        allow_precise = bool(values.get("allow_precise_location", current["allow_precise_location"]))
        latitude = values.get("latitude", current.get("latitude")) if allow_precise else None
        longitude = values.get("longitude", current.get("longitude")) if allow_precise else None
        try:
            latitude = float(latitude) if latitude not in (None, "") else None
            longitude = float(longitude) if longitude not in (None, "") else None
        except (TypeError, ValueError):
            latitude = longitude = None
        refresh_minutes = max(5, min(1440, int(values.get("refresh_minutes", current["refresh_minutes"]))))
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE world_real_context_settings SET enabled=?, city=?, latitude=?, longitude=?, allow_precise_location=?, refresh_minutes=?, updated_at=? WHERE id=1",
                (int(enabled), city, latitude, longitude, int(allow_precise), refresh_minutes, now),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_real_context_settings()

    def refresh_real_context(self, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """从真实天气源抓取并保存快照；失败时保存 unavailable，而不是生成模拟天气。"""
        values = values or {}
        settings = self.update_real_context_settings(values) if values else self.get_real_context_settings()
        now = datetime.now().astimezone()
        captured_at = now.isoformat()
        city = str(values.get("city") or settings.get("city") or "").strip()
        base = {
            "captured_at": captured_at, "source": "unavailable", "source_status": "unavailable",
            "city": city, "latitude": settings.get("latitude"), "longitude": settings.get("longitude"),
            "weather": "未同步", "weather_icon": "?", "temperature": None, "condition_code": "",
            "humidity": None, "wind": "", "timezone": str(now.tzinfo or ""), "raw_payload": {}, "is_stale": 1,
        }
        if not settings.get("enabled"):
            return self._save_real_context_snapshot(base)
        if not city:
            base["source_status"] = "needs_location"
            return self._save_real_context_snapshot(base)
        try:
            from config.config_utils import get_api_key
            import httpx

            api_key = get_api_key("SENIVERSE_API_KEY") or get_api_key("WEATHER_API_KEY")
            if not api_key:
                base["source_status"] = "not_configured"
                return self._save_real_context_snapshot(base)
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    "https://api.seniverse.com/v3/weather/now.json",
                    params={"key": api_key, "location": city, "language": "zh-Hans", "unit": "c"},
                )
            response.raise_for_status()
            payload = response.json()
            result = (payload.get("results") or [])[0]
            current = result.get("now") or {}
            location = result.get("location") or {}
            text = str(current.get("text") or "未知")
            icon = "☼" if any(x in text for x in ("晴", "阳光")) else "≋" if any(x in text for x in ("雨", "雪")) else "◌"
            base.update({
                "source": "seniverse", "source_status": "ok", "city": str(location.get("name") or city),
                "weather": text, "weather_icon": icon, "temperature": self._to_float(current.get("temperature")),
                "condition_code": str(current.get("code") or ""), "humidity": self._to_float(current.get("humidity")),
                "wind": f"{current.get('wind_direction', '')} {current.get('wind_scale', '')}级".strip(),
                "timezone": str(now.tzinfo or ""), "raw_payload": payload, "is_stale": 0,
            })
        except Exception as exc:
            logger.warning("[EarthOnline] 现实天气同步失败: %s", exc)
            base["source_status"] = "error"
        return self._save_real_context_snapshot(base)

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def _save_real_context_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO world_real_context_snapshots (captured_at, source, source_status, city, latitude, longitude, weather, weather_icon, temperature, condition_code, humidity, wind, timezone, raw_payload, is_stale) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (snapshot["captured_at"], snapshot["source"], snapshot["source_status"], snapshot.get("city", ""), snapshot.get("latitude"), snapshot.get("longitude"), snapshot.get("weather", ""), snapshot.get("weather_icon", ""), snapshot.get("temperature"), snapshot.get("condition_code", ""), snapshot.get("humidity"), snapshot.get("wind", ""), snapshot.get("timezone", ""), json.dumps(snapshot.get("raw_payload", {}), ensure_ascii=False), int(snapshot.get("is_stale", 0))),
            )
            # v17: 只保留最近 200 条快照，历史不再无限堆积
            conn.execute(
                "DELETE FROM world_real_context_snapshots WHERE id NOT IN (SELECT id FROM world_real_context_snapshots ORDER BY id DESC LIMIT 200)"
            )
            conn.commit()
        finally:
            conn.close()
        snapshot = dict(snapshot)
        snapshot["last_synced_at"] = snapshot.get("captured_at")
        return snapshot

    def get_real_context(self, auto_refresh: bool = True) -> Dict[str, Any]:
        settings = self.get_real_context_settings()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM world_real_context_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            conn.close()
        snapshot = dict(row) if row else None
        if snapshot and isinstance(snapshot.get("raw_payload"), str):
            try:
                snapshot["raw_payload"] = json.loads(snapshot["raw_payload"])
            except Exception:
                snapshot["raw_payload"] = {}
        stale = True
        if snapshot:
            try:
                age = (datetime.now().astimezone() - datetime.fromisoformat(snapshot["captured_at"]).astimezone()).total_seconds() / 60
                stale = age > settings["refresh_minutes"]
            except Exception:
                stale = True
            if str(snapshot.get("city") or "").strip() != str(settings.get("city") or "").strip():
                stale = True
        if auto_refresh and (snapshot is None or stale):
            snapshot = self.refresh_real_context()
            stale = snapshot.get("source_status") != "ok"
        if snapshot is None:
            snapshot = {"captured_at": "", "source": "unavailable", "source_status": "needs_location", "city": settings.get("city", ""), "weather": "未同步", "weather_icon": "?", "is_stale": 1}
        snapshot["is_stale"] = int(bool(stale or snapshot.get("source_status") != "ok"))
        snapshot["settings"] = settings
        return snapshot

    def get_world_status(self) -> Dict[str, Any]:
        """本地时间 + 最近一次真实现实上下文；天气不可用时明确显示未同步。"""
        now = datetime.now()
        periods = [(5, "清晨", "☼"), (11, "白昼", "◇"), (17, "黄昏", "◌"), (22, "夜晚", "☾"), (24, "深夜", "✦")]
        period_name, period_icon = "深夜", "✦"
        for boundary, label, icon in periods:
            if now.hour < boundary:
                period_name, period_icon = label, icon
                break
        real = self.get_real_context(auto_refresh=True)
        weather_name = real.get("weather") or "未同步"
        weather_icon = real.get("weather_icon") or "?"
        today = now.strftime("%Y-%m-%d")
        events = []
        for area in self.list_world_event_areas():
            active = area["start"] <= today <= area["end"] and bool(area.get("active", 1))
            events.append({**area, "active": active})
        return {
            "date": today,
            "time": now.strftime("%H:%M"),
            "period": period_name,
            "period_icon": period_icon,
            "weather": weather_name,
            "weather_icon": weather_icon,
            "real_context": real,
            "source_status": real.get("source_status", "unavailable"),
            "event_areas": events,
        }

    def create_region_commission(self, region_key: str) -> Dict[str, Any]:
        """为区域生成当天唯一的专属委托。"""
        region = next((r for r in WORLD_REGION_SEEDS if r["key"] == region_key), None)
        seed = REGION_COMMISSION_SEEDS.get(region_key)
        if not region or not seed:
            return {"success": False, "message": "未知区域"}
        player = self.get_player()
        if int(player.get("level", 1)) < int(region["level_req"]):
            return {"success": False, "message": f"需要达到 Lv.{region['level_req']} 才能领取该区域委托"}
        today = self._today()
        for quest in self.list_quests():
            fields = quest.get("fields") or {}
            if fields.get("world_region") == region_key and fields.get("generated_date") == today and quest.get("status") in ("pending", "ongoing"):
                return {"success": True, "created": False, "quest": quest}
        status = self.get_world_status()
        boost_applied = self._consume_boost_item("commission_resonance")
        quest = self.create_quest(
            title=f"{seed['title']} · {status['weather']}{status['period']}",
            description=seed["description"],
            quest_type="daily",
            must_complete=False,
            reward_currency=12 + int(region["level_req"]) * 3,
            reward_exp=18 + int(region["level_req"]) * 5,
            penalty_currency=0,
            source="miya",
            difficulty=min(5, max(1, int(region["level_req"]))),
            fields={"world_region": region_key, "generated_date": today, "weather": status["weather"], "period": status["period"], "boosted": 1 if boost_applied else 0},
            subtasks=[{"text": text, "done": 0} for text in seed["subtasks"]],
            recurring="",
        )
        if boost_applied:
            now = datetime.now().isoformat()
            conn = self._connect()
            try:
                self._add_world_resonance_locked(conn, region_key, 30, now, "现实委托改写券生效")
                self._log_activity(conn, "miya", "❦", "现实委托改写券已生效", "这次区域委托附带了额外的共鸣加成")
                conn.commit()
            finally:
                conn.close()
            self._write_mirror()
        return {"success": True, "created": True, "quest": quest, "boost_applied": bool(boost_applied)}

    def _consume_boost_item(self, boost_key: str) -> bool:
        """找到并消耗一枚背包里的 boost 券 (fields.boost 匹配)，返回是否消耗成功。"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, quantity, fields FROM items WHERE fields LIKE ?",
                (f'%{json.dumps({"boost": boost_key}, ensure_ascii=False)[1:-1]}%',),
            ).fetchall()
            # LIKE 模糊匹配可能撞到其它 key，逐条精确核对
            for row in rows:
                fields = row["fields"] if isinstance(row["fields"], dict) else {}
                if str(fields.get("boost") or "") != boost_key:
                    continue
                if int(row["quantity"] or 1) > 1:
                    conn.execute("UPDATE items SET quantity = quantity - 1, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), row["id"]))
                else:
                    conn.execute("DELETE FROM items WHERE id = ?", (row["id"],))
                conn.commit()
                return True
            return False
        finally:
            conn.close()

    def explore_world_region(self, region_key: str, latitude: Optional[float] = None, longitude: Optional[float] = None) -> Dict[str, Any]:
        """探索一个区域，首次发现事件才发放奖励；重复探索会返回已发现提示。

        区域绑定了地理围栏时，必须携带真实坐标且在半径范围内才能探索。
        """
        region_key = str(region_key or "").strip()
        region_def = next((r for r in WORLD_REGION_SEEDS if r["key"] == region_key), None)
        if not region_def:
            return {"success": False, "message": "未知区域"}
        geofence = self._check_geofence(region_key, latitude, longitude)
        if not geofence.get("passed"):
            return {"success": False, "message": geofence["message"], "geofence": geofence}
        with self._lock:
            conn = self._connect()
            try:
                player_row = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
                player_level = self._exp_to_level(int(player_row["exp"])) if player_row else 1
                if player_level < int(region_def["level_req"]):
                    return {
                        "success": False,
                        "message": f"需要达到 Lv.{region_def['level_req']} 才能探索「{region_def['name']}」",
                        "level_req": int(region_def["level_req"]),
                    }
                real_context = self.get_real_context(auto_refresh=True)
                period = self._world_period(datetime.now())
                world_context = {**real_context, "period": period}
                existing = conn.execute(
                    "SELECT event_key FROM world_discoveries WHERE region_key = ?", (region_key,)
                ).fetchall()
                seen = {str(row["event_key"]) for row in existing}
                candidates = [
                    (event_key, event) for event_key, event in self._world_events_for_region(region_key, include_locked=False, context=world_context)
                    if event_key not in seen
                ]
                if not candidates:
                    region = conn.execute("SELECT * FROM world_regions WHERE key = ?", (region_key,)).fetchone()
                    return {
                        "success": True,
                        "complete": True,
                        "message": f"「{region_def['name']}」已经探索完毕，弥娅把这里标记成了你的观测站。",
                        "region": dict(region) if region else {"key": region_key, "name": region_def["name"]},
                        "discovery": None,
                        "player": self.get_player(),
                    }
                event_key, event = candidates[0]
                now = datetime.now().isoformat()
                companion = self._world_companion_dialogue(region_def, event, world_context)
                context_snapshot = {"date": now, "real_context": real_context, "companion": companion}
                discovery_cursor = conn.execute(
                    "INSERT INTO world_discoveries (region_key, event_key, kind, title, content, reward_currency, reward_exp, discovered_at, context_snapshot) VALUES (?,?,?,?,?,?,?,?,?)",
                    (region_key, event_key, str(event.get("kind", "story")), event["title"], event["text"], int(event["reward_currency"]), int(event["reward_exp"]), now, json.dumps(context_snapshot, ensure_ascii=False)),
                )
                conn.execute(
                    "UPDATE world_regions SET discovered=1, discovery_count=discovery_count+1, last_explored_at=?, updated_at=? WHERE key=?",
                    (now, now, region_key),
                )
                resonance = self._add_world_resonance_locked(conn, region_key, 16 if event.get("condition") else 10, now, f"发现「{event['title']}」")
                self._grant_miya_locked(conn, int(event["reward_currency"]), f"探索发现: {event['title']}")
                level_up = self._add_exp_locked(conn, int(event["reward_exp"]))
                self._log_activity(
                    conn, "world", region_def["icon"], f"探索发现: {region_def['name']} · {event['title']}",
                    f"奖励 +{event['reward_currency']} 弥娅币 · +{event['reward_exp']} 经验",
                )
                self._link_story_locked(conn, f"探索发现: {event['title']}", event["text"], event_type="world")
                self._react_locked(conn, "world_discovered", f"在「{region_def['name']}」发现「{event['title']}」")
                conn.commit()
                region = conn.execute("SELECT * FROM world_regions WHERE key = ?", (region_key,)).fetchone()
                result = {
                    "success": True,
                    "complete": len(candidates) == 1,
                    "region": dict(region) if region else {},
                    "discovery": {
                        "region_key": region_key,
                        "event_key": event_key,
                        "kind": str(event.get("kind", "story")),
                        "title": event["title"],
                        "content": event["text"],
                        "reward_currency": int(event["reward_currency"]),
                        "reward_exp": int(event["reward_exp"]),
                        "discovered_at": now,
                        "companion": companion,
                        "id": discovery_cursor.lastrowid,
                    },
                    "player": self.get_player(),
                    "level_up": level_up,
                    "resonance": resonance,
                }
            finally:
                conn.close()
        self._write_mirror()
        self.refresh_achievements()
        # 属性联动: 探索消耗少量体力, 好发现补充心情
        result["attrs"] = {"energy": self._adjust_attr("energy", -4), "mood": self._adjust_attr("mood", 2)}
        result["geofence"] = geofence
        return result

    def _check_geofence(self, region_key: str, latitude: Optional[float], longitude: Optional[float]) -> Dict[str, Any]:
        """地理围栏校验: 区域未绑定坐标时直接放行; 绑定后必须在真实半径内。"""
        conn = self._connect()
        try:
            region = conn.execute("SELECT latitude, longitude, geofence_radius, name FROM world_regions WHERE key=?", (region_key,)).fetchone()
        finally:
            conn.close()
        if not region or not region["latitude"] or not region["longitude"] or not int(region["geofence_radius"] or 0):
            return {"enabled": False, "passed": True}
        radius = int(region["geofence_radius"])
        try:
            latitude = float(latitude) if latitude not in (None, "") else None
            longitude = float(longitude) if longitude not in (None, "") else None
        except (TypeError, ValueError):
            latitude = longitude = None
        if latitude is None or longitude is None:
            return {
                "enabled": True, "passed": False,
                "message": f"「{region['name']}」是真实地点，需要开启定位并到达附近 {radius} 米内才能探索哦",
            }
        distance = self._geo_distance_m(latitude, longitude, float(region["latitude"]), float(region["longitude"]))
        info = {"enabled": True, "passed": distance <= radius, "distance_m": round(distance), "radius_m": radius}
        if not info["passed"]:
            info["message"] = f"距离「{region['name']}」还有 {round(distance)} 米，走近一点再试试吧 (围栏半径 {radius} 米)"
        return info

    # ── v17: 每日自动日常委托 ──────────────────────

    def generate_daily_commissions(self) -> Dict[str, Any]:
        """按配置自动生成今日日常委托 (earth_online.daily.auto_generate / daily_quest_count)。

        同一天幂等: 已生成数量达标就不再生成；抽取以日期为种子，当天内容稳定。
        """
        if not bool(self._cfg("daily", "auto_generate", default=True)):
            return {"success": False, "message": "每日日常自动生成未启用 (earth_online.daily.auto_generate)", "created": [], "skipped": "disabled"}
        count = max(1, min(8, int(self._cfg("daily", "daily_quest_count", default=3))))
        today = self._today()
        existing = [
            q for q in self.list_quests()
            if (q.get("fields") or {}).get("daily_commission") and (q.get("fields") or {}).get("generated_date") == today
        ]
        if len(existing) >= count:
            return {"success": True, "created": False, "quests": existing, "message": "今天的日常委托已经齐了"}
        import random

        rng = random.Random(f"earth-daily-{today}")
        used_keys = {(q.get("fields") or {}).get("daily_key") for q in existing}
        pool = [tpl for tpl in DAILY_COMMISSION_POOL if tpl["key"] not in used_keys]
        rng.shuffle(pool)
        created: List[Dict[str, Any]] = []
        for tpl in pool[: count - len(existing)]:
            created.append(self.create_quest(
                title=f"日常 · {tpl['title']}",
                description=tpl["description"],
                quest_type="daily",
                must_complete=False,
                reward_currency=int(tpl["reward_currency"]),
                reward_exp=int(tpl["reward_exp"]),
                penalty_currency=0,
                source="miya",
                difficulty=int(tpl.get("difficulty", 1)),
                fields={"daily_commission": 1, "daily_key": tpl["key"], "generated_date": today},
                subtasks=[{"text": text, "done": 0} for text in tpl.get("subtasks", [])],
                recurring="",
            ))
        return {
            "success": True,
            "created": bool(created),
            "quests": existing + created,
            "created_quests": created,
            "date": today,
        }

    # ── v17.2: 关怀委托引擎 ────────────────────────

    def _care_match(self, tpl: Dict[str, Any], now: datetime, attrs: Dict[str, Any], weather: str) -> bool:
        match = tpl.get("match") or {}
        hour_range = match.get("hour_range")
        if hour_range and not (int(hour_range[0]) <= now.hour < int(hour_range[1])):
            return False
        if match.get("period_any") and self._world_period(now) not in match["period_any"]:
            return False
        attr_rule = match.get("attr_below")
        if attr_rule:
            attr = attrs.get(str(attr_rule.get("key")))
            if not attr or int(attr.get("value", 100)) >= int(attr_rule.get("value", 0)):
                return False
        if match.get("weather_any") and not any(token in weather for token in match["weather_any"]):
            return False
        return True

    def detect_care_moment(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """纯检测: 现在是否存在值得关怀的时机 (不创建任何东西)。

        规则层只负责"什么时候该关心"，委托内容 (标题/子任务/文案) 由弥娅结合上下文现场创作
        (earth_issue_care_commission)；LLM 沉默时由 generate_care_commission 用模板兜底。
        返回 {moment: bool, care_key, hint, cooldown/cap 原因}。
        """
        now = now or datetime.now()
        if not bool(self._cfg("care", "enabled", default=True)):
            return {"moment": False, "reason": "disabled"}
        max_per_day = max(0, int(self._cfg("care", "max_per_day", default=6)))
        cooldown_hours = max(0.0, float(self._cfg("care", "cooldown_hours", default=2.0)))
        if max_per_day <= 0:
            return {"moment": False, "reason": "daily_cap_zero"}
        today = self._today()
        care_quests = [
            q for q in self.list_quests()
            if (q.get("fields") or {}).get("care") and (q.get("fields") or {}).get("generated_date") == today
        ]
        if len(care_quests) >= max_per_day:
            return {"moment": False, "reason": "daily_cap"}
        cooldown_cutoff = (now - timedelta(hours=cooldown_hours)).isoformat()
        recent_keys = {
            str((q.get("fields") or {}).get("care_key"))
            for q in self.list_quests()
            if (q.get("fields") or {}).get("care")
            and str((q.get("fields") or {}).get("issued_at") or "") >= cooldown_cutoff
        }
        attrs = self._get_attrs()
        try:
            weather = str(self.get_world_status().get("weather") or "")
        except Exception:
            weather = ""
        matched = [
            tpl for tpl in sorted(CARE_COMMISSION_TEMPLATES, key=lambda t: -int(t.get("priority", 0)))
            if self._care_match(tpl, now, attrs, weather)
        ]
        if not matched:
            return {"moment": False, "reason": "no_match"}
        tpl = matched[0]
        if tpl["key"] in recent_keys:
            return {"moment": False, "reason": "cooldown", "care_key": tpl["key"]}
        hints = {
            "care_sleep": f"现在是{self._world_period(now)} ({now.strftime('%H:%M')})，佳可能还没睡",
            "care_breakfast": "现在是早餐时段",
            "care_lunch": "现在是午饭时段",
            "care_dinner": "现在是晚饭时段",
            "care_low_energy": "佳的体力条低于30",
            "care_low_mood": "佳的心情值低于30",
            "care_rain": f"真实天气是「{weather}」",
            "care_rest_eyes": "现在是下午，容易久坐",
            "care_water": "日常补水时机",
        }
        return {
            "moment": True,
            "care_key": tpl["key"],
            "hint": hints.get(tpl["key"], "关怀时机"),
            "today_count": len(care_quests),
            "max_per_day": max_per_day,
        }

    def issue_care_commission(
        self,
        care_key: str,
        title: str,
        description: str = "",
        subtasks: Optional[List[Any]] = None,
        reward_currency: int = 6,
        reward_exp: int = 10,
        message: str = "",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """弥娅现场创作关怀委托 (内容由 LLM 即兴生成，本方法只做限额校验与落板)。

        message 会存入委托 fields，供运营周期作为主动敲门候选；返回 message_candidate。
        """
        now = now or datetime.now()
        care_key = str(care_key or "").strip() or "care_custom"
        title = str(title or "").strip()
        if not title:
            return {"success": False, "message": "委托标题不能为空"}
        if not bool(self._cfg("care", "enabled", default=True)):
            return {"success": False, "message": "关怀委托未启用 (earth_online.care.enabled)"}
        # 限额校验复用检测层: 全局上限拒绝；同 key 冷却拒绝；其余信任弥娅的现场判断
        # (规则没覆盖的时机——比如佳刚在对话里说累了——她也可以签发)
        check = self.detect_care_moment(now=now)
        reason = str(check.get("reason") or "")
        if reason in ("disabled", "daily_cap", "daily_cap_zero"):
            return {"success": False, "message": f"关怀委托限额 ({reason})"}
        if reason == "cooldown" and str(check.get("care_key")) == care_key:
            return {"success": False, "message": f"关怀类型「{care_key}」仍在冷却中"}
        today = self._today()
        subtask_list = []
        for st in subtasks or []:
            text = str(st.get("text") if isinstance(st, dict) else st).strip()
            if text:
                subtask_list.append({"text": text, "done": 0})
        quest = self.create_quest(
            title=title[:120],
            description=str(description)[:500],
            quest_type="daily",
            must_complete=False,
            reward_currency=max(0, min(20, int(reward_currency))),
            reward_exp=max(0, min(30, int(reward_exp))),
            penalty_currency=0,
            source="miya",
            difficulty=1,
            fields={"care": 1, "care_key": care_key, "generated_date": today, "issued_at": now.isoformat(), "message": str(message)[:200]},
            subtasks=subtask_list,
            recurring="",
        )
        return {
            "success": True,
            "quest": quest,
            "care_key": care_key,
            "message_candidate": str(message)[:200],
            "today_count": check.get("today_count", 0) + 1,
        }

    def generate_care_commission(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """模板兜底: 弥娅没有现场创作时，用固定模板生成一张关怀委托 (时机判断复用 detect_care_moment)。

        正常路径是弥娅先用 earth_issue_care_commission 现场创作；本方法只在 LLM 沉默时兜底
        (care.fallback_to_templates 控制)，保证"该关心的时候一定有关怀"。
        """
        now = now or datetime.now()
        check = self.detect_care_moment(now=now)
        if str(check.get("reason")) == "disabled":
            return {"success": False, "message": "关怀委托未启用 (earth_online.care.enabled)", "created": False}
        if not check.get("moment"):
            return {"success": True, "created": False, "reason": check.get("reason"), "care_key": check.get("care_key")}
        tpl = next(t for t in CARE_COMMISSION_TEMPLATES if t["key"] == check["care_key"])
        today = self._today()
        quest = self.create_quest(
            title=f"关怀 · {tpl['title']}",
            description=tpl["description"],
            quest_type="daily",
            must_complete=False,
            reward_currency=int(tpl["reward_currency"]),
            reward_exp=int(tpl["reward_exp"]),
            penalty_currency=0,
            source="miya",
            difficulty=1,
            fields={"care": 1, "care_key": tpl["key"], "generated_date": today, "issued_at": now.isoformat()},
            subtasks=[{"text": text, "done": 0} for text in tpl.get("subtasks", [])],
            recurring="",
        )
        message = str(tpl.get("message") or "").replace("{time}", now.strftime("%H:%M"))
        self._react_locked_conn_safe("care_created", f"发布关怀委托 {tpl['title']}")
        return {
            "success": True,
            "created": True,
            "quest": quest,
            "care_key": tpl["key"],
            "title": tpl["title"],
            "message_candidate": message,
            "today_count": int(check.get("today_count", 0)) + 1,
        }

    def _react_locked_conn_safe(self, kind: str, context: str) -> None:
        """独立连接版弥娅反应 (引擎在事务外调用时使用)"""
        with self._lock:
            conn = self._connect()
            try:
                self._react_locked(conn, kind, context)
                conn.commit()
            finally:
                conn.close()

    # ── v17: 地球币 (现实资产) 流水化 ──────────────

    def adjust_earth_currency(self, amount: float, reason: str = "") -> Dict[str, Any]:
        """调整现实资产 (人民币元, 可正可负)，写流水。用于记账: 收入/支出/资产重估。"""
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            return {"success": False, "message": "金额必须是数字"}
        if amount == 0:
            return {"success": False, "message": "调整金额不能为 0"}
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT earth_currency FROM player_profile WHERE id = 1").fetchone()
                balance = round(float(row["earth_currency"] or 0), 2) if row else 0.0
                new_balance = round(balance + amount, 2)
                if new_balance < 0:
                    return {"success": False, "message": f"现实资产余额不足 (当前 ¥{balance})"}
                conn.execute(
                    "UPDATE player_profile SET earth_currency = ?, updated_at = ? WHERE id = 1",
                    (new_balance, datetime.now().isoformat()),
                )
                self._ledger_locked(conn, "earth", amount, reason or "现实资产调整")
                self._log_activity(
                    conn, "miya", "¥",
                    f"现实资产 {amount:+.2f} 元 → ¥{new_balance:.2f}",
                    reason or "",
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {"success": True, "amount": amount, "balance": new_balance, "player": self.get_player()}

    # ── v17: 回忆抽卡 (记忆碎片) ──────────────────

    def get_memory_pool_info(self) -> Dict[str, Any]:
        """卡池信息: 价格/保底/稀有度权重/收集进度"""
        conn = self._connect()
        try:
            owned = {
                str(row["pool_key"])
                for row in conn.execute("SELECT DISTINCT pool_key FROM memory_pulls WHERE is_new = 1").fetchall()
            }
            total_pulls = conn.execute("SELECT COUNT(*) c FROM memory_pulls").fetchone()["c"]
            pity = conn.execute("SELECT gacha_pity FROM player_profile WHERE id = 1").fetchone()
        finally:
            conn.close()
        pool = [{"key": m["key"], "title": m["title"], "rarity": m["rarity"], "owned": m["key"] in owned} for m in MEMORY_POOL]
        return {
            "name": "回忆卡池 · 与弥娅的时间碎片",
            "cost_single": MEMORY_PULL_COST,
            "cost_ten": MEMORY_PULL10_COST,
            "pity_threshold": MEMORY_PITY_THRESHOLD,
            "pity": int(pity["gacha_pity"]) if pity else 0,
            "weights": dict(MEMORY_RARITY_WEIGHTS),
            "dup_refund": dict(MEMORY_DUP_REFUND),
            "total_pulls": int(total_pulls),
            "collected": len(owned),
            "pool_size": len(MEMORY_POOL),
            "pool": pool,
            "player": self.get_player(),
        }

    def _roll_memory(self, rng, min_rarity: str = "") -> Dict[str, Any]:
        rarities = list(MEMORY_RARITY_WEIGHTS.keys())
        if min_rarity in RARITIES:
            floor = RARITIES.index(min_rarity)
            rarities = [r for r in rarities if RARITIES.index(r) >= floor]
        weights = [MEMORY_RARITY_WEIGHTS[r] for r in rarities]
        rarity = rng.choices(rarities, weights=weights, k=1)[0]
        candidates = [m for m in MEMORY_POOL if m["rarity"] == rarity]
        return dict(rng.choice(candidates))

    def pull_memory(self, times: int = 1) -> Dict[str, Any]:
        """回忆抽卡: times=1 单抽 / times=10 十连 (九折 + 保底)。消耗弥娅币，重复碎片自动转化。"""
        import random

        times = int(times)
        if times not in (1, 10):
            return {"success": False, "message": "只支持单抽 (1) 或十连 (10)"}
        cost = MEMORY_PULL_COST if times == 1 else MEMORY_PULL10_COST
        spend = self.spend_miya_coins(cost, f"回忆抽卡 ×{times}")
        if not spend.get("success"):
            return spend
        rng = random.Random()
        results: List[Dict[str, Any]] = []
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                pity_row = conn.execute("SELECT gacha_pity FROM player_profile WHERE id = 1").fetchone()
                pity = int(pity_row["gacha_pity"]) if pity_row else 0
                owned_keys = {
                    str(row["pool_key"])
                    for row in conn.execute("SELECT DISTINCT pool_key FROM memory_pulls WHERE is_new = 1").fetchall()
                }
                refund_total = 0
                for _ in range(times):
                    # 保底: 连续 pity_threshold 抽无史诗+ 时强制史诗以上
                    min_rarity = "epic" if pity >= MEMORY_PITY_THRESHOLD else ""
                    memory = self._roll_memory(rng, min_rarity)
                    rarity = memory["rarity"]
                    if rarity in ("epic", "legendary"):
                        pity = 0
                    else:
                        pity += 1
                    is_new = memory["key"] not in owned_keys
                    refund = 0 if is_new else MEMORY_DUP_REFUND.get(rarity, 0)
                    refund_total += refund
                    item_id = None
                    if is_new:
                        owned_keys.add(memory["key"])
                        cur = conn.execute(
                            "INSERT INTO items (name, category, rarity, quantity, description, image_path, markdown, fields, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (
                                f"回忆碎片 · {memory['title']}", "collectible", rarity, 1,
                                memory["text"], "", "", json.dumps({"memory_pool": memory["key"], "source": "gacha"}, ensure_ascii=False),
                                now, now,
                            ),
                        )
                        item_id = cur.lastrowid
                    conn.execute(
                        "INSERT INTO memory_pulls (pool_key, title, rarity, is_new, item_id, refund_currency, created_at) VALUES (?,?,?,?,?,?,?)",
                        (memory["key"], memory["title"], rarity, 1 if is_new else 0, item_id, refund, now),
                    )
                    results.append({
                        "pool_key": memory["key"], "title": memory["title"], "text": memory["text"],
                        "rarity": rarity, "is_new": is_new, "item_id": item_id, "refund_currency": refund,
                    })
                conn.execute("UPDATE player_profile SET gacha_pity = ?, updated_at = ? WHERE id = 1", (pity, now))
                if refund_total > 0:
                    self._grant_miya_locked(conn, refund_total, "回忆抽卡 · 重复碎片转化")
                best = max((r for r in results), key=lambda r: RARITIES.index(r["rarity"]))
                new_count = sum(1 for r in results if r["is_new"])
                self._log_activity(
                    conn, "miya", "✦", f"回忆抽卡 ×{times}: 最佳「{best['title']}」",
                    f"新碎片 {new_count}/{times}" + (f" · 重复转化 +{refund_total} 弥娅币" if refund_total else ""),
                )
                if best["rarity"] == "legendary":
                    self._react_locked(conn, "memory_legendary", f"抽到传说碎片「{best['title']}」")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {
            "success": True,
            "times": times,
            "cost": cost,
            "results": results,
            "refund_total": refund_total,
            "pity": pity,
            "player": self.get_player(),
        }

    def list_memory_pulls(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM memory_pulls ORDER BY id DESC LIMIT ?", (max(1, min(1000, int(limit))),)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── v17: 纪念日 (每年循环, 临近自动开限时活动) ──

    def list_commemorations(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM commemorations ORDER BY date ASC").fetchall()
        finally:
            conn.close()
        today = datetime.now()
        result = []
        for row in rows:
            memo = dict(row)
            try:
                month, day = str(memo["date"]).split("-")
                try:
                    target = today.replace(month=int(month), day=int(day))
                except ValueError:  # 02-30 之类的非法日期 → 收敛到当月 28 日
                    target = today.replace(month=int(month), day=28)
                days_until = (target.date() - today.date()).days
                if days_until < 0:  # 今年已过 → 看明年
                    try:
                        target = target.replace(year=today.year + 1)
                    except ValueError:
                        target = target.replace(year=today.year + 1, day=28)
                    days_until = (target.date() - today.date()).days
                memo["days_until"] = days_until
                memo["phase"] = "today" if days_until == 0 else ("upcoming" if days_until <= int(memo.get("lead_days", 2)) else "later")
                memo["next_date"] = target.date().isoformat()
            except Exception:
                memo["days_until"] = None
                memo["phase"] = "invalid"
                memo["next_date"] = ""
            result.append(memo)
        return result

    def add_commemoration(self, key: str, name: str, date: str, description: str = "", icon: str = "✦", lead_days: int = 2) -> Dict[str, Any]:
        """新增纪念日。date 格式 MM-DD (每年循环)，例如 05-20。"""
        key = str(key or "").strip()
        name = str(name or "").strip()
        date = str(date or "").strip()
        if not key or not name:
            return {"success": False, "message": "key 与名称不能为空"}
        try:
            month, day = date.split("-")
            if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
                raise ValueError
        except ValueError:
            return {"success": False, "message": "date 必须是 MM-DD 格式 (如 05-20)"}
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            exists = conn.execute("SELECT id FROM commemorations WHERE key = ?", (key,)).fetchone()
            if exists:
                return {"success": False, "message": f"纪念日 key「{key}」已存在"}
            conn.execute(
                "INSERT INTO commemorations (key, name, date, description, icon, lead_days, enabled, created_at, updated_at) VALUES (?,?,?,?,?,?,1,?,?)",
                (key[:64], name[:120], date, str(description)[:500], str(icon)[:8] or "✦", max(0, min(30, int(lead_days))), now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM commemorations WHERE key = ?", (key,)).fetchone()
            result = {"success": True, "commemoration": dict(row)}
        finally:
            conn.close()
        self._write_mirror()
        return result

    def update_commemoration(self, key: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "date", "description", "icon", "lead_days", "enabled"}
        updates = {k: values[k] for k in allowed if k in values}
        if not updates:
            conn = self._connect()
            try:
                return self._row_to_dict(conn.execute("SELECT * FROM commemorations WHERE key=?", (key,)).fetchone())
            finally:
                conn.close()
        if "enabled" in updates:
            updates["enabled"] = 1 if updates["enabled"] else 0
        if "lead_days" in updates:
            updates["lead_days"] = max(0, min(30, int(updates["lead_days"])))
        now = datetime.now().isoformat()
        conn = self._connect()
        try:
            assignments = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE commemorations SET {assignments}, updated_at=? WHERE key=?", (*updates.values(), now, key))
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM commemorations WHERE key=?", (key,)).fetchone())
        finally:
            conn.close()

    def delete_commemoration(self, key: str) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM commemorations WHERE key=?", (key,))
            changed = conn.total_changes > 0
            conn.commit()
            return changed
        finally:
            conn.close()

    def sync_commemorations(self) -> Dict[str, Any]:
        """纪念日同步: 临近 (lead_days 内) 自动创建当年限时活动区域; 当天自动写一条寄语。幂等。"""
        today = datetime.now().date()
        activated: List[str] = []
        notes_sent: List[str] = []
        for memo in self.list_commemorations():
            if not int(memo.get("enabled", 1)) or memo.get("phase") in ("invalid", None):
                continue
            raw_days = memo.get("days_until")
            days_until = int(raw_days) if raw_days is not None else 999
            if days_until > int(memo.get("lead_days", 2)):
                continue
            try:
                month, day = str(memo["date"]).split("-")
                target = today.replace(month=int(month), day=int(day))
                if target < today:  # 已过 → 明年
                    target = target.replace(year=today.year + 1)
            except ValueError:
                continue
            event_key = f"memo_{memo['key']}_{target.year}"
            start = (target - timedelta(days=int(memo.get("lead_days", 2)))).isoformat()
            end = target.isoformat()
            existing = [a for a in self.list_world_event_areas() if a.get("key") == event_key]
            if not existing:
                self.create_world_event_area({
                    "key": event_key,
                    "name": f"{memo['name']} · {target.year}",
                    "subtitle": f"纪念日限定 · {start} ~ {end}",
                    "description": memo.get("description") or f"「{memo['name']}」到了。这一天值得被世界标记出来。",
                    "icon": memo.get("icon") or "✦",
                    "color": "#e18ab9",
                    "start": start,
                    "end": end,
                    "reward_currency": 20,
                    "reward_exp": 30,
                })
                activated.append(memo["name"])
            if days_until == 0:
                marker = f"[纪念日]{memo['name']}"
                already = any(
                    str(n.get("content", "")).startswith(marker) and str(n.get("created_at", ""))[:10] == today.isoformat()
                    for n in self.list_notes(limit=30)
                )
                if not already:
                    self.add_note(
                        f"{marker} 今天是「{memo['name']}」。{memo.get('description') or '这一天因为你们而被记住了。'}",
                        mood="warm",
                        pinned=True,
                    )
                    notes_sent.append(memo["name"])
        return {"success": True, "activated": activated, "notes_sent": notes_sent, "date": today.isoformat()}

    # ── v17: 每周纪行 (Battle Pass, 免费单轨) ──────

    @staticmethod
    def _week_bounds(now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now()
        monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        iso = now.isocalendar()
        return {"monday": monday, "monday_iso": monday.isoformat(), "monday_date": monday.strftime("%Y-%m-%d"), "week_key": f"{iso[0]}-W{iso[1]:02d}", "iso_week": int(iso[1])}

    def get_battle_pass(self) -> Dict[str, Any]:
        """本周纪行: 积分来自真实游玩数据 (完成委托/签到/探索/剧情/抽卡)，达到阈值可领奖励。"""
        bounds = self._week_bounds()
        conn = self._connect()
        try:
            quests_done = conn.execute(
                "SELECT COUNT(*) c FROM quest_history WHERE status = 'completed' AND completed_at >= ?",
                (bounds["monday_iso"],),
            ).fetchone()["c"]
            checkins = conn.execute(
                "SELECT COUNT(*) c FROM daily_checkins WHERE date >= ?", (bounds["monday_date"],)
            ).fetchone()["c"]
            discoveries = conn.execute(
                "SELECT COUNT(*) c FROM world_discoveries WHERE discovered_at >= ?", (bounds["monday_iso"],)
            ).fetchone()["c"]
            stories = conn.execute(
                "SELECT COUNT(*) c FROM story_events WHERE happened_at >= ?", (bounds["monday_iso"],)
            ).fetchone()["c"]
            pulls = conn.execute(
                "SELECT COUNT(*) c FROM memory_pulls WHERE created_at >= ?", (bounds["monday_iso"],)
            ).fetchone()["c"]
            claimed = {
                int(row["tier"])
                for row in conn.execute("SELECT tier FROM battle_pass_claims WHERE week = ?", (bounds["week_key"],)).fetchall()
            }
        finally:
            conn.close()
        breakdown = {
            "quest_completed": {"count": int(quests_done), "points_each": BATTLE_PASS_POINTS["quest_completed"]},
            "checkin": {"count": int(checkins), "points_each": BATTLE_PASS_POINTS["checkin"]},
            "discovery": {"count": int(discoveries), "points_each": BATTLE_PASS_POINTS["discovery"]},
            "story": {"count": int(stories), "points_each": BATTLE_PASS_POINTS["story"]},
            "memory_pull": {"count": int(pulls), "points_each": BATTLE_PASS_POINTS["memory_pull"]},
        }
        points = sum(item["count"] * item["points_each"] for item in breakdown.values())
        tiers = []
        for tier in BATTLE_PASS_TIERS:
            reached = points >= int(tier["threshold"])
            tiers.append({
                "tier": int(tier["tier"]),
                "threshold": int(tier["threshold"]),
                "reward_currency": int(tier["reward_currency"]),
                "reached": reached,
                "claimed": int(tier["tier"]) in claimed,
                "claimable": reached and int(tier["tier"]) not in claimed,
            })
        return {
            "name": "每周纪行",
            "week_key": bounds["week_key"],
            "week_start": bounds["monday_date"],
            "points": points,
            "breakdown": breakdown,
            "tiers": tiers,
            "current_tier": max([t["tier"] for t in tiers if t["reached"]], default=0),
            "claimable_count": sum(1 for t in tiers if t["claimable"]),
        }

    def claim_battle_pass_tier(self, tier: int) -> Dict[str, Any]:
        """领取纪行某一档奖励 (积分达标且未领过)"""
        tier = int(tier)
        info = self.get_battle_pass()
        entry = next((t for t in info["tiers"] if t["tier"] == tier), None)
        if not entry:
            return {"success": False, "message": f"纪行没有第 {tier} 档"}
        if entry["claimed"]:
            return {"success": False, "message": "这一档已经领过了"}
        if not entry["reached"]:
            return {"success": False, "message": f"积分还差 {entry['threshold'] - info['points']} 点到达第 {tier} 档"}
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT OR IGNORE INTO battle_pass_claims (week, tier, reward_currency, claimed_at) VALUES (?,?,?,?)",
                    (info["week_key"], tier, entry["reward_currency"], now),
                )
                if conn.total_changes == 0:
                    return {"success": False, "message": "这一档已经领过了"}
                self._grant_miya_locked(conn, entry["reward_currency"], f"每周纪行 · 第 {tier} 档")
                self._log_activity(conn, "miya", "❖", f"纪行奖励已领取: 第 {tier} 档", f"+{entry['reward_currency']} 弥娅币")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {"success": True, "tier": tier, "reward_currency": entry["reward_currency"], "battle_pass": self.get_battle_pass()}

    # ── v17: 周挑战 (主题轮换 + 星级) ──────────────

    def get_weekly_challenge(self) -> Dict[str, Any]:
        """本周挑战: 主题按 ISO 周号轮换，完成委托数决定星级 (2/4/5 → ★/★★/★★★)。"""
        bounds = self._week_bounds()
        theme = WEEKLY_CHALLENGE_THEMES[bounds["iso_week"] % len(WEEKLY_CHALLENGE_THEMES)]
        conn = self._connect()
        try:
            done = conn.execute(
                "SELECT COUNT(*) c FROM quest_history WHERE status = 'completed' AND completed_at >= ?",
                (bounds["monday_iso"],),
            ).fetchone()["c"]
        finally:
            conn.close()
        stars = 3 if done >= WEEKLY_CHALLENGE_GOAL else (2 if done >= 4 else (1 if done >= 2 else 0))
        return {
            "name": f"周挑战 · {theme['name']}",
            "theme": theme,
            "week_key": bounds["week_key"],
            "goal": WEEKLY_CHALLENGE_GOAL,
            "completed_quests": int(done),
            "stars": stars,
            "stars_label": "★" * stars + "☆" * (3 - stars),
            "progress_percent": round(min(100, done / WEEKLY_CHALLENGE_GOAL * 100)),
        }

    # ── 汇总 (弥娅/前端一键读取) ────────────────────

    def summary(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            player = self.get_player()
            active_quests = conn.execute(
                "SELECT COUNT(*) as c FROM quests WHERE status IN ('pending', 'ongoing')"
            ).fetchone()["c"]
            item_count = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
            character_count = conn.execute("SELECT COUNT(*) as c FROM characters").fetchone()["c"]
            story_count = conn.execute("SELECT COUNT(*) as c FROM story_events").fetchone()["c"]
            return {
                "player": player,
                "stats": {
                    "active_quests": active_quests,
                    "items": item_count,
                    "characters": character_count,
                    "stories": story_count,
                },
            }
        finally:
            conn.close()


_store: Optional[EarthOnlineStore] = None
_store_lock = threading.Lock()


def get_earth_store() -> EarthOnlineStore:
    """获取全局地球online存储实例"""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = EarthOnlineStore()
    return _store
