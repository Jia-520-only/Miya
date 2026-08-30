"""
更新角色卡工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class UpdatePC(BaseTool):
    """更新角色卡工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "update_pc",
            "description": "更新角色卡的属性或状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "attribute": {
                        "type": "string",
                        "description": "属性名称，如 '力量', 'hp', 'mp', 'san'"
                    },
                    "value": {
                        "type": "integer",
                        "description": "新值或变化值"
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["set", "add", "subtract"],
                        "description": "操作类型：set=设置, add=增加, subtract=减少",
                        "default": "set"
                    }
                },
                "required": ["attribute", "value"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        attribute = args.get("attribute", "")
        value = args.get("value", 0)
        operation = args.get("operation", "set")
        group_id = context.group_id

        from ..character import get_character_manager

        character_manager = get_character_manager()
        pc = character_manager.get(context.user_id)

        if not pc:
            return "❌ 未找到角色卡，请先创建角色卡"

        state = pc.get_state(group_id)
        old_value = None

        # 根据属性类型处理
        if attribute in ['力量', 'strength']:
            old_value = pc.strength
            if operation == "set":
                pc.strength = value
            elif operation == "add":
                pc.strength += value
            elif operation == "subtract":
                pc.strength -= value
            pc.updated_at = pc.updated_at.__class__.now()

        elif attribute in ['hp', 'HP']:
            old_value = state.hp
            if operation == "set":
                state.hp = value
            elif operation == "add":
                state.hp = min(state.hp_max, state.hp + value)
            elif operation == "subtract":
                state.hp = max(0, state.hp - value)

        elif attribute in ['mp', 'MP']:
            old_value = state.mp
            if operation == "set":
                state.mp = value
            elif operation == "add":
                state.mp = min(state.mp_max, state.mp + value)
            elif operation == "subtract":
                state.mp = max(0, state.mp - value)

        elif attribute in ['san', 'SAN']:
            old_value = state.san
            if operation == "set":
                state.san = max(0, min(99, value))
            elif operation == "add":
                state.san = min(99, state.san + value)
            elif operation == "subtract":
                state.san = max(0, state.san - value)

        else:
            # 其他属性
            attr_map = {
                '敏捷': 'dexterity', 'dexterity': 'dexterity',
                '体质': 'constitution', 'constitution': 'constitution',
                '外貌': 'appearance', 'appearance': 'appearance',
                '智力': 'intelligence', 'intelligence': 'intelligence',
                '意志': 'power', 'power': 'power',
                '幸运': 'luck', 'luck': 'luck',
                '教育': 'education', 'education': 'education'
            }

            if attribute in attr_map:
                attr_name = attr_map[attribute]
                old_value = getattr(pc, attr_name)
                new_value = value if operation == "set" else (old_value + value if operation == "add" else old_value - value)
                setattr(pc, attr_name, new_value)
                pc.updated_at = pc.updated_at.__class__.now()

        character_manager.save()

        # 返回更新结果
        op_text = {"set": "设置为", "add": "增加", "subtract": "减少"}[operation]

        if old_value is not None:
            new_value = (value if operation == "set" else
                        (old_value + value if operation == "add" else old_value - value))
            return f"""✅ **角色卡已更新**

属性：{attribute}
{op_text}：{value}
旧值：{old_value}
新值：{new_value}

使用 /pc show 查看完整角色卡"""

        return f"❌ 不支持的属性：{attribute}"


class DeletePC(BaseTool):
    """删除角色卡工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "delete_pc",
            "description": "删除当前角色的角色卡",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirm": {
                        "type": "boolean",
                        "description": "确认删除，需要设为 true"
                    }
                },
                "required": ["confirm"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        confirm = args.get("confirm", False)

        if not confirm:
            return "❌ 删除操作需要确认，请设置 confirm=true"

        from ..character import get_character_manager

        character_manager = get_character_manager()
        pc = character_manager.get(context.user_id)

        if not pc:
            return "❌ 未找到角色卡"

        character_name = pc.character_name
        character_manager.delete(context.user_id)

        return f"""✅ **角色卡已删除**

角色：{character_name}

如需重新创建，请使用 /pc create 指令"""
