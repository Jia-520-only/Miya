"""
星座运势工具
"""
from typing import Dict, Any
import logging
import httpx
from webnet.tools.base import BaseTool, ToolContext
from core.constants import NetworkTimeout


logger = logging.getLogger(__name__)

# 星座名称映射（中文 -> 英文）
CONSTELLATION_MAP = {
    "白羊座": "aries",
    "金牛座": "taurus",
    "双子座": "gemini",
    "巨蟹座": "cancer",
    "狮子座": "leo",
    "处女座": "virgo",
    "天秤座": "libra",
    "天蝎座": "scorpio",
    "射手座": "sagittarius",
    "摩羯座": "capricorn",
    "水瓶座": "aquarius",
    "双鱼座": "pisces",
}

# 时间类型映射（中文 -> 英文）
TIME_TYPE_MAP = {
    "今日": "today",
    "本周": "week",
    "本月": "month",
    "本年": "year",
}

# 星座星级显示
STAR_MAP = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}

# API 配置
HOROSCOPE_API = "https://api.xygeng.cn/one/horoscope.php"


class Horoscope(BaseTool):
    """星座运势工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "horoscope",
            "description": "查询指定星座的今日、明日、本周或本月运势。重要：此工具返回的结果已经是格式化的完整运势信息，包含emoji、markdown等，直接返回给用户即可，不要添加额外说明或润色。",
            "parameters": {
                "type": "object",
                "properties": {
                    "constellation": {
                        "type": "string",
                        "description": f"星座名称：{', '.join(CONSTELLATION_MAP.keys())}",
                        "enum": list(CONSTELLATION_MAP.keys())
                    },
                    "time_type": {
                        "type": "string",
                        "description": f"时间类型：{', '.join(TIME_TYPE_MAP.keys())}",
                        "enum": list(TIME_TYPE_MAP.keys()),
                        "default": "今日"
                    }
                },
                "required": ["constellation"]
            }
        }

    async def _save_to_memory(self, fortune_text: str, constellation: str, time_type: str) -> str:
        """保存运势到记忆系统"""
        try:
            from memory.undefined_memory import get_undefined_memory_adapter
            from datetime import datetime

            adapter = get_undefined_memory_adapter()

            # 构建记忆内容（完整格式）
            tags = ["运势", "星座", constellation, time_type]

            # 保存完整的运势文本
            uuid = await adapter.add(fortune_text, tags)
            logger.info(f"运势已保存到记忆: {uuid}")
            return uuid

        except Exception as e:
            logger.warning(f"保存运势到记忆失败: {e}")
            return None

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """查询星座运势，优先使用 API，失败时使用本地数据"""
        constellation = args.get("constellation")
        time_type = args.get("time_type", "今日")

        if not constellation:
            return "❌ 星座不能为空"

        # 转换星座名称为英文
        constellation_en = CONSTELLATION_MAP.get(constellation, constellation)
        if constellation_en not in CONSTELLATION_MAP.values():
            return f"❌ 不支持的星座: {constellation}\n支持的星座: {', '.join(CONSTELLATION_MAP.keys())}"

        # 转换时间类型为英文
        time_type_en = TIME_TYPE_MAP.get(time_type, time_type)
        if time_type_en not in TIME_TYPE_MAP.values():
            return f"❌ 不支持的时间类型: {time_type}\n支持的时间类型: {', '.join(TIME_TYPE_MAP.keys())}"

        # 优先尝试从 API 获取
        try:
            params = {"type": constellation_en, "time": time_type_en}
            logger.info(
                f"获取星座运势: {constellation} ({constellation_en}), 时间: {time_type} ({time_type_en})"
            )

            async with httpx.AsyncClient(timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT) as client:
                response = await client.get(HOROSCOPE_API, params=params)
                response.raise_for_status()
                data = response.json()

            if data.get("code") != 200:
                raise ValueError(f"API 返回错误: {data.get('msg', '未知错误')}")

            fortune_data = data.get("data", {})

            # 格式化运势信息
            title = fortune_data.get("title", constellation)
            time_text = fortune_data.get("type", time_type)
            short_comment = fortune_data.get("shortcomment", "")
            date_text = fortune_data.get("time", "")

            # 运势评分
            fortune = fortune_data.get("fortune", {})
            fortune_stars = {
                "综合": STAR_MAP.get(fortune.get("all", 0), ""),
                "健康": STAR_MAP.get(fortune.get("health", 0), ""),
                "爱情": STAR_MAP.get(fortune.get("love", 0), ""),
                "财运": STAR_MAP.get(fortune.get("money", 0), ""),
                "工作": STAR_MAP.get(fortune.get("work", 0), ""),
            }

            # 运势指数
            index = fortune_data.get("index", {})

            # 运势文本
            fortunetext = fortune_data.get("fortunetext", {})

            # 幸运信息
            lucky_color = fortune_data.get("luckycolor", "")
            lucky_constellation = fortune_data.get("luckyconstellation", "")
            lucky_number = fortune_data.get("luckynumber", "")

            # 宜忌
            todo = fortune_data.get("todo", {})
            todo_yi = todo.get("ji", "")
            todo_ji = todo.get("yi", "")

            # 构建结果（现代格式）
            result = f"{constellation}{time_type}运势很不错哦！✨\n\n"

            result += "**今日运势亮点：**\n"
            result += f"- 🌟 **综合运势：{fortune_stars['综合']}**（{index.get('综合', 80)}%）精力充沛，思维敏捷\n"
            result += f"- 💖 **爱情运势：{fortune_stars['爱情']}**（{index.get('爱情', 85)}%）{short_comment}\n"
            result += f"- 💼 **工作运势：{fortune_stars['工作']}**（{index.get('工作', 78)}%）思路清晰，才华得到认可\n"
            result += f"- 💰 **财运：{fortune_stars['财运']}**（{index.get('财运', 75)}%）财务稳定\n"
            result += f"- ❤️ **健康：{fortune_stars['健康']}**（{index.get('健康', 88)}%）身体状态良好\n\n"

            result += "**今日小贴士：**\n"
            result += f"- 🎨 **幸运色：{lucky_color}** - 可以穿点{lucky_color}系衣服\n"
            result += f"- 🤝 **幸运星座：{lucky_constellation}** - 多和{lucky_constellation}朋友互动\n"
            result += f"- 🔢 **幸运数字：{lucky_number}**\n\n"

            if todo_yi or todo_ji:
                result += "**今日宜忌：**\n"
                if todo_yi:
                    result += f"- ✅ **宜：{todo_yi}**\n"
                if todo_ji:
                    result += f"- ❌ **忌：{todo_ji}**\n"

            result += "\n看起来今天是个充满机会和惊喜的日子！无论是工作、爱情还是生活，都顺风顺水～保持积极心态，勇敢追求目标吧！"

            # 保存到记忆系统
            await self._save_to_memory(result, constellation, time_type)

            logger.info("成功从 API 获取星座运势")
            return result

        except Exception as api_error:
            logger.warning(f"API 请求失败，降级使用本地数据: {api_error}")
            # API 失败，使用本地生成的运势
            return await self._get_local_fortune(constellation, time_type)


    async def _get_local_fortune(self, constellation: str, time_type: str) -> str:
        """生成本地星座运势"""
        import random

        # 随机生成运势数据
        fortune_stars = {
            "all": random.randint(3, 5),
            "health": random.randint(3, 5),
            "love": random.randint(3, 5),
            "money": random.randint(3, 5),
            "work": random.randint(3, 5),
        }

        stars_display = {
            "综合": STAR_MAP[fortune_stars["all"]],
            "健康": STAR_MAP[fortune_stars["health"]],
            "爱情": STAR_MAP[fortune_stars["love"]],
            "财运": STAR_MAP[fortune_stars["money"]],
            "工作": STAR_MAP[fortune_stars["work"]],
        }

        # 随机生成运势指数
        luck_color = random.choice(["红色", "蓝色", "绿色", "黄色", "紫色", "白色", "黑色"])
        luck_number = random.randint(1, 99)
        luck_constellation = random.choice(list(CONSTELLATION_MAP.keys()))

        # 根据星座生成通用建议
        advice_map = {
            "白羊座": "今天充满活力，适合开始新计划，但要注意控制情绪。",
            "金牛座": "财运不错，适合理财，感情方面需要多一点耐心。",
            "双子座": "沟通运佳，适合社交，工作上会有新的合作机会。",
            "巨蟹座": "家庭运旺，适合处理家务，感情上要主动表达。",
            "狮子座": "贵人运强，展示自己才华，但不要过于张扬。",
            "处女座": "注重细节会让工作出色，但不要过于苛求完美。",
            "天秤座": "人缘不错，适合社交活动，感情上会有桃花。",
            "天蝎座": "直觉敏锐，适合深入思考，工作上会有突破。",
            "射手座": "适合出行和学习，保持乐观态度，好运自然来。",
            "摩羯座": "工作运势强，专注目标会取得好成绩。",
            "水瓶座": "创意满满，适合创新项目，社交运也不错。",
            "双鱼座": "灵感丰富，适合艺术创作，感情上要真诚。"
        }

        short_comment = advice_map.get(constellation, "今天整体运势平稳，保持平常心。")

        # 构建结果（现代格式）
        result = f"{constellation}{time_type}运势很不错哦！✨\n\n"

        result += "**今日运势亮点：**\n"
        result += f"- 🌟 **综合运势：{stars_display['综合']}**（{fortune_stars['all']*20}%）精力充沛，思维敏捷\n"
        result += f"- 💖 **爱情运势：{stars_display['爱情']}**（{fortune_stars['love']*20}%）{short_comment}\n"
        result += f"- 💼 **工作运势：{stars_display['工作']}**（{fortune_stars['work']*20}%）思路清晰，才华得到认可\n"
        result += f"- 💰 **财运：{stars_display['财运']}**（{fortune_stars['money']*20}%）财务稳定\n"
        result += f"- ❤️ **健康：{stars_display['健康']}**（{fortune_stars['health']*20}%）身体状态良好\n\n"

        result += "**今日小贴士：**\n"
        result += f"- 🎨 **幸运色：{luck_color}** - 可以穿点{luck_color}系衣服\n"
        result += f"- 🤝 **幸运星座：{luck_constellation}** - 多和{luck_constellation}朋友互动\n"
        result += f"- 🔢 **幸运数字：{luck_number}**\n\n"

        result += "**建议**保持积极心态，把握机会，好运自然来！✨"

        # 保存到记忆系统
        await self._save_to_memory(result, constellation, time_type)

        return result
