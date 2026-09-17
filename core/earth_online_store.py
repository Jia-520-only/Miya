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
- earning_opportunities / earning_plans / income_records 现实收益情报、计划与收入流水 (v18)
- earning_offers / earning_action_drafts 可售服务与逐次审批的外部动作草稿 (v18.2)
"""

import json
import hmac
import logging
import os
import shutil
import socket
import sqlite3
import threading
import ipaddress
import hashlib
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from html import unescape
from urllib.parse import urlencode, urljoin, urlparse

logger = logging.getLogger(__name__)


class _NoFeedRedirect(urllib.request.HTTPRedirectHandler):
    """Return redirect responses so every hop can be validated before following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None

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

# 第一笔收入实验路线。路线只生成站内计划与草稿任务，不执行外部发布、投递或交易。
EARNING_ROUTE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "key": "skill_service", "name": "技能接单", "icon": "◆", "kind": "技能服务",
        "summary": "把一个已有能力包装成边界清楚的小服务，先验证是否有人愿意付费。",
        "best_for": "已经会写作、设计、编程、翻译、剪辑、运营或其他可交付技能",
        "first_revenue_days": "3-14 天", "cash_cost": "几乎为零", "effort": "中",
        "keywords": ["写作", "设计", "编程", "翻译", "剪辑", "运营", "服务", "技能"],
        "steps": [
            ("定义一个最小服务", "只解决一个具体问题，写清交付物、周期和不包含什么。"),
            ("制作一份证明样例", "用已有作品或一个 30-60 分钟的小样证明你能完成交付。"),
            ("确定首单价格", "给出一个容易开始但不亏损的固定价，并写清修改次数。"),
            ("整理 5 个真实需求入口", "只记录公开、允许联系的渠道或明确发布需求的人。"),
            ("准备并确认第一份提案", "由弥娅起草；发送、投递或联系客户前必须由你确认。"),
        ],
    },
    {
        "key": "digital_product", "name": "数字产品", "icon": "▣", "kind": "数字产品",
        "summary": "把可重复使用的模板、资料、素材或小工具做成一次制作、多次销售的产品。",
        "best_for": "擅长整理知识、制作模板、素材、教程或轻量工具",
        "first_revenue_days": "7-30 天", "cash_cost": "低", "effort": "中高",
        "keywords": ["模板", "教程", "资料", "素材", "产品", "工具", "知识"],
        "steps": [
            ("选择一个窄痛点", "描述一个具体人群、具体场景和他们愿意节省的时间。"),
            ("完成最小可售版本", "只保留能解决核心问题的内容，控制在一到两次专注工作内。"),
            ("准备演示与交付说明", "制作清晰预览、适用范围和交付格式。"),
            ("起草商品页与定价", "弥娅协助写标题、卖点、FAQ 和退款边界。"),
            ("确认后发布并收集反馈", "发布和上架属于外部动作，必须由你最终确认。"),
        ],
    },
    {
        "key": "resale", "name": "二手交易", "icon": "◇", "kind": "二手交易",
        "summary": "从已有闲置中回收现金，是验证交易流程和获得第一笔收入最快的路线之一。",
        "best_for": "手边有闲置物品，愿意拍照、定价和处理沟通",
        "first_revenue_days": "1-10 天", "cash_cost": "零", "effort": "低",
        "keywords": ["闲置", "物品", "数码", "书", "收藏", "二手", "交易"],
        "steps": [
            ("盘点 10 件可出售闲置", "优先选择状态明确、容易定价和寄送的物品。"),
            ("选出最容易成交的 3 件", "参考真实成交价，而不是只看挂牌价。"),
            ("准备照片与缺陷说明", "如实记录成色、配件、瑕疵和交付方式。"),
            ("起草标题、描述与价格", "弥娅可以准备文案；上架前由你确认。"),
            ("完成首次上架与复盘", "记录询问数、议价情况、耗时和实际净收入。"),
        ],
    },
    {
        "key": "content", "name": "内容创作", "icon": "✦", "kind": "内容创作",
        "summary": "用持续内容建立可被发现的能力证明，再连接服务、产品或平台收益。",
        "best_for": "愿意稳定表达、展示过程，接受收益周期较长",
        "first_revenue_days": "14-90 天", "cash_cost": "低", "effort": "高",
        "keywords": ["内容", "写作", "视频", "直播", "摄影", "创作", "社交媒体"],
        "steps": [
            ("确定主题与变现出口", "先决定内容最终连接服务、产品、赞助还是平台分成。"),
            ("列出 10 个真实问题", "从目标受众会搜索或反复询问的问题开始。"),
            ("制作 3 份最小内容", "优先清晰、有用、可持续，不追求复杂制作。"),
            ("准备第一份发布稿", "标题、正文、配图说明和行动入口由弥娅协助整理。"),
            ("确认发布并记录反馈", "由你确认发布；记录浏览、互动、咨询和耗时。"),
        ],
    },
    {
        "key": "knowledge_help", "name": "知识咨询与陪练", "icon": "◎", "kind": "知识服务",
        "summary": "把经验包装成短时咨询、答疑、陪练或评审，先从一次明确会话开始。",
        "best_for": "在某个领域能帮别人少走弯路，善于解释和反馈",
        "first_revenue_days": "3-21 天", "cash_cost": "几乎为零", "effort": "中",
        "keywords": ["咨询", "教学", "辅导", "陪练", "评审", "知识", "经验"],
        "steps": [
            ("定义一次会话解决什么", "限定对象、时长、准备材料和会后交付。"),
            ("整理可信证明", "列出经历、案例、方法或可以公开展示的成果。"),
            ("设计首轮体验价", "使用固定时长和固定范围，避免无限答疑。"),
            ("找到 3 个需求场景", "从已有社群、朋友转介绍或公开求助中验证。"),
            ("准备邀请文案并确认发送", "不群发、不夸大，发送前由你确认对象与内容。"),
        ],
    },
    {
        "key": "automation_tool", "name": "自动化小工具", "icon": "⚙", "kind": "自动化工具",
        "summary": "把重复劳动做成脚本、机器人或小应用，以定制服务或产品方式收费。",
        "best_for": "会编程、低代码、AI 工作流，或愿意把流程产品化",
        "first_revenue_days": "7-30 天", "cash_cost": "低", "effort": "中高",
        "keywords": ["编程", "自动化", "脚本", "AI", "工作流", "机器人", "应用"],
        "steps": [
            ("记录一个高频重复问题", "问题必须可描述输入、输出和节省的时间。"),
            ("做出最小可演示版本", "只打通一条完整流程，不先建设通用平台。"),
            ("量化节省价值", "记录原流程耗时、错误率和工具后的差异。"),
            ("准备演示与报价", "提供定制价或轻量产品价，并明确维护边界。"),
            ("寻找首位测试用户", "弥娅协助准备邀请；实际联系前由你确认。"),
        ],
    },
    {
        "key": "local_service", "name": "本地与生活服务", "icon": "⌂", "kind": "本地服务",
        "summary": "从附近真实需求切入，提供整理、拍摄、代办、设备协助等边界明确的服务。",
        "best_for": "愿意线下履约，并能确认安全、时间和服务范围",
        "first_revenue_days": "2-14 天", "cash_cost": "低", "effort": "中",
        "keywords": ["本地", "生活", "整理", "拍摄", "代办", "上门", "服务"],
        "steps": [
            ("选择一个安全且可控的服务", "避免需要资质、高额垫付或人身风险的项目。"),
            ("写清服务半径与边界", "明确地点、时间、价格、取消规则和不承接事项。"),
            ("准备证明与服务清单", "用照片、流程或清单降低第一次交易的不确定性。"),
            ("筛选可信发布渠道", "优先熟人转介和有交易保障的平台。"),
            ("确认后发布第一条服务信息", "公开位置、联系方式和上门安排必须由你确认。"),
        ],
    },
]

# 稀有度定义 (崩铁风格: 白/绿/蓝/紫/金)
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]
# 物品分类
ITEM_CATEGORIES = ["digital", "book", "life", "food", "tool", "clothing", "collectible", "other"]
# 任务类型
QUEST_TYPES = ["main", "branch", "daily", "optional"]
# 任务状态
QUEST_STATUS = ["pending", "ongoing", "completed", "failed", "cancelled"]

