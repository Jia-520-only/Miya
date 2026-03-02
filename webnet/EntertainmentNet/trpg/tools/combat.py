"""
战斗系统工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CombatLog:
    """战斗日志"""
    timestamp: datetime
    group_id: int
    actor: str           # 行动者
    action: str          # 动作描述
    target: str = ""     # 目标
    result: str = ""     # 结果
    damage: int = 0      # 伤害值


class CombatSystem:
    """战斗系统"""

    def __init__(self, data_path: str = "data/trpg_combat_logs.json"):
        self.data_path = data_path
        self.combat_logs: Dict[int, list] = {}  # group_id -> [CombatLog]
        self.active_combats: Dict[int, dict] = {}  # group_id -> combat_info
        self.load()

    def load(self):
        """加载战斗日志"""
        from pathlib import Path
        import json

        if Path(self.data_path).exists():
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for group_id, logs in data.items():
                        self.combat_logs[int(group_id)] = [
                            CombatLog(
                                timestamp=datetime.fromisoformat(log['timestamp']),
                                group_id=log['group_id'],
                                actor=log['actor'],
                                action=log['action'],
                                target=log.get('target', ''),
                                result=log.get('result', ''),
                                damage=log.get('damage', 0)
                            )
                            for log in logs
                        ]
                    print(f"[CombatSystem] 加载了 {len(self.combat_logs)} 个战斗记录")
            except Exception as e:
                print(f"[CombatSystem] 加载失败: {e}")

    def save(self):
        """保存战斗日志"""
        from pathlib import Path
        import json

        try:
            Path(self.data_path).parent.mkdir(parents=True, exist_ok=True)
            data = {
                str(gid): [
                    {
                        'timestamp': log.timestamp.isoformat(),
                        'group_id': log.group_id,
                        'actor': log.actor,
                        'action': log.action,
                        'target': log.target,
                        'result': log.result,
                        'damage': log.damage
                    }
                    for log in logs
                ]
                for gid, logs in self.combat_logs.items()
            }
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CombatSystem] 保存失败: {e}")

    def start_combat(self, group_id: int):
        """开始战斗"""
        self.active_combats[group_id] = {
            'started_at': datetime.now(),
            'round': 0,
            'turn': 0
        }
        return self.active_combats[group_id]

    def end_combat(self, group_id: int):
        """结束战斗"""
        if group_id in self.active_combats:
            del self.active_combats[group_id]
            return True
        return False

    def add_log(self, group_id: int, actor: str, action: str,
                target: str = "", result: str = "", damage: int = 0):
        """添加战斗日志"""
        if group_id not in self.combat_logs:
            self.combat_logs[group_id] = []

        log = CombatLog(
            timestamp=datetime.now(),
            group_id=group_id,
            actor=actor,
            action=action,
            target=target,
            result=result,
            damage=damage
        )
        self.combat_logs[group_id].append(log)
        self.save()

    def get_recent_logs(self, group_id: int, limit: int = 10) -> list:
        """获取最近的战斗日志"""
        if group_id not in self.combat_logs:
            return []
        return self.combat_logs[group_id][-limit:]


class Attack(BaseTool):
    """攻击工具"""

    def __init__(self):
        self.combat_system = CombatSystem()

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "attack",
            "description": "进行攻击检定",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "目标名称"
                    },
                    "attack_bonus": {
                        "type": "integer",
                        "description": "攻击加值",
                        "default": 0
                    },
                    "damage_dice": {
                        "type": "string",
                        "description": "伤害骰子，如 2d6",
                        "default": "1d6"
                    },
                    "damage_bonus": {
                        "type": "integer",
                        "description": "伤害加值",
                        "default": 0
                    }
                },
                "required": ["target"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        target = args.get("target", "")
        attack_bonus = args.get("attack_bonus", 0)
        damage_dice = args.get("damage_dice", "1d6")
        damage_bonus = args.get("damage_bonus", 0)
        group_id = context.group_id
        user_id = context.user_id

        from ..character import get_character_manager
        from ..dice import DiceEngine

        # 获取角色卡
        character_manager = get_character_manager()
        pc = character_manager.get(user_id)

        if not pc:
            return "❌ 请先创建角色卡"

        dice = DiceEngine()

        # 攻击检定
        attack_roll = dice.roll("1d20")
        attack_total = attack_roll.total + attack_bonus

        # 伤害检定
        damage_roll = dice.roll(damage_dice)
        damage_total = damage_roll.total + damage_bonus

        # 判断是否命中
        hit = attack_total >= 10
        critical = attack_roll.total == 20
        fumble = attack_roll.total == 1

        # 格式化结果
        actor_name = pc.character_name

        lines = [
            f"⚔️ **{actor_name} 攻击 {target}**",
            "",
            f"攻击检定：{attack_roll.detail} + {attack_bonus} = **{attack_total}**"
        ]

        if critical:
            lines.append("🌟 **暴击！**")
        elif fumble:
            lines.append("💀 **大失败！**")
        elif hit:
            lines.append("✅ **命中！**")
        else:
            lines.append("❌ **未命中**")

        if hit or critical:
            lines.append(f"伤害：{damage_roll.detail} + {damage_bonus} = **{damage_total}**")
        else:
            lines.append(f"伤害：{damage_total} (未命中)")

        # 记录战斗日志
        self.combat_system.add_log(
            group_id=group_id,
            actor=actor_name,
            action="攻击",
            target=target,
            result="暴击" if critical else ("大失败" if fumble else ("命中" if hit else "未命中")),
            damage=damage_total if hit else 0
        )

        return "\n".join(lines)


class CombatLog(BaseTool):
    """战斗日志工具"""

    def __init__(self):
        self.combat_system = CombatSystem()

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "combat_log",
            "description": "查看最近的战斗日志",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "显示的日志数量",
                        "default": 10
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        limit = args.get("limit", 10)
        group_id = context.group_id

        logs = self.combat_system.get_recent_logs(group_id, limit)

        if not logs:
            return "📝 暂无战斗记录"

        lines = ["📝 **最近战斗记录**\n"]

        for log in logs:
            time_str = log.timestamp.strftime("%H:%M:%S")
            if log.target:
                action_str = f"{log.action} {log.target}"
            else:
                action_str = log.action

            line = f"[{time_str}] {log.actor} {action_str}"
            if log.result:
                line += f" - {log.result}"
            if log.damage > 0:
                line += f" ({log.damage} 伤害)"

            lines.append(line)

        return "\n".join(lines)
