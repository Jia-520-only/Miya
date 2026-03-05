"""
游戏模式记忆管理器
管理游戏模式的独立记忆分区

架构修复: 移除Token管理职责,委托给独立的TokenManager
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
import uuid
import shutil
from core.constants import Encoding


logger = logging.getLogger(__name__)


@dataclass
class CharacterCard:
    """角色卡数据"""
    character_id: str
    character_name: str
    player_id: int
    player_name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    skills: Dict[str, Any] = field(default_factory=dict)
    inventory: List[str] = field(default_factory=list)
    backstory: str = ""
    notes: str = ""
    is_public: bool = True  # 是否对其他玩家可见
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.character_id:
            self.character_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'CharacterCard':
        return cls(**data)


@dataclass
class GameMetadata:
    """游戏元数据"""
    game_id: str
    game_name: str
    rule_system: str  # coc7, dnd5e, tavern
    mode_type: str    # trpg, tavern
    group_id: Optional[int] = None
    user_id: Optional[int] = None  # 私聊时的用户ID
    created_at: str = ""
    updated_at: str = ""
    auto_save_enabled: bool = True

    def __post_init__(self):
        if not self.game_id:
            self.game_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'GameMetadata':
        return cls(**data)


@dataclass
class SaveData:
    """存档数据"""
    save_id: str
    game_id: str
    save_name: str
    story_progress: Dict[str, Any] = field(default_factory=dict)
    game_state: Dict[str, Any] = field(default_factory=dict)
    characters: List[Dict] = field(default_factory=list)
    permissions: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.save_id:
            self.save_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'SaveData':
        # 设置默认值
        return cls(
            save_id=data.get('save_id', str(uuid.uuid4())),
            game_id=data.get('game_id', ''),
            save_name=data.get('save_name', '未命名存档'),
            story_progress=data.get('story_progress', {}),
            game_state=data.get('game_state', {}),
            characters=data.get('characters', []),
            permissions=data.get('permissions', {}),
            created_at=data.get('created_at', '')
        )


class GameMemoryManager:
    """
    游戏记忆管理器

    职责:
    1. 管理游戏模式的独立记忆分区
    2. 支持多粒度存储(群/用户/游戏实例)
    3. 提供自动保存和手动保存接口
    4. 权限验证
    5. Token感知的智能对话压缩
    """

    def __init__(self, base_path: str = "data/game_memory", token_manager=None):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (self.base_path / "groups").mkdir(exist_ok=True)
        (self.base_path / "users").mkdir(exist_ok=True)
        (self.base_path / "archives").mkdir(exist_ok=True)

        # 内存缓存
        self._metadata_cache: Dict[str, GameMetadata] = {}
        self._characters_cache: Dict[str, List[CharacterCard]] = {}
        self._save_data_cache: Dict[str, SaveData] = {}

        # 架构修复: 委托Token管理给独立的TokenManager
        self.token_manager = token_manager

        logger.info(f"[GameMemoryManager] 初始化完成, 基础路径: {self.base_path}")

    # ==================== 游戏元数据管理 ====================

    def create_game(
        self,
        game_name: str,
        rule_system: str,
        mode_type: str,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        auto_save_enabled: bool = True
    ) -> str:
        """
        创建新游戏

        Args:
            game_name: 游戏名称
            rule_system: 规则系统(coc7, dnd5e, tavern)
            mode_type: 模式类型(trpg, tavern)
            group_id: 群号(群聊)
            user_id: 用户号(私聊)
            auto_save_enabled: 是否启用自动保存

        Returns:
            game_id
        """
        game_id = str(uuid.uuid4())

        metadata = GameMetadata(
            game_id=game_id,
            game_name=game_name,
            rule_system=rule_system,
            mode_type=mode_type,
            group_id=group_id,
            user_id=user_id,
            auto_save_enabled=auto_save_enabled
        )

        # 确定存储路径
        if group_id:
            game_dir = self.base_path / "groups" / str(group_id) / "games" / game_id
        elif user_id:
            game_dir = self.base_path / "users" / str(user_id) / "games" / game_id
        else:
            raise ValueError("必须提供 group_id 或 user_id")

        game_dir.mkdir(parents=True, exist_ok=True)

        # 保存元数据
        self._save_metadata(metadata, game_dir)

        # 初始化空数据文件
        (game_dir / "characters.json").write_text("[]", encoding=Encoding.UTF8)
        (game_dir / "story.json").write_text("{}", encoding=Encoding.UTF8)
        (game_dir / "save_data.json").write_text("{}", encoding=Encoding.UTF8)

        # 缓存
        self._metadata_cache[game_id] = metadata
        self._characters_cache[game_id] = []
        self._save_data_cache[game_id] = SaveData(
            save_id="autosave",
            game_id=game_id,
            save_name="自动存档"
        )

        logger.info(f"[GameMemoryManager] 创建游戏: {game_name} ({game_id})")
        return game_id

    def get_game_metadata(self, game_id: str) -> Optional[GameMetadata]:
        """获取游戏元数据"""
        # 先查缓存
        if game_id in self._metadata_cache:
            return self._metadata_cache[game_id]

        # 从文件加载
        metadata_path = self._find_game_path(game_id) / "meta.json"
        if metadata_path.exists():
            try:
                data = json.loads(metadata_path.read_text(encoding=Encoding.UTF8))
                metadata = GameMetadata.from_dict(data)
                self._metadata_cache[game_id] = metadata
                return metadata
            except Exception as e:
                logger.error(f"[GameMemoryManager] 加载元数据失败: {e}")

        return None

    def update_game_metadata(self, game_id: str, **kwargs) -> bool:
        """更新游戏元数据"""
        metadata = self.get_game_metadata(game_id)
        if not metadata:
            return False

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(metadata, key):
                setattr(metadata, key, value)

        metadata.updated_at = datetime.now().isoformat()

        # 保存到文件
        game_dir = self._find_game_path(game_id)
        self._save_metadata(metadata, game_dir)

        # 更新缓存
        self._metadata_cache[game_id] = metadata

        return True

    def list_games(
        self,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        mode_type: Optional[str] = None
    ) -> List[GameMetadata]:
        """
        列出游戏

        Args:
            group_id: 筛选群号
            user_id: 筛选用户号
            mode_type: 筛选模式类型

        Returns:
            游戏元数据列表
        """
        games = []

        # 扫描群游戏
        if group_id or user_id is None:
            groups_dir = self.base_path / "groups"
            if groups_dir.exists():
                for group_path in groups_dir.iterdir():
                    if group_id and group_path.name != str(group_id):
                        continue

                    games_dir = group_path / "games"
                    if games_dir.exists():
                        for game_dir in games_dir.iterdir():
                            metadata = self.get_game_metadata(game_dir.name)
                            if metadata and (mode_type is None or metadata.mode_type == mode_type):
                                games.append(metadata)

        # 扫描用户游戏
        if user_id or group_id is None:
            users_dir = self.base_path / "users"
            if users_dir.exists():
                for user_path in users_dir.iterdir():
                    if user_id and user_path.name != str(user_id):
                        continue

                    games_dir = user_path / "games"
                    if games_dir.exists():
                        for game_dir in games_dir.iterdir():
                            metadata = self.get_game_metadata(game_dir.name)
                            if metadata and (mode_type is None or metadata.mode_type == mode_type):
                                games.append(metadata)

        # 按创建时间排序
        games.sort(key=lambda x: x.created_at, reverse=True)
        return games

    def delete_game(self, game_id: str) -> bool:
        """删除游戏"""
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return False

        try:
            shutil.rmtree(game_dir)

            # 清除缓存
            if game_id in self._metadata_cache:
                del self._metadata_cache[game_id]
            if game_id in self._characters_cache:
                del self._characters_cache[game_id]
            if game_id in self._save_data_cache:
                del self._save_data_cache[game_id]

            logger.info(f"[GameMemoryManager] 删除游戏: {game_id}")
            return True
        except Exception as e:
            logger.error(f"[GameMemoryManager] 删除游戏失败: {e}")
            return False

    # ==================== 角色卡管理 ====================

    def add_character(self, game_id: str, character: CharacterCard) -> bool:
        """添加角色卡"""
        characters = self.get_characters(game_id)
        if characters is None:
            return False

        characters.append(character)
        self._save_characters(game_id, characters)

        # 更新缓存
        self._characters_cache[game_id] = characters

        logger.info(f"[GameMemoryManager] 添加角色: {character.character_name}")
        return True

    def get_characters(self, game_id: str) -> Optional[List[CharacterCard]]:
        """获取游戏的角色卡列表"""
        # 先查缓存
        if game_id in self._characters_cache:
            return self._characters_cache[game_id]

        # 从文件加载
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return None

        characters_file = game_dir / "characters.json"
        if characters_file.exists():
            try:
                data = json.loads(characters_file.read_text(encoding=Encoding.UTF8))
                characters = [CharacterCard.from_dict(d) for d in data]
                self._characters_cache[game_id] = characters
                return characters
            except Exception as e:
                logger.error(f"[GameMemoryManager] 加载角色卡失败: {e}")

        return []

    def get_character(self, game_id: str, character_id: str) -> Optional[CharacterCard]:
        """获取单个角色卡"""
        characters = self.get_characters(game_id)
        if not characters:
            return None

        for char in characters:
            if char.character_id == character_id:
                return char

        return None

    def update_character(self, game_id: str, character_id: str, **kwargs) -> bool:
        """更新角色卡"""
        characters = self.get_characters(game_id)
        if not characters:
            return False

        for char in characters:
            if char.character_id == character_id:
                # 更新字段
                for key, value in kwargs.items():
                    if hasattr(char, key):
                        setattr(char, key, value)

                char.updated_at = datetime.now().isoformat()
                self._save_characters(game_id, characters)
                return True

        return False

    def delete_character(self, game_id: str, character_id: str) -> bool:
        """删除角色卡"""
        characters = self.get_characters(game_id)
        if not characters:
            return False

        for i, char in enumerate(characters):
            if char.character_id == character_id:
                characters.pop(i)
                self._save_characters(game_id, characters)
                return True

        return False

    def get_visible_characters(
        self,
        game_id: str,
        player_id: int,
        is_admin: bool = False
    ) -> List[CharacterCard]:
        """
        获取可见的角色卡

        Args:
            game_id: 游戏ID
            player_id: 请求的玩家ID
            is_admin: 是否是管理员

        Returns:
            可见的角色卡列表
        """
        characters = self.get_characters(game_id)
        if not characters:
            return []

        if is_admin:
            # 管理员可以看到所有角色
            return characters

        # 普通玩家只能看到自己的角色和公开的角色
        visible = [
            char for char in characters
            if char.is_public or char.player_id == player_id
        ]

        return visible

    # ==================== 故事进度管理 ====================

    def update_story_progress(self, game_id: str, progress_data: Dict[str, Any]) -> bool:
        """更新故事进度"""
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return False

        story_file = game_dir / "story.json"

        try:
            # 合并现有数据
            if story_file.exists():
                existing = json.loads(story_file.read_text(encoding=Encoding.UTF8))
                existing.update(progress_data)
                progress_data = existing

            story_file.write_text(json.dumps(progress_data, ensure_ascii=False, indent=2), encoding=Encoding.UTF8)
            logger.debug(f"[GameMemoryManager] 更新故事进度: {game_id}")
            return True
        except Exception as e:
            logger.error(f"[GameMemoryManager] 更新故事进度失败: {e}")
            return False

    def get_story_progress(self, game_id: str) -> Dict[str, Any]:
        """获取故事进度"""
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return {}

        story_file = game_dir / "story.json"
        if story_file.exists():
            try:
                return json.loads(story_file.read_text(encoding=Encoding.UTF8))
            except Exception as e:
                logger.error(f"[GameMemoryManager] 加载故事进度失败: {e}")

        return {}

    # ==================== 存档管理 ====================

    def save_game(self, game_id: str, save_name: str = None) -> Optional[str]:
        """
        保存游戏

        Args:
            game_id: 游戏ID
            save_name: 存档名称(可选)

        Returns:
            save_id
        """
        metadata = self.get_game_metadata(game_id)
        if not metadata:
            return None

        # 收集数据
        characters = self.get_characters(game_id) or []
        story = self.get_story_progress(game_id)

        save_data = SaveData(
            save_id=str(uuid.uuid4()),
            game_id=game_id,
            save_name=save_name or f"存档_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            story_progress=story,
            game_state={"mode_type": metadata.mode_type, "rule_system": metadata.rule_system},
            characters=[char.to_dict() for char in characters],
            permissions={"auto_save": metadata.auto_save_enabled}
        )

        # 保存到文件
        game_dir = self._find_game_path(game_id)
        save_file = game_dir / "save_data.json"

        try:
            save_file.write_text(json.dumps(save_data.to_dict(), ensure_ascii=False, indent=2), encoding=Encoding.UTF8)
            self._save_data_cache[game_id] = save_data

            logger.info(f"[GameMemoryManager] 保存游戏: {save_name} ({save_data.save_id})")
            return save_data.save_id
        except Exception as e:
            logger.error(f"[GameMemoryManager] 保存游戏失败: {e}")
            return None

    def load_game(self, game_id: str) -> Optional[SaveData]:
        """加载游戏存档"""
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return None

        save_file = game_dir / "save_data.json"
        if save_file.exists():
            try:
                data = json.loads(save_file.read_text(encoding=Encoding.UTF8))
                save_data = SaveData.from_dict(data)
                return save_data
            except Exception as e:
                logger.error(f"[GameMemoryManager] 加载存档失败: {e}")

        return None

    # ==================== 导出/导入 ====================

    def export_archive(self, game_id: str, archive_name: str = None) -> Optional[str]:
        """
        导出游戏存档

        Args:
            game_id: 游戏ID
            archive_name: 存档名称

        Returns:
            导出文件路径
        """
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return None

        metadata = self.get_game_metadata(game_id)
        if not metadata:
            return None

        archive_name = archive_name or f"{metadata.game_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        archive_path = self.base_path / "archives" / f"{archive_name}.json"

        try:
            # 收集所有数据
            archive_data = {
                "metadata": metadata.to_dict(),
                "characters": [char.to_dict() for char in (self.get_characters(game_id) or [])],
                "story": self.get_story_progress(game_id),
                "save_data": self.load_game(game_id).to_dict() if self.load_game(game_id) else None,
                "exported_at": datetime.now().isoformat()
            }

            # 保存到归档目录
            archive_path.write_text(json.dumps(archive_data, ensure_ascii=False, indent=2), encoding=Encoding.UTF8)

            logger.info(f"[GameMemoryManager] 导出存档: {archive_path}")
            return str(archive_path)

        except Exception as e:
            logger.error(f"[GameMemoryManager] 导出存档失败: {e}")
            return None

    def import_archive(
        self,
        archive_path: str,
        target_group_id: Optional[int] = None,
        target_user_id: Optional[int] = None
    ) -> Optional[str]:
        """
        导入游戏存档

        Args:
            archive_path: 归档文件路径
            target_group_id: 目标群号(可选)
            target_user_id: 目标用户号(可选)

        Returns:
            新的游戏ID
        """
        archive_file = Path(archive_path)
        if not archive_file.exists():
            return None

        try:
            data = json.loads(archive_file.read_text(encoding=Encoding.UTF8))

            # 重新创建游戏
            game_id = self.create_game(
                game_name=data["metadata"]["game_name"],
                rule_system=data["metadata"]["rule_system"],
                mode_type=data["metadata"]["mode_type"],
                group_id=target_group_id,
                user_id=target_user_id,
                auto_save_enabled=data["metadata"].get("auto_save_enabled", True)
            )

            # 恢复角色卡
            if data.get("characters"):
                characters = [CharacterCard.from_dict(char) for char in data["characters"]]
                self._save_characters(game_id, characters)
                self._characters_cache[game_id] = characters

            # 恢复故事进度
            if data.get("story"):
                self.update_story_progress(game_id, data["story"])

            # 恢复存档
            if data.get("save_data"):
                game_dir = self._find_game_path(game_id)
                save_file = game_dir / "save_data.json"
                save_file.write_text(json.dumps(data["save_data"], ensure_ascii=False, indent=2), encoding=Encoding.UTF8)

            logger.info(f"[GameMemoryManager] 导入存档: {game_id}")
            return game_id

        except Exception as e:
            logger.error(f"[GameMemoryManager] 导入存档失败: {e}")
            return None

    # ==================== Token估算工具 (架构修复: 委托给TokenManager) ====================

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量

        Args:
            text: 输入文本

        Returns:
            token数量
        """
        if self.token_manager:
            return self.token_manager.estimate_tokens(text)
        # 降级估算
        return len(text) // 2 + len(text.split())

    def estimate_conversation_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算对话列表的总token数

        Args:
            messages: 消息列表 [{'role': 'user', 'content': '...'}, ...]

        Returns:
            总token数
        """
        if self.token_manager:
            return self.token_manager.estimate_conversation_tokens(messages)
        # 降级估算
        total = 0
        for msg in messages:
            total += 10
            total += self.estimate_tokens(msg.get('content', ''))
        return total

    def estimate_conversation_history_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算对话历史的总token数(兼容方法名)

        Args:
            messages: 消息列表 [{'role': 'user', 'content': '...'}, ...]

        Returns:
            总token数
        """
        return self.estimate_conversation_tokens(messages)

    # ==================== 智能对话压缩 ====================

    async def compress_old_messages(
        self,
        game_id: str,
        target_tokens: int = 80000,
        compression_ratio: float = 0.3
    ) -> bool:
        """
        智能压缩旧对话消息

        压缩策略:
        1. 保留最近的消息(热数据)
        2. 将较旧的消息压缩成摘要(温数据)
        3. 保留关键事件标记

        Args:
            game_id: 游戏ID
            target_tokens: 目标token数(留出空间给其他内容)
            compression_ratio: 压缩比例(压缩多少旧消息)

        Returns:
            是否成功
        """
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return False

        conversation_file = game_dir / "conversation.json"
        if not conversation_file.exists():
            return False

        try:
            # 加载所有消息
            messages = json.loads(conversation_file.read_text(encoding=Encoding.UTF8))

            if len(messages) <= 20:
                # 消息数量太少,不需要压缩
                return True

            # 估算当前token数
            current_tokens = self.estimate_conversation_tokens(messages)
            logger.info(f"[GameMemoryManager] 当前对话token数: {current_tokens}")

            if current_tokens <= target_tokens:
                # 未超过限制,不需要压缩
                return True

            # 计算需要压缩的消息数量
            keep_messages = 15  # 保留最近15条完整消息
            compress_count = max(10, int(len(messages) * compression_ratio))

            # 分割消息
            to_compress = messages[:-keep_messages][-compress_count:]
            to_keep = messages[-keep_messages:]

            # 生成压缩摘要
            summary = await self._generate_summary(to_compress)

            # 创建摘要条目
            summary_message = {
                'role': 'system',
                'content': f"【对话摘要({to_compress[0].get('timestamp', '')} ~ {to_compress[-1].get('timestamp', '')})】\n{summary}",
                'timestamp': to_compress[-1].get('timestamp', ''),
                'is_summary': True
            }

            # 重组消息: 保留更旧的消息 + 摘要 + 保留最近的消息
            very_old_messages = messages[:len(messages) - keep_messages - compress_count]
            new_messages = very_old_messages + [summary_message] + to_keep

            # 保存压缩后的对话
            conversation_file.write_text(json.dumps(new_messages, ensure_ascii=False, indent=2), encoding=Encoding.UTF8)

            new_tokens = self.estimate_conversation_tokens(new_messages)
            logger.info(f"[GameMemoryManager] 对话压缩完成: {len(messages)} -> {len(new_messages)} 条消息")
            logger.info(f"[GameMemoryManager] Token数: {current_tokens} -> {new_tokens}")

            return True

        except Exception as e:
            logger.error(f"[GameMemoryManager] 压缩对话失败: {e}")
            return False

    async def _generate_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        生成对话摘要

        Args:
            messages: 消息列表

        Returns:
            摘要文本
        """
        # 提取对话内容
        dialogue = []
        for msg in messages:
            role_name = "玩家" if msg.get('role') == 'user' else "KP(弥娅)"
            dialogue.append(f"{role_name}: {msg.get('content', '')}")

        dialogue_text = "\n".join(dialogue)

        # 简单的关键词摘要(避免额外的AI调用)
        # TODO: 后续可以接入AI生成更智能的摘要
        summary_lines = []

        # 提取关键信息
        if "检定" in dialogue_text or "判定" in dialogue_text:
            summary_lines.append("• 进行了多项检定判定")
        if "战斗" in dialogue_text or "攻击" in dialogue_text:
            summary_lines.append("• 发生了战斗冲突")
        if "探索" in dialogue_text or "调查" in dialogue_text:
            summary_lines.append("• 进行了场景探索和调查")
        if "骰子" in dialogue_text or "投掷" in dialogue_text:
            summary_lines.append("• 进行了随机投掷")

        # 提取角色行动
        user_actions = [msg for msg in messages if msg.get('role') == 'user']
        if user_actions:
            summary_lines.append(f"• 玩家进行了{len(user_actions)}次行动")

        # 统计KP回复
        kp_responses = [msg for msg in messages if msg.get('role') == 'assistant']
        if kp_responses:
            summary_lines.append(f"• KP进行了{len(kp_responses)}次描述和回应")

        if not summary_lines:
            summary_lines.append("• 进行了常规对话交互")

        return "\n".join(summary_lines)

    # ==================== 对话历史管理(优化版) ====================

    def add_conversation_message(
        self,
        game_id: str,
        role: str,  # 'user' or 'assistant'
        content: str,
        player_id: Optional[int] = None,
        player_name: Optional[str] = None
    ) -> bool:
        """
        添加游戏对话消息

        Args:
            game_id: 游戏ID
            role: 角色 ('user' or 'assistant')
            content: 消息内容
            player_id: 玩家ID (user消息时)
            player_name: 玩家名称 (user消息时)

        Returns:
            是否成功
        """
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return False

        conversation_file = game_dir / "conversation.json"

        try:
            # 加载现有对话
            messages = []
            if conversation_file.exists():
                messages = json.loads(conversation_file.read_text(encoding=Encoding.UTF8))

            # 添加新消息
            message = {
                'role': role,
                'content': content,
                'timestamp': datetime.now().isoformat()
            }
            if role == 'user':
                message['player_id'] = player_id
                message['player_name'] = player_name

            messages.append(message)

            # Token感知的限制: 不是简单限制条数,而是估算token数
            max_tokens = 100000  # 总token限制(留出31072给其他内容)
            current_tokens = self.estimate_conversation_tokens(messages)

            if current_tokens > max_tokens:
                # 超过限制,触发压缩
                logger.warning(f"[GameMemoryManager] 对话token数 {current_tokens} 超过限制 {max_tokens}")
                # 移除最旧的非摘要消息(保留摘要)
                new_messages = []
                removed_count = 0
                for msg in messages:
                    if msg.get('is_summary'):
                        new_messages.append(msg)
                    elif len(new_messages) >= 40:  # 保留最近40条完整消息
                        removed_count += 1
                    else:
                        new_messages.append(msg)
                messages = new_messages
                logger.info(f"[GameMemoryManager] 移除了 {removed_count} 条旧消息以控制token数")

            # 保存
            conversation_file.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding=Encoding.UTF8)
            logger.debug(f"[GameMemoryManager] 添加对话消息: {game_id}, role={role}, total_messages={len(messages)}")
            return True
        except Exception as e:
            logger.error(f"[GameMemoryManager] 添加对话消息失败: {e}")
            return False

    def get_conversation_history(
        self,
        game_id: str,
        max_tokens: int = 80000
    ) -> List[Dict[str, str]]:
        """
        获取游戏对话历史(Token感知版本)

        Args:
            game_id: 游戏ID
            max_tokens: 最大token数(留出空间给其他内容)

        Returns:
            消息列表 [{'role': 'user', 'content': '...'}, ...]
        """
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return []

        conversation_file = game_dir / "conversation.json"
        if not conversation_file.exists():
            return []

        try:
            messages = json.loads(conversation_file.read_text(encoding=Encoding.UTF8))

            # Token感知的选择: 从最新开始累加,直到接近token限制
            result = []
            total_tokens = 0

            # 先保留摘要(系统消息)
            summaries = [msg for msg in messages if msg.get('is_summary')]
            for summary in summaries:
                summary_tokens = self.estimate_tokens(summary.get('content', ''))
                if total_tokens + summary_tokens <= max_tokens:
                    result.append({
                        'role': summary['role'],
                        'content': summary['content']
                    })
                    total_tokens += summary_tokens

            # 再添加最新消息(倒序遍历)
            recent_messages = [msg for msg in messages if not msg.get('is_summary')]
            for msg in reversed(recent_messages):
                msg_tokens = 10 + self.estimate_tokens(msg.get('content', ''))  # 10是角色标记token
                if total_tokens + msg_tokens <= max_tokens:
                    result.insert(len([s for s in result if not s['role'] == 'system']), {
                        'role': msg['role'],
                        'content': msg['content']
                    })
                    total_tokens += msg_tokens
                else:
                    break

            logger.debug(f"[GameMemoryManager] 获取对话历史: {game_id}, count={len(result)}, tokens={total_tokens}")
            return result
        except Exception as e:
            logger.error(f"[GameMemoryManager] 获取对话历史失败: {e}")
            return []

    # ==================== 辅助方法 ====================

    def _find_game_path(self, game_id: str) -> Path:
        """查找游戏目录"""
        # 先在群目录中查找
        groups_dir = self.base_path / "groups"
        if groups_dir.exists():
            for group_path in groups_dir.iterdir():
                game_path = group_path / "games" / game_id
                if game_path.exists():
                    return game_path

        # 再在用户目录中查找
        users_dir = self.base_path / "users"
        if users_dir.exists():
            for user_path in users_dir.iterdir():
                game_path = user_path / "games" / game_id
                if game_path.exists():
                    return game_path

        # 返回空路径
        return self.base_path / "temp" / game_id

    def _save_metadata(self, metadata: GameMetadata, game_dir: Path):
        """保存元数据"""
        meta_file = game_dir / "meta.json"
        meta_file.write_text(json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2), encoding=Encoding.UTF8)

    def _save_characters(self, game_id: str, characters: List[CharacterCard]):
        """保存角色卡"""
        game_dir = self._find_game_path(game_id)
        characters_file = game_dir / "characters.json"
        characters_file.write_text(
            json.dumps([char.to_dict() for char in characters], ensure_ascii=False, indent=2),
            encoding=Encoding.UTF8
        )
        self._characters_cache[game_id] = characters

    def clear_conversation_history(self, game_id: str) -> bool:
        """
        清空对话历史

        Args:
            game_id: 游戏ID

        Returns:
            是否成功
        """
        game_dir = self._find_game_path(game_id)
        if not game_dir.exists():
            return False

        conversation_file = game_dir / "conversation.json"
        try:
            if conversation_file.exists():
                conversation_file.unlink()
            logger.info(f"[GameMemoryManager] 清空对话历史: {game_id}")
            return True
        except Exception as e:
            logger.error(f"[GameMemoryManager] 清空对话历史失败: {e}")
            return False


# 全局单例
_game_memory_manager = None


def get_game_memory_manager() -> GameMemoryManager:
    """获取游戏记忆管理器单例"""
    global _game_memory_manager
    if _game_memory_manager is None:
        _game_memory_manager = GameMemoryManager()
    return _game_memory_manager
