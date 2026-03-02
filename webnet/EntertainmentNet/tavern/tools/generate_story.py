"""
生成故事工具
GenerateStory - 生成短篇故事（记录请求）
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.memory import TavernMemory


class GenerateStory(BaseTool):
    """生成故事工具 - 记录故事请求并返回提示信息"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "generate_story",
            "description": "记录用户的故事生成请求（实际故事生成由AI完成）",
            "parameters": {
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "description": "故事主题，如'恐怖探险'、'温馨日常'、'奇幻冒险'"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["horror", "warm", "fantasy", "scifi", "romance", "mystery"],
                        "description": "故事风格",
                        "default": "fantasy"
                    },
                    "length": {
                        "type": "string",
                        "enum": ["short", "medium", "long"],
                        "description": "故事长度",
                        "default": "short"
                    }
                },
                "required": ["theme"]
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        theme = args.get("theme", "")
        style = args.get("style", "fantasy")
        length = args.get("length", "short")
        chat_id = str(context.group_id or context.user_id)

        # 风格映射
        style_names = {
            "horror": "恐怖",
            "warm": "温馨",
            "fantasy": "奇幻",
            "scifi": "科幻",
            "romance": "浪漫",
            "mystery": "悬疑"
        }

        # 长度映射
        length_words = {
            "short": "300-500",
            "medium": "500-800",
            "long": "800-1200"
        }

        # 保存故事请求到记忆
        memory = TavernMemory()
        memory.add_message(chat_id, "system", f"[故事请求] 主题:{theme}, 风格:{style_names[style]}, 长度:{length}")

        # 返回确认信息，让 AI 继续生成故事
        return f"[已记录故事请求: {theme}，风格:{style_names[style]}，长度:{length_words[length]}字。现在AI将生成故事。]"
