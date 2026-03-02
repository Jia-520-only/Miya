"""
续写故事工具
ContinueStory - 续写已有的故事（记录请求）
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.memory import TavernMemory


class ContinueStory(BaseTool):
    """续写故事工具 - 记录续写请求"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "continue_story",
            "description": "记录故事续写请求（实际续写由AI完成）",
            "parameters": {
                "type": "object",
                "properties": {
                    "continuation": {
                        "type": "string",
                        "description": "续写内容或方向"
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        continuation = args.get("continuation", "")
        chat_id = str(context.group_id or context.user_id)

        # 获取最近的对话，找最后一个故事
        memory = TavernMemory()
        recent_messages = memory.get_recent_messages(chat_id, limit=20)

        # 找到上一个故事
        last_story = None
        for msg in reversed(recent_messages):
            if msg.get("role") == "assistant" and "📖" in msg.get("content", ""):
                # 提取故事内容
                content = msg["content"]
                story_start = content.find("深夜故事")
                if story_start != -1:
                    # 提取故事正文（去掉开头和结尾）
                    story_content = content.split("***")[0]
                    if "📖" in story_content:
                        story_content = story_content.split("📖", 1)[1].strip()
                        if "**深夜故事**" in story_content:
                            story_content = story_content.split("**深夜故事**", 1)[1].strip()
                        last_story = story_content
                        break

        if not last_story:
            return "我找不到最近的故事呢...要不让我重新讲一个吧？🤔 ☕"

        # 保存续写请求
        memory.add_message(chat_id, "system", f"[续写请求] {continuation}")

        # 返回确认和故事内容，让 AI 继续生成续写
        if continuation:
            return f"[上一个故事:\n{last_story}\n\n续写要求: {continuation}\n\nAI现在生成续写内容。]"
        else:
            return f"[上一个故事:\n{last_story}\n\nAI现在自动续写故事。]"
