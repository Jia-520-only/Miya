"""
KP 主持人指令工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class KPCommand(BaseTool):
    """KP 主持人指令工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "kp_command",
            "description": "KP 主持人指令：设置场景、NPC、线索、KP 模式等",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "set_scene",
                            "add_npc",
                            "remove_npc",
                            "list_npc",
                            "add_clue",
                            "list_clue",
                            "set_kp_mode",
                            "set_kp",
                            "set_phase",
                            "show_scene"
                        ],
                        "description": "指令动作"
                    },
                    "name": {
                        "type": "string",
                        "description": "名称（场景名、NPC名等）"
                    },
                    "description": {
                        "type": "string",
                        "description": "描述内容"
                    },
                    "kp_mode": {
                        "type": "string",
                        "enum": ["independent", "cross_group", "global"],
                        "description": "KP 模式"
                    },
                    "allowed_groups": {
                        "type": "string",
                        "description": "允许的群列表（用逗号分隔）"
                    },
                    "kp_id": {
                        "type": "integer",
                        "description": "KP 的 QQ 号"
                    },
                    "phase": {
                        "type": "string",
                        "enum": ["exploration", "combat", "interaction", "rest"],
                        "description": "当前阶段"
                    }
                },
                "required": ["action"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        action = args.get("action", "")
        group_id = context.group_id
        user_id = context.user_id

        from ..session import get_session_manager
        from ..scene import get_scene_manager

        session_manager = get_session_manager()
        scene_manager = get_scene_manager()

        # 检查是否是 KP
        session = session_manager.get(group_id)
        if session and session.get_kp_id() != user_id and action != "set_kp":
            return "❌ 只有 KP 才能执行此指令"

        # 根据动作处理
        if action == "set_scene":
            name = args.get("name", "新场景")
            description = args.get("description", "等待 KP 设置...")
            environment = args.get("environment", "")
            atmosphere = args.get("atmosphere", "")

            scene = scene_manager.set_scene(group_id, name, description, environment, atmosphere)
            return self._format_scene_info(scene)

        elif action == "add_npc":
            name = args.get("name", "")
            description = args.get("description", "")

            if not name or not description:
                return "❌ 请提供 NPC 名称和描述"

            npc = scene_manager.add_npc(group_id, name, description)
            if npc:
                return f"""✅ **NPC 已添加**

名称：{npc.name}
描述：{npc.description}

使用 /kp list_npc 查看所有 NPC"""

        elif action == "remove_npc":
            name = args.get("name", "")
            scene = scene_manager.get(group_id)

            if not scene or not scene.remove_npc(name):
                return f"❌ 未找到 NPC: {name}"

            scene_manager.save()
            return f"✅ NPC {name} 已删除"

        elif action == "list_npc":
            npcs = scene_manager.list_npcs(group_id)

            if not npcs:
                return "📝 当前场景没有 NPC"

            lines = ["📝 **NPC 列表**\n"]
            for i, npc in enumerate(npcs, 1):
                lines.append(f"{i}. **{npc.name}**")
                lines.append(f"   {npc.description}")
                if npc.personality:
                    lines.append(f"   性格：{npc.personality}")
                if npc.notes:
                    lines.append(f"   备注：{npc.notes}")
                lines.append("")

            return "\n".join(lines)

        elif action == "add_clue":
            content = args.get("description", "")

            if not content:
                return "❌ 请提供线索内容"

            clue = scene_manager.add_clue(group_id, content, hidden=True)
            if clue:
                return f"""✅ **线索已添加**

内容：{content}

使用 /kp list_clue 查看所有线索"""

        elif action == "list_clue":
            clues = scene_manager.list_clues(group_id)

            if not clues:
                return "📝 当前场景没有线索"

            lines = ["📝 **线索列表**\n"]
            for i, clue in enumerate(clues, 1):
                status = "🔒 [隐藏]" if clue.hidden else "✅ [已发现]"
                lines.append(f"{i}. {status}")
                lines.append(f"   {clue.content}")
                lines.append("")

            return "\n".join(lines)

        elif action == "set_kp_mode":
            kp_mode = args.get("kp_mode", "independent")
            allowed_groups_str = args.get("allowed_groups", "")

            if not session:
                session = session_manager.get_or_create(group_id)

            allowed_groups = []
            if allowed_groups_str:
                try:
                    allowed_groups = [int(g.strip()) for g in allowed_groups_str.split(",")]
                except:
                    return "❌ 群列表格式错误，请用逗号分隔，如：123456,789012"

            session.set_kp_mode(kp_mode, user_id, allowed_groups)

            mode_names = {
                "independent": "独立 KP 模式",
                "cross_group": "跨群 KP 模式",
                "global": "全局 KP 模式"
            }

            return f"""✅ **KP 模式已设置**

模式：{mode_names.get(kp_mode, kp_mode)}
KP：{user_id}
允许的群：{', '.join(map(str, allowed_groups)) if allowed_groups else '无'}"""

        elif action == "set_kp":
            kp_id = args.get("kp_id", 0)

            if not kp_id:
                return "❌ 请提供 KP 的 QQ 号"

            if not session:
                session = session_manager.get_or_create(group_id)

            session.kp_id = kp_id
            session_manager.save()

            return f"""✅ **KP 已设置**

KP：{kp_id}

现在 {kp_id} 可以使用 KP 指令了"""

        elif action == "set_phase":
            phase = args.get("phase", "exploration")

            if not session:
                session = session_manager.get_or_create(group_id)

            session.phase = phase
            session_manager.save()

            phase_names = {
                "exploration": "探索阶段",
                "combat": "战斗阶段",
                "interaction": "互动阶段",
                "rest": "休息阶段"
            }

            return f"""✅ **当前阶段已设置**

阶段：{phase_names.get(phase, phase)}"""

        elif action == "show_scene":
            scene = scene_manager.get(group_id)

            if not scene:
                return "❌ 当前没有场景，请使用 /kp set_scene 创建"

            return self._format_scene_info(scene)

        return f"❌ 未知的动作: {action}"

    def _format_scene_info(self, scene) -> str:
        """格式化场景信息"""
        lines = [
            f"📍 **{scene.name}**",
            "",
            f"{scene.description}",
            ""
        ]

        if scene.environment:
            lines.append(f"**环境**：{scene.environment}")
            lines.append("")

        if scene.atmosphere:
            lines.append(f"**氛围**：{scene.atmosphere}")
            lines.append("")

        if scene.npcs:
            lines.append("**NPC**：")
            for npc in scene.npcs:
                lines.append(f"• {npc.name} - {npc.description}")
            lines.append("")

        if scene.clues:
            hidden_count = sum(1 for c in scene.clues if c.hidden)
            found_count = len(scene.clues) - hidden_count
            lines.append(f"**线索**：{found_count}/{len(scene.clues)} 已发现")
            lines.append("")

        return "\n".join(lines)
