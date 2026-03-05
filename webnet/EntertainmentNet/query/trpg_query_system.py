"""
跑团查询系统
提供专门针对 TRPG 角色卡和会话的查询功能
"""

from typing import List, Dict, Optional, Any
from .base_query import BaseQuerySystem


class TRPGQuerySystem(BaseQuerySystem):
    """跑团查询系统"""

    def __init__(self, data_path: str = "data/"):
        """
        初始化跑团查询系统

        Args:
            data_path: 数据文件路径
        """
        super().__init__(data_path)
        self.characters_path = self.data_path / "trpg_characters.json"
        self.sessions_path = self.data_path / "trpg_sessions.json"

        # 数据容器
        self.characters = []
        self.sessions_data = {'sessions': {}, 'scenes': {}, 'combats': {}}

        # 加载数据
        self._load_index()

    def _load_index(self):
        """加载数据索引"""
        try:
            chars_data = self._load_json(self.characters_path)
            # trpg_characters.json 是一个列表，不是字典
            if isinstance(chars_data, list):
                self.characters = chars_data
            elif isinstance(chars_data, dict):
                # 如果是字典格式，转换为列表
                self.characters = list(chars_data.values())
            else:
                self.characters = []

            sessions_data = self._load_json(self.sessions_path)
            if sessions_data and isinstance(sessions_data, dict):
                self.sessions_data = sessions_data
            else:
                self.sessions_data = {'sessions': {}, 'scenes': {}, 'combats': {}}

            self.logger.info(f"跑团查询系统已加载: {len(self.characters)} 个角色卡, "
                            f"{len(self.sessions_data.get('sessions', {}))} 个会话")
        except Exception as e:
            self.logger.error(f"加载数据索引失败: {e}")
            self.characters = []
            self.sessions_data = {'sessions': {}, 'scenes': {}, 'combats': {}}

    async def search_characters(
        self,
        query: str,
        rule_system: Optional[str] = None,
        min_attribute: Optional[Dict[str, int]] = None,
        group_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索角色卡

        Args:
            query: 搜索关键词
            rule_system: 规则系统过滤（coc7, dnd5e 等）
            min_attribute: 最低属性值过滤
            group_id: 群组过滤
            limit: 返回结果数量

        Returns:
            角色卡列表
        """
        results = []

        for char_data in self.characters:
            # 规则系统过滤
            if rule_system and char_data.get('rule_system') != rule_system:
                continue

            # 群组过滤
            if group_id:
                group_states = char_data.get('group_states', {})
                if group_id not in group_states:
                    continue

            # 属性过滤
            if min_attribute:
                skip = False
                for attr_name, min_value in min_attribute.items():
                    if char_data.get(attr_name, 0) < min_value:
                        skip = True
                        break
                if skip:
                    continue

            # 计算相关性分数
            score = 0.0

            # 1. 角色名匹配（权重最高）
            if query.lower() in char_data.get('character_name', '').lower():
                score += 2.0

            # 2. 技能匹配
            for skill_name, skill_value in char_data.get('skills', {}).items():
                if query.lower() in skill_name.lower():
                    score += 1.0 + (skill_value / 100)

            # 3. 装备匹配
            for item in char_data.get('inventory', []):
                if isinstance(item, dict):
                    item_name = item.get('name', '')
                else:
                    item_name = str(item)

                if query.lower() in item_name.lower():
                    score += 0.5

            # 4. 背景描述匹配（如果有）
            if 'background' in char_data:
                score += self.calculate_relevance(query, char_data['background']) * 0.5

            if score > 0:
                results.append({
                    'player_id': char_data['player_id'],
                    'character_data': char_data,
                    'score': score
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search_sessions(
        self,
        query: str,
        group_id: Optional[int] = None,
        player_id: Optional[int] = None,
        rule_system: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索跑团会话

        Args:
            query: 搜索关键词
            group_id: 群组过滤
            player_id: 玩家过滤
            rule_system: 规则系统过滤
            limit: 返回结果数量

        Returns:
            会话列表
        """
        results = []

        for session_id, session in self.sessions_data.get('sessions', {}).items():
            # 群组过滤
            if group_id and session.get('group_id') != group_id:
                continue

            # 玩家过滤
            if player_id and session.get('gm_id') != player_id:
                continue

            # 规则系统过滤
            if rule_system and session.get('rule_system') != rule_system:
                continue

            # 计算相关性
            content = f"{session.get('name', '')} {session.get('description', '')}"
            score = self.calculate_relevance(query, content)

            if score > 0:
                results.append({
                    'session_id': session_id,
                    'session': session,
                    'score': score
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search_by_attribute(
        self,
        attribute_name: str,
        min_value: int,
        rule_system: Optional[str] = None,
        group_id: Optional[int] = None,
        sort_desc: bool = True,
        limit: int = 10
    ) -> List[Dict]:
        """
        按属性值搜索角色

        Args:
            attribute_name: 属性名（strength, dexterity, constitution 等）
            min_value: 最低值
            rule_system: 规则系统过滤
            group_id: 群组过滤
            sort_desc: 是否降序排序
            limit: 返回结果数量

        Returns:
            角色列表
        """
        results = []

        for char_data in self.characters:
            # 规则系统过滤
            if rule_system and char_data.get('rule_system') != rule_system:
                continue

            # 群组过滤
            if group_id:
                group_states = char_data.get('group_states', {})
                if group_id not in group_states:
                    continue

            # 属性值过滤
            attr_value = char_data.get(attribute_name, 0)
            if attr_value >= min_value:
                results.append({
                    'player_id': char_data['player_id'],
                    'character_data': char_data,
                    'attribute_value': attr_value,
                    'score': attr_value
                })

        # 按属性值排序
        results.sort(key=lambda x: x['score'], reverse=sort_desc)
        return results[:limit]

    async def search_by_skill(
        self,
        skill_name: str,
        min_value: int = 0,
        rule_system: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        按技能搜索角色

        Args:
            skill_name: 技能名称
            min_value: 最低技能值
            rule_system: 规则系统过滤
            limit: 返回结果数量

        Returns:
            角色列表
        """
        results = []

        for char_data in self.characters:
            # 规则系统过滤
            if rule_system and char_data.get('rule_system') != rule_system:
                continue

            # 技能匹配
            skill_value = char_data.get('skills', {}).get(skill_name, 0)
            if skill_value >= min_value:
                results.append({
                    'player_id': char_data['player_id'],
                    'character_data': char_data,
                    'skill_name': skill_name,
                    'skill_value': skill_value,
                    'score': skill_value
                })

        # 按技能值排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search_scenes(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索场景

        Args:
            query: 搜索关键词
            session_id: 会话过滤
            limit: 返回结果数量

        Returns:
            场景列表
        """
        results = []

        for scene_id, scene in self.sessions_data.get('scenes', {}).items():
            # 会话过滤
            if session_id and scene.get('session_id') != session_id:
                continue

            # 计算相关性
            content = f"{scene.get('name', '')} {scene.get('description', '')}"
            score = self.calculate_relevance(query, content)

            if score > 0:
                results.append({
                    'scene_id': scene_id,
                    'scene': scene,
                    'score': score
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search(self, query: str, filters: Optional[Dict] = None, limit: int = 10) -> List[Dict]:
        """
        综合查询（搜索所有类型）

        Args:
            query: 查询关键词
            filters: 过滤条件
            limit: 返回结果数量

        Returns:
            查询结果列表
        """
        filters = filters or {}

        # 并发搜索多种类型
        char_results = await self.search_characters(
            query,
            rule_system=filters.get('rule_system'),
            group_id=filters.get('group_id'),
            limit=limit
        )

        session_results = await self.search_sessions(
            query,
            group_id=filters.get('group_id'),
            rule_system=filters.get('rule_system'),
            limit=limit
        )

        # 合并结果
        all_results = []

        for r in char_results:
            all_results.append({
                'type': 'character',
                'data': r,
                'score': r['score']
            })

        for r in session_results:
            all_results.append({
                'type': 'session',
                'data': r,
                'score': r['score']
            })

        # 按分数排序
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:limit]

    async def index_data(self, data: Dict) -> bool:
        """
        索引新数据

        Args:
            data: 要索引的数据

        Returns:
            是否成功
        """
        try:
            # 更新角色卡
            if 'characters' in data:
                new_chars = data['characters']
                for new_char in new_chars:
                    # 查找是否已存在
                    player_id = new_char['player_id']
                    existing = next((c for c in self.characters if c['player_id'] == player_id), None)

                    if existing:
                        # 更新现有角色卡
                        existing.update(new_char)
                    else:
                        # 添加新角色卡
                        self.characters.append(new_char)

            # 更新会话
            if 'sessions' in data:
                self.sessions_data['sessions'].update(data['sessions'])

            # 更新场景
            if 'scenes' in data:
                self.sessions_data['scenes'].update(data['scenes'])

            # 清空缓存
            self.clear_cache()

            return True
        except Exception as e:
            self.logger.error(f"索引数据失败: {e}")
            return False

    async def get_character_by_player_id(self, player_id: int) -> Optional[Dict]:
        """
        根据玩家ID获取角色卡

        Args:
            player_id: 玩家QQ号

        Returns:
            角色卡数据
        """
        for char_data in self.characters:
            if char_data['player_id'] == player_id:
                return char_data
        return None

    async def get_character_by_name(self, character_name: str, group_id: Optional[int] = None) -> Optional[Dict]:
        """
        根据角色名获取角色卡

        Args:
            character_name: 角色名
            group_id: 群组ID（可选，用于多群隔离）

        Returns:
            角色卡数据
        """
        for char_data in self.characters:
            if char_data['character_name'].lower() == character_name.lower():
                # 如果指定了群组，检查是否在群组中
                if group_id:
                    group_states = char_data.get('group_states', {})
                    if group_id in group_states:
                        return char_data
                else:
                    return char_data
        return None

    async def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        """
        根据ID获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话数据
        """
        return self.sessions_data.get('sessions', {}).get(session_id)

    async def list_rule_systems(self) -> List[str]:
        """
        列出所有规则系统

        Returns:
            规则系统列表
        """
        rule_systems = set()
        for char_data in self.characters:
            if char_data.get('rule_system'):
                rule_systems.add(char_data['rule_system'])
        return sorted(list(rule_systems))

    async def list_groups(self) -> List[int]:
        """
        列出所有有数据的群组

        Returns:
            群组ID列表
        """
        groups = set()
        for char_data in self.characters:
            groups.update(char_data.get('group_states', {}).keys())
        return sorted(list(groups))
