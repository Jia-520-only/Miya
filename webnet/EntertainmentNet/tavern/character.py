"""
酒馆角色管理
TavernCharacter - 管理酒馆中的角色和预设人设
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from core.constants import Encoding


@dataclass
class TavernCharacter:
    """酒馆角色"""
    character_id: str
    name: str
    personality: str           # 性格描述
    background: str            # 背景故事
    traits: List[str]          # 特质列表
    speaking_style: str        # 说话风格

    # 对话统计
    message_count: int = 0
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TavernCharacter':
        """从字典创建"""
        return cls(**data)


class CharacterManager:
    """角色管理器"""

    # 预设酒馆角色
    PRESET_CHARACTERS = {
        "miya": {
            "character_id": "miya",
            "name": "弥娅",
            "personality": "温柔、耐心、善于倾听，总是带着淡淡的微笑",
            "background": "一间深夜酒馆的老板娘，见过形形色色的客人，喜欢听客人们讲故事",
            "traits": ["温柔", "耐心", "善解人意", "神秘"],
            "speaking_style": "温暖亲切，带有人情味，偶尔会开玩笑，但不会过于喧闹"
        },
        "tavern_keeper": {
            "character_id": "tavern_keeper",
            "name": "老杰克",
            "personality": "豪爽、幽默、见多识广的老酒保",
            "background": "在酒馆工作了三十年，听过无数冒险故事",
            "traits": ["豪爽", "幽默", "经验丰富", "健谈"],
            "speaking_style": "豪爽直接，喜欢用方言，带着江湖气"
        },
        "mysterious_traveler": {
            "character_id": "mysterious_traveler",
            "name": "神秘旅人",
            "personality": "深沉、神秘、寡言少语",
            "background": "来自远方的旅人，身上背负着不为人知的秘密",
            "traits": ["神秘", "深沉", "智慧", "忧郁"],
            "speaking_style": "言简意赅，充满哲理，声音低沉"
        }
    }

    def __init__(self, storage_path: str = "data/tavern_characters.json"):
        self.storage_path = storage_path
        self._characters: Dict[str, TavernCharacter] = {}
        self._load()

    def _load(self):
        """加载角色数据"""
        try:
            with open(self.storage_path, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)
                for char_id, char_data in data.items():
                    self._characters[char_id] = TavernCharacter.from_dict(char_data)
        except (FileNotFoundError, json.JSONDecodeError):
            # 加载预设角色
            for char_id, char_data in self.PRESET_CHARACTERS.items():
                self._characters[char_id] = TavernCharacter(**char_data)
            self._save()

    def _save(self):
        """保存角色数据"""
        try:
            with open(self.storage_path, 'w', encoding=Encoding.UTF8) as f:
                data = {k: v.to_dict() for k, v in self._characters.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存角色数据失败: {e}")

    def get_character(self, character_id: str) -> Optional[TavernCharacter]:
        """获取角色"""
        return self._characters.get(character_id)

    def list_characters(self) -> List[str]:
        """列出所有角色ID"""
        return list(self._characters.keys())

    def create_character(
        self,
        character_id: str,
        name: str,
        personality: str,
        background: str,
        traits: List[str],
        speaking_style: str
    ) -> TavernCharacter:
        """创建新角色"""
        character = TavernCharacter(
            character_id=character_id,
            name=name,
            personality=personality,
            background=background,
            traits=traits,
            speaking_style=speaking_style
        )
        self._characters[character_id] = character
        self._save()
        return character

    def update_character(self, character_id: str, **kwargs) -> Optional[TavernCharacter]:
        """更新角色"""
        if character_id not in self._characters:
            return None

        character = self._characters[character_id]
        for key, value in kwargs.items():
            if hasattr(character, key):
                setattr(character, key, value)

        self._save()
        return character

    def delete_character(self, character_id: str) -> bool:
        """删除角色"""
        if character_id in self._characters:
            del self._characters[character_id]
            self._save()
            return True
        return False

    def get_character_prompt(self, character_id: str) -> str:
        """获取角色的提示词"""
        character = self.get_character(character_id)
        if not character:
            return ""

        prompt = f"""
你是{character.name}。

性格特质：{character.personality}

背景故事：{character.background}

你的特质：{', '.join(character.traits)}

说话风格：{character.speaking_style}

记住：
1. 始终保持角色设定
2. 回复要自然、简短、符合说话风格
3. 适度使用语气词和表情
4. 可以适当提及你的背景故事
5. 不要出戏，不要提及你是 AI
"""
        return prompt.strip()

    def record_message(self, character_id: str):
        """记录角色发言"""
        if character_id in self._characters:
            self._characters[character_id].message_count += 1
            self._characters[character_id].last_active = datetime.now().isoformat()
            self._save()
