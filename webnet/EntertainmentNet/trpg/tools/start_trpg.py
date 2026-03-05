"""
启动跑团模式工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any
from webnet.EntertainmentNet.game_mode import get_game_mode_manager, GameModeType


class StartTRPG(BaseTool):
    """启动跑团模式"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_trpg",
            "description": "启动 TRPG 跑团模式。当用户说 '启动跑团'、'开始跑团'、'进入跑团模式'、'/trpg coc7'、'/trpg dnd5e'、'COC7跑团'、'DND5E跑团'、'跑团'、'COC7'、'DND5E'、'主持游戏'、'KP'、'守秘人'、'start_trpg'、'启动COC7跑团模式'、'你作为KP开始主持游戏' 等关键词时调用此工具。如果当前已在游戏模式中，会先退出再启动。只有管理员可以使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_system": {
                        "type": "string",
                        "enum": ["coc7", "dnd5e"],
                        "description": "规则系统（coc7 或 dnd5e）"
                    },
                    "session_name": {
                        "type": "string",
                        "description": "团名称（可选）"
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        # 获取参数
        rule_system = args.get("rule_system", "coc7")
        session_name = args.get("session_name", "未命名团")

        # 管理员权限检查（仅在群聊中）
        if context.group_id and hasattr(context, 'superadmin'):
            group_id = context.group_id
            user_id = context.user_id
            superadmin = context.superadmin

            # 检查是否为 superadmin
            is_superadmin = (superadmin and user_id == superadmin)
            self.logger.info(f"[StartTRPG] 权限检查: user_id={user_id}, superadmin={superadmin}, is_superadmin={is_superadmin}")

            # 检查用户是否为群管理员
            is_admin = False
            if hasattr(context, 'onebot_client') and context.onebot_client:
                try:
                    # QQNet对象有一个onebot_client属性指向底层的QQOneBotClient
                    client = context.onebot_client
                    if hasattr(client, 'onebot_client') and client.onebot_client:
                        client = client.onebot_client
                    
                    member_info = await client.get_group_member_info(
                        group_id=group_id,
                        user_id=user_id
                    )
                    is_admin = member_info.get('role', 'member') in ['admin', 'owner']
                    self.logger.info(f"[StartTRPG] 群管理员检查: role={member_info.get('role')}, is_admin={is_admin}")
                except Exception as e:
                    self.logger.warning(f"检查群管理员失败: {e}")

            # 只有 superadmin 或群管理员才能启动游戏模式
            if not is_superadmin and not is_admin:
                self.logger.warning(f"[StartTRPG] 权限拒绝: user_id={user_id}")
                return "⚠️ 只有群管理员或超级管理员才能启动跑团模式哦～"

        # 获取聊天ID
        chat_id = str(context.group_id or context.user_id)
        group_id = context.group_id
        user_id = context.user_id

        # 检查是否已在游戏模式中
        mode_manager = get_game_mode_manager()
        current_mode = mode_manager.get_mode(chat_id)
        if current_mode and current_mode.mode_type != GameModeType.NONE:
            # 检查是否是同类型的游戏模式重启(保留对话历史)
            if (current_mode.mode_type == GameModeType.TRPG and
                current_mode.extra_config.get('rule_system') == rule_system):
                # 同类型游戏模式重启,保留当前game_id和对话历史
                self.logger.info(f"[StartTRPG] 重新启动{rule_system}跑团模式,保留对话历史")
            else:
                # 不同类型游戏模式,先退出并保存
                mode_manager.exit_mode(chat_id, auto_save=True)
                self.logger.info(f"[StartTRPG] 已退出之前的游戏模式: {current_mode.mode_type.value}")

        # 获取会话管理器
        from ..session import get_session_manager
        session_manager = get_session_manager()

        session = session_manager.get_or_create(context.group_id or context.user_id)
        session.rule_system = rule_system
        session.session_name = session_name
        session_manager.save()

        # 激活游戏模式
        mode_manager = get_game_mode_manager()

        # 检查是否需要保留现有的 game_id (同类型重启)
        preserve_game_id = None
        if current_mode and current_mode.mode_type == GameModeType.TRPG:
            if current_mode.extra_config.get('rule_system') == rule_system:
                # 同类型重启,保留 game_id
                preserve_game_id = current_mode.game_id
                self.logger.info(f"[StartTRPG] 保留现有 game_id: {preserve_game_id}")

        # 调用 set_mode
        # 修复:使用正确的prompt_key(trpg_kp而非trpg_coc7,因为prompts目录中只有trpg_kp.txt)
        prompt_key_map = {
            "coc7": "trpg_kp",
            "dnd5e": "trpg_dnd"
        }
        mode_manager.set_mode(
            chat_id=chat_id,
            mode_type=GameModeType.TRPG,
            prompt_key=prompt_key_map.get(rule_system, "trpg_kp"),
            extra_config={
                'rule_system': rule_system,
                'session_name': session_name
            },
            create_game_memory=(preserve_game_id is None),  # 只有在需要保留 game_id 时不创建新游戏
            game_name=session_name,
            group_id=group_id,
            user_id=user_id,
            preserve_game_id=preserve_game_id  # 传递保留的 game_id
        )

        # 【核心改进】设置游戏状态为 NOT_STARTED
        # 游戏启动后还未开始，用户需要创建角色或加载存档
        from webnet.EntertainmentNet.game_mode.mode_state import GameState
        mode_manager.set_game_state(chat_id, GameState.NOT_STARTED)

        rule_names = {
            "coc7": "COC 7版",
            "dnd5e": "D&D 5E"
        }

        return f"""🎲 **跑团模式已启动**

**规则系统**：{rule_names.get(rule_system, rule_system)}
**团名称**：{session_name}

⚠️ **已进入沉浸式游戏模式**
• 现在只能使用跑团相关工具
• 其他功能暂时不可用
• 输入 `/exit` 可退出游戏模式

**可用指令**：
• /roll 3d6         - 投骰
• /sc 侦查 70        - 技能检定
• /rs 1d100 侦查     - 暗骰
• /pc create 名字    - 创建角色卡
• /pc show           - 查看角色卡
• /kp set_mode       - 设置 KP 模式
• /exit              - 退出游戏模式

开始你的冒险吧！🗡️"""
