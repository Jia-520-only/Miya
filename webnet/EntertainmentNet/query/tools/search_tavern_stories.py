"""
酒馆故事搜索工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SearchTavernStories(BaseTool):
    """搜索酒馆故事"""

    def __init__(self):
        super().__init__()
        from webnet.EntertainmentNet.query.tavern_query_system import TavernQuerySystem
        self.query_system = TavernQuerySystem()

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_tavern_stories",
            "description": "搜索酒馆故事、对话记录和剧情内容。支持按角色、情绪、主题等条件筛选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或自然语言查询，如'浪漫的夜晚'、'神秘的客人'等"
                    },
                    "character_id": {
                        "type": "string",
                        "description": "限定搜索特定角色的故事，如'miya'"
                    },
                    "mood": {
                        "type": "string",
                        "description": "限定搜索特定情绪氛围，如'温馨'、'浪漫'、'悬疑'等"
                    },
                    "theme": {
                        "type": "string",
                        "description": "限定搜索特定主题"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["query"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        query = args.get("query", "").strip()
        character_id = args.get("character_id")
        mood = args.get("mood")
        theme = args.get("theme")
        limit = args.get("limit", 10)

        if not query:
            return "❌ 搜索查询不能为空"

        try:
            results = await self.query_system.search_stories(
                query=query,
                character_id=character_id,
                mood=mood,
                theme=theme,
                limit=limit
            )

            if not results:
                return f"🔍 未找到与 '{query}' 相关的故事"

            # 格式化结果
            result = f"📚 酒馆故事搜索结果: '{query}'\n共 {len(results)} 条匹配\n\n"

            for i, r in enumerate(results, 1):
                result += f"{i}. 【{r['type']}】 (相关性: {r['score']:.2f})\n"

                if r['type'] == 'story':
                    story = r['story']
                    result += f"   📖 主题: {story.get('theme', 'N/A')}\n"
                    result += f"   🎭 氛围: {story.get('mood', 'N/A')}\n"
                    content = story.get('content', 'N/A')
                    result += f"   📝 内容: {content[:100]}{'...' if len(content) > 100 else ''}\n"
                elif r['type'] == 'session_message':
                    msg = r['message']
                    role = msg.get('role', 'N/A')
                    content = msg.get('content', 'N/A')
                    result += f"   💬 {role}: {content[:100]}{'...' if len(content) > 100 else ''}\n"

                result += "\n"

            return result

        except Exception as e:
            logger.error(f"搜索酒馆故事失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"


class SearchTavernCharacters(BaseTool):
    """搜索酒馆角色"""

    def __init__(self):
        super().__init__()
        from webnet.EntertainmentNet.query.tavern_query_system import TavernQuerySystem
        self.query_system = TavernQuerySystem()

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_tavern_characters",
            "description": "搜索酒馆角色和NPC，支持按角色名、性格、背景、特质等条件搜索",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，可以是角色名、性格描述、背景故事等"
                    },
                    "personality_trait": {
                        "type": "string",
                        "description": "限定特定性格特质，如'温柔'、'神秘'等"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["query"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        query = args.get("query", "").strip()
        personality_trait = args.get("personality_trait")
        limit = args.get("limit", 10)

        if not query:
            return "❌ 搜索查询不能为空"

        try:
            results = await self.query_system.search_characters(
                query=query,
                personality_trait=personality_trait,
                limit=limit
            )

            if not results:
                return f"🔍 未找到与 '{query}' 相关的角色"

            # 格式化结果
            result = f"👥 酒馆角色搜索结果: '{query}'\n共 {len(results)} 个匹配\n\n"

            for i, r in enumerate(results, 1):
                char = r['character_data']
                result += f"{i}. **{char['name']}** (相关性: {r['score']:.2f})\n"
                result += f"   🎭 性格: {char.get('personality', 'N/A')}\n"
                background = char.get('background', 'N/A')
                result += f"   📖 背景: {background[:80]}{'...' if len(background) > 80 else ''}\n"
                traits = char.get('traits', [])
                result += f"   ✨ 特质: {', '.join(traits) if traits else '无'}\n\n"

            return result

        except Exception as e:
            logger.error(f"搜索酒馆角色失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"


class SearchTavernPreferences(BaseTool):
    """搜索玩家偏好"""

    def __init__(self):
        super().__init__()
        from webnet.EntertainmentNet.query.tavern_query_system import TavernQuerySystem
        self.query_system = TavernQuerySystem()

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_tavern_preferences",
            "description": "搜索酒馆玩家偏好设置，包括角色特质和故事偏好",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如'冒险'、'浪漫'等"
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "限定搜索特定用户的偏好"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["query"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        query = args.get("query", "").strip()
        user_id = args.get("user_id")
        limit = args.get("limit", 10)

        if not query:
            return "❌ 搜索查询不能为空"

        try:
            results = await self.query_system.search_player_preferences(
                query=query,
                user_id=user_id,
                limit=limit
            )

            if not results:
                return f"🔍 未找到与 '{query}' 相关的偏好"

            # 格式化结果
            result = f"💭 玩家偏好搜索结果: '{query}'\n共 {len(results)} 条匹配\n\n"

            for i, r in enumerate(results, 1):
                result += f"{i}. 【{r['type']}】 (玩家: {r['player_id']}, 相关性: {r['score']:.2f})\n"

                if r['type'] == 'trait':
                    result += f"   🎯 {r['trait_key']}: {r['trait_value']}\n"
                elif r['type'] == 'preference':
                    pref = r['preference']
                    result += f"   💝 {pref.get('preference', 'N/A')}\n"

                result += "\n"

            return result

        except Exception as e:
            logger.error(f"搜索玩家偏好失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"
