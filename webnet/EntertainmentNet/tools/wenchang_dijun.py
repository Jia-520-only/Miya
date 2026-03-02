"""
文昌帝君抽签工具
"""
from typing import Dict, Any
import logging
import random
import httpx
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)

# API 配置
WENCHANG_API = "https://api.xygeng.cn/one/wenchangdijunrandom.php"

# 文昌帝君灵签本地数据（当 API 不可用时使用）
FORTUNE_SIGNS = [
    {"id": 1, "title": "上上签", "poem": "苏秦佩剑出西游，联合诸邦志愿酬", "content": "此签大吉。学业有成，事业顺遂，贵人相助，心想事成。"},
    {"id": 2, "title": "中上签", "poem": "时运未来莫强求，且须放下钓鱼钩", "content": "此签中平。时机未到，宜守不宜攻，静待良机，切勿急躁。"},
    {"id": 3, "title": "中下签", "poem": "荷叶田田在水中，开花结籽满池红", "content": "此签中下。美景易逝，宜珍惜当下，把握机会，免留遗憾。"},
    {"id": 4, "title": "上签", "poem": "万里风鹏正举时，青云直上九天飞", "content": "此签大吉。前程似锦，一帆风顺，大展宏图，功成名就。"},
    {"id": 5, "title": "中签", "poem": "山重水复疑无路，柳暗花明又一村", "content": "此签中平。困境将解，转机将至，坚持不懈，必有收获。"},
    {"id": 6, "title": "上上签", "poem": "十年窗下无人问，一举成名天下知", "content": "此签大吉。刻苦努力必有回报，金榜题名，前程光明。"},
    {"id": 7, "title": "中签", "poem": "宝剑锋从磨砺出，梅花香自苦寒来", "content": "此签中平。经受考验方能成长，坚持不懈，终成正果。"},
    {"id": 8, "title": "上签", "poem": "春风得意马蹄疾，一日看尽长安花", "content": "此签大吉。运势亨通，万事顺心，春风得意，喜气洋洋。"},
    {"id": 9, "title": "中签", "poem": "路遥知马力，日久见人心", "content": "此签中平。时间能证明一切，贵在坚持，真诚待人必有回报。"},
    {"id": 10, "title": "上签", "poem": "海阔凭鱼跃，天高任鸟飞", "content": "此签大吉。前途广阔，自由发展，大有可为，施展才华。"},
    {"id": 11, "title": "中上签", "poem": "千里之行，始于足下", "content": "此签中平。从小事做起，脚踏实地，积少成多，终达目标。"},
    {"id": 12, "title": "上签", "poem": "春风送暖入屠苏，总把新桃换旧符", "content": "此签大吉。新年新气象，万象更新，喜庆连连，好运相伴。"},
    {"id": 13, "title": "中签", "poem": "莫道桑榆晚，为霞尚满天", "content": "此签中平。年龄不是障碍，晚年也能发光发热，老有所为。"},
    {"id": 14, "title": "上签", "poem": "天生我材必有用，千金散尽还复来", "content": "此签大吉。相信自己的才能，不要气馁，机遇终会到来。"},
    {"id": 15, "title": "中上签", "poem": "落红不是无情物，化作春泥更护花", "content": "此签中平。奉献精神值得敬佩，帮助他人亦是成就自己。"},
    {"id": 16, "title": "上签", "poem": "长风破浪会有时，直挂云帆济沧海", "content": "此签大吉。克服困难，勇往直前，必能到达成功的彼岸。"},
    {"id": 17, "title": "中签", "poem": "山不在高，有仙则名", "content": "此签中平。内在品质比外在条件更重要，修身养性，自然发光。"},
    {"id": 18, "title": "上签", "poem": "欲穷千里目，更上一层楼", "content": "此签大吉。不断进步，提升自己，站得更高，看得更远。"},
    {"id": 19, "title": "中上签", "poem": "海内存知己，天涯若比邻", "content": "此签中平。真挚友谊无距离，珍惜身边的朋友，互相扶持。"},
    {"id": 20, "title": "上签", "poem": "会当凌绝顶，一览众山小", "content": "此签大吉。登高望远，胸怀宽广，成就非凡，令人仰望。"},
]


def get_local_fortune() -> str:
    """获取本地抽签结果"""
    fortune = random.choice(FORTUNE_SIGNS)

    result = "🎋 **文昌帝君灵签结果** 🎋\n\n"
    result += f"**签号：** {fortune['id']}号\n"
    result += f"**签型：** {fortune['title']}\n\n"

    result += "**签诗：**\n"
    result += f"> {fortune['poem']}\n\n"

    result += "**解签：**\n"
    result += f"- {fortune['content']}\n\n"

    result += "愿文昌帝君庇佑，学业进步，前程似锦！🙏"

    return result


async def get_api_fortune() -> str:
    """从 API 获取抽签结果"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(WENCHANG_API)
        response.raise_for_status()
        data = response.json()

    if data.get("code") != 200:
        raise ValueError(f"API 返回错误: {data.get('msg')}")

    fortune_data = data.get("data", {})
    title = fortune_data.get("title", "")
    poem = fortune_data.get("poem", "")
    content = fortune_data.get("content", "")
    pic = fortune_data.get("pic", "")
    fortune_id = fortune_data.get("id", "")

    result = "🎋 **文昌帝君灵签结果** 🎋\n\n"
    result += f"**签号：** {fortune_id}号\n"
    result += f"**签型：** {title}\n\n"

    result += "**签诗：**\n"
    result += f"> {poem}\n\n"

    result += "**解签：**\n"
    result += f"- {content}\n"

    if pic:
        result += f"\n\n签文图片：{pic}"

    return result


class WenchangDijun(BaseTool):
    """文昌帝君抽签工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "wenchang_dijun",
            "description": "向文昌帝君祈福，抽取灵签，获取一段励志或考试相关的祝福语。用户说'抽个签'、'求签'等时应调用此工具。重要：此工具返回的结果已经是格式化的完整抽签结果，包含emoji、markdown等，直接返回给用户即可，不要添加额外说明或润色。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }

    async def _save_to_memory(self, fortune_text: str) -> str:
        """保存抽签结果到记忆系统"""
        try:
            from memory.undefined_memory import get_undefined_memory_adapter

            adapter = get_undefined_memory_adapter()

            # 构建记忆内容（完整格式）
            tags = ["抽签", "文昌帝君", "运势"]

            # 保存完整的抽签文本
            uuid = await adapter.add(fortune_text, tags)
            logger.info(f"抽签已保存到记忆: {uuid}")
            return uuid

        except Exception as e:
            logger.warning(f"保存抽签到记忆失败: {e}")
            return None

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """抽取文昌帝君灵签，优先使用 API，失败时使用本地数据"""
        try:
            logger.info("抽取文昌帝君灵签")

            # 优先尝试从 API 获取
            try:
                fortune_data = {}
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(WENCHANG_API)
                    response.raise_for_status()
                    data = response.json()

                if data.get("code") != 200:
                    raise ValueError(f"API 返回错误: {data.get('msg')}")

                fortune_data = data.get("data", {})

                logger.info("成功从 API 获取抽签结果")
                result = await get_api_fortune()
                # 保存到记忆系统
                await self._save_to_memory(result)
                return result
            except Exception as api_error:
                logger.warning(f"API 请求失败，降级使用本地数据: {api_error}")
                # API 失败，使用本地数据
                result = get_local_fortune()
                # 保存到记忆系统
                await self._save_to_memory(result)
                return result

        except Exception as e:
            logger.error(f"文昌帝君抽签失败: {e}", exc_info=True)
            return "抽签失败，请稍后重试"
