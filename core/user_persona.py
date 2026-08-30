"""
弥娅用户侧写系统 (User Persona System)

自动从对话中提取并记忆用户特征：
- 用户基本信息（名字、昵称、身份）
- 兴趣爱好
- 习惯用语
- 情绪状态
- 群聊角色
- 与弥娅的互动历史

参考 Undefined 项目的认知记忆架构
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UserPersona:
    """用户侧写"""

    user_id: str = ""
    user_name: str = ""
    nicknames: List[str] = field(default_factory=list)
    group_id: str = ""
    group_name: str = ""

    # 基本信息
    age: str = ""
    birthday: str = ""
    location: str = ""
    occupation: str = ""

    # 兴趣爱好
    hobbies: List[str] = field(default_factory=list)
    favorite_games: List[str] = field(default_factory=list)
    favorite_animes: List[str] = field(default_factory=list)

    # 习惯
    speaking_style: str = ""
    common_phrases: List[str] = field(default_factory=list)

    # 互动统计
    message_count: int = 0
    last_interaction: str = ""
    total_interactions: int = 0

    # 【新增】行为模式学习
    active_hours: List[int] = field(default_factory=list)  # 活跃小时
    response_length_prefer: str = ""  # 响应长度偏好: short/medium/long
    emoji_frequency: int = 0  # 表情使用频率
    question_frequency: int = 0  # 提问频率

    # 备注
    notes: List[str] = field(default_factory=list)

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class GroupPersona:
    """群聊侧写"""

    group_id: str = ""
    group_name: str = ""
    member_count: int = 0

    # 群特点
    topic: str = ""
    atmosphere: str = ""

    # 互动统计
    message_count: int = 0
    last_interaction: str = ""

    # 群成员
    active_members: List[str] = field(default_factory=list)

    # 备注
    notes: List[str] = field(default_factory=list)

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class UserPersonaManager:
    """用户侧写管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.user_personas: Dict[str, UserPersona] = {}
        self.group_personas: Dict[str, GroupPersona] = {}
        self._storage_dir = Path("data/user_personas")
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # 加载已保存的侧写
        self._load_personas()

        logger.info("[用户侧写系统] 初始化完成")

    def _get_user_file(self, user_id: str) -> Path:
        """获取用户侧写存储文件"""
        return self._storage_dir / f"user_{user_id}.json"

    def _get_group_file(self, group_id: str) -> Path:
        """获取群聊侧写存储文件"""
        return self._storage_dir / f"group_{group_id}.json"

    def _load_personas(self):
        """加载已保存的侧写"""
        try:
            # 加载用户侧写
            for file in self._storage_dir.glob("user_*.json"):
                user_id = file.stem.replace("user_", "")
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        persona = UserPersona(**data)
                        self.user_personas[user_id] = persona
                except Exception as e:
                    logger.warning(f"[用户侧写系统] 加载用户侧写失败 {user_id}: {e}")

            # 加载群聊侧写
            for file in self._storage_dir.glob("group_*.json"):
                group_id = file.stem.replace("group_", "")
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        persona = GroupPersona(**data)
                        self.group_personas[group_id] = persona
                except Exception as e:
                    logger.warning(f"[用户侧写系统] 加载群聊侧写失败 {group_id}: {e}")

            logger.info(
                f"[用户侧写系统] 已加载 {len(self.user_personas)} 个用户侧写, {len(self.group_personas)} 个群聊侧写"
            )
        except Exception as e:
            logger.warning(f"[用户侧写系统] 加载侧写失败: {e}")

    def _save_user_persona(self, user_id: str):
        """保存用户侧写"""
        if user_id not in self.user_personas:
            return
        try:
            persona = self.user_personas[user_id]
            persona.updated_at = datetime.now().isoformat()
            with open(self._get_user_file(user_id), "w", encoding="utf-8") as f:
                json.dump(asdict(persona), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[用户侧写系统] 保存用户侧写失败 {user_id}: {e}")

    def _save_group_persona(self, group_id: str):
        """保存群聊侧写"""
        if group_id not in self.group_personas:
            return
        try:
            persona = self.group_personas[group_id]
            persona.updated_at = datetime.now().isoformat()
            with open(self._get_group_file(group_id), "w", encoding="utf-8") as f:
                json.dump(asdict(persona), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[用户侧写系统] 保存群聊侧写失败 {group_id}: {e}")

    def get_or_create_user_persona(self, user_id: str, user_name: str = "", group_id: str = "") -> UserPersona:
        """获取或创建用户侧写"""
        key = f"{group_id}:{user_id}" if group_id else user_id

        if key not in self.user_personas:
            self.user_personas[key] = UserPersona(
                user_id=str(user_id),
                user_name=user_name,
                group_id=str(group_id) if group_id else "",
            )

        # 更新用户名
        if user_name and user_name != self.user_personas[key].user_name:
            self.user_personas[key].user_name = user_name
            self._save_user_persona(key)

        return self.user_personas[key]

    def get_or_create_group_persona(self, group_id: str, group_name: str = "") -> GroupPersona:
        """获取或创建群聊侧写"""
        if group_id not in self.group_personas:
            self.group_personas[group_id] = GroupPersona(
                group_id=str(group_id),
                group_name=group_name,
            )

        # 更新群名
        if group_name and group_name != self.group_personas[group_id].group_name:
            self.group_personas[group_id].group_name = group_name
            self._save_group_persona(group_id)

        return self.group_personas[group_id]

    def update_from_message(
        self,
        user_id: str,
        user_name: str,
        group_id: Optional[str],
        group_name: Optional[str],
        message: str,
    ):
        """从消息中更新用户/群聊侧写"""
        now = datetime.now().isoformat()

        # 更新用户侧写
        user_key = f"{group_id}:{user_id}" if group_id else user_id

        persona = self.get_or_create_user_persona(user_id, user_name, group_id or "")

        # 更新统计
        persona.message_count += 1
        persona.last_interaction = now
        persona.total_interactions += 1

        # 提取名字（如果收到新的名字）
        if user_name and user_name != persona.user_name and user_name not in persona.nicknames:
            persona.nicknames.append(user_name)

        # 从消息中提取信息
        self._extract_info_from_message(persona, message)

        # 【新增】学习行为模式
        self._learn_behavior_pattern(persona, message)

        # 更新群聊侧写
        if group_id:
            group_persona = self.get_or_create_group_persona(group_id, group_name or "")
            group_persona.message_count += 1
            group_persona.last_interaction = now
            if user_id not in group_persona.active_members:
                group_persona.active_members.append(user_id)
            self._save_group_persona(group_id)

        # 保存
        self._save_user_persona(user_key)

    def _learn_behavior_pattern(self, persona: UserPersona, message: str):
        """学习用户行为模式"""
        if not message:
            return

        # 1. 学习活跃时间段
        current_hour = datetime.now().hour
        if current_hour not in persona.active_hours:
            persona.active_hours.append(current_hour)
        if len(persona.active_hours) > 20:
            persona.active_hours = persona.active_hours[-20:]

        # 2. 学习响应长度偏好
        msg_len = len(message)
        if msg_len < 10:
            persona.response_length_prefer = "short"
        elif msg_len < 50:
            persona.response_length_prefer = "medium"
        else:
            persona.response_length_prefer = "long"

        # 3. 学习表情使用频率
        if any(c in message for c in ["[", "]", "表情", "emoji"]):
            persona.emoji_frequency += 1

        # 4. 学习提问频率
        if (
            "?" in message
            or "？" in message
            or any(w in message for w in ["怎么", "为什么", "如何", "是不是", "能不能"])
        ):
            persona.question_frequency += 1

    def _extract_info_from_message(self, persona: UserPersona, message: str):
        """从消息中提取信息"""
        # 提取年龄
        age_patterns = [
            r"我今年(\d+)岁",
            r"我(\d+)岁",
            r"年龄(\d+)",
        ]
        for pattern in age_patterns:
            match = re.search(pattern, message)
            if match:
                persona.age = match.group(1) + "岁"
                break

        # 提取生日
        birthday_patterns = [
            r"生日(\d+月\d+日)",
            r"(\d+月\d+日)生日",
        ]
        for pattern in birthday_patterns:
            match = re.search(pattern, message)
            if match:
                persona.birthday = match.group(1)
                break

        # 提取位置
        location_patterns = [
            r"我在(.+?)家",
            r"住在(.+?)",
            r"(.+?)人",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, message)
            if match:
                location = match.group(1)
                if len(location) > 1:
                    persona.location = location
                break

        # 提取职业
        occupation_patterns = [
            r"我是(.+?)学生",
            r"我在(.+?)工作",
            r"做(.+?)的",
        ]
        for pattern in occupation_patterns:
            match = re.search(pattern, message)
            if match:
                persona.occupation = match.group(1)
                break

        # 提取游戏爱好
        games = ["原神", "星穹铁道", "鸣潮", "王者荣耀", "和平精英", "LOL", "Dota"]
        for game in games:
            if game in message and game not in persona.favorite_games:
                persona.favorite_games.append(game)

        # 提取动漫
        # 可以扩展更多

        # 提取喜欢的事物
        like_patterns = [
            r"我喜欢(.+?)[，。]",
            r"我爱(.+?)[，。]",
            r"最喜欢(.+?)[，。]",
        ]
        for pattern in like_patterns:
            match = re.search(pattern, message)
            if match:
                like = match.group(1)
                if len(like) > 1 and like not in persona.hobbies:
                    persona.hobbies.append(like)

    def build_user_context(self, user_id: str, group_id: Optional[str] = None) -> str:
        """构建用户侧写上下文"""
        key = f"{group_id}:{user_id}" if group_id else user_id

        if key not in self.user_personas:
            return ""

        persona = self.user_personas[key]
        lines = []

        # 名字
        if persona.user_name:
            lines.append(f"用户昵称: {persona.user_name}")
        if persona.nicknames:
            lines.append(f"其他昵称: {', '.join(persona.nicknames[:3])}")

        # 基本信息
        if persona.age:
            lines.append(f"年龄: {persona.age}")
        if persona.birthday:
            lines.append(f"生日: {persona.birthday}")
        if persona.location:
            lines.append(f"所在地: {persona.location}")
        if persona.occupation:
            lines.append(f"身份: {persona.occupation}")

        # 兴趣爱好
        if persona.favorite_games:
            lines.append(f"常玩游戏: {', '.join(persona.favorite_games)}")
        if persona.hobbies:
            lines.append(f"兴趣爱好: {', '.join(persona.hobbies[:3])}")

        # 互动统计
        if persona.total_interactions > 0:
            lines.append(f"历史互动: {persona.total_interactions}次")

        # 【新增】行为模式
        if persona.active_hours:
            lines.append(f"活跃时间段: {', '.join(map(str, persona.active_hours[-3:]))}点")
        if persona.response_length_prefer:
            lines.append(f"回复偏好: {persona.response_length_prefer}")
        if persona.emoji_frequency > 5:
            lines.append("使用表情: 频繁")
        if persona.question_frequency > 10:
            lines.append("喜欢提问")

        # 备注
        if persona.notes:
            lines.append(f"备注: {', '.join(persona.notes[:2])}")

        if not lines:
            return ""

        return "【用户侧写】\n" + "\n".join(lines)

    def build_group_context(self, group_id: str) -> str:
        """构建群聊侧写上下文"""
        if group_id not in self.group_personas:
            return ""

        persona = self.group_personas[group_id]
        lines = []

        # 群信息
        if persona.group_name:
            lines.append(f"群名称: {persona.group_name}")
        if persona.topic:
            lines.append(f"群主题: {persona.topic}")
        if persona.atmosphere:
            lines.append(f"群氛围: {persona.atmosphere}")

        # 成员
        if persona.active_members:
            lines.append(f"活跃成员数: {len(persona.active_members)}")

        # 互动统计
        if persona.message_count > 0:
            lines.append(f"消息数: {persona.message_count}")

        # 备注
        if persona.notes:
            lines.append(f"备注: {', '.join(persona.notes[:2])}")

        if not lines:
            return ""

        return "【群聊侧写】\n" + "\n".join(lines)

    def identify_user(self, user_id: str, group_id: Optional[str] = None) -> str:
        """识别用户身份 - 返回用户是谁"""
        key = f"{group_id}:{user_id}" if group_id else user_id

        if key not in self.user_personas:
            return ""

        persona = self.user_personas[key]

        # 优先使用名字
        if persona.user_name:
            return persona.user_name

        # 使用昵称
        if persona.nicknames:
            return persona.nicknames[0]

        return ""


def get_user_persona_manager() -> UserPersonaManager:
    """获取用户侧写管理器单例"""
    return UserPersonaManager()
