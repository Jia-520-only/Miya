"""
QQ表情包工具 v2.0

支持发送表情包到QQ群或私聊，包含常用表情包和自定义表情包管理
智能模式：根据用户消息语义自动判断是否发送表情包
"""

import logging
import os
import random
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

SMART_EMOJI_TRIGGERS = [
    "发个表情",
    "发个图",
    "表情包",
    "发个图片",
    "来个表情",
    "送个表情",
    "给我表情",
    "随机表情",
    "随机图",
]

AUTO_EMOJI_PATTERNS = [
    "高兴",
    "开心",
    "哈哈",
    "笑",
    "嘻嘻",
    "难过",
    "伤心",
    "哭",
    "泪",
    "生气",
    "愤怒",
    "气",
    "怒",
    "惊讶",
    "震惊",
    "哇",
    "啊",
    "害羞",
    "脸红",
    "羞涩",
    "可爱",
    "萌",
    "甜",
    "得意",
    "骄傲",
    "厉害",
    "棒",
    "无语",
    "无奈",
    "尴尬",
    "囧",
    "亲亲",
    "爱你",
    "喜欢",
    "么么哒",
    "加油",
    "努力",
    "冲",
    "谢谢",
    "感谢",
    "谢",
    "对不起",
    "抱歉",
    "不好意思",
    "早安",
    "晚安",
    "你好",
    "hi",
    "hello",
    "祝福",
    "祝你",
    "生日",
    "好耶",
    "太好了",
    "开心",
    "快乐",
    "呜呜",
    "委屈",
    "可怜",
]


