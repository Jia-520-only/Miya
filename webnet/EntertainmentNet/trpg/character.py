"""
角色卡系统
支持跨群角色卡共享
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path


@dataclass
class CharacterState:
    """角色状态（按群隔离）"""
    group_id: int           # 群号
    hp: int                 # 当前生命值
    hp_max: int             # 最大生命值
    mp: int                 # 当前魔法值
    mp_max: int             # 最大魔法值
    san: int                # 理智值
    temp_bonus: Dict[str, int] = field(default_factory=dict)  # 临时加值
    status_effects: List[str] = field(default_factory=list)  # 状态效果


@dataclass
class CharacterCard:
    """TRPG 角色卡"""

    # 基础信息
    player_id: int          # 玩家QQ号
    character_name: str     # 角色名
    rule_system: str       # 规则系统 (coc7, dnd5e, wod)

    # COC 7 属性
    strength: int = 50      # 力量
    dexterity: int = 50     # 敏捷
    constitution: int = 50  # 体质
    appearance: int = 50    # 外貌
    intelligence: int = 50  # 智力
    power: int = 50         # 意志
    luck: int = 50          # 幸运
    education: int = 50     # 教育

    # D&D 5E 属性
    dnd_strength: int = 10      # 力量
    dnd_dexterity: int = 10     # 敏捷
    dnd_constitution: int = 10   # 体质
    dnd_intelligence: int = 10  # 智力
    dnd_wisdom: int = 10        # 感知
    dnd_charisma: int = 10      # 魅力

    # 技能
    skills: Dict[str, int] = field(default_factory=dict)

    # 装备和物品
    inventory: List[str] = field(default_factory=list)

    # 跨群配置
    shared_across_groups: bool = False  # 是否跨群共享
    allowed_groups: List[int] = field(default_factory=list)  # 允许的群列表

    # 按群隔离的状态
    group_states: Dict[int, CharacterState] = field(default_factory=dict)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def get_state(self, group_id: int) -> CharacterState:
        """获取角色在指定群的状态"""
        if group_id not in self.group_states:
            # 默认初始化状态
            hp_max = self.constitution // 10
            mp_max = self.power // 5
            self.group_states[group_id] = CharacterState(
                group_id=group_id,
                hp=hp_max,
                hp_max=hp_max,
                mp=mp_max,
                mp_max=mp_max,
                san=99
            )
        return self.group_states[group_id]

    def update_state(self, group_id: int, **kwargs):
        """更新角色状态"""
        state = self.get_state(group_id)
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self.updated_at = datetime.now()

    def format_summary(self, group_id: int = None) -> str:
        """格式化显示角色卡摘要"""
        lines = [
            f"👤 角色：{self.character_name}",
            f"🎮 规则：{self.rule_system.upper()}",
            ""
        ]

        if self.rule_system == "coc7":
            lines.extend([
                "【基础属性】",
                f"力量：{self.strength:3d}  敏捷：{self.dexterity:3d}  体质：{self.constitution:3d}",
                f"外貌：{self.appearance:3d}  智力：{self.intelligence:3d}  意志：{self.power:3d}",
                f"幸运：{self.luck:3d}  教育：{self.education:3d}",
                ""
            ])

            if group_id:
                state = self.get_state(group_id)
                lines.extend([
                    "【当前状态】",
                    f"HP：{state.hp}/{state.hp_max}  MP：{state.mp}/{state.mp_max}  SAN：{state.san}"
                ])

        elif self.rule_system == "dnd5e":
            lines.extend([
                "【属性值】",
                f"力量：{self.dnd_strength:3d}  敏捷：{self.dnd_dexterity:3d}  体质：{self.dnd_constitution:3d}",
                f"智力：{self.dnd_intelligence:3d}  感知：{self.dnd_wisdom:3d}  魅力：{self.dnd_charisma:3d}",
                ""
            ])

        if self.skills:
            lines.append("\n【技能】")
            for skill, value in sorted(self.skills.items()):
                lines.append(f"{skill}：{value}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'player_id': self.player_id,
            'character_name': self.character_name,
            'rule_system': self.rule_system,
            'strength': self.strength,
            'dexterity': self.dexterity,
            'constitution': self.constitution,
            'appearance': self.appearance,
            'intelligence': self.intelligence,
            'power': self.power,
            'luck': self.luck,
            'education': self.education,
            'dnd_strength': self.dnd_strength,
            'dnd_dexterity': self.dnd_dexterity,
            'dnd_constitution': self.dnd_constitution,
            'dnd_intelligence': self.dnd_intelligence,
            'dnd_wisdom': self.dnd_wisdom,
            'dnd_charisma': self.dnd_charisma,
            'skills': self.skills,
            'inventory': self.inventory,
            'shared_across_groups': self.shared_across_groups,
            'allowed_groups': self.allowed_groups,
            'group_states': {
                gid: {
                    'group_id': s.group_id,
                    'hp': s.hp,
                    'hp_max': s.hp_max,
                    'mp': s.mp,
                    'mp_max': s.mp_max,
                    'san': s.san,
                    'temp_bonus': s.temp_bonus,
                    'status_effects': s.status_effects
                }
                for gid, s in self.group_states.items()
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class CharacterManager:
    """角色卡管理器"""

    def __init__(self, data_path: str = "data/trpg_characters.json"):
        self.data_path = Path(data_path)
        self.characters: Dict[int, CharacterCard] = {}  # player_id -> CharacterCard
        self.load()

    def load(self):
        """加载角色卡数据"""
        if self.data_path.exists():
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for char_data in data:
                        char = CharacterCard(
                            player_id=char_data['player_id'],
                            character_name=char_data['character_name'],
                            rule_system=char_data['rule_system'],
                            strength=char_data.get('strength', 50),
                            dexterity=char_data.get('dexterity', 50),
                            constitution=char_data.get('constitution', 50),
                            appearance=char_data.get('appearance', 50),
                            intelligence=char_data.get('intelligence', 50),
                            power=char_data.get('power', 50),
                            luck=char_data.get('luck', 50),
                            education=char_data.get('education', 50),
                            dnd_strength=char_data.get('dnd_strength', 10),
                            dnd_dexterity=char_data.get('dnd_dexterity', 10),
                            dnd_constitution=char_data.get('dnd_constitution', 10),
                            dnd_intelligence=char_data.get('dnd_intelligence', 10),
                            dnd_wisdom=char_data.get('dnd_wisdom', 10),
                            dnd_charisma=char_data.get('dnd_charisma', 10),
                            skills=char_data.get('skills', {}),
                            inventory=char_data.get('inventory', []),
                            shared_across_groups=char_data.get('shared_across_groups', False),
                            allowed_groups=char_data.get('allowed_groups', [])
                        )

                        # 恢复状态
                        for gid, state_data in char_data.get('group_states', {}).items():
                            char.group_states[int(gid)] = CharacterState(
                                group_id=int(gid),
                                hp=state_data['hp'],
                                hp_max=state_data['hp_max'],
                                mp=state_data['mp'],
                                mp_max=state_data['mp_max'],
                                san=state_data['san'],
                                temp_bonus=state_data.get('temp_bonus', {}),
                                status_effects=state_data.get('status_effects', [])
                            )

                        self.characters[char.player_id] = char
                    print(f"[CharacterManager] 加载了 {len(self.characters)} 个角色卡")
            except Exception as e:
                print(f"[CharacterManager] 加载失败: {e}")

    def save(self):
        """保存角色卡数据"""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            data = [char.to_dict() for char in self.characters.values()]
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CharacterManager] 保存失败: {e}")

    def create_empty_pc(self, player_id: int, name: str, rule_system: str) -> CharacterCard:
        """创建空角色卡"""
        char = CharacterCard(
            player_id=player_id,
            character_name=name,
            rule_system=rule_system
        )
        self.characters[player_id] = char
        self.save()
        return char

    def create_random_pc(self, player_id: int, name: str, rule_system: str) -> CharacterCard:
        """随机生成角色卡"""
        import random

        char = CharacterCard(
            player_id=player_id,
            character_name=name,
            rule_system=rule_system
        )

        if rule_system == "coc7":
            # COC7 属性随机生成
            char.strength = sum([random.randint(1, 6) for _ in range(5)]) * 5
            char.dexterity = sum([random.randint(1, 6) for _ in range(5)]) * 5
            char.constitution = sum([random.randint(1, 6) for _ in range(5)]) * 5
            char.appearance = sum([random.randint(1, 6) for _ in range(5)]) * 5
            char.intelligence = sum([random.randint(1, 6) for _ in range(2)]) * 5 + 10
            char.power = sum([random.randint(1, 6) for _ in range(5)]) * 5
            char.luck = sum([random.randint(1, 6) for _ in range(3)]) * 5
            char.education = sum([random.randint(1, 6) for _ in range(2)]) * 5 + 10

        elif rule_system == "dnd5e":
            # D&D 5E 属性随机生成 (4d6取高3)
            def roll_4d6_drop_lowest():
                rolls = sorted([random.randint(1, 6) for _ in range(4)], reverse=True)
                return sum(rolls[:3])

            char.dnd_strength = roll_4d6_drop_lowest()
            char.dnd_dexterity = roll_4d6_drop_lowest()
            char.dnd_constitution = roll_4d6_drop_lowest()
            char.dnd_intelligence = roll_4d6_drop_lowest()
            char.dnd_wisdom = roll_4d6_drop_lowest()
            char.dnd_charisma = roll_4d6_drop_lowest()

        self.characters[player_id] = char
        self.save()
        return char

    def get(self, player_id: int) -> Optional[CharacterCard]:
        """获取角色卡"""
        return self.characters.get(player_id)

    def delete(self, player_id: int):
        """删除角色卡"""
        if player_id in self.characters:
            del self.characters[player_id]
            self.save()

    def set_cross_group(self, player_id: int, enabled: bool, allowed_groups: List[int] = None):
        """设置跨群共享"""
        char = self.get(player_id)
        if char:
            char.shared_across_groups = enabled
            if allowed_groups:
                char.allowed_groups = allowed_groups
            self.save()

    def list_characters(self) -> List[CharacterCard]:
        """列出所有角色卡"""
        return list(self.characters.values())


# 全局单例
_character_manager = None


def get_character_manager() -> CharacterManager:
    """获取角色卡管理器单例"""
    global _character_manager
    if _character_manager is None:
        _character_manager = CharacterManager()
    return _character_manager
