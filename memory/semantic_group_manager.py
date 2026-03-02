"""
弥娅 - 语义组管理器
从VCPToolBox浪潮RAG V3整合
实现语义组的动态管理和向量增强
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class SemanticGroup:
    """语义组"""
    name: str
    words: List[str] = field(default_factory=list)
    auto_learned: List[str] = field(default_factory=list)
    weight: float = 1.0
    vector_id: Optional[str] = None


@dataclass
class SemanticGroupConfig:
    """语义组配置"""
    config: Dict = field(default_factory=dict)
    groups: Dict[str, SemanticGroup] = field(default_factory=dict)


class SemanticGroupManager:
    """
    语义组管理器

    功能：
    1. 管理语义组配置
    2. 提供语义组向量增强
    3. 支持自动学习和权重调整
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化语义组管理器

        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = config_dir or Path(__file__).parent
        self.config_path = self.config_dir / 'semantic_groups.json'
        self.edit_path = self.config_dir / 'semantic_groups.edit.json'
        self.vectors_dir = self.config_dir / 'semantic_vectors'

        self.config: SemanticGroupConfig = SemanticGroupConfig()
        self.group_vector_cache: Dict[str, List[float]] = {}
        self.save_lock = False

        # 创建向量目录
        self.vectors_dir.mkdir(exist_ok=True)

        logger.info("[SemanticGroupManager] 初始化完成")

    async def initialize(self):
        """初始化，加载配置"""
        try:
            # 1. 同步.edit.json到主配置
            await self._synchronize_from_edit_file()

            # 2. 加载配置
            await self.load_groups()

            logger.info("[SemanticGroupManager] 初始化成功")
        except Exception as e:
            logger.error(f"[SemanticGroupManager] 初始化失败: {e}")

    async def _synchronize_from_edit_file(self):
        """从.edit.json同步到主配置文件"""
        if not self.edit_path.exists():
            return

        try:
            with open(self.edit_path, 'r', encoding='utf-8') as f:
                edit_data = json.load(f)

            logger.info("[SemanticGroupManager] 发现.edit.json，开始同步...")

            # 读取主配置（如果存在）
            main_data = None
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    main_data = json.load(f)

            # 比较核心数据是否发生变化
            if self._are_core_data_different(edit_data, main_data):
                logger.info(
                    "[SemanticGroupManager] .edit.json与主配置不同，执行智能合并..."
                )
                new_main_data = self._merge_group_data(edit_data, main_data)

                # 写入主配置
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(new_main_data, f, ensure_ascii=False, indent=2)

                logger.info("[SemanticGroupManager] 同步完成")
            else:
                logger.info("[SemanticGroupManager] .edit.json与主配置相同，无需同步")

        except Exception as e:
            logger.error(f"[SemanticGroupManager] 同步.edit.json失败: {e}")

    def _are_core_data_different(
        self,
        edit_data: Dict,
        main_data: Optional[Dict]
    ) -> bool:
        """比较核心数据是否不同"""
        if not main_data:
            return True  # 主配置不存在，肯定不同

        # 比较config部分
        edit_config = edit_data.get('config', {})
        main_config = main_data.get('config', {})
        if edit_config != main_config:
            return True

        # 比较groups部分
        edit_groups = edit_data.get('groups', {})
        main_groups = main_data.get('groups', {})

        if len(edit_groups) != len(main_groups):
            return True

        for group_name in edit_groups:
            if group_name not in main_groups:
                return True

            edit_group = edit_groups[group_name]
            main_group = main_groups[group_name]

            # 比较词元（排序后比较）
            edit_words = sorted(edit_group.get('words', []))
            main_words = sorted(main_group.get('words', []))
            if edit_words != main_words:
                return True

            edit_auto = sorted(edit_group.get('auto_learned', []))
            main_auto = sorted(main_group.get('auto_learned', []))
            if edit_auto != main_auto:
                return True

            # 比较权重
            if edit_group.get('weight', 1.0) != main_group.get('weight', 1.0):
                return True

        return False

    def _merge_group_data(
        self,
        edit_data: Dict,
        main_data: Optional[Dict]
    ) -> Dict:
        """智能合并组数据"""
        if not main_data:
            # 主配置不存在，直接使用编辑数据
            return edit_data.copy()

        # 以主配置为基础
        new_data = json.loads(json.dumps(main_data))

        # 更新config
        new_data['config'] = edit_data.get('config', {})

        # 更新groups
        edit_groups = edit_data.get('groups', {})
        new_groups = {}

        for group_name, edit_group in edit_groups.items():
            if group_name in new_data['groups']:
                # 组存在：更新词元和权重，保留vector_id等元数据
                existing_group = new_data['groups'][group_name]
                existing_group['words'] = edit_group.get('words', [])
                existing_group['auto_learned'] = edit_group.get('auto_learned', [])
                existing_group['weight'] = edit_group.get('weight', 1.0)
                new_groups[group_name] = existing_group
            else:
                # 组是新增的
                new_groups[group_name] = edit_group.copy()

        new_data['groups'] = new_groups
        return new_data

    async def load_groups(self):
        """加载语义组配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.config.config = data.get('config', {})

            # 转换为SemanticGroup对象
            self.config.groups = {}
            for name, group_data in data.get('groups', {}).items():
                self.config.groups[name] = SemanticGroup(
                    name=name,
                    words=group_data.get('words', []),
                    auto_learned=group_data.get('auto_learned', []),
                    weight=group_data.get('weight', 1.0),
                    vector_id=group_data.get('vector_id')
                )

            logger.info(
                f"[SemanticGroupManager] 加载了 {len(self.config.groups)} 个语义组"
            )
        except FileNotFoundError:
            logger.info("[SemanticGroupManager] 配置文件不存在，使用空配置")
        except Exception as e:
            logger.error(f"[SemanticGroupManager] 加载配置失败: {e}")

    async def save_groups(self):
        """保存语义组配置"""
        if self.save_lock:
            logger.warning("[SemanticGroupManager] 保存锁定，跳过")
            return

        self.save_lock = True
        try:
            data = {
                'config': self.config.config,
                'groups': {
                    name: {
                        'words': group.words,
                        'auto_learned': group.auto_learned,
                        'weight': group.weight,
                        'vector_id': group.vector_id
                    }
                    for name, group in self.config.groups.items()
                }
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info("[SemanticGroupManager] 配置已保存")
        except Exception as e:
            logger.error(f"[SemanticGroupManager] 保存配置失败: {e}")
        finally:
            self.save_lock = False

    def get_group(self, name: str) -> Optional[SemanticGroup]:
        """获取语义组"""
        return self.config.groups.get(name)

    def get_all_groups(self) -> Dict[str, SemanticGroup]:
        """获取所有语义组"""
        return self.config.groups

    def add_group(self, group: SemanticGroup):
        """添加语义组"""
        self.config.groups[group.name] = group
        logger.info(f"[SemanticGroupManager] 添加语义组: {group.name}")

    def remove_group(self, name: str):
        """移除语义组"""
        if name in self.config.groups:
            del self.config.groups[name]
            logger.info(f"[SemanticGroupManager] 移除语义组: {name}")

    def update_group(self, name: str, **kwargs):
        """更新语义组"""
        if name not in self.config.groups:
            logger.warning(f"[SemanticGroupManager] 语义组不存在: {name}")
            return

        group = self.config.groups[name]

        if 'words' in kwargs:
            group.words = kwargs['words']
        if 'auto_learned' in kwargs:
            group.auto_learned = kwargs['auto_learned']
        if 'weight' in kwargs:
            group.weight = kwargs['weight']
        if 'vector_id' in kwargs:
            group.vector_id = kwargs['vector_id']

        logger.info(f"[SemanticGroupManager] 更新语义组: {name}")

    def match_groups(
        self,
        text: str,
        threshold: float = 0.0
    ) -> List[Tuple[str, float, SemanticGroup]]:
        """
        匹配文本中激活的语义组

        Args:
            text: 待匹配文本
            threshold: 最小匹配阈值（词元匹配数）

        Returns:
            [(group_name, match_score, group), ...] 按匹配分数降序排序
        """
        text_lower = text.lower()
        matches = []

        for name, group in self.config.groups.items():
            match_count = 0
            matched_words = []

            # 检查词元
            for word in group.words:
                if word.lower() in text_lower:
                    match_count += 1
                    matched_words.append(word)

            # 检查自动学习的词元
            for word in group.auto_learned:
                if word.lower() in text_lower:
                    match_count += 1
                    matched_words.append(word)

            if match_count >= threshold:
                # 计算加权分数
                score = match_count * group.weight
                matches.append((name, score, group, matched_words))

        # 按分数降序排序
        matches.sort(key=lambda x: x[1], reverse=True)

        return [(name, score, group) for name, score, group, _ in matches]

    def get_active_groups(
        self,
        text: str,
        threshold: float = 1.0,
        max_groups: int = 5
    ) -> List[SemanticGroup]:
        """
        获取激活的语义组

        Args:
            text: 文本
            threshold: 最小匹配阈值
            max_groups: 最大返回组数

        Returns:
            激活的语义组列表
        """
        matches = self.match_groups(text, threshold)
        return [group for _, _, group in matches[:max_groups]]

    def get_enhanced_query(
        self,
        text: str,
        active_groups: Optional[List[SemanticGroup]] = None
    ) -> str:
        """
        获取语义增强的查询文本

        Args:
            text: 原始查询
            active_groups: 激活的语义组（如果不提供则自动匹配）

        Returns:
            增强后的查询文本
        """
        if active_groups is None:
            active_groups = self.get_active_groups(text)

        if not active_groups:
            return text

        # 收集所有词元
        all_words = set()
        for group in active_groups:
            all_words.update(group.words)
            all_words.update(group.auto_learned)

        # 增强查询
        enhanced_words = ' '.join(all_words)
        enhanced_query = f"{text} [语义增强: {enhanced_words}]"

        logger.debug(
            f"[SemanticGroupManager] 查询增强: "
            f"激活{len(active_groups)}个语义组, 添加{len(all_words)}个词元"
        )

        return enhanced_query


# 全局管理器实例
_manager_instance = None


def get_semantic_group_manager(config_dir: Optional[Path] = None) -> SemanticGroupManager:
    """获取语义组管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SemanticGroupManager(config_dir)
    return _manager_instance