class QQEmojiTool(BaseTool):
    """QQ表情包工具"""

    # QQ标准表情ID映射
    STANDARD_EMOJIS = {
        # 常用表情
        "微笑": 14,
        "撇嘴": 1,
        "色": 2,
        "发呆": 3,
        "得意": 4,
        "流泪": 5,
        "害羞": 6,
        "闭嘴": 7,
        "睡": 8,
        "大哭": 9,
        "尴尬": 10,
        "发怒": 11,
        "调皮": 12,
        "呲牙": 13,
        "惊讶": 14,
        "难过": 15,
        "酷": 16,
        "冷汗": 96,
        "抓狂": 97,
        "吐": 98,
        "偷笑": 99,
        "可爱": 100,
        "白眼": 101,
        "傲慢": 102,
        "饥饿": 103,
        "困": 104,
        "惊恐": 105,
        "流汗": 106,
        "憨笑": 107,
        "悠闲": 108,
        "奋斗": 109,
        "咒骂": 110,
        "疑问": 111,
        "嘘": 112,
        "晕": 113,
        "折磨": 114,
        "衰": 115,
        "骷髅": 116,
        "敲打": 117,
        "再见": 118,
        "擦汗": 119,
        "抠鼻": 120,
        "鼓掌": 121,
        "糗大了": 122,
        "坏笑": 123,
        "左哼哼": 124,
        "右哼哼": 125,
        "哈欠": 126,
        "鄙视": 127,
        "委屈": 128,
        "快哭了": 129,
        "阴险": 130,
        "亲亲": 131,
        "吓": 132,
        "可怜": 133,
        "菜刀": 134,
        "西瓜": 135,
        "啤酒": 136,
        "篮球": 137,
        "乒乓": 138,
        "咖啡": 139,
        "饭": 140,
        "猪头": 141,
        "玫瑰": 142,
        "凋谢": 143,
        "示爱": 144,
        "爱心": 145,
        "心碎": 146,
        "蛋糕": 147,
        "闪电": 148,
        "炸弹": 149,
        "刀": 150,
        "足球": 151,
        "瓢虫": 152,
        "便便": 153,
        "月亮": 154,
        "太阳": 155,
        "礼物": 156,
        "拥抱": 157,
        "强": 158,
        "弱": 159,
        "握手": 160,
        "胜利": 161,
        "抱拳": 162,
        "勾引": 163,
        "拳头": 164,
        "差劲": 165,
        "爱你": 166,
        "NO": 167,
        "OK": 168,
        "转圈": 169,
        "磕头": 170,
        "回头": 171,
        "跳绳": 172,
        "挥手": 173,
        "激动": 174,
        "街舞": 175,
        "献吻": 176,
        "左太极": 177,
        "右太极": 178,
        "双喜": 179,
        "鞭炮": 180,
        "灯笼": 181,
        "K歌": 182,
        "喝彩": 183,
        "祈祷": 184,
        "爆筋": 185,
        "棒棒糖": 186,
        "喝奶": 187,
        "飞机": 188,
        "钞票": 189,
        "药": 190,
        "手枪": 191,
        "茶": 192,
        "眨眼睛": 193,
        "泪奔": 194,
        "无奈": 195,
        "卖萌": 196,
        "小纠结": 197,
        "喷血": 198,
        "斜眼笑": 199,
        "doge": 200,
        "惊喜": 201,
        "骚扰": 202,
        "笑哭": 203,
        "我最美": 204,
        "河蟹": 205,
        "羊驼": 206,
        "幽灵": 207,
        "蛋": 208,
        "菊花": 209,
        "红包": 210,
        "大笑": 211,
        "不开心": 212,
        "冷漠": 213,
        "呃": 214,
        "好棒": 215,
        "拜托": 216,
        "点赞": 217,
        "无聊": 218,
        "托脸": 219,
        "吃": 220,
        "送花": 221,
        "害怕": 222,
        "花痴": 223,
        "小样儿": 224,
        "飙泪": 225,
        "我不看": 226,
        "托腮": 227,
        "啵啵": 228,
        "糊脸": 229,
        "拍头": 230,
        "扯一扯": 231,
        "舔一舔": 232,
        "蹭一蹭": 233,
        "拽炸天": 234,
        "顶呱呱": 235,
        "抱抱": 236,
        "暴击": 237,
        "开枪": 238,
        "撩一撩": 239,
        "拍桌": 240,
        "拍手": 241,
        "恭喜": 242,
        "干杯": 243,
        "嘲讽": 244,
        "哼": 245,
        "佛系": 246,
        "掐一掐": 247,
        "惊呆": 248,
        "颤抖": 249,
        "啃头": 250,
        "偷看": 251,
        "扇脸": 252,
        "原谅": 253,
        "喷脸": 254,
        "生日快乐": 255,
        "头撞击": 256,
        "甩头": 257,
        "扔狗": 258,
        "加油必胜": 259,
        "加油抱抱": 260,
        "口罩护体": 261,
        "搬砖中": 262,
        "忙到飞起": 263,
        "脑阔疼": 264,
        "沧桑": 265,
        "捂脸": 266,
        "辣眼睛": 267,
        "哦哟": 268,
        "头秃": 269,
        "问号脸": 270,
        "暗中观察": 271,
        "emm": 272,
        "吃瓜": 273,
        "呵呵哒": 274,
        "我酸了": 275,
        "太南了": 276,
        "辣椒酱": 277,
        "汪汪": 278,
        "汗": 279,
        "打脸": 280,
        "击掌": 281,
        "无眼笑": 282,
        "敬礼": 283,
        "狂笑": 284,
        "面无表情": 285,
        "摸鱼": 286,
        "魔鬼笑": 287,
        "哦": 288,
        "请": 289,
        "睁眼": 290,
        "敲开心": 291,
        "震惊": 292,
        "让我康康": 293,
        "摸锦鲤": 294,
        "期待": 295,
        "拿到红包": 296,
        "真好": 297,
        "拜谢": 298,
        "元宝": 299,
        "牛啊": 300,
        "胖三斤": 301,
        "好闪": 302,
        "左拜年": 303,
        "右拜年": 304,
        "红包包": 305,
        "右亲亲": 306,
        "牛气冲天": 307,
        "喵喵": 308,
        "求红包": 309,
        "谢红包": 310,
        "新年烟花": 311,
        "打call": 312,
        "变形": 313,
        "嗑到了": 314,
        "仔细分析": 315,
        "加油": 316,
        "我没事": 317,
        "菜狗": 318,
        "崇拜": 319,
        "比心": 320,
        "庆祝": 321,
        "老色痞": 322,
        "拒绝": 323,
        "嫌弃": 324,
        "吃糖": 325,
        "惊吓": 326,
        "生气": 327,
        "加一": 328,
        "错号": 329,
        "对号": 330,
        "完成": 331,
        "明白": 332,
    }

    # 表情包分类
    EMOJI_CATEGORIES = {
        "日常": ["微笑", "撇嘴", "发呆", "得意", "流泪", "害羞", "闭嘴", "睡", "大哭"],
        "开心": ["憨笑", "悠闲", "偷笑", "可爱", "呲牙", "调皮", "坏笑"],
        "生气": ["发怒", "抓狂", "咒骂", "鄙视", "左哼哼", "右哼哼"],
        "惊讶": ["惊讶", "惊恐", "晕", "吓", "流汗", "冷汗"],
        "难过": ["难过", "委屈", "快哭了", "可怜", "泪奔", "心碎"],
        "爱": ["亲亲", "拥抱", "爱心", "示爱", "爱你", "啵啵"],
        "动作": ["鼓掌", "握手", "抱拳", "拳头", "转圈", "磕头", "挥手"],
        "物品": ["玫瑰", "蛋糕", "礼物", "啤酒", "咖啡", "足球", "篮球"],
        "网络": ["笑哭", "doge", "斜眼笑", "吃瓜", "我酸了", "太南了"],
        "动物": ["喵喵", "汪汪", "猪头", "羊驼"],
        "节日": ["生日快乐", "恭喜", "干杯", "新年烟花", "红包"],
    }

    def __init__(self):
        super().__init__()
        self.user_favorites = {}  # 用户收藏的表情包
        self.emoji_stats = {}  # 表情包使用统计
        self.emoji_db_path = None

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "qq_emoji",
            "description": "发送QQ表情包到群或私聊，支持智能语义匹配。当用户说'发个表情'、'发个笑脸'、'发个表情包'时调用此工具。智能模式：弥娅会根据对话内容自动判断是否发送表情包，并选择最合适的表情包。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型：send(发送表情)、smart(智能发送)、search(搜索表情)、random(随机表情)、list(列表表情)、analyze(分析消息)、favorite(收藏表情)",
                        "enum": [
                            "send",
                            "smart",
                            "search",
                            "random",
                            "list",
                            "analyze",
                            "favorite",
                        ],
                        "default": "send",
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标类型：group(群聊)或private(私聊)，默认为当前会话类型",
                        "enum": ["group", "private"],
                        "default": "group",
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标ID（群号或用户QQ号），默认为当前用户ID或群ID",
                    },
                    "message": {
                        "type": "string",
                        "description": "用户消息内容，用于智能模式分析语义（action=smart时使用）",
                    },
                    "emoji_name": {
                        "type": "string",
                        "description": "表情名称，如'微笑'、'笑哭'、'doge'等，或图片表情包文件名。支持模糊搜索。",
                    },
                    "emoji_id": {
                        "type": "integer",
                        "description": "QQ内置表情ID（1-333），可直接指定表情ID",
                    },
                    "emoji_type": {
                        "type": "string",
                        "description": "表情类型：standard(QQ内置表情)或image(图片表情包)。默认为standard",
                        "enum": ["standard", "image"],
                        "default": "standard",
                    },
                    "emoji_path": {
                        "type": "string",
                        "description": "图片表情包文件路径，当emoji_type为image时使用。支持相对或绝对路径。",
                    },
                    "category": {
                        "type": "string",
                        "description": "表情分类，如'custom'(自定义)、'miya_special'(弥娅专属)、'cute'(可爱)、'reaction'(反应)、'stickers'(贴纸)等。当action为random或search时使用",
                        "enum": [
                            "custom",
                            "miya_special",
                            "standard",
                            "cute",
                            "reaction",
                            "seasonal",
                            "memes",
                            "all",
                        ],
                    },
                    "search_keyword": {
                        "type": "string",
                        "description": "搜索关键词，当action为search时使用。支持搜索图片表情包文件名。",
                    },
                    "count": {
                        "type": "integer",
                        "description": "发送表情数量（1-5），默认为1。仅对QQ内置表情有效。",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 1,
                    },
                },
                "required": ["action"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行表情包操作"""
        try:
            action = args.get("action", "send")

            if action == "send":
                return await self._send_emoji(args, context)
            elif action == "smart":
                return await self._smart_emoji(args, context)
            elif action == "search":
                return await self._search_emoji(args, context)
            elif action == "random":
                return await self._random_emoji(args, context)
            elif action == "list":
                return await self._list_emoji(args, context)
            elif action == "analyze":
                return await self._analyze_message(args, context)
            elif action == "favorite":
                return await self._manage_favorite(args, context)
            else:
                return f"❌ 不支持的操作类型: {action}"

        except Exception as e:
            logger.error(f"表情包操作失败: {e}", exc_info=True)
            return f"❌ 表情包操作失败: {str(e)}"

    async def _send_emoji(self, args: Dict[str, Any], context: ToolContext) -> str:
        """发送表情包"""
        args.get("target_type", "group")
        args.get("target_id", self._get_default_target_id(context))
        args.get("emoji_name", "")
        args.get("emoji_id", 0)
        emoji_path = args.get("emoji_path", "")
        emoji_type = args.get("emoji_type", "standard")  # standard: QQ内置, image: 图片表情
        args.get("count", 1)

        # 获取QQ客户端
        qq_client = getattr(context, "onebot_client", None)
        if not qq_client:
            return "❌ QQ客户端不可用"

        # 检查是发送QQ内置表情还是图片表情
        if emoji_type == "image" or emoji_path:
            # 发送图片表情包
            return await self._send_image_emoji(args, context, qq_client)
        else:
            # 发送QQ内置表情
            return await self._send_qq_face_emoji(args, context, qq_client)

    async def _send_qq_face_emoji(self, args: Dict[str, Any], context: ToolContext, qq_client) -> str:
        """发送QQ内置表情"""
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id", self._get_default_target_id(context))
        emoji_name = args.get("emoji_name", "")
        emoji_id = args.get("emoji_id", 0)
        count = args.get("count", 1)

        # 确定表情ID
        emoji_id_to_send = 0

        if emoji_id and 1 <= emoji_id <= 333:
            emoji_id_to_send = emoji_id
            emoji_name = self._get_emoji_name_by_id(emoji_id)
        elif emoji_name:
            emoji_id_to_send = self.STANDARD_EMOJIS.get(emoji_name, 0)
            if not emoji_id_to_send:
                # 尝试模糊匹配
                matched_name = self._fuzzy_match_emoji(emoji_name)
                if matched_name:
                    emoji_id_to_send = self.STANDARD_EMOJIS[matched_name]
                    emoji_name = matched_name

        if not emoji_id_to_send:
            return f"❌ 未找到QQ表情: {emoji_name}"

        # 发送表情
        try:
            result = await qq_client.send_face_message(
                target_type=target_type, target_id=target_id, face_id=emoji_id_to_send
            )

            # 记录使用统计
            self._record_emoji_usage(emoji_name, emoji_id_to_send, context)

            if result and result.get("status") == "ok":
                target_desc = f"群 {target_id}" if target_type == "group" else f"用户 {target_id}"
                count_desc = f"{count}个" if count > 1 else "1个"
                return f"✅ {count_desc} '{emoji_name}' 表情已发送到 {target_desc}"
            else:
                return f"❌ QQ表情发送失败: {result}"

        except Exception as e:
            return f"❌ QQ表情发送失败: {str(e)}"

    async def _send_image_emoji(self, args: Dict[str, Any], context: ToolContext, qq_client) -> str:
        """发送图片表情包"""
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id", self._get_default_target_id(context))
        emoji_path = args.get("emoji_path", "")
        emoji_name = args.get("emoji_name", "")
        category = args.get("category", "custom")

        try:
            # 导入表情包管理器
            from utils.emoji_manager import get_emoji_manager

            emoji_manager = get_emoji_manager()

            # 获取表情包信息
            emoji_info = None
            if emoji_path and os.path.exists(emoji_path):
                # 使用指定路径的表情包
                emoji_info = {
                    "path": emoji_path,
                    "name": os.path.basename(emoji_path),
                    "category": "direct_path",
                }
            elif emoji_name:
                # 根据名称搜索表情包
                search_results = emoji_manager.search_emoji(emoji_name, category)
                if search_results:
                    emoji_info = search_results[0]
            else:
                # 随机获取表情包
                if random.random() < 0.5:
                    emoji_info = emoji_manager.get_random_emoji(category)
                else:
                    emoji_info = emoji_manager.get_random_sticker(category)

            if not emoji_info:
                return "❌ 未找到合适的图片表情包"

            # 检查文件是否存在
            if not os.path.exists(emoji_info["path"]):
                return f"❌ 表情包文件不存在: {emoji_info['path']}"

            # 检查文件大小
            max_size = 5242880  # 5MB
            file_size = os.path.getsize(emoji_info["path"])
            if file_size > max_size:
                return f"❌ 表情包文件过大: {file_size}字节 > {max_size}字节"

            # 读取文件并转换为 base64
            import base64

            with open(emoji_info["path"], "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

            # 使用 CQ 码方式发送图片
            cq_image = f"[CQ:image,file=base64://{image_base64}]"

            # 发送消息
            if target_type == "private":
                result = await qq_client.send_private_message(target_id, cq_image)
            else:
                result = await qq_client.send_group_message(target_id, cq_image)

            if result and result.get("status") == "ok":
                emoji_type = "贴纸" if "stickers" in emoji_info.get("category", "") else "表情包"
                target_desc = f"群 {target_id}" if target_type == "group" else f"用户 {target_id}"
                return f"✅ {emoji_type} '{emoji_info['name']}' 已发送到 {target_desc}"
            else:
                return f"❌ 图片表情发送失败: {result}"

        except ImportError:
            return "❌ 表情包管理器未安装，请确保utils.emoji_manager模块存在"
        except Exception as e:
            logger.error(f"发送图片表情包失败: {e}", exc_info=True)
            return f"❌ 图片表情发送失败: {str(e)}"

    async def _search_emoji(self, args: Dict[str, Any], context: ToolContext) -> str:
        """搜索表情包"""
        keyword = args.get("search_keyword", "")
        if not keyword:
            return "❌ 请输入搜索关键词"

        # 同时搜索QQ内置表情和图片表情包
        qq_results = []
        image_results = []

        # 1. 搜索QQ内置表情
        for name, emoji_id in self.STANDARD_EMOJIS.items():
            if keyword in name:
                qq_results.append(("QQ内置", name, emoji_id, "face"))

        # 2. 搜索图片表情包（如果有表情包管理器）
        try:
            from utils.emoji_manager import get_emoji_manager

            emoji_manager = get_emoji_manager()
            image_search_results = emoji_manager.search_emoji(keyword)

            for item in image_search_results:
                category_name = item.get("category", "未知")
                emoji_type = "贴纸" if "stickers" in category_name else "图片表情"

                image_results.append((emoji_type, item["name"], "", "image", item["path"]))

        except ImportError:
            # 表情包管理器未安装，只搜索QQ内置表情
            pass
        except Exception as e:
            logger.warning(f"搜索图片表情包失败: {e}")

        # 合并结果
        all_results = qq_results + image_results

        if not all_results:
            return f"❌ 未找到包含 '{keyword}' 的表情或表情包"

        # 格式化结果
        result_lines = [f"🔍 找到 {len(all_results)} 个相关表情/表情包:"]

        # 显示QQ内置表情
        if qq_results:
            result_lines.append("\n💬 **QQ内置表情:**")
            for i, (_, name, emoji_id, _) in enumerate(qq_results[:5], 1):
                result_lines.append(f"{i}. {name} (ID: {emoji_id})")

        # 显示图片表情包
        if image_results:
            result_lines.append("\n🖼️ **图片表情包/贴纸:**")
            start_idx = len(qq_results) + 1
            for i, (emoji_type, name, _, _, _path) in enumerate(image_results[:5], start_idx):
                result_lines.append(f"{i}. {emoji_type}: {name}")

        if len(all_results) > 10:
            result_lines.append(f"\n... 还有 {len(all_results) - 10} 个未显示")

        result_lines.append("\n💡 **使用说明:**")
        result_lines.append("- 发送QQ表情: '发个{表情名}' 或 '发送表情 {表情名}'")
        result_lines.append("- 发送图片表情: '发个图片表情' 或 '发送图片表情 {名称}'")
        result_lines.append("- 随机表情: '随机表情' 或 '随机表情包'")

        return "\n".join(result_lines)

    async def _random_emoji(self, args: Dict[str, Any], context: ToolContext) -> str:
        """随机表情包"""
        category = args.get("category", "")
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id", self._get_default_target_id(context))
        emoji_type = args.get("emoji_type", "mixed")  # mixed: 混合, qq: QQ内置, image: 图片

        # 获取QQ客户端
        qq_client = getattr(context, "onebot_client", None)
        if not qq_client:
            return "❌ QQ客户端不可用"

        # 根据类型选择表情包
        if emoji_type == "qq" or (emoji_type == "mixed" and random.random() < 0.5):
            # 发送QQ内置表情
            if category and category in self.EMOJI_CATEGORIES:
                # 从指定分类中随机
                emoji_names = self.EMOJI_CATEGORIES[category]
                emoji_name = random.choice(emoji_names)
            else:
                # 完全随机
                emoji_name = random.choice(list(self.STANDARD_EMOJIS.keys()))

            emoji_id = self.STANDARD_EMOJIS[emoji_name]

            # 发送QQ表情
            try:
                result = await qq_client.send_face_message(
                    target_type=target_type, target_id=target_id, face_id=emoji_id
                )

                if result and result.get("status") == "ok":
                    target_desc = f"群 {target_id}" if target_type == "group" else f"用户 {target_id}"
                    category_desc = f" ({category}类)" if category else ""
                    return f"✅ 随机QQ表情 '{emoji_name}'{category_desc} 已发送到 {target_desc}"
                else:
                    return f"❌ 随机QQ表情发送失败: {result}"

            except Exception as e:
                return f"❌ 随机QQ表情发送失败: {str(e)}"

        else:
            # 发送图片表情包
            try:
                from utils.emoji_manager import get_emoji_manager

                emoji_manager = get_emoji_manager()

                # 确定搜索类别
                search_category = None
                if category in [
                    "custom",
                    "miya_special",
                    "cute",
                    "reaction",
                    "seasonal",
                    "memes",
                ]:
                    search_category = category

                # 随机选择表情包或贴纸
                if random.random() < 0.5:
                    emoji_info = emoji_manager.get_random_emoji(search_category)
                    emoji_type_desc = "表情包"
                else:
                    emoji_info = emoji_manager.get_random_sticker(search_category)
                    emoji_type_desc = "贴纸"

                if not emoji_info:
                    # 回退到QQ内置表情
                    emoji_name = random.choice(list(self.STANDARD_EMOJIS.keys()))
                    emoji_id = self.STANDARD_EMOJIS[emoji_name]

                    result = await qq_client.send_face_message(
                        target_type=target_type, target_id=target_id, face_id=emoji_id
                    )

                    if result and result.get("status") == "ok":
                        target_desc = f"群 {target_id}" if target_type == "group" else f"用户 {target_id}"
                        category_desc = f" ({category}类)" if category else ""
                        return f"✅ 随机QQ表情 '{emoji_name}'{category_desc} 已发送到 {target_desc}"
                    else:
                        return f"❌ 随机表情发送失败: {result}"

                # 发送图片表情包
                with open(emoji_info["path"], "rb") as f:
                    image_data = f.read()

                result = await qq_client.send_image_message(
                    target_type=target_type,
                    target_id=target_id,
                    image_data=image_data,
                    image_name=emoji_info["name"],
                )

                if result and result.get("status") == "ok":
                    target_desc = f"群 {target_id}" if target_type == "group" else f"用户 {target_id}"
                    category_desc = f" ({search_category}类)" if search_category else ""
                    return f"✅ 随机{emoji_type_desc} '{emoji_info['name']}'{category_desc} 已发送到 {target_desc}"
                else:
                    return f"❌ 随机图片表情发送失败: {result}"

            except ImportError:
                # 表情包管理器未安装，使用QQ内置表情
                emoji_name = random.choice(list(self.STANDARD_EMOJIS.keys()))
                emoji_id = self.STANDARD_EMOJIS[emoji_name]

                result = await qq_client.send_face_message(
                    target_type=target_type, target_id=target_id, face_id=emoji_id
                )

                if result and result.get("status") == "ok":
                    target_desc = f"群 {target_id}" if target_type == "group" else f"用户 {target_id}"
                    category_desc = f" ({category}类)" if category else ""
                    return f"✅ 随机QQ表情 '{emoji_name}'{category_desc} 已发送到 {target_desc}"
                else:
                    return f"❌ 随机表情发送失败: {result}"

            except Exception as e:
                logger.error(f"随机图片表情发送失败: {e}", exc_info=True)
                return f"❌ 随机图片表情发送失败: {str(e)}"

    async def _list_emoji(self, args: Dict[str, Any], context: ToolContext) -> str:
        """列出表情包"""
        category = args.get("category", "")

        if category and category in self.EMOJI_CATEGORIES:
            # 列出指定分类的表情
            emoji_names = self.EMOJI_CATEGORIES[category]
            result_lines = [f"📂 {category} 分类表情 ({len(emoji_names)}个):"]

            for name in emoji_names:
                emoji_id = self.STANDARD_EMOJIS.get(name, 0)
                if emoji_id:
                    result_lines.append(f"  • {name} (ID: {emoji_id})")

        else:
            # 列出所有分类
            result_lines = ["📚 QQ表情包分类:"]
            for cat_name, emoji_names in self.EMOJI_CATEGORIES.items():
                result_lines.append(f"  📂 {cat_name}: {len(emoji_names)}个表情")

            result_lines.append("\n💡 查看具体分类: '列出{分类名}表情' 如'列出日常表情'")

        return "\n".join(result_lines)

    async def _manage_favorite(self, args: Dict[str, Any], context: ToolContext) -> str:
        """管理收藏的表情包"""
        user_id = context.user_id
        if not user_id:
            return "❌ 需要用户ID来管理收藏"

        emoji_name = args.get("emoji_name", "")
        emoji_id = args.get("emoji_id", 0)

        # 初始化用户收藏
        if user_id not in self.user_favorites:
            self.user_favorites[user_id] = []

        if emoji_name or emoji_id:
            # 添加收藏
            if emoji_id and 1 <= emoji_id <= 333:
                emoji_name = self._get_emoji_name_by_id(emoji_id)
            elif emoji_name:
                emoji_id = self.STANDARD_EMOJIS.get(emoji_name, 0)

            if not emoji_id:
                return f"❌ 未找到表情: {emoji_name}"

            # 检查是否已收藏
            for fav in self.user_favorites[user_id]:
                if fav.get("emoji_id") == emoji_id:
                    return f"✅ 表情 '{emoji_name}' 已在收藏列表中"

            # 添加收藏
            self.user_favorites[user_id].append(
                {
                    "emoji_name": emoji_name,
                    "emoji_id": emoji_id,
                    "added_at": datetime.now().isoformat(),
                }
            )

            return f"✅ 已收藏表情: {emoji_name} (ID: {emoji_id})"
        else:
            # 列出收藏
            favorites = self.user_favorites.get(user_id, [])
            if not favorites:
                return "📭 您还没有收藏任何表情"

            result_lines = [f"❤️ 您的收藏表情 ({len(favorites)}个):"]
            for i, fav in enumerate(favorites, 1):
                result_lines.append(f"{i}. {fav['emoji_name']} (ID: {fav['emoji_id']})")

            return "\n".join(result_lines)

    def _get_default_target_id(self, context: ToolContext) -> int:
        """获取默认目标ID"""
        if context.group_id:
            return context.group_id
        elif context.user_id:
            return context.user_id
        else:
            return 0

    def _get_emoji_name_by_id(self, emoji_id: int) -> str:
        """根据表情ID获取表情名称"""
        for name, eid in self.STANDARD_EMOJIS.items():
            if eid == emoji_id:
                return name
        return f"未知表情{emoji_id}"

    def _fuzzy_match_emoji(self, keyword: str) -> Optional[str]:
        """模糊匹配表情名称"""
        keyword = keyword.lower()

        # 先尝试精确匹配
        for name in self.STANDARD_EMOJIS:
            if keyword == name.lower():
                return name

        # 尝试包含匹配
        for name in self.STANDARD_EMOJIS:
            if keyword in name.lower():
                return name

        # 尝试翻译匹配（常见别称）
        aliases = {
            "笑脸": "微笑",
            "哭脸": "大哭",
            "笑哭": "笑哭",
            "狗头": "doge",
            "捂脸": "捂脸",
            "点赞": "强",
            "666": "强",
            "鼓掌": "鼓掌",
            "哈哈": "大笑",
            "呵呵": "呵呵哒",
            "拜拜": "再见",
            "爱心": "爱心",
            "心": "爱心",
            "生气": "发怒",
            "怒": "发怒",
            "惊讶": "惊讶",
            "吓": "吓",
            "亲": "亲亲",
            "抱": "拥抱",
            "ok": "OK",
            "okay": "OK",
            "胜利": "胜利",
            "耶": "胜利",
        }

        return aliases.get(keyword)

    def _record_emoji_usage(self, emoji_name: str, emoji_id: int, context: ToolContext):
        """记录表情包使用统计"""
        user_id = context.user_id
        if not user_id:
            return

        if emoji_id not in self.emoji_stats:
            self.emoji_stats[emoji_id] = {
                "name": emoji_name,
                "total_uses": 0,
                "user_uses": {},
                "last_used": None,
            }

        stats = self.emoji_stats[emoji_id]
        stats["total_uses"] += 1
        stats["last_used"] = datetime.now().isoformat()

        if user_id not in stats["user_uses"]:
            stats["user_uses"][user_id] = 0
        stats["user_uses"][user_id] += 1

        logger.debug(f"表情使用统计: {emoji_name} 被用户 {user_id} 使用，总次数: {stats['total_uses']}")

    async def _smart_emoji(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        智能表情包发送
        根据用户消息语义自动判断是否发送表情包，以及发送什么表情包
        """
        try:
            message = args.get("message", "")
            target_type = args.get("target_type", "group")
            target_id = args.get("target_id", self._get_default_target_id(context))

            if not message:
                user_message = getattr(context, "raw_message", "") or ""
                message = user_message

            from utils.emoji_manager import get_emoji_manager

            emoji_manager = get_emoji_manager()

            analysis = emoji_manager.analyze_message(message)

            if not analysis["should_send"]:
                return ""

            emoji_info = emoji_manager.get_emoji_by_context(message)

            if not emoji_info:
                return ""

            qq_client = getattr(context, "onebot_client", None)
            if not qq_client:
                return "❌ QQ客户端不可用"

            emoji_path = emoji_info["path"]
            emoji_name = emoji_info["name"]

            if os.path.exists(emoji_path):
                with open(emoji_path, "rb") as f:
                    image_data = f.read()

                result = await qq_client.send_image_message(
                    target_type=target_type,
                    target_id=target_id,
                    image_data=image_data,
                    image_name=emoji_name,
                )

                if result and result.get("status") == "ok":
                    suggested_tags = ", ".join(analysis["suggested_tags"][:3])
                    return f"[智能表情] 基于'{suggested_tags}'发送了表情包"
                else:
                    return "❌ 发送失败"
            else:
                return "❌ 表情包文件不存在"

        except ImportError:
            logger.warning("表情包管理器导入失败，使用随机表情")
            return await self._random_emoji(args, context)
        except Exception as e:
            logger.error(f"智能表情包发送失败: {e}", exc_info=True)
            return f"❌ 智能表情包发送失败: {str(e)}"

    async def _analyze_message(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        分析消息，返回语义分析结果
        用于调试和了解弥娅如何理解用户消息
        """
        try:
            message = args.get("message", "")

            if not message:
                user_message = getattr(context, "raw_message", "") or ""
                message = user_message

            if not message:
                return "❌ 请提供要分析的消息"

            from utils.emoji_manager import get_emoji_manager

            emoji_manager = get_emoji_manager()

            analysis = emoji_manager.analyze_message(message)

            result_lines = ["📊 **消息语义分析结果**"]
            result_lines.append(f"\n原始消息: {message}")

            if analysis["sentiment"]:
                sentiments = sorted(analysis["sentiment"].items(), key=lambda x: x[1], reverse=True)
                sentiment_str = ", ".join([f"{k}({v:.1%})" for k, v in sentiments[:3]])
                result_lines.append(f"\n💭 情感倾向: {sentiment_str}")
            else:
                result_lines.append("\n💭 情感倾向: 无明显情感")

            if analysis["context_type"]:
                result_lines.append(f"📝 上下文类型: {', '.join(analysis['context_type'])}")

            if analysis["keywords"]:
                result_lines.append(f"🔑 关键词: {', '.join(analysis['keywords'][:5])}")

            if analysis["suggested_tags"]:
                result_lines.append(f"🏷️ 建议标签: {', '.join(analysis['suggested_tags'])}")

            result_lines.append(f"\n🤔 是否发送表情: {'是' if analysis['should_send'] else '否'}")
            if analysis["should_send"]:
                result_lines.append(f"📊 置信度: {analysis['confidence']:.1%}")

            search_results = emoji_manager.smart_search(message, limit=3)
            if search_results:
                result_lines.append("\n🔍 匹配的表情包:")
                for i, emoji in enumerate(search_results[:3], 1):
                    tags = emoji_manager.emoji_tags.get(emoji["path"], [])
                    tags_str = ", ".join(tags[:3]) if tags else "无标签"
                    result_lines.append(f"  {i}. {emoji['name']} [{tags_str}]")

            return "\n".join(result_lines)

        except ImportError:
            return "❌ 表情包管理器未安装"
        except Exception as e:
            logger.error(f"消息分析失败: {e}")
            return f"❌ 消息分析失败: {str(e)}"

    def is_emoji_request(self, text: str) -> bool:
        """检测是否为表情包请求"""
        text_lower = text.lower().strip()

        for trigger in SMART_EMOJI_TRIGGERS:
            if trigger in text_lower:
                return True

        if text_lower.startswith("发") and any(word in text_lower for word in ["表情", "图", "贴纸"]):
            return True

        if any(word in text_lower for word in ["随机", "来个"]):
            if any(word in text_lower for word in ["表情", "图", "贴纸"]):
                return True

        return False

    def should_auto_send(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        判断是否应该自动发送表情包

        Returns:
            (是否发送, 原因说明)
        """
        text_lower = text.lower()

        if self.is_emoji_request(text):
            return True, "明确的表情包请求"

        for pattern in AUTO_EMOJI_PATTERNS:
            if pattern in text_lower:
                return True, f"匹配到情感关键词: {pattern}"

        if ("?" in text or "？" in text) and random.random() < 0.2:
            return True, "疑问句，发送表情增加趣味"

        exclamation_count = sum(1 for c in text if c in "!~?")
        if exclamation_count >= 2:
            return True, "强烈情感表达"

        if len(text) <= 10 and any(word in text_lower for word in ["哈哈", "嘿嘿", "嘻嘻", "呀", "哦", "嗯", "好"]):
            return True, "短句配表情更可爱"

        return False, None
