"""
跑团角色卡搜索工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SearchTRPGCharacters(BaseTool):
    """搜索跑团角色卡"""

    def __init__(self):
        super().__init__()
        try:
            from webnet.EntertainmentNet.query.trpg_query_system import TRPGQuerySystem
            self.query_system = TRPGQuerySystem()
        except Exception as e:
            logger.error(f"初始化查询系统失败: {e}", exc_info=True)
            self.query_system = None

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_trpg_characters",
            "description": "搜索跑团角色卡，支持按角色名、技能、装备、规则系统等条件搜索。可以用来查找特定角色、对比属性、查找高技能角色等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，可以是角色名、技能名、装备名等，如'亚瑟'、'侦查'、'剑'等"
                    },
                    "rule_system": {
                        "type": "string",
                        "description": "限定特定规则系统，如'coc7'、'dnd5e'等"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "限定特定群组的角色卡"
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
        if self.query_system is None:
            return "❌ 查询系统未初始化"

        query = args.get("query", "").strip()
        rule_system = args.get("rule_system")
        group_id = args.get("group_id")
        limit = args.get("limit", 10)

        if not query:
            return "❌ 搜索查询不能为空"

        try:
            results = await self.query_system.search_characters(
                query=query,
                rule_system=rule_system,
                group_id=group_id,
                limit=limit
            )

            if not results:
                return f"🔍 未找到与 '{query}' 相关的角色卡"

            # 格式化结果
            result = f"🎭 跑团角色卡搜索结果: '{query}'\n共 {len(results)} 个匹配\n\n"

            for i, r in enumerate(results, 1):
                char = r['character_data']
                result += f"{i}. **{char['character_name']}** (相关性: {r['score']:.2f})\n"
                result += f"   👤 玩家ID: {char['player_id']}\n"
                result += f"   🎲 规则系统: {char.get('rule_system', 'N/A')}\n"

                # 显示核心属性
                attributes = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
                attr_names = {'strength': '力量', 'dexterity': '敏捷', 'constitution': '体质',
                              'intelligence': '智力', 'wisdom': '感知', 'charisma': '魅力'}

                result += "   📊 属性: "
                attrs = []
                for attr in attributes:
                    if attr in char and char[attr] > 0:
                        attrs.append(f"{attr_names.get(attr, attr)}:{char[attr]}")
                result += ', '.join(attrs) if attrs else '无\n'

                # 显示主要技能
                skills = char.get('skills', {})
                if skills:
                    top_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)[:3]
                    result += f"\n   🎯 主要技能: {', '.join([f'{k}({v})' for k, v in top_skills])}"

                result += "\n\n"

            return result

        except Exception as e:
            logger.error(f"搜索跑团角色卡失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"


class SearchTRPGByAttribute(BaseTool):
    """按属性搜索角色卡"""

    def __init__(self):
        super().__init__()
        try:
            from webnet.EntertainmentNet.query.trpg_query_system import TRPGQuerySystem
            self.query_system = TRPGQuerySystem()
        except Exception as e:
            logger.error(f"初始化查询系统失败: {e}", exc_info=True)
            self.query_system = None

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_trpg_by_attribute",
            "description": "按属性值搜索角色卡，例如查找力量大于80的角色、敏捷最高的角色等",
            "parameters": {
                "type": "object",
                "properties": {
                    "attribute_name": {
                        "type": "string",
                        "description": "属性名称，如'strength'（力量）、'dexterity'（敏捷）、'constitution'（体质）等"
                    },
                    "min_value": {
                        "type": "integer",
                        "description": "最低属性值"
                    },
                    "rule_system": {
                        "type": "string",
                        "description": "限定特定规则系统，如'coc7'、'dnd5e'等"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "限定特定群组的角色卡"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["attribute_name", "min_value"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        if self.query_system is None:
            return "❌ 查询系统未初始化"

        attribute_name = args.get("attribute_name", "").strip()
        min_value = args.get("min_value", 0)
        rule_system = args.get("rule_system")
        group_id = args.get("group_id")
        limit = args.get("limit", 10)

        if not attribute_name:
            return "❌ 属性名称不能为空"

        try:
            results = await self.query_system.search_by_attribute(
                attribute_name=attribute_name,
                min_value=min_value,
                rule_system=rule_system,
                group_id=group_id,
                sort_desc=True,
                limit=limit
            )

            if not results:
                return f"🔍 未找到 {attribute_name} ≥ {min_value} 的角色卡"

            # 属性名称映射
            attr_names = {'strength': '力量', 'dexterity': '敏捷', 'constitution': '体质',
                          'intelligence': '智力', 'wisdom': '感知', 'charisma': '魅力'}

            # 格式化结果
            attr_display = attr_names.get(attribute_name, attribute_name)
            result = f"📊 {attr_display}≥{min_value} 的角色卡\n共 {len(results)} 个匹配\n\n"

            for i, r in enumerate(results, 1):
                char = r['character_data']
                result += f"{i}. **{char['character_name']}** (玩家: {char['player_id']})\n"
                result += f"   💪 {attr_display}: {r['attribute_value']}\n"

                # 显示其他核心属性
                result += "   📊 其他属性: "
                attributes = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
                attrs = []
                for attr in attributes:
                    if attr in char and attr != attribute_name and char[attr] > 0:
                        attrs.append(f"{attr_names.get(attr, attr)}:{char[attr]}")
                result += ', '.join(attrs) if attrs else '无'

                result += "\n\n"

            return result

        except Exception as e:
            logger.error(f"按属性搜索失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"


class SearchTRPGBySkill(BaseTool):
    """按技能搜索角色卡"""

    def __init__(self):
        super().__init__()
        try:
            from webnet.EntertainmentNet.query.trpg_query_system import TRPGQuerySystem
            self.query_system = TRPGQuerySystem()
        except Exception as e:
            logger.error(f"初始化查询系统失败: {e}", exc_info=True)
            self.query_system = None

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_trpg_by_skill",
            "description": "按技能值搜索角色卡，例如查找侦查技能大于60的角色、潜行最高的角色等",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "技能名称，如'侦查'、'潜行'、'格斗'等"
                    },
                    "min_value": {
                        "type": "integer",
                        "description": "最低技能值",
                        "default": 0
                    },
                    "rule_system": {
                        "type": "string",
                        "description": "限定特定规则系统，如'coc7'、'dnd5e'等"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["skill_name"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        if self.query_system is None:
            return "❌ 查询系统未初始化"

        skill_name = args.get("skill_name", "").strip()
        min_value = args.get("min_value", 0)
        rule_system = args.get("rule_system")
        limit = args.get("limit", 10)

        if not skill_name:
            return "❌ 技能名称不能为空"

        try:
            results = await self.query_system.search_by_skill(
                skill_name=skill_name,
                min_value=min_value,
                rule_system=rule_system,
                limit=limit
            )

            if not results:
                return f"🔍 未找到 {skill_name}≥{min_value} 的角色卡"

            # 格式化结果
            result = f"🎯 {skill_name}≥{min_value} 的角色卡\n共 {len(results)} 个匹配\n\n"

            for i, r in enumerate(results, 1):
                char = r['character_data']
                result += f"{i}. **{char['character_name']}** (玩家: {char['player_id']})\n"
                result += f"   ⚔️ {r['skill_name']}: {r['skill_value']}\n"

                # 显示规则系统
                result += f"   🎲 规则系统: {char.get('rule_system', 'N/A')}\n"

                # 显示其他主要技能
                skills = char.get('skills', {})
                if skills:
                    top_skills = sorted([k for k, v in skills.items() if v >= 50])[:5]
                    result += f"   🎯 其他技能(≥50): {', '.join(top_skills)}" if top_skills else ""

                result += "\n\n"

            return result

        except Exception as e:
            logger.error(f"按技能搜索失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"