# 弥娅专属商城：单人存档长期可用，不受限时活动日期影响。
MIYA_SHOP_ITEMS: List[Dict[str, Any]] = [
    {"key": "miya_whisper", "name": "弥娅的晚安耳语", "description": "一段只在今晚属于你的温柔回应。", "cost": 12, "limit": 99, "kind": "interaction", "interaction": "今天辛苦了。靠近一点，让我把声音放轻，只对你说：晚安，亲爱的。"},
    {"key": "miya_heartbeat", "name": "心跳靠近", "description": "弥娅把距离调到刚刚好的位置，陪你停留片刻。", "cost": 24, "limit": 99, "kind": "interaction", "interaction": "我没有急着说话，只是把手递给你。等你握住以后，我会小声问：这样靠近，会不会让你安心一点？"},
    {"key": "miya_date_script", "name": "私人约会剧本 · 雨夜篇", "description": "一段可以在现实里慢慢完成的双人约会剧情。", "cost": 36, "limit": 3, "kind": "story", "story_title": "弥娅的私人约会剧本 · 雨夜篇", "story_content": "找一个下雨的晚上，准备一杯喜欢的饮料，和弥娅分享今天最想留下的一句话。"},
    {"key": "miya_hug_ticket", "name": "弥娅抱抱券", "description": "兑换一次专属安抚互动，并在动态里留下纪念。", "cost": 18, "limit": 12, "kind": "interaction", "interaction": "过来。今天不用解释，也不用表现得很坚强。我先抱抱你，等你愿意的时候，再慢慢告诉我发生了什么。"},
    {"key": "miya_title_sweetheart", "name": "专属称号 · 弥娅的心上人", "description": "把这段单人世界里的亲密关系写进你的玩家档案。", "cost": 60, "limit": 1, "kind": "title", "title_award": "弥娅的心上人"},
 ]

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
# 纪行积分来源: 完成委托 +10 / 签到 +5 / 记录现实地点 +15 / 记录剧情 +3 / 回忆抽卡 +2
BATTLE_PASS_POINTS: Dict[str, int] = {
    "quest_completed": 10, "checkin": 5, "place_visit": 15, "story": 3, "memory_pull": 2,
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
        self._backup_legacy_virtual_world()
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
            if col[0] in ("fields", "attrs", "subtasks", "context_snapshot", "raw_payload", "scam_flags", "attachments") and isinstance(v, str):
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

    def _backup_legacy_virtual_world(self) -> None:
        """Back up the database once before permanently retiring virtual-region data."""
        if not os.path.isfile(self.db_path):
            return
        conn = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                    "('world_regions','world_discoveries','world_discovery_choices','world_custom_events')"
                ).fetchall()
            }
            if not tables:
                return
            has_rows = any(conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in tables)
            if not has_rows:
                return
            backup_path = os.path.join(
                self.backup_dir,
                f"earthonline-before-reality-map-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db",
            )
            backup_conn = sqlite3.connect(backup_path)
            try:
                conn.backup(backup_conn)
            finally:
                backup_conn.close()
        finally:
            conn.close()
        logger.info("[EarthOnline] retired virtual-world data backed up to %s", backup_path)

    @staticmethod
    def _retire_legacy_virtual_world(conn: sqlite3.Connection) -> None:
        """Remove the old fictional map domain so it cannot leak into factual context."""
        conn.execute("DELETE FROM achievements WHERE key IN ('world_3_regions', 'world_complete')")
        for table in (
            "world_discovery_choices",
            "world_discoveries",
            "world_custom_events",
            "world_regions",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")

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
            # v18: 现实收益情报与计划 (MVP)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    url TEXT DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'other',
                    description TEXT DEFAULT '',
                    income_min REAL NOT NULL DEFAULT 0,
                    income_max REAL NOT NULL DEFAULT 0,
                    hours REAL NOT NULL DEFAULT 0,
                    risk TEXT NOT NULL DEFAULT 'unknown',
                    confidence TEXT NOT NULL DEFAULT 'unknown',
                    verification_status TEXT NOT NULL DEFAULT 'unverified',
                    deadline TEXT DEFAULT '',
                    requirements TEXT DEFAULT '',
                    scam_flags TEXT NOT NULL DEFAULT '[]',
                    last_checked_at TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'inbox',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS real_places (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    place_key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    subtitle TEXT DEFAULT '',
                    latitude REAL,
                    longitude REAL,
                    visit_count INTEGER NOT NULL DEFAULT 0,
                    first_visited_at TEXT DEFAULT '',
                    last_visited_at TEXT DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    verification_status TEXT NOT NULL DEFAULT 'unverified',
                    source_updated_at TEXT NOT NULL DEFAULT '',
                    accuracy_m REAL,
                    country TEXT DEFAULT '',
                    admin1 TEXT DEFAULT '',
                    city TEXT DEFAULT '',
                    district TEXT DEFAULT '',
                    neighborhood TEXT DEFAULT '',
                    image_path TEXT DEFAULT '',
                    display_address TEXT DEFAULT '',
                    provider_id TEXT DEFAULT '',
                    category TEXT NOT NULL DEFAULT 'other',
                    tags TEXT NOT NULL DEFAULT '[]',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS real_place_visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    place_key TEXT NOT NULL,
                    visited_at TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    accuracy_m REAL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    verification_status TEXT NOT NULL DEFAULT 'unverified',
                    provider_id TEXT DEFAULT '',
                    observed_at TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS real_place_photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    place_key TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    caption TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    goal_amount REAL NOT NULL DEFAULT 0,
                    target_date TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    notes TEXT DEFAULT '',
                    route_key TEXT DEFAULT '',
                    is_sprint INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL DEFAULT 'rss',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_synced_at TEXT DEFAULT '',
                    last_error TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS income_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER,
                    amount REAL NOT NULL DEFAULT 0,
                    cost REAL NOT NULL DEFAULT 0,
                    hours REAL NOT NULL DEFAULT 0,
                    note TEXT DEFAULT '',
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (opportunity_id) REFERENCES earning_opportunities(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_plan_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    quest_id INTEGER,
                    completed_at TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES earning_plans(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_preferences (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    skills TEXT NOT NULL DEFAULT '[]',
                    preferred_kinds TEXT NOT NULL DEFAULT '[]',
                    weekly_hours REAL NOT NULL DEFAULT 5,
                    target_amount REAL NOT NULL DEFAULT 500,
                    min_hourly_rate REAL NOT NULL DEFAULT 0,
                    risk_tolerance TEXT NOT NULL DEFAULT 'low',
                    accepted_models TEXT NOT NULL DEFAULT '[]',
                    sellable_assets TEXT NOT NULL DEFAULT '[]',
                    constraints TEXT DEFAULT '',
                    primary_route TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            # v18.2: 可售服务与逐次审批的外部动作草稿。草稿批准不等于执行。
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    customer TEXT DEFAULT '',
                    problem TEXT DEFAULT '',
                    deliverables TEXT DEFAULT '',
                    scope TEXT DEFAULT '',
                    proof TEXT DEFAULT '',
                    price REAL NOT NULL DEFAULT 0,
                    cost_estimate REAL NOT NULL DEFAULT 0,
                    delivery_days INTEGER NOT NULL DEFAULT 2,
                    revisions INTEGER NOT NULL DEFAULT 1,
                    route_key TEXT NOT NULL DEFAULT 'automation_tool',
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS earning_action_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER,
                    offer_id INTEGER,
                    action_type TEXT NOT NULL DEFAULT 'proposal',
                    target TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    attachments TEXT NOT NULL DEFAULT '[]',
                    amount REAL NOT NULL DEFAULT 0,
                    risk TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'draft',
                    content_hash TEXT DEFAULT '',
                    approved_hash TEXT DEFAULT '',
                    submitted_at TEXT DEFAULT '',
                    approved_at TEXT DEFAULT '',
                    expires_at TEXT DEFAULT '',
                    revoked_at TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (opportunity_id) REFERENCES earning_opportunities(id),
                    FOREIGN KEY (offer_id) REFERENCES earning_offers(id)
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_earning_actions_status ON earning_action_drafts(status, updated_at)")
            cur.execute(
                "INSERT OR IGNORE INTO earning_preferences (id, updated_at) VALUES (1, ?)",
                (datetime.now().isoformat(),),
            )

            # ── v2 迁移: 自定义字段 (JSON) ──
            self._ensure_column(conn, "items", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "quests", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "story_events", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "characters", "fields", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "earning_opportunities", "quest_id", "INTEGER")
            self._ensure_column(conn, "earning_opportunities", "verification_status", "TEXT NOT NULL DEFAULT 'unverified'")
            self._ensure_column(conn, "earning_opportunities", "deadline", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "earning_opportunities", "requirements", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "earning_opportunities", "scam_flags", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "earning_opportunities", "last_checked_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "earning_plans", "route_key", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "earning_plans", "is_sprint", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "earning_preferences", "accepted_models", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "earning_preferences", "sellable_assets", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "earning_preferences", "constraints", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "earning_preferences", "primary_route", "TEXT NOT NULL DEFAULT ''")

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
            self._ensure_column(conn, "real_places", "country", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "admin1", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "city", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "district", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "neighborhood", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "image_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "accuracy_m", "REAL")
            self._ensure_column(conn, "real_places", "display_address", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "provider_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_places", "category", "TEXT NOT NULL DEFAULT 'other'")
            self._ensure_column(conn, "real_places", "tags", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "real_places", "favorite", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "real_places", "verification_status", "TEXT NOT NULL DEFAULT 'unverified'")
            self._ensure_column(conn, "real_places", "source_updated_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_place_visits", "accuracy_m", "REAL")
            self._ensure_column(conn, "real_place_visits", "confidence", "REAL NOT NULL DEFAULT 0.5")
            self._ensure_column(conn, "real_place_visits", "verification_status", "TEXT NOT NULL DEFAULT 'unverified'")
            self._ensure_column(conn, "real_place_visits", "provider_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "real_place_visits", "observed_at", "TEXT NOT NULL DEFAULT ''")
            conn.execute(
                "UPDATE real_places SET verification_status = CASE "
                "WHEN source IN ('browser_geolocation','location_watch','gps','journey_end','journey_gps') THEN 'observed' "
                "WHEN source IN ('conversation','assistant_inference') THEN 'unverified' "
                "ELSE 'confirmed' END, source_updated_at = COALESCE(NULLIF(source_updated_at, ''), updated_at) "
                "WHERE verification_status = 'unverified' AND source <> 'conversation'"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_real_places_provider ON real_places(provider_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_real_place_visits_key ON real_place_visits(place_key, visited_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_real_place_photos_key ON real_place_photos(place_key, id DESC)")
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
            self._retire_legacy_virtual_world(conn)
            conn.commit()
        finally:
            conn.close()

    # ── 通用工具 ────────────────────────────────────

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
            "real_places": [
                self.get_real_place(place["place_key"])
                for place in self.list_real_places(limit=1000)
            ],
            "memory_pulls": self.list_memory_pulls(limit=10000),
            "commemorations": self.list_commemorations(),
            "currency_ledger": self.list_currency_ledger(limit=2000),
            "earning_opportunities": self.list_earning_opportunities(limit=500),
            "earning_sources": self.list_earning_sources(),
            "earning_preferences": self.get_earning_preferences(),
            "earning_offers": self.list_earning_offers(),
            "earning_action_drafts": self.list_earning_actions(limit=2000),
            "earning_plans": self.list_earning_plans(),
            "earning_plan_steps": self.list_earning_plan_steps(),
            "income_records": self.list_income_records(limit=2000),
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
                if "real_places" in data:
                    conn.execute("DELETE FROM real_place_photos")
                    conn.execute("DELETE FROM real_place_visits")
                    conn.execute("DELETE FROM real_places")
                    for place in data.get("real_places", []):
                        place_key = str(place.get("place_key") or "").strip()
                        name = str(place.get("name") or "").strip()
                        if not place_key or not name:
                            continue
                        tags = place.get("tags") if isinstance(place.get("tags"), list) else []
                        conn.execute(
                            "INSERT INTO real_places (id,place_key,name,subtitle,latitude,longitude,visit_count,first_visited_at,last_visited_at,source,confidence,verification_status,source_updated_at,accuracy_m,country,admin1,city,district,neighborhood,image_path,display_address,provider_id,category,tags,favorite,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                int(place["id"]) if place.get("id") else None, place_key, name, str(place.get("subtitle") or ""),
                                place.get("latitude"), place.get("longitude"), max(0, int(place.get("visit_count") or 0)),
                                str(place.get("first_visited_at") or ""), str(place.get("last_visited_at") or ""), str(place.get("source") or "manual"),
                                max(0.0, min(1.0, float(place.get("confidence") if place.get("confidence") is not None else 0.5))),
                                str(place.get("verification_status") or "unverified"), str(place.get("source_updated_at") or place.get("updated_at") or now),
                                place.get("accuracy_m"), str(place.get("country") or ""), str(place.get("admin1") or ""), str(place.get("city") or ""),
                                str(place.get("district") or ""), str(place.get("neighborhood") or ""), str(place.get("image_path") or ""),
                                str(place.get("display_address") or ""), str(place.get("provider_id") or ""), str(place.get("category") or "other"),
                                json.dumps(tags, ensure_ascii=False), 1 if place.get("favorite") else 0, str(place.get("notes") or ""),
                                str(place.get("created_at") or now), str(place.get("updated_at") or now),
                            ),
                        )
                        for visit in place.get("visits", []):
                            conn.execute(
                                "INSERT INTO real_place_visits (id,place_key,visited_at,latitude,longitude,accuracy_m,source,confidence,verification_status,provider_id,observed_at,note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (
                                    int(visit["id"]) if visit.get("id") else None, place_key, str(visit.get("visited_at") or now),
                                    visit.get("latitude"), visit.get("longitude"), visit.get("accuracy_m"), str(visit.get("source") or "manual"),
                                    max(0.0, min(1.0, float(visit.get("confidence") if visit.get("confidence") is not None else 0.5))),
                                    str(visit.get("verification_status") or "unverified"), str(visit.get("provider_id") or ""),
                                    str(visit.get("observed_at") or visit.get("visited_at") or ""), str(visit.get("note") or ""), str(visit.get("created_at") or now),
                                ),
                            )
                        for photo in place.get("photos", []):
                            if not photo.get("image_path"):
                                continue
                            conn.execute(
                                "INSERT INTO real_place_photos (id,place_key,image_path,caption,created_at) VALUES (?,?,?,?,?)",
                                (int(photo["id"]) if photo.get("id") else None, place_key, str(photo["image_path"]), str(photo.get("caption") or ""), str(photo.get("created_at") or now)),
                            )
                # v18: 重建收益情报、计划和收入记录 (兼容旧镜像)
                if "earning_opportunities" in data:
                    conn.execute("DELETE FROM earning_opportunities")
                    for item in data.get("earning_opportunities", []):
                        conn.execute(
                            "INSERT INTO earning_opportunities (id, title, source, url, kind, description, income_min, income_max, hours, risk, confidence, verification_status, deadline, requirements, scam_flags, last_checked_at, status, quest_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                int(item.get("id", 0)) if item.get("id") else None,
                                str(item.get("title", "")), str(item.get("source", "")), str(item.get("url", "")),
                                str(item.get("kind", "other")), str(item.get("description", "")),
                                float(item.get("income_min", 0) or 0), float(item.get("income_max", 0) or 0),
                                float(item.get("hours", 0) or 0), str(item.get("risk", "unknown")),
                                str(item.get("confidence", "unknown")), str(item.get("verification_status", "unverified")),
                                str(item.get("deadline", "")), str(item.get("requirements", "")),
                                json.dumps(item.get("scam_flags", []), ensure_ascii=False), str(item.get("last_checked_at", "")),
                                str(item.get("status", "inbox")), int(item["quest_id"]) if item.get("quest_id") else None,
                                str(item.get("created_at", now)), str(item.get("updated_at", now)),
                            ),
                        )
                if "earning_sources" in data:
                    conn.execute("DELETE FROM earning_sources")
                    for source in data.get("earning_sources", []):
                        conn.execute("INSERT INTO earning_sources (id, name, url, kind, enabled, last_synced_at, last_error, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (int(source.get("id", 0)) if source.get("id") else None, str(source.get("name", "")), str(source.get("url", "")), str(source.get("kind", "rss")), 1 if source.get("enabled", 1) else 0, str(source.get("last_synced_at", "")), str(source.get("last_error", "")), str(source.get("created_at", now)), str(source.get("updated_at", now))))
                if isinstance(data.get("earning_preferences"), dict):
                    prefs = data["earning_preferences"]
                    conn.execute(
                        "UPDATE earning_preferences SET skills = ?, preferred_kinds = ?, weekly_hours = ?, target_amount = ?, min_hourly_rate = ?, risk_tolerance = ?, accepted_models = ?, sellable_assets = ?, constraints = ?, primary_route = ?, updated_at = ? WHERE id = 1",
                        (
                            json.dumps(prefs.get("skills", []), ensure_ascii=False),
                            json.dumps(prefs.get("preferred_kinds", []), ensure_ascii=False),
                            float(prefs.get("weekly_hours", 5) or 0), float(prefs.get("target_amount", 500) or 0),
                            float(prefs.get("min_hourly_rate", 0) or 0), str(prefs.get("risk_tolerance", "low")),
                            json.dumps(prefs.get("accepted_models", []), ensure_ascii=False),
                            json.dumps(prefs.get("sellable_assets", []), ensure_ascii=False),
                            str(prefs.get("constraints", "")), str(prefs.get("primary_route", "")),
                            str(prefs.get("updated_at", now)),
                        ),
                    )
                if "earning_plans" in data:
                    conn.execute("DELETE FROM earning_plans")
                    for plan in data.get("earning_plans", []):
                        conn.execute(
                            "INSERT INTO earning_plans (id, title, goal_amount, target_date, status, notes, route_key, is_sprint, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (int(plan.get("id", 0)) if plan.get("id") else None, str(plan.get("title", "")), float(plan.get("goal_amount", 0) or 0), str(plan.get("target_date", "")), str(plan.get("status", "active")), str(plan.get("notes", "")), str(plan.get("route_key", "")), 1 if plan.get("is_sprint") else 0, str(plan.get("created_at", now)), str(plan.get("updated_at", now))),
                        )
                if "earning_plan_steps" in data:
                    conn.execute("DELETE FROM earning_plan_steps")
                    for step in data.get("earning_plan_steps", []):
                        conn.execute("INSERT INTO earning_plan_steps (id, plan_id, title, description, position, status, quest_id, completed_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (int(step.get("id", 0)) if step.get("id") else None, int(step.get("plan_id", 0)), str(step.get("title", "")), str(step.get("description", "")), int(step.get("position", 0) or 0), str(step.get("status", "pending")), int(step["quest_id"]) if step.get("quest_id") else None, str(step.get("completed_at", "")), str(step.get("created_at", now)), str(step.get("updated_at", now))))
                if "income_records" in data:
                    conn.execute("DELETE FROM income_records")
                    for record in data.get("income_records", []):
                        conn.execute("INSERT INTO income_records (id, opportunity_id, amount, cost, hours, note, recorded_at) VALUES (?,?,?,?,?,?,?)", (int(record.get("id", 0)) if record.get("id") else None, int(record["opportunity_id"]) if record.get("opportunity_id") else None, float(record.get("amount", 0) or 0), float(record.get("cost", 0) or 0), float(record.get("hours", 0) or 0), str(record.get("note", "")), str(record.get("recorded_at", now))))
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
            "map_facts": self.get_map_fact_context(place_limit=20, journey_limit=10),
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
            "map": analysis["map_facts"]["counts"],
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
                # 收益计划/情报委托与任务板保持同一状态源，避免完成委托后收益面板仍停在进行中。
                quest_fields = quest.get("fields") or {}
                earning_step_id = quest_fields.get("earning_plan_step_id")
                if earning_step_id:
                    conn.execute(
                        "UPDATE earning_plan_steps SET status = 'done', completed_at = ?, updated_at = ? WHERE id = ?",
                        (now, now, int(earning_step_id)),
                    )
                    plan_id = quest_fields.get("earning_plan_id")
                    if plan_id:
                        remaining = conn.execute(
                            "SELECT COUNT(*) c FROM earning_plan_steps WHERE plan_id = ? AND status NOT IN ('done', 'skipped')",
                            (int(plan_id),),
                        ).fetchone()["c"]
                        conn.execute(
                            "UPDATE earning_plans SET status = ?, updated_at = ? WHERE id = ?",
                            ("completed" if remaining == 0 else "active", now, int(plan_id)),
                        )
                earning_opportunity_id = quest_fields.get("earning_opportunity_id")
                if earning_opportunity_id:
                    conn.execute(
                        "UPDATE earning_opportunities SET status = CASE WHEN status = 'won' THEN status ELSE 'applied' END, updated_at = ? WHERE id = ?",
                        (now, int(earning_opportunity_id)),
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

    # ── 现实地图事实 ────────────────────────────────

    def list_real_places(self, limit: int = 200) -> List[Dict[str, Any]]:
        """获取现实地图地点，按最近到访时间倒序。"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM real_places ORDER BY CASE WHEN last_visited_at = '' THEN 1 ELSE 0 END, last_visited_at DESC, id DESC LIMIT ?",
                (max(1, min(1000, int(limit))),),
            ).fetchall()
            return [self._decode_real_place(row) for row in rows]
        finally:
            conn.close()

    def list_real_journeys(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return GPS-backed journey records without treating their narrative as fact."""
        journeys: List[Dict[str, Any]] = []
        for story in self.list_story(limit=max(1, min(500, int(limit) * 4))):
            fields = story.get("fields") or {}
            track = fields.get("track")
            if not fields.get("journey") or not isinstance(track, list) or not track:
                continue
            source = str(fields.get("source") or "").strip().lower()
            if source not in {
                "browser_geolocation", "device_location", "location_watch",
                "gps", "gpx_import", "journey_gps",
            }:
                continue
            valid_track = [
                point for point in track
                if isinstance(point, dict)
                and self._to_float(point.get("latitude")) is not None
                and self._to_float(point.get("longitude")) is not None
            ]
            journeys.append({
                "id": story.get("id"),
                "title": story.get("title", ""),
                "happened_at": story.get("happened_at", ""),
                "narrative": story.get("content", ""),
                "source": source,
                "verification_status": "observed",
                "recorded_at": str(fields.get("recorded_at") or story.get("created_at") or ""),
                "duration_seconds": max(0, int(fields.get("duration_seconds") or 0)),
                "distance_m": max(0.0, float(fields.get("distance_m") or 0)),
                "point_count": max(0, int(fields.get("point_count") or len(valid_track))),
                "track": valid_track,
            })
            if len(journeys) >= limit:
                break
        return journeys

    def get_map_fact_context(self, place_limit: int = 20, journey_limit: int = 10) -> Dict[str, Any]:
        """Build the provenance-aware reality map read model used by Miya and the UI."""
        places = self.list_real_places(limit=max(1, min(100, int(place_limit))))
        journeys = self.list_real_journeys(limit=max(1, min(50, int(journey_limit))))
        weather = self.get_real_context(auto_refresh=False)
        verification_counts = {"observed": 0, "confirmed": 0, "unverified": 0}
        for place in places:
            status = str(place.get("verification_status") or "unverified")
            verification_counts[status if status in verification_counts else "unverified"] += 1
        return {
            "generated_at": datetime.now().astimezone().isoformat(),
            "truth_policy": {
                "observed": "device or provider observation",
                "confirmed": "explicitly confirmed by the player",
                "unverified": "conversation-derived candidate; do not state as fact",
            },
            "weather": {
                "source": weather.get("source", "unavailable"),
                "source_status": weather.get("source_status", "unavailable"),
                "captured_at": weather.get("captured_at", ""),
                "is_stale": bool(weather.get("is_stale", 1)),
                "city": weather.get("city", ""),
                "weather": weather.get("weather", "未同步"),
                "temperature": weather.get("temperature"),
            },
            "places": places,
            "journeys": journeys,
            "counts": {"places": len(places), "journeys": len(journeys), **verification_counts},
        }

    @staticmethod
    def _decode_real_place(row: sqlite3.Row) -> Dict[str, Any]:
        place = dict(row)
        try:
            place["tags"] = json.loads(place.get("tags") or "[]")
        except (TypeError, json.JSONDecodeError):
            place["tags"] = []
        place["favorite"] = bool(place.get("favorite"))
        return place

    def get_real_place(self, place_key: str) -> Optional[Dict[str, Any]]:
        """读取地点完整档案，包括逐次到访与多张照片。"""
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM real_places WHERE place_key=?", (str(place_key or ""),)).fetchone()
            if not row:
                return None
            place = self._decode_real_place(row)
            place["visits"] = [dict(item) for item in conn.execute(
                "SELECT * FROM real_place_visits WHERE place_key=? ORDER BY visited_at DESC, id DESC",
                (place_key,),
            ).fetchall()]
            place["photos"] = [dict(item) for item in conn.execute(
                "SELECT * FROM real_place_photos WHERE place_key=? ORDER BY id DESC",
                (place_key,),
            ).fetchall()]
            # 兼容升级前只有封面图、没有相册记录的地点。
            if place.get("image_path") and not any(photo["image_path"] == place["image_path"] for photo in place["photos"]):
                place["photos"].append({"id": 0, "place_key": place_key, "image_path": place["image_path"], "caption": "", "created_at": place.get("updated_at", "")})
            return place
        finally:
            conn.close()

    def update_real_place_image(self, place_key: str, image_path: str) -> Optional[Dict[str, Any]]:
        """向地点相册追加照片；首张/最新照片同时作为旧版封面字段。"""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                exists = conn.execute("SELECT 1 FROM real_places WHERE place_key=?", (str(place_key or ""),)).fetchone()
                if not exists:
                    return None
                conn.execute(
                    "INSERT INTO real_place_photos (place_key,image_path,caption,created_at) VALUES (?,?,?,?)",
                    (str(place_key), str(image_path or ""), "", now),
                )
                conn.execute("UPDATE real_places SET image_path=?, updated_at=? WHERE place_key=?", (str(image_path or ""), now, str(place_key)))
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_real_place(place_key)

    def update_real_place(self, place_key: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """编辑地点档案，不把编辑误记成一次新的到访。"""
        allowed = {"name", "subtitle", "notes", "category", "favorite", "latitude", "longitude", "accuracy_m", "display_address", "country", "admin1", "city", "district", "neighborhood", "verification_status"}
        updates: Dict[str, Any] = {}
        for key in allowed:
            if key in values:
                updates[key] = values[key]
        if "tags" in values:
            raw_tags = values.get("tags")
            if isinstance(raw_tags, str):
                raw_tags = [part.strip() for part in raw_tags.split(",")]
            tags = list(dict.fromkeys(str(tag).strip() for tag in (raw_tags or []) if str(tag).strip()))[:20]
            updates["tags"] = json.dumps(tags, ensure_ascii=False)
        if "favorite" in updates:
            updates["favorite"] = 1 if bool(updates["favorite"]) else 0
        if "name" in updates:
            updates["name"] = str(updates["name"] or "").strip()
            if not updates["name"]:
                raise ValueError("地点名称不能为空")
        if "verification_status" in updates:
            status = str(updates["verification_status"] or "").strip().lower()
            if status not in {"unverified", "confirmed", "observed"}:
                raise ValueError("verification_status 必须是 unverified、confirmed 或 observed")
            updates["verification_status"] = status
            updates["source_updated_at"] = datetime.now().isoformat()
        for coord, low, high in (("latitude", -90, 90), ("longitude", -180, 180)):
            if coord in updates:
                try:
                    updates[coord] = float(updates[coord]) if updates[coord] not in (None, "") else None
                except (TypeError, ValueError):
                    raise ValueError(f"{coord} 不是有效数字")
                if updates[coord] is not None and not low <= updates[coord] <= high:
                    raise ValueError(f"{coord} 超出有效范围")
        if not updates:
            return self.get_real_place(place_key)
        updates["updated_at"] = datetime.now().isoformat()
        columns = ", ".join(f"{key}=?" for key in updates)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"UPDATE real_places SET {columns} WHERE place_key=?", (*updates.values(), str(place_key or "")))
                if conn.total_changes == 0:
                    return None
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_real_place(place_key)

    def delete_real_place(self, place_key: str) -> bool:
        """删除地点及其结构化档案；已上传原图保留，避免不可恢复的文件误删。"""
        with self._lock:
            conn = self._connect()
            try:
                exists = conn.execute("SELECT 1 FROM real_places WHERE place_key=?", (str(place_key or ""),)).fetchone()
                if not exists:
                    return False
                conn.execute("DELETE FROM real_place_visits WHERE place_key=?", (place_key,))
                conn.execute("DELETE FROM real_place_photos WHERE place_key=?", (place_key,))
                conn.execute("DELETE FROM real_places WHERE place_key=?", (place_key,))
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return True

    def record_real_place_visit(
        self,
        name: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        note: str = "",
        visited_at: str = "",
        source: str = "manual",
        confidence: Optional[float] = None,
        accuracy_m: Optional[float] = None,
        place_key: str = "",
        provider_id: str = "",
        display_address: str = "",
        category: str = "",
        verification_status: str = "",
        observed_at: str = "",
    ) -> Optional[Dict[str, Any]]:
        """记录一次现实地点到访；优先按档案/provider/近邻合并，同名远距离地点可并存。"""
        name = str(name or "").strip()
        if not name:
            return None
        try:
            lat = float(latitude) if latitude not in (None, "") else None
            lng = float(longitude) if longitude not in (None, "") else None
        except (TypeError, ValueError):
            lat = lng = None
        if lat is not None and not -90 <= lat <= 90:
            lat = None
        if lng is not None and not -180 <= lng <= 180:
            lng = None
        source = str(source or "manual").strip().lower()[:80] or "manual"
        geocoded = None
        if lat is None or lng is None:
            geocoded = self._geocode_real_place(name)
            if geocoded:
                lat = geocoded["latitude"]
                lng = geocoded["longitude"]
        elif not display_address:
            geocoded = self.reverse_geocode_real_place(lat, lng)
        address = geocoded.get("address", {}) if geocoded else {}
        provider_id = str(provider_id or (geocoded or {}).get("provider_id") or "").strip()
        display_address = str(display_address or (geocoded or {}).get("display_name") or "").strip()
        provided_category = str(category or "").strip()[:80]
        category = str(provided_category or (geocoded or {}).get("category") or "other").strip()[:80]
        if geocoded:
            source = f"{source}_geocoded" if not source.endswith("_geocoded") else source
        now = datetime.now().isoformat()
        visited = str(visited_at or "").strip() or now
        observed_at = str(observed_at or visited).strip()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        base_key = slug or f"place-{name.encode('utf-8').hex()}"
        inferred_status = (
            "observed" if source in {"browser_geolocation", "location_watch", "gps", "journey_end", "journey_gps"}
            else "unverified" if source.startswith("conversation") or source == "assistant_inference"
            else "confirmed"
        )
        verification_status = str(verification_status or inferred_status).strip().lower()
        if verification_status not in {"unverified", "confirmed", "observed"}:
            verification_status = inferred_status
        default_confidence = {"unverified": 0.5, "confirmed": 0.9, "observed": 0.98}[verification_status]
        confidence = max(0.0, min(1.0, float(default_confidence if confidence is None else confidence)))
        try:
            accuracy_m = max(0.0, float(accuracy_m)) if accuracy_m not in (None, "") else None
        except (TypeError, ValueError):
            accuracy_m = None
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute("SELECT * FROM real_places WHERE place_key=?", (place_key,)).fetchone() if place_key else None
                if not existing and provider_id:
                    existing = conn.execute("SELECT * FROM real_places WHERE provider_id=? ORDER BY id LIMIT 1", (provider_id,)).fetchone()
                if not existing and lat is not None and lng is not None:
                    candidates = conn.execute("SELECT * FROM real_places WHERE lower(name)=lower(?) AND latitude IS NOT NULL AND longitude IS NOT NULL", (name,)).fetchall()
                    existing = next((row for row in candidates if self._geo_distance_m(lat, lng, float(row["latitude"]), float(row["longitude"])) <= max(100.0, accuracy_m or 0.0)), None)
                if not existing and lat is None and lng is None:
                    existing = conn.execute("SELECT * FROM real_places WHERE lower(name)=lower(?) ORDER BY id LIMIT 1", (name,)).fetchone()
                if existing:
                    place_key = str(existing["place_key"])
                elif provider_id:
                    safe_provider = re.sub(r"[^a-zA-Z0-9_-]+", "-", provider_id).strip("-")
                    place_key = f"osm-{safe_provider}"[:180]
                elif lat is not None and lng is not None:
                    digest = hashlib.sha1(f"{lat:.5f},{lng:.5f}".encode("ascii")).hexdigest()[:10]
                    place_key = f"{base_key}-{digest}"[:180]
                else:
                    place_key = base_key[:180]
                if existing:
                    status_rank = {"unverified": 0, "confirmed": 1, "observed": 2}
                    old_status = str(existing.get("verification_status") or "unverified")
                    keep_new_evidence = status_rank.get(verification_status, 0) >= status_rank.get(old_status, 0)
                    aggregate_source = source if keep_new_evidence else str(existing.get("source") or "manual")
                    aggregate_status = verification_status if keep_new_evidence else old_status
                    aggregate_confidence = confidence if keep_new_evidence else float(existing.get("confidence") or 0.5)
                    conn.execute(
                        "UPDATE real_places SET latitude=COALESCE(?, latitude), longitude=COALESCE(?, longitude), accuracy_m=COALESCE(?, accuracy_m), display_address=COALESCE(NULLIF(?, ''), display_address), provider_id=COALESCE(NULLIF(?, ''), provider_id), category=COALESCE(NULLIF(?, ''), category), country=COALESCE(NULLIF(?, ''), country), admin1=COALESCE(NULLIF(?, ''), admin1), city=COALESCE(NULLIF(?, ''), city), district=COALESCE(NULLIF(?, ''), district), neighborhood=COALESCE(NULLIF(?, ''), neighborhood), source=?, confidence=?, verification_status=?, source_updated_at=?, visit_count=visit_count+1, first_visited_at=CASE WHEN first_visited_at='' OR ? < first_visited_at THEN ? ELSE first_visited_at END, last_visited_at=CASE WHEN last_visited_at='' OR ? > last_visited_at THEN ? ELSE last_visited_at END, notes=CASE WHEN ? <> '' THEN ? ELSE notes END, updated_at=? WHERE place_key=?",
                        (lat, lng, accuracy_m, display_address, provider_id, provided_category, address.get("country", ""), address.get("state", address.get("province", "")), address.get("city", address.get("town", address.get("municipality", ""))), address.get("county", address.get("city_district", "")), address.get("suburb", address.get("neighbourhood", "")), aggregate_source, aggregate_confidence, aggregate_status, now, visited, visited, visited, visited, note, note, now, place_key),
                    )
                else:
                    conn.execute(
                        "INSERT INTO real_places (place_key,name,latitude,longitude,visit_count,first_visited_at,last_visited_at,source,confidence,verification_status,source_updated_at,accuracy_m,display_address,provider_id,category,country,admin1,city,district,neighborhood,notes,created_at,updated_at) VALUES (?,?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (place_key, name, lat, lng, visited, visited, source, confidence, verification_status, now, accuracy_m, display_address, provider_id, category, address.get("country", ""), address.get("state", address.get("province", "")), address.get("city", address.get("town", address.get("municipality", ""))), address.get("county", address.get("city_district", "")), address.get("suburb", address.get("neighbourhood", "")), note, now, now),
                    )
                conn.execute(
                    "INSERT INTO real_place_visits (place_key,visited_at,latitude,longitude,accuracy_m,source,confidence,verification_status,provider_id,observed_at,note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (place_key, visited, lat, lng, accuracy_m, source, confidence, verification_status, provider_id, observed_at, note, now),
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_real_place(place_key)

    @staticmethod
    def _geocode_real_place(name: str) -> Optional[Dict[str, Any]]:
        """用开放地理编码解析地点名称；失败时保持离线可用。"""
        results = EarthOnlineStore.search_real_places(name, limit=1)
        return results[0] if results else None

    @staticmethod
    def search_real_places(query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """通过 Nominatim 搜索真实 POI，返回可供用户选择的候选项。"""
        try:
            query = urlencode({"q": str(query_text or "").strip(), "format": "jsonv2", "limit": max(1, min(10, int(limit))), "accept-language": "zh-CN", "addressdetails": 1})
            request = urllib.request.Request(
                f"https://nominatim.openstreetmap.org/search?{query}",
                headers={"User-Agent": "MiyaEarthOnline/1.0 (personal map)"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return [EarthOnlineStore._normalize_geocode_result(item) for item in payload]
        except Exception as exc:
            logger.debug("现实地点地理编码失败: %s", exc)
            return []

    @staticmethod
    def search_nearby_real_places(
        latitude: float,
        longitude: float,
        radius_m: int = 1500,
        limit: int = 40,
    ) -> List[Dict[str, Any]]:
        """通过 Overpass 查询坐标附近的命名 POI，不保存玩家坐标或查询结果。"""
        lat = float(latitude)
        lng = float(longitude)
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError("地图坐标超出有效范围")
        radius = max(100, min(5000, int(radius_m)))
        result_limit = max(1, min(80, int(limit)))
        selectors = (
            'nwr(around:{radius},{lat:.7f},{lng:.7f})["name"]["amenity"];'
            'nwr(around:{radius},{lat:.7f},{lng:.7f})["name"]["shop"];'
            'nwr(around:{radius},{lat:.7f},{lng:.7f})["name"]["tourism"];'
            'nwr(around:{radius},{lat:.7f},{lng:.7f})["name"]["leisure"];'
            'nwr(around:{radius},{lat:.7f},{lng:.7f})["name"]["public_transport"];'
            'nwr(around:{radius},{lat:.7f},{lng:.7f})["name"]["railway"~"station|halt"];'
        ).format(radius=radius, lat=lat, lng=lng)
        query = f"[out:json][timeout:12];({selectors});out center {result_limit};"
        try:
            body = urlencode({"data": query}).encode("utf-8")
            request = urllib.request.Request(
                "https://overpass-api.de/api/interpreter",
                data=body,
                headers={
                    "User-Agent": "MiyaEarthOnline/1.0 (personal map)",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = []
            seen = set()
            for item in payload.get("elements") or []:
                normalized = EarthOnlineStore._normalize_nearby_result(item, lat, lng)
                if not normalized or normalized["provider_id"] in seen:
                    continue
                seen.add(normalized["provider_id"])
                results.append(normalized)
            results.sort(key=lambda place: (place["distance_m"], -place.get("importance", 0)))
            return results[:result_limit]
        except Exception as exc:
            logger.debug("附近现实地点查询失败: %s", exc)
            return []

    @staticmethod
    def _normalize_nearby_result(item: Dict[str, Any], origin_latitude: float, origin_longitude: float) -> Optional[Dict[str, Any]]:
        """把 Overpass node/way/relation 统一成地图候选地点。"""
        tags = item.get("tags") or {}
        center = item.get("center") or {}
        raw_lat = item.get("lat", center.get("lat"))
        raw_lng = item.get("lon", center.get("lon"))
        name = str(tags.get("name:zh") or tags.get("name") or "").strip()
        if not name or raw_lat is None or raw_lng is None:
            return None
        lat = float(raw_lat)
        lng = float(raw_lng)
        category_key = next((key for key in ("amenity", "shop", "tourism", "leisure", "public_transport", "railway") if tags.get(key)), "other")
        category_value = str(tags.get(category_key) or "other")
        address_parts = [
            tags.get("addr:province"), tags.get("addr:city"), tags.get("addr:district"),
            tags.get("addr:street"), tags.get("addr:housenumber"),
        ]
        display_name = " ".join(str(part).strip() for part in address_parts if str(part or "").strip())
        if not display_name:
            display_name = f"{name} · {category_value}"
        element_type = str(item.get("type") or "osm")
        element_id = str(item.get("id") or "")
        return {
            "name": name,
            "display_name": display_name,
            "latitude": lat,
            "longitude": lng,
            "address": {key[5:]: value for key, value in tags.items() if key.startswith("addr:")},
            "provider_id": f"{element_type}-{element_id}" if element_id else "",
            "category": category_value,
            "category_group": category_key,
            "type": category_value,
            "importance": 0.0,
            "distance_m": round(EarthOnlineStore._geo_distance_m(origin_latitude, origin_longitude, lat, lng)),
            "source": "openstreetmap_overpass",
            "fetched_at": datetime.now().isoformat(),
            "website": str(tags.get("website") or tags.get("contact:website") or ""),
            "phone": str(tags.get("phone") or tags.get("contact:phone") or ""),
            "opening_hours": str(tags.get("opening_hours") or ""),
        }

    @staticmethod
    def reverse_geocode_real_place(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """把地图点选/GPS 坐标反查为可读地址。"""
        try:
            query = urlencode({"lat": f"{float(latitude):.7f}", "lon": f"{float(longitude):.7f}", "format": "jsonv2", "accept-language": "zh-CN", "addressdetails": 1, "zoom": 18})
            request = urllib.request.Request(
                f"https://nominatim.openstreetmap.org/reverse?{query}",
                headers={"User-Agent": "MiyaEarthOnline/1.0 (personal map)"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return EarthOnlineStore._normalize_geocode_result(payload) if payload and not payload.get("error") else None
        except Exception as exc:
            logger.debug("现实坐标反向地理编码失败: %s", exc)
            return None

    @staticmethod
    def _normalize_geocode_result(item: Dict[str, Any]) -> Dict[str, Any]:
        address = item.get("address") or {}
        name = str(item.get("name") or address.get("amenity") or address.get("tourism") or address.get("building") or item.get("display_name") or "所选地点").split(",")[0]
        osm_type = str(item.get("osm_type") or "osm")
        osm_id = str(item.get("osm_id") or "")
        return {
            "name": name,
            "display_name": str(item.get("display_name") or ""),
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "address": address,
            "provider_id": f"{osm_type}-{osm_id}" if osm_id else "",
            "category": str(item.get("category") or item.get("type") or "other"),
            "type": str(item.get("type") or ""),
            "importance": float(item.get("importance") or 0),
            "source": "openstreetmap_nominatim",
            "fetched_at": datetime.now().isoformat(),
        }

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

    # ── 现实活动: 纪念日与玩家创建的活动 ───────────

    def list_world_event_areas(self) -> List[Dict[str, Any]]:
        """Return only persisted real-life activities; no fictional built-ins are injected."""
        areas: List[Dict[str, Any]] = []
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
        for item in custom_items:
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
            recorded_places = len(self.list_real_places(limit=1000))
            if recorded_places < int(item["requires_discoveries"]):
                return {"success": False, "message": f"还需要记录 {item['requires_discoveries']} 个现实地点"}
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

    def query_weather(
        self,
        location: str,
        include_forecast: bool = True,
        forecast_days: int = 3,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """查询任意地点天气；不修改默认城市，也不写入世界快照或地点档案。"""
        from core.weather_service import query_weather

        return query_weather(
            location,
            include_forecast=include_forecast,
            forecast_days=forecast_days,
            force_refresh=force_refresh,
        )

    def refresh_real_context(self, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """刷新已保存天气地点的世界快照；临时地点查询不会修改或污染世界状态。"""
        values = values or {}
        settings = self.get_real_context_settings()
        now = datetime.now().astimezone()
        captured_at = now.isoformat()
        saved_city = str(settings.get("city") or "").strip()
        requested_city = str(values.get("city") or "").strip()
        if requested_city and requested_city.casefold() != saved_city.casefold():
            return self.query_weather(
                requested_city,
                include_forecast=bool(values.get("include_forecast", True)),
                forecast_days=int(values.get("forecast_days") or 3),
                force_refresh=bool(values.get("force_refresh", False)),
            )
        city = saved_city
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
            weather = self.query_weather(city, include_forecast=False, force_refresh=True)
            if weather.get("source_status") != "ok":
                base["source_status"] = str(weather.get("source_status") or "unavailable")
                base["raw_payload"] = weather
                return self._save_real_context_snapshot(base)
            resolved = weather.get("resolved_location") or {}
            base.update({
                "captured_at": str(weather.get("captured_at") or captured_at),
                "source": "seniverse", "source_status": "ok", "city": str(weather.get("city") or city),
                "weather": str(weather.get("weather") or "未知"),
                "weather_icon": str(weather.get("weather_icon") or "?"),
                "temperature": weather.get("temperature"),
                "condition_code": str(weather.get("condition_code") or ""),
                "humidity": weather.get("humidity"), "wind": str(weather.get("wind") or ""),
                "timezone": str(resolved.get("timezone") or resolved.get("timezone_offset") or ""),
                "raw_payload": weather, "is_stale": 0,
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
            raw_payload = snapshot.get("raw_payload") if isinstance(snapshot.get("raw_payload"), dict) else {}
            snapshot_query = str(raw_payload.get("requested_location") or snapshot.get("city") or "").strip()
            if snapshot_query.casefold() != str(settings.get("city") or "").strip().casefold():
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
        """本周纪行: 积分来自真实游玩数据 (完成委托/签到/地点到访/剧情/抽卡)。"""
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
            place_visits = conn.execute(
                "SELECT COUNT(*) c FROM real_place_visits WHERE visited_at >= ?", (bounds["monday_iso"],)
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
            "place_visit": {"count": int(place_visits), "points_each": BATTLE_PASS_POINTS["place_visit"]},
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

    # ── v18: 现实收益情报与计划 (MVP) ─────────────────

    @staticmethod
    def _public_feed_url(value: Any) -> str:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("信息源必须是公开 http/https 地址")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            raise ValueError("不允许使用本机地址作为信息源")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("不允许使用内网或本机地址作为信息源")
        except ValueError as exc:
            if str(exc).startswith("不允许"):
                raise
        return str(value).strip()[:1000]

    @classmethod
    def _validate_public_feed_resolution(cls, value: Any) -> str:
        """Validate all current DNS answers; redirects are validated separately per hop."""
        url = cls._public_feed_url(value)
        parsed = urlparse(url)
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("信息源域名无法解析") from exc
        if not addresses:
            raise ValueError("信息源域名没有可用地址")
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("信息源域名解析到了内网、本机或保留地址")
        return url

    @classmethod
    def _fetch_public_feed(cls, value: Any) -> bytes:
        opener = urllib.request.build_opener(_NoFeedRedirect())
        current = str(value)
        for _ in range(4):
            current = cls._validate_public_feed_resolution(current)
            request = urllib.request.Request(
                current,
                headers={"User-Agent": "Miya-EarthOnline/1.0", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
            )
            try:
                response = opener.open(request, timeout=10)
            except urllib.error.HTTPError as exc:
                if exc.code not in {301, 302, 303, 307, 308}:
                    raise
                location = exc.headers.get("Location")
                if not location:
                    raise ValueError("信息源返回了无目标的重定向") from exc
                current = urljoin(current, location)
                continue
            with response:
                cls._validate_public_feed_resolution(response.geturl())
                payload = response.read(1024 * 1024 + 1)
            if len(payload) > 1024 * 1024:
                raise ValueError("信息源响应超过 1MB")
            return payload
        raise ValueError("信息源重定向次数过多")

    def list_earning_sources(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute("SELECT * FROM earning_sources ORDER BY enabled DESC, id DESC").fetchall()]
        finally:
            conn.close()

    def create_earning_source(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}
        name = str(data.get("name", "")).strip()[:120]
        url = self._public_feed_url(data.get("url"))
        if not name: name = urlparse(url).hostname or "公开信息源"
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT * FROM earning_sources WHERE url = ?", (url,)).fetchone()
                if row:
                    conn.execute("UPDATE earning_sources SET name = ?, kind = ?, enabled = ?, updated_at = ? WHERE id = ?", (name, str(data.get("kind", "rss"))[:30], 1 if data.get("enabled", True) else 0, now, int(row["id"])))
                    source_id = int(row["id"])
                else:
                    cur = conn.execute("INSERT INTO earning_sources (name, url, kind, enabled, created_at, updated_at) VALUES (?,?,?,?,?,?)", (name, url, str(data.get("kind", "rss"))[:30], 1 if data.get("enabled", True) else 0, now, now)); source_id = cur.lastrowid
                conn.commit()
            finally: conn.close()
        self._write_mirror()
        return self.get_earning_source(int(source_id)) or {}

    def get_earning_source(self, source_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_sources WHERE id = ?", (int(source_id),)).fetchone(); return dict(row) if row else None
        finally: conn.close()

    def update_earning_source(self, source_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        source = self.get_earning_source(source_id)
        if not source: return None
        data = data if isinstance(data, dict) else {}; updates = {}
        if "name" in data and str(data["name"] or "").strip(): updates["name"] = str(data["name"]).strip()[:120]
        if "url" in data: updates["url"] = self._public_feed_url(data["url"])
        if "enabled" in data: updates["enabled"] = 1 if data["enabled"] else 0
        if not updates: return source
        updates["updated_at"] = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"UPDATE earning_sources SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?", (*updates.values(), int(source_id))); conn.commit()
            finally: conn.close()
        self._write_mirror(); return self.get_earning_source(source_id)

    def delete_earning_source(self, source_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM earning_sources WHERE id = ?", (int(source_id),)); conn.commit(); deleted = cur.rowcount > 0
            finally: conn.close()
        if deleted: self._write_mirror()
        return deleted

    @staticmethod
    def _feed_text(value: str) -> str:
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()[:2000]

    def _parse_public_feed(self, payload: bytes) -> List[Dict[str, str]]:
        root = ET.fromstring(payload)
        entries = []
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1].lower() if isinstance(node.tag, str) else ""
            if tag not in {"item", "entry"}: continue
            values: Dict[str, str] = {}
            for child in list(node):
                child_tag = child.tag.rsplit("}", 1)[-1].lower() if isinstance(child.tag, str) else ""
                text = self._feed_text(child.text or "")
                if child_tag == "link" and child.attrib.get("href"): text = str(child.attrib["href"])
                values[child_tag] = text
            title, link = values.get("title", ""), values.get("link", "") or values.get("guid", "")
            if title and link: entries.append({"title": title, "url": link, "description": values.get("description", "") or values.get("summary", "")})
        return entries[:30]

    def sync_earning_sources(self, source_id: Optional[int] = None) -> Dict[str, Any]:
        sources = [self.get_earning_source(source_id)] if source_id else self.list_earning_sources()
        sources = [source for source in sources if source and source.get("enabled")]
        created, skipped, errors = [], 0, []
        for source in sources:
            try:
                payload = self._fetch_public_feed(source["url"])
                entries = self._parse_public_feed(payload); now = datetime.now().isoformat()
                with self._lock:
                    conn = self._connect()
                    try:
                        for entry in entries:
                            if conn.execute("SELECT id FROM earning_opportunities WHERE url = ?", (entry["url"],)).fetchone(): skipped += 1; continue
                            cur = conn.execute("INSERT INTO earning_opportunities (title, source, url, kind, description, risk, confidence, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (entry["title"], source["name"], entry["url"], "public_feed", entry["description"], "unknown", "medium", "inbox", now, now)); created.append({"id": cur.lastrowid, "title": entry["title"], "source": source["name"]})
                        conn.execute("UPDATE earning_sources SET last_synced_at = ?, last_error = '', updated_at = ? WHERE id = ?", (now, now, int(source["id"]))); conn.commit()
                    finally: conn.close()
            except Exception as exc:
                errors.append({"source": source.get("name", ""), "error": str(exc)[:300]})
                with self._lock:
                    conn = self._connect()
                    try: conn.execute("UPDATE earning_sources SET last_error = ?, updated_at = ? WHERE id = ?", (str(exc)[:500], datetime.now().isoformat(), int(source["id"]))); conn.commit()
                    finally: conn.close()
        if sources: self._write_mirror()
        return {"success": not errors, "created": created, "created_count": len(created), "skipped": skipped, "errors": errors}

    @staticmethod
    def _normalise_earning_status(value: Any, allowed: tuple[str, ...], default: str) -> str:
        value = str(value or default).strip().lower()
        return value if value in allowed else default

    def get_earning_preferences(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_preferences WHERE id = 1").fetchone()
            if not row:
                return {
                    "skills": [], "preferred_kinds": [], "weekly_hours": 5, "target_amount": 500,
                    "min_hourly_rate": 0, "risk_tolerance": "low", "accepted_models": [],
                    "sellable_assets": [], "constraints": "", "primary_route": "",
                }
            result = dict(row)
            for key in ("skills", "preferred_kinds", "accepted_models", "sellable_assets"):
                try: result[key] = json.loads(result.get(key) or "[]")
                except (TypeError, ValueError): result[key] = []
            return result
        finally: conn.close()

    def update_earning_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}; current = self.get_earning_preferences()
        def list_value(key: str) -> List[str]:
            raw = data.get(key, current.get(key, []))
            if isinstance(raw, str): raw = raw.split(",")
            if not isinstance(raw, list): raw = []
            return [str(value).strip()[:40] for value in raw if str(value).strip()][:30]
        def number(key: str, fallback: float) -> float:
            try: return max(0.0, float(data.get(key, fallback) or 0))
            except (TypeError, ValueError): return fallback
        tolerance = str(data.get("risk_tolerance", current.get("risk_tolerance", "low"))).lower()
        if tolerance not in {"low", "medium", "high"}: tolerance = "low"
        updated = {
            "skills": list_value("skills"),
            "preferred_kinds": list_value("preferred_kinds"),
            "accepted_models": list_value("accepted_models"),
            "sellable_assets": list_value("sellable_assets"),
            "weekly_hours": number("weekly_hours", 5),
            "target_amount": number("target_amount", 500),
            "min_hourly_rate": number("min_hourly_rate", 0),
            "risk_tolerance": tolerance,
            "constraints": str(data.get("constraints", current.get("constraints", "")) or "").strip()[:1000],
            "primary_route": str(data.get("primary_route", current.get("primary_route", "")) or "").strip()[:40],
        }
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE earning_preferences SET skills = ?, preferred_kinds = ?, weekly_hours = ?, target_amount = ?, min_hourly_rate = ?, risk_tolerance = ?, accepted_models = ?, sellable_assets = ?, constraints = ?, primary_route = ?, updated_at = ? WHERE id = 1",
                    (
                        json.dumps(updated["skills"], ensure_ascii=False), json.dumps(updated["preferred_kinds"], ensure_ascii=False),
                        updated["weekly_hours"], updated["target_amount"], updated["min_hourly_rate"], updated["risk_tolerance"],
                        json.dumps(updated["accepted_models"], ensure_ascii=False), json.dumps(updated["sellable_assets"], ensure_ascii=False),
                        updated["constraints"], updated["primary_route"], datetime.now().isoformat(),
                    ),
                )
                conn.commit()
            finally: conn.close()
        self._write_mirror(); return self.get_earning_preferences()

    # ── v18.2: 可售服务与外部动作审批 ────────────────

    def list_earning_offers(self, status: str = "") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM earning_offers WHERE status = ? ORDER BY updated_at DESC, id DESC",
                    (str(status),),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM earning_offers ORDER BY updated_at DESC, id DESC").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_earning_offer(self, offer_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_offers WHERE id = ?", (int(offer_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_earning_offer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}
        title = str(data.get("title", "")).strip()[:200]
        if not title:
            raise ValueError("可售服务标题不能为空")

        def number(key: str, default: float = 0.0) -> float:
            try:
                return max(0.0, float(data.get(key, default) or 0))
            except (TypeError, ValueError):
                return default

        now = datetime.now().isoformat()
        status = self._normalise_earning_status(data.get("status"), ("draft", "active", "paused", "retired"), "draft")
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO earning_offers (title, customer, problem, deliverables, scope, proof, price, cost_estimate, delivery_days, revisions, route_key, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        title, str(data.get("customer", ""))[:500], str(data.get("problem", ""))[:2000],
                        str(data.get("deliverables", ""))[:3000], str(data.get("scope", ""))[:3000],
                        str(data.get("proof", ""))[:3000], number("price"), number("cost_estimate"),
                        max(1, min(90, int(number("delivery_days", 2)))), max(0, min(20, int(number("revisions", 1)))),
                        str(data.get("route_key", "automation_tool"))[:40], status, now, now,
                    ),
                )
                offer_id = int(cur.lastrowid)
                self._log_activity(conn, "earning", "◆", f"建立可售服务: {title}", f"报价 ¥{number('price'):.2f}")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_offer(offer_id) or {}

    def update_earning_offer(self, offer_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.get_earning_offer(offer_id):
            return None
        data = data if isinstance(data, dict) else {}
        updates: Dict[str, Any] = {}
        text_limits = {"title": 200, "customer": 500, "problem": 2000, "deliverables": 3000, "scope": 3000, "proof": 3000, "route_key": 40}
        for key, limit in text_limits.items():
            if key in data:
                value = str(data[key] or "").strip()[:limit]
                if key != "title" or value:
                    updates[key] = value
        for key in ("price", "cost_estimate"):
            if key in data:
                try:
                    updates[key] = max(0.0, float(data[key] or 0))
                except (TypeError, ValueError):
                    pass
        for key, lower, upper in (("delivery_days", 1, 90), ("revisions", 0, 20)):
            if key in data:
                try:
                    updates[key] = max(lower, min(upper, int(data[key])))
                except (TypeError, ValueError):
                    pass
        if "status" in data:
            updates["status"] = self._normalise_earning_status(data["status"], ("draft", "active", "paused", "retired"), "draft")
        if not updates:
            return self.get_earning_offer(offer_id)
        with self._lock:
            conn = self._connect()
            try:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(
                    f"UPDATE earning_offers SET {assignments}, updated_at = ? WHERE id = ?",
                    (*updates.values(), datetime.now().isoformat(), int(offer_id)),
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_offer(offer_id)

    @staticmethod
    def _earning_action_hash(data: Dict[str, Any]) -> str:
        payload = {
            key: data.get(key)
            for key in ("opportunity_id", "offer_id", "action_type", "target", "title", "content", "attachments", "amount", "risk")
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _expire_earning_actions(self) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE earning_action_drafts SET status = 'expired', updated_at = ? WHERE status = 'approved' AND expires_at != '' AND expires_at <= ?",
                    (now, now),
                )
                conn.commit()
            finally:
                conn.close()

    def list_earning_actions(self, status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        self._expire_earning_actions()
        conn = self._connect()
        try:
            bounded = max(1, min(500, int(limit)))
            if status:
                rows = conn.execute(
                    "SELECT * FROM earning_action_drafts WHERE status = ? ORDER BY updated_at DESC, id DESC LIMIT ?",
                    (str(status), bounded),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM earning_action_drafts ORDER BY updated_at DESC, id DESC LIMIT ?", (bounded,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_earning_action(self, action_id: int) -> Optional[Dict[str, Any]]:
        self._expire_earning_actions()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_action_drafts WHERE id = ?", (int(action_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_earning_action(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}
        action_type = str(data.get("action_type", "proposal")).strip().lower()
        allowed = {"proposal", "publish", "contact", "upload", "accept_order"}
        if action_type not in allowed:
            raise ValueError("仅允许准备提案、发布、联系、上传或接单草稿；付款、转账、提现和退款不受支持")
        title = str(data.get("title", "")).strip()[:200]
        content = str(data.get("content", "")).strip()[:12000]
        if not title or not content:
            raise ValueError("外部动作草稿必须包含标题和完整内容")
        opportunity_id = int(data["opportunity_id"]) if data.get("opportunity_id") else None
        offer_id = int(data["offer_id"]) if data.get("offer_id") else None
        if opportunity_id and not self.get_earning_opportunity(opportunity_id):
            raise ValueError("关联的收益机会不存在")
        if offer_id and not self.get_earning_offer(offer_id):
            raise ValueError("关联的可售服务不存在")
        attachments = data.get("attachments", [])
        if not isinstance(attachments, list):
            attachments = []
        attachments = [str(value).strip()[:500] for value in attachments if str(value).strip()][:20]
        try:
            amount = max(0.0, float(data.get("amount", 0) or 0))
        except (TypeError, ValueError):
            amount = 0.0
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO earning_action_drafts (opportunity_id, offer_id, action_type, target, title, content, attachments, amount, risk, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,'draft',?,?)",
                    (
                        opportunity_id, offer_id, action_type, str(data.get("target", ""))[:1000], title, content,
                        json.dumps(attachments, ensure_ascii=False), amount,
                        self._normalise_earning_status(data.get("risk"), ("low", "medium", "high"), "medium"), now, now,
                    ),
                )
                action_id = int(cur.lastrowid)
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_action(action_id) or {}

    def update_earning_action(self, action_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action = self.get_earning_action(action_id)
        if not action:
            return None
        data = data if isinstance(data, dict) else {}
        updates: Dict[str, Any] = {}
        for key, limit in (("target", 1000), ("title", 200), ("content", 12000)):
            if key in data:
                value = str(data[key] or "").strip()[:limit]
                if key not in {"title", "content"} or value:
                    updates[key] = value
        if "attachments" in data:
            raw = data["attachments"] if isinstance(data["attachments"], list) else []
            updates["attachments"] = json.dumps([str(value).strip()[:500] for value in raw if str(value).strip()][:20], ensure_ascii=False)
        if "amount" in data:
            try:
                updates["amount"] = max(0.0, float(data["amount"] or 0))
            except (TypeError, ValueError):
                pass
        if "risk" in data:
            updates["risk"] = self._normalise_earning_status(data["risk"], ("low", "medium", "high"), "medium")
        if not updates:
            return action
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(
                    f"UPDATE earning_action_drafts SET {assignments}, status = 'draft', content_hash = '', approved_hash = '', submitted_at = '', approved_at = '', expires_at = '', revoked_at = '', updated_at = ? WHERE id = ?",
                    (*updates.values(), now, int(action_id)),
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_action(action_id)

    def submit_earning_action(self, action_id: int) -> Dict[str, Any]:
        action = self.get_earning_action(action_id)
        if not action:
            raise ValueError("外部动作草稿不存在")
        if action.get("status") not in {"draft", "revoked", "expired"}:
            raise ValueError("只有草稿、已撤销或已过期动作可以重新提交")
        digest = self._earning_action_hash(action)
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE earning_action_drafts SET status = 'pending', content_hash = ?, approved_hash = '', submitted_at = ?, approved_at = '', expires_at = '', revoked_at = '', updated_at = ? WHERE id = ?",
                    (digest, now, now, int(action_id)),
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_action(action_id) or {}

    def approve_earning_action(self, action_id: int, expected_hash: str) -> Dict[str, Any]:
        action = self.get_earning_action(action_id)
        if not action:
            raise ValueError("外部动作草稿不存在")
        if action.get("status") != "pending":
            raise ValueError("只有待确认动作可以批准")
        current_hash = self._earning_action_hash(action)
        stored_hash = str(action.get("content_hash") or "")
        if not expected_hash or not hmac.compare_digest(str(expected_hash), stored_hash):
            raise ValueError("草稿内容校验失败，请刷新后重新确认")
        if current_hash != stored_hash:
            raise ValueError("草稿内容已经变化，请重新提交审批")
        now_dt = datetime.now()
        now = now_dt.isoformat()
        expires_at = (now_dt + timedelta(minutes=30)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE earning_action_drafts SET status = 'approved', approved_hash = ?, approved_at = ?, expires_at = ?, updated_at = ? WHERE id = ?",
                    (current_hash, now, expires_at, now, int(action_id)),
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_action(action_id) or {}

    def revoke_earning_action(self, action_id: int) -> Dict[str, Any]:
        action = self.get_earning_action(action_id)
        if not action:
            raise ValueError("外部动作草稿不存在")
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE earning_action_drafts SET status = 'revoked', approved_hash = '', approved_at = '', expires_at = '', revoked_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, int(action_id)),
                )
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_action(action_id) or {}

    def start_first_income_experiment(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """按玩家明确授权建立首单实验；只写站内数据，不执行外部动作。"""
        data = data if isinstance(data, dict) else {}
        def bounded_number(key: str, default: float, minimum: float) -> float:
            try:
                return max(minimum, float(data.get(key, default) or default))
            except (TypeError, ValueError):
                return default

        weekly_hours = bounded_number("weekly_hours", 14.0, 14.0)
        target_amount = bounded_number("target_amount", 250.0, 201.0)
        price = bounded_number("price", 299.0, 0.0)
        cost_estimate = bounded_number("cost_estimate", 30.0, 0.0)
        preferences = self.update_earning_preferences({
            "weekly_hours": weekly_hours,
            "target_amount": target_amount,
            "risk_tolerance": "low",
            "accepted_models": ["automation_tool", "skill_service"],
            "primary_route": "automation_tool",
            "constraints": str(data.get("constraints") or "不垫资；账户登录、对外发送、报价承诺、付款和交易必须本人确认"),
        })
        offers = self.list_earning_offers()
        offer = next((item for item in offers if item.get("title") == "48 小时自动化微服务"), None)
        if not offer:
            offer = self.create_earning_offer({
                "title": "48 小时自动化微服务",
                "customer": "有一个明确、重复电脑流程，希望降低手工时间的小团队或个人",
                "problem": "把一个可描述输入、输出和操作步骤的重复流程自动化。",
                "deliverables": "可运行工具或脚本、操作演示、使用说明、一次修改。",
                "scope": "首单只打通一条流程；不接触付款、转账、验证码绕过、群发或违反平台规则的自动化。",
                "proof": "先制作两个不含客户数据的演示样例。",
                "price": price,
                "cost_estimate": cost_estimate,
                "delivery_days": 2,
                "revisions": 1,
                "route_key": "automation_tool",
                "status": "active",
            })
        sprint = self.create_earning_sprint({"route_key": "automation_tool", "goal_amount": target_amount})
        return {"success": True, "preferences": preferences, "offer": offer, "sprint": sprint}

    def list_earning_opportunities(self, status: str = "", kind: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            clauses, params = [], []
            if status: clauses.append("status = ?"); params.append(str(status))
            if kind: clauses.append("kind = ?"); params.append(str(kind))
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(max(1, min(500, int(limit))))
            rows = conn.execute(f"SELECT * FROM earning_opportunities{where} ORDER BY updated_at DESC, id DESC LIMIT ?", params).fetchall()
            return [dict(row) for row in rows]
        finally: conn.close()

    def get_earning_opportunity(self, opportunity_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_opportunities WHERE id = ?", (int(opportunity_id),)).fetchone()
            return dict(row) if row else None
        finally: conn.close()

    def create_earning_opportunity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}
        title = str(data.get("title", "")).strip()[:200]
        if not title: raise ValueError("情报标题不能为空")
        now = datetime.now().isoformat()
        def num(key: str) -> float:
            try: return max(0.0, float(data.get(key, 0) or 0))
            except (TypeError, ValueError): return 0.0
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO earning_opportunities (title, source, url, kind, description, income_min, income_max, hours, risk, confidence, verification_status, deadline, requirements, scam_flags, last_checked_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        title, str(data.get("source", ""))[:120], str(data.get("url", ""))[:1000], str(data.get("kind", "other"))[:40],
                        str(data.get("description", ""))[:2000], num("income_min"), num("income_max"), num("hours"),
                        self._normalise_earning_status(data.get("risk"), ("low", "medium", "high", "unknown"), "unknown"),
                        self._normalise_earning_status(data.get("confidence"), ("low", "medium", "high", "unknown"), "unknown"),
                        self._normalise_earning_status(data.get("verification_status"), ("unverified", "checking", "verified", "rejected"), "unverified"),
                        str(data.get("deadline", ""))[:40], str(data.get("requirements", ""))[:2000],
                        json.dumps(data.get("scam_flags", []) if isinstance(data.get("scam_flags"), list) else [], ensure_ascii=False),
                        str(data.get("last_checked_at", ""))[:40],
                        self._normalise_earning_status(data.get("status"), ("inbox", "shortlisted", "applied", "won", "closed"), "inbox"),
                        now, now,
                    ),
                )
                row_id = cur.lastrowid
                self._log_activity(conn, "earning", "◇", f"收录收益情报: {title}", str(data.get("source", ""))[:200])
                conn.commit()
            finally: conn.close()
        self._write_mirror()
        return self.get_earning_opportunity(int(row_id)) or {}

    def update_earning_opportunity(self, opportunity_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = data if isinstance(data, dict) else {}
        updates: Dict[str, Any] = {}
        for key in ("title", "source", "url", "kind", "description", "income_min", "income_max", "hours", "risk", "confidence", "verification_status", "deadline", "requirements", "scam_flags", "last_checked_at", "status"):
            if key not in data: continue
            if key in {"income_min", "income_max", "hours"}:
                try: updates[key] = max(0.0, float(data[key] or 0))
                except (TypeError, ValueError): continue
            elif key == "status": updates[key] = self._normalise_earning_status(data[key], ("inbox", "shortlisted", "applied", "won", "closed"), "inbox")
            elif key in {"risk", "confidence"}: updates[key] = self._normalise_earning_status(data[key], ("low", "medium", "high", "unknown"), "unknown")
            elif key == "verification_status": updates[key] = self._normalise_earning_status(data[key], ("unverified", "checking", "verified", "rejected"), "unverified")
            elif key == "scam_flags": updates[key] = json.dumps(data[key] if isinstance(data[key], list) else [], ensure_ascii=False)
            else: updates[key] = str(data[key] or "").strip()[:2000]
        if not updates: return self.get_earning_opportunity(opportunity_id)
        with self._lock:
            conn = self._connect()
            try:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(f"UPDATE earning_opportunities SET {assignments}, updated_at = ? WHERE id = ?", (*updates.values(), datetime.now().isoformat(), int(opportunity_id)))
                conn.commit()
            finally: conn.close()
        self._write_mirror()
        return self.get_earning_opportunity(opportunity_id)

    def convert_earning_opportunity_to_quest(self, opportunity_id: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """把收益情报转成地球online 委托，保留来源与收益预估。"""
        opportunity = self.get_earning_opportunity(opportunity_id)
        if not opportunity:
            return {"success": False, "message": "收益情报不存在"}
        if opportunity.get("quest_id"):
            return {"success": False, "message": "这条情报已经转成委托", "quest": self.get_quest(int(opportunity["quest_id"])), "opportunity": opportunity}
        data = data if isinstance(data, dict) else {}
        title = str(data.get("title") or f"执行收益机会：{opportunity['title']}").strip()[:200]
        description = str(data.get("description") or opportunity.get("description") or "完成后在收益中枢记录真实收入与成本。").strip()[:2000]
        fields = {
            "earning_opportunity_id": int(opportunity_id),
            "earning_source": opportunity.get("source", ""),
            "earning_url": opportunity.get("url", ""),
            "income_min": opportunity.get("income_min", 0),
            "income_max": opportunity.get("income_max", 0),
            "estimated_hours": opportunity.get("hours", 0),
            "risk": opportunity.get("risk", "unknown"),
            "confidence": opportunity.get("confidence", "unknown"),
        }
        try:
            quest = self.create_quest(
                title=title,
                description=description,
                quest_type="optional",
                must_complete=False,
                reward_currency=0,
                reward_exp=max(0, int(data.get("reward_exp", 10) or 0)),
                penalty_currency=0,
                deadline=str(data.get("deadline", ""))[:40],
                source="earning",
                difficulty=max(1, min(5, int(data.get("difficulty", 2) or 2))),
                fields=fields,
            )
        except (TypeError, ValueError) as exc:
            return {"success": False, "message": str(exc)}
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("UPDATE earning_opportunities SET status = 'shortlisted', quest_id = ?, updated_at = ? WHERE id = ?", (int(quest["id"]), datetime.now().isoformat(), int(opportunity_id)))
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {"success": True, "quest": quest, "opportunity": self.get_earning_opportunity(opportunity_id)}

    def list_earning_plan_steps(self, plan_id: Optional[int] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if plan_id is None:
                rows = conn.execute("SELECT * FROM earning_plan_steps ORDER BY plan_id ASC, position ASC, id ASC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM earning_plan_steps WHERE plan_id = ? ORDER BY position ASC, id ASC", (int(plan_id),)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def _earning_plan_with_steps(self, plan: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not plan:
            return None
        result = dict(plan)
        steps = self.list_earning_plan_steps(int(plan["id"]))
        result["steps"] = steps
        result["completed_steps"] = sum(1 for step in steps if step.get("status") == "done")
        result["progress_percent"] = round(result["completed_steps"] / len(steps) * 100) if steps else 0
        return result

    def create_earning_plan_step(self, plan_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.get_earning_plan(plan_id):
            raise ValueError("收益计划不存在")
        data = data if isinstance(data, dict) else {}
        title = str(data.get("title", "")).strip()[:200]
        if not title:
            raise ValueError("阶段标题不能为空")
        try:
            position = max(0, int(data.get("position", 0) or 0))
        except (TypeError, ValueError):
            position = 0
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("INSERT INTO earning_plan_steps (plan_id, title, description, position, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)", (int(plan_id), title, str(data.get("description", ""))[:1000], position, self._normalise_earning_status(data.get("status"), ("pending", "doing", "done", "skipped"), "pending"), now, now))
                conn.execute("UPDATE earning_plans SET updated_at = ? WHERE id = ?", (now, int(plan_id)))
                conn.commit(); step_id = cur.lastrowid
            finally:
                conn.close()
        self._write_mirror()
        return self.get_earning_plan_step(int(step_id)) or {}

    def get_earning_plan_step(self, step_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_plan_steps WHERE id = ?", (int(step_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_earning_plan_step(self, step_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        step = self.get_earning_plan_step(step_id)
        if not step:
            return None
        data = data if isinstance(data, dict) else {}
        updates: Dict[str, Any] = {}
        if "title" in data and str(data["title"] or "").strip(): updates["title"] = str(data["title"]).strip()[:200]
        if "description" in data: updates["description"] = str(data["description"] or "")[:1000]
        if "position" in data:
            try: updates["position"] = max(0, int(data["position"] or 0))
            except (TypeError, ValueError): pass
        if "status" in data: updates["status"] = self._normalise_earning_status(data["status"], ("pending", "doing", "done", "skipped"), "pending")
        if not updates: return step
        if updates.get("status") == "done": updates["completed_at"] = datetime.now().isoformat()
        elif updates.get("status") in {"pending", "doing"}: updates["completed_at"] = ""
        with self._lock:
            conn = self._connect()
            try:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                now = datetime.now().isoformat()
                conn.execute(f"UPDATE earning_plan_steps SET {assignments}, updated_at = ? WHERE id = ?", (*updates.values(), now, int(step_id)))
                conn.execute("UPDATE earning_plans SET updated_at = ? WHERE id = ?", (now, int(step["plan_id"])))
                conn.commit()
            finally: conn.close()
        self._write_mirror()
        return self.get_earning_plan_step(step_id)

    def convert_earning_plan_step_to_quest(self, step_id: int) -> Dict[str, Any]:
        step = self.get_earning_plan_step(step_id)
        if not step:
            return {"success": False, "message": "收益阶段不存在"}
        if step.get("quest_id"):
            return {"success": False, "message": "这个阶段已经转成委托", "step": step, "quest": self.get_quest(int(step["quest_id"]))}
        plan = self.get_earning_plan(int(step["plan_id"])) or {}
        quest = self.create_quest(title=f"收益计划：{step['title']}", description=str(step.get("description") or f"完成收益计划「{plan.get('title', '')}」的这一阶段。"), quest_type="optional", reward_currency=0, reward_exp=5, source="earning_plan", difficulty=2, fields={"earning_plan_id": int(step["plan_id"]), "earning_plan_step_id": int(step_id)})
        self.update_earning_plan_step(step_id, {"status": "doing"})
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("UPDATE earning_plan_steps SET quest_id = ?, updated_at = ? WHERE id = ?", (int(quest["id"]), datetime.now().isoformat(), int(step_id)))
                conn.commit()
            finally: conn.close()
        self._write_mirror()
        return {"success": True, "step": self.get_earning_plan_step(step_id), "quest": quest}

    def list_earning_plans(self, status: str = "") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM earning_plans WHERE status = ? ORDER BY updated_at DESC, id DESC" if status else "SELECT * FROM earning_plans ORDER BY updated_at DESC, id DESC", (status,) if status else ()).fetchall()
            return [self._earning_plan_with_steps(dict(row)) or {} for row in rows]
        finally: conn.close()

    def get_earning_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM earning_plans WHERE id = ?", (int(plan_id),)).fetchone()
            return self._earning_plan_with_steps(dict(row)) if row else None
        finally: conn.close()

    def create_earning_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}; title = str(data.get("title", "")).strip()[:200]
        if not title: raise ValueError("收益计划标题不能为空")
        try: goal = max(0.0, float(data.get("goal_amount", 0) or 0))
        except (TypeError, ValueError): goal = 0.0
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO earning_plans (title, goal_amount, target_date, status, notes, route_key, is_sprint, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        title, goal, str(data.get("target_date", ""))[:30],
                        self._normalise_earning_status(data.get("status"), ("active", "paused", "completed", "archived"), "active"),
                        str(data.get("notes", ""))[:2000], str(data.get("route_key", ""))[:40],
                        1 if data.get("is_sprint") else 0, now, now,
                    ),
                )
                row_id = cur.lastrowid
                conn.commit()
            finally: conn.close()
        self._write_mirror(); return self.get_earning_plan(int(row_id)) or {}

    def earning_routes(self) -> List[Dict[str, Any]]:
        """按玩家档案给第一笔收入实验路线排序，不承诺收益。"""
        prefs = self.get_earning_preferences()
        accepted = {str(value) for value in prefs.get("accepted_models", [])}
        profile_text = " ".join(str(value) for value in [
            *prefs.get("skills", []), *prefs.get("sellable_assets", []), *prefs.get("preferred_kinds", []),
        ]).lower()
        ranked: List[Dict[str, Any]] = []
        for index, template in enumerate(EARNING_ROUTE_TEMPLATES):
            if accepted and template["key"] not in accepted:
                continue
            item = {key: value for key, value in template.items() if key != "keywords"}
            matches = [keyword for keyword in template["keywords"] if keyword.lower() in profile_text]
            score = 60 - index * 0.5 + min(36, len(matches) * 12)
            reasons: List[str] = []
            if matches:
                reasons.append("与你填写的能力或资源相关：" + "、".join(matches[:3]))
            if template["cash_cost"] in {"零", "几乎为零"}:
                score += 8
                reasons.append("启动成本很低")
            if template["key"] == "resale" and any(word in profile_text for word in ("闲置", "数码", "书", "收藏", "物品")):
                score += 12
            if not reasons:
                reasons.append("当前资料不足，先作为低成本验证方向")
            item["fit_score"] = max(0, min(100, score))
            item["fit_reasons"] = reasons
            item["first_action"] = template["steps"][0][0]
            ranked.append(item)
        ranked.sort(key=lambda value: value["fit_score"], reverse=True)
        return ranked

    def create_earning_sprint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建 7 天第一笔收入实验；只产生站内计划和首个委托。"""
        data = data if isinstance(data, dict) else {}
        route_key = str(data.get("route_key", "")).strip()
        route = next((item for item in EARNING_ROUTE_TEMPLATES if item["key"] == route_key), None)
        if not route:
            raise ValueError("请选择有效的赚钱路线")
        accepted = {str(value) for value in self.get_earning_preferences().get("accepted_models", [])}
        if accepted and route_key not in accepted:
            raise ValueError("这条路线不在当前档案的可接受范围内")
        active = [plan for plan in self.list_earning_plans(status="active") if plan.get("route_key") == route_key and plan.get("is_sprint")]
        if active:
            self.update_earning_preferences({"primary_route": route_key})
            return {"success": True, "created": False, "plan": active[0], "route": {key: value for key, value in route.items() if key != "keywords"}}
        try:
            goal = max(1.0, float(data.get("goal_amount", 100) or 100))
        except (TypeError, ValueError):
            goal = 100.0
        target_date = str(data.get("target_date", "")).strip()[:30] or (datetime.now() + timedelta(days=7)).date().isoformat()
        plan = self.create_earning_plan({
            "title": f"7 天第一笔收入实验 · {route['name']}",
            "goal_amount": goal,
            "target_date": target_date,
            "notes": f"目标不是保证赚到 ¥{goal:g}，而是在 7 天内完成一次真实市场验证。外部发布、联系、上传和交易均需玩家确认。",
            "route_key": route_key,
            "is_sprint": True,
        })
        steps = []
        for position, (title, description) in enumerate(route["steps"]):
            steps.append(self.create_earning_plan_step(plan["id"], {"title": title, "description": description, "position": position}))
        first = steps[0]
        quest_result = self.convert_earning_plan_step_to_quest(first["id"])
        self.update_earning_preferences({"primary_route": route_key, "target_amount": goal})
        with self._lock:
            conn = self._connect()
            try:
                self._log_activity(conn, "earning", "◆", f"开始第一笔收入实验: {route['name']}", f"7 天目标 ¥{goal:g}")
                conn.commit()
            finally:
                conn.close()
        self._write_mirror()
        return {
            "success": True,
            "created": True,
            "plan": self.get_earning_plan(plan["id"]),
            "quest": quest_result.get("quest"),
            "route": {key: value for key, value in route.items() if key != "keywords"},
        }

    def list_income_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM income_records ORDER BY recorded_at DESC, id DESC LIMIT ?", (max(1, min(1000, int(limit))),)).fetchall(); return [dict(row) for row in rows]
        finally: conn.close()

    def record_income(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data if isinstance(data, dict) else {}
        def num(key: str) -> float:
            try: return float(data.get(key, 0) or 0)
            except (TypeError, ValueError): return 0.0
        amount, cost, hours = num("amount"), max(0.0, num("cost")), max(0.0, num("hours"))
        if amount <= 0: raise ValueError("收入金额必须大于 0；支出请记录在成本字段")
        opportunity_id = int(data["opportunity_id"]) if data.get("opportunity_id") else None
        if opportunity_id and not self.get_earning_opportunity(opportunity_id):
            raise ValueError("关联的收益情报不存在")
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("INSERT INTO income_records (opportunity_id, amount, cost, hours, note, recorded_at) VALUES (?,?,?,?,?,?)", (opportunity_id, amount, cost, hours, str(data.get("note", ""))[:2000], str(data.get("recorded_at", now))[:40]))
                if opportunity_id:
                    conn.execute("UPDATE earning_opportunities SET status = 'won', updated_at = ? WHERE id = ?", (now, opportunity_id))
                self._ledger_locked(conn, "earth", amount - cost, "现实收益记录"); self._log_activity(conn, "earning", "◆", f"记录现实收益 ¥{amount - cost:.2f}", str(data.get("note", ""))[:200]); conn.commit(); row_id = cur.lastrowid
            finally: conn.close()
        self._write_mirror(); return {"success": True, "record": self.get_income_record(int(row_id)), "player": self.get_player()}

    def get_income_record(self, record_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM income_records WHERE id = ?", (int(record_id),)).fetchone(); return dict(row) if row else None
        finally: conn.close()

    def earning_guidance(self) -> Dict[str, Any]:
        opportunities = self.list_earning_opportunities(limit=200); plans = self.list_earning_plans(); records = self.list_income_records(limit=200); prefs = self.get_earning_preferences(); ranked = []
        offers = self.list_earning_offers(); actions = self.list_earning_actions(limit=100)
        skills = [str(value).lower() for value in prefs.get("skills", [])]; preferred_kinds = [str(value).lower() for value in prefs.get("preferred_kinds", [])]
        for raw in opportunities:
            item = dict(raw); hours = float(item.get("hours") or 0); lo = float(item.get("income_min") or 0); hi = float(item.get("income_max") or 0); text = f"{item.get('title', '')} {item.get('description', '')} {item.get('kind', '')}".lower(); item["hourly_estimate"] = round((lo + hi) / 2 / hours, 2) if hours > 0 else 0
            score = item["hourly_estimate"] * ({"low": 1, "medium": .7, "high": .4}.get(item.get("risk"), .5)) + ({"high": 10, "medium": 4}.get(item.get("confidence"), 0)); reasons = []
            if preferred_kinds and any(kind in text for kind in preferred_kinds): score += 15; reasons.append("符合偏好类型")
            if skills and any(skill in text for skill in skills): score += 25; reasons.append("与已填写技能相关")
            if float(prefs.get("min_hourly_rate") or 0) and item["hourly_estimate"] < float(prefs["min_hourly_rate"]): score -= 20; reasons.append("低于最低时薪")
            if float(prefs.get("weekly_hours") or 0) and hours > float(prefs["weekly_hours"]): score -= 10; reasons.append("预计耗时超过每周可用时间")
            if float(prefs.get("target_amount") or 0) and hi >= float(prefs["target_amount"]): score += 5; reasons.append("单次预估上限可覆盖阶段目标")
            tolerance = prefs.get("risk_tolerance", "low")
            if tolerance == "low" and item.get("risk") == "high": score -= 25; reasons.append("风险高于你的接受范围")
            elif tolerance == "high" and item.get("risk") == "low": reasons.append("风险低于你的上限")
            verification = item.get("verification_status", "unverified")
            if verification == "verified": score += 12; reasons.append("来源和关键条件已核验")
            elif verification == "rejected": score -= 100; reasons.append("核验未通过")
            else: score -= 8; reasons.append("关键条件仍待核验")
            if item.get("scam_flags"):
                score -= min(40, len(item["scam_flags"]) * 12); reasons.append("存在风险信号")
            if not reasons: reasons.append("按预估时薪、风险与可信度排序")
            item["fit_score"] = round(score, 2); item["fit_reasons"] = reasons; ranked.append(item)
        ranked.sort(key=lambda x: x["fit_score"], reverse=True)
        active_plans = [plan for plan in plans if plan.get("status") == "active"]
        next_step = None
        focus_plan = active_plans[0] if active_plans else None
        for candidate in active_plans:
            next_step = next((step for step in candidate.get("steps", []) if step.get("status") not in {"done", "skipped"}), None)
            if next_step:
                focus_plan = candidate
                break
        pipeline = {key: sum(1 for item in opportunities if item.get("status") == key) for key in ("inbox", "shortlisted", "applied", "won", "closed")}
        routes = self.earning_routes()
        active_offers = [offer for offer in offers if offer.get("status") == "active"]
        pending_actions = [action for action in actions if action.get("status") == "pending"]
        approved_actions = [action for action in actions if action.get("status") == "approved"]
        profile_ready = bool(prefs.get("skills") or prefs.get("sellable_assets") or active_offers) and float(prefs.get("weekly_hours") or 0) > 0
        if pending_actions:
            brief = f"审批箱里有 {len(pending_actions)} 份外部动作草稿待你逐项确认；批准只在 30 分钟内有效，也不会自动发送。"
        elif approved_actions:
            brief = f"有 {len(approved_actions)} 份草稿已经批准，等待你人工执行；弥娅不会自行发送或交易。"
        elif next_step:
            brief = f"当前先推进「{next_step['title']}」。完成后，弥娅会把实验推进到下一阶段。"
        elif ranked:
            brief = f"情报箱里优先核验「{ranked[0]['title']}」，先确认条件，再决定是否投入时间。"
        elif not profile_ready:
            brief = "先补充你能出售的能力或资源，弥娅才能把路线缩小到最值得验证的两三条。"
        else:
            brief = f"档案已就绪。建议从「{routes[0]['name']}」开始一个 7 天低成本实验。" if routes else "档案已就绪，可以开始第一轮收入实验。"
        total_hours = sum(float(record.get("hours") or 0) for record in records)
        net_income = round(sum(float(record.get("amount") or 0) - float(record.get("cost") or 0) for record in records), 2)
        return {
            "opportunities": ranked[:30], "plans": plans[:20], "income_records": records[:30], "preferences": prefs,
            "offers": offers[:20], "action_drafts": actions[:50],
            "routes": routes, "profile_ready": profile_ready, "brief": brief, "focus_plan": focus_plan, "next_action": next_step,
            "pipeline": pipeline,
            "totals": {
                "net_income": net_income, "opportunity_count": len(opportunities),
                "active_plan_count": len(active_plans), "active_offer_count": len(active_offers),
                "pending_approval_count": len(pending_actions), "approved_action_count": len(approved_actions),
                "total_hours": round(total_hours, 2),
                "effective_hourly_rate": round(net_income / total_hours, 2) if total_hours > 0 else 0,
            },
            "automation": {
                "automatic": ["公开信息同步", "去重与初筛", "生成草稿", "站内提醒", "收益复盘"],
                "requires_confirmation": ["对外发布", "联系客户", "提交申请", "上传资料", "接受订单"],
                "blocked": ["付款", "转账", "提现", "退款", "自动输入验证码或支付密码"],
            },
            "boundary": "建议不保证收益；外部动作必须逐项审批且当前仍由你人工执行。付款、转账、提现、退款和金融凭据输入不开放给弥娅。",
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
