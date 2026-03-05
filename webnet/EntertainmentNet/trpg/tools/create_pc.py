"""
创建角色卡工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class CreatePC(BaseTool):
    """创建角色卡工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "create_pc",
            "description": "创建 TRPG 角色卡，支持 COC7、DND5E 等规则系统",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名称"
                    },
                    "rule_system": {
                        "type": "string",
                        "enum": ["coc7", "dnd5e"],
                        "description": "规则系统"
                    },
                    "use_random": {
                        "type": "boolean",
                        "description": "是否随机生成属性",
                        "default": True
                    }
                },
                "required": ["name", "rule_system"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        name = args.get("name")
        rule_system = args.get("rule_system")
        use_random = args.get("use_random", True)
        user_id = context.user_id
        group_id = context.group_id

        from ..character import get_character_manager

        character_manager = get_character_manager()

        # 检查是否已有角色卡
        if character_manager.get(user_id):
            return f"❌ 你已经创建了角色卡，如需重新创建请先删除现有角色卡"

        # 创建角色卡
        if use_random:
            pc = character_manager.create_random_pc(user_id, name, rule_system)
        else:
            pc = character_manager.create_empty_pc(user_id, name, rule_system)

        # 【新功能】如果在游戏模式下，自动将角色添加到游戏中
        try:
            from ...game_mode import get_game_mode_manager
            from ...game_mode.game_memory_manager import get_game_memory_manager, CharacterCard as GameCharacterCard

            mode_manager = get_game_mode_manager()
            chat_id = str(group_id or user_id)
            current_mode = mode_manager.get_mode(chat_id)

            if current_mode and current_mode.game_id:
                game_memory_manager = get_game_memory_manager()

                # 将 TRPG CharacterCard 转换为游戏 CharacterCard
                game_character = GameCharacterCard(
                    character_id=pc.character_id,
                    character_name=pc.character_name,
                    player_id=pc.player_id,
                    player_name=pc.character_name,  # 使用角色名作为玩家名
                    attributes={
                        'hp': 10,  # COC7 默认 HP
                        'max_hp': 10,
                        'str': pc.strength,
                        'dex': pc.dexterity,
                        'con': pc.constitution,
                        'app': pc.appearance,
                        'int': pc.intelligence,
                        'pow': pc.power,
                        'edu': pc.education,
                        'luck': pc.luck
                    },
                    skills=pc.skills,
                    inventory=pc.inventory,
                    backstory="",
                    notes="",
                    is_public=True,
                    created_at=pc.created_at,
                    updated_at=pc.updated_at
                )

                # 将角色卡添加到游戏
                game_memory_manager.add_character(current_mode.game_id, game_character)
                self.logger.info(f"[CreatePC] 角色卡 {name} 已添加到游戏 {current_mode.game_id}")
        except Exception as e:
            self.logger.warning(f"[CreatePC] 添加角色卡到游戏失败: {e}")

        return f"""✅ **角色卡创建成功！**

{pc.format_summary(group_id)}

**提示**：
• 使用 /pc show 查看完整角色卡
• 使用 /pc cross_group on 开启跨群共享
• 使用 /pc update 更新角色属性"""
