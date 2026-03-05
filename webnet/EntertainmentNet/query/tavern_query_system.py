"""
酒馆查询系统
提供专门针对酒馆故事的查询功能
"""

from typing import List, Dict, Optional, Any
import time
from .base_query import BaseQuerySystem


class TavernQuerySystem(BaseQuerySystem):
    """酒馆查询系统"""

    def __init__(self, data_path: str = "data/"):
        """
        初始化酒馆查询系统

        Args:
            data_path: 数据文件路径
        """
        super().__init__(data_path)
        self.characters_path = self.data_path / "tavern_characters.json"
        self.memory_path = self.data_path / "tavern_memory.json"

        # 数据容器
        self.characters = {}
        self.memory_data = {'sessions': {}, 'players': {}, 'stories': {}}

        # 加载数据
        self._load_index()

    def _load_index(self):
        """加载数据索引"""
        self.characters = self._load_json(self.characters_path)
        self.memory_data = self._load_json(self.memory_path)

        if not self.memory_data:
            self.memory_data = {'sessions': {}, 'players': {}, 'stories': {}}

        self.logger.info(f"酒馆查询系统已加载: {len(self.characters)} 个角色, "
                        f"{len(self.memory_data['sessions'])} 个会话")

    async def search_characters(
        self,
        query: str,
        personality_trait: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索酒馆角色

        Args:
            query: 搜索关键词（角色名、性格、背景等）
            personality_trait: 特定性格特质过滤
            limit: 返回结果数量

        Returns:
            角色列表，每项包含角色数据和相关性分数
        """
        results = []

        for char_id, char_data in self.characters.items():
            # 计算相关性分数
            score = 0.0

            # 1. 角色名匹配（权重最高）
            if query.lower() in char_data.get('name', '').lower():
                score += 2.0

            # 2. 性格描述匹配
            personality = char_data.get('personality', '')
            score += self.calculate_relevance(query, personality) * 1.5

            # 3. 背景故事匹配
            background = char_data.get('background', '')
            score += self.calculate_relevance(query, background) * 1.0

            # 4. 特质匹配
            for trait in char_data.get('traits', []):
                if query.lower() in trait.lower():
                    score += 0.8

            # 5. 特质过滤
            if personality_trait and personality_trait in char_data.get('traits', []):
                score += 1.0

            if score > 0:
                results.append({
                    'character_id': char_id,
                    'character_data': char_data,
                    'score': score
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search_stories(
        self,
        query: str,
        character_id: Optional[str] = None,
        mood: Optional[str] = None,
        theme: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索酒馆故事

        Args:
            query: 搜索关键词
            character_id: 限定特定角色
            mood: 情绪氛围过滤
            theme: 主题过滤
            limit: 返回结果数量

        Returns:
            故事列表
        """
        results = []

        # 1. 搜索会话记忆
        for chat_id, messages in self.memory_data.get('sessions', {}).items():
            for msg in messages:
                content = msg.get('content', '')
                score = self.calculate_relevance(query, content)

                # 角色过滤
                if character_id:
                    role = msg.get('role', '')
                    if character_id.lower() not in role.lower():
                        score = 0

                if score > 0:
                    results.append({
                        'type': 'session_message',
                        'chat_id': chat_id,
                        'message': msg,
                        'score': score
                    })

        # 2. 搜索故事历史
        for story_id, story in self.memory_data.get('stories', {}).items():
            content = f"{story.get('theme', '')} {story.get('content', '')}"
            score = self.calculate_relevance(query, content)

            # 角色过滤
            if character_id and character_id not in story.get('characters', []):
                score = 0

            # 情绪过滤
            if mood and story.get('mood') != mood:
                score = 0

            # 主题过滤
            if theme and theme not in story.get('theme', ''):
                score = 0

            if score > 0:
                results.append({
                    'type': 'story',
                    'story_id': story_id,
                    'story': story,
                    'score': score
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search_player_preferences(
        self,
        query: str,
        user_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索玩家偏好

        Args:
            query: 搜索关键词
            user_id: 限定特定用户
            limit: 返回结果数量

        Returns:
            玩家偏好列表
        """
        results = []

        for player_id, player_data in self.memory_data.get('players', {}).items():
            # 用户过滤
            if user_id and str(player_id) != str(user_id):
                continue

            # 搜索特质
            for trait_key, trait_value in player_data.get('traits', {}).items():
                text = f"{trait_key} {trait_value}"
                score = self.calculate_relevance(query, text)

                if score > 0:
                    results.append({
                        'player_id': player_id,
                        'type': 'trait',
                        'trait_key': trait_key,
                        'trait_value': trait_value,
                        'score': score
                    })

            # 搜索偏好
            for pref in player_data.get('preferences', []):
                pref_text = pref.get('preference', '')
                score = self.calculate_relevance(query, pref_text)

                if score > 0:
                    results.append({
                        'player_id': player_id,
                        'type': 'preference',
                        'preference': pref,
                        'score': score
                    })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    async def search_by_mood(
        self,
        mood: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        按情绪氛围搜索故事

        Args:
            mood: 情绪类型（温馨、浪漫、悬疑等）
            limit: 返回结果数量

        Returns:
            故事列表
        """
        results = []

        for story_id, story in self.memory_data.get('stories', {}).items():
            if story.get('mood') == mood:
                results.append({
                    'story_id': story_id,
                    'story': story,
                    'score': 1.0
                })

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
            personality_trait=filters.get('personality_trait'),
            limit=limit
        )

        story_results = await self.search_stories(
            query,
            character_id=filters.get('character_id'),
            mood=filters.get('mood'),
            theme=filters.get('theme'),
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

        for r in story_results:
            all_results.append({
                'type': 'story',
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
            # 更新角色
            if 'characters' in data:
                self.characters.update(data['characters'])

            # 更新会话
            if 'sessions' in data:
                self.memory_data['sessions'].update(data['sessions'])

            # 更新故事
            if 'stories' in data:
                self.memory_data['stories'].update(data['stories'])

            # 更新玩家
            if 'players' in data:
                self.memory_data['players'].update(data['players'])

            # 清空缓存
            self.clear_cache()

            return True
        except Exception as e:
            self.logger.error(f"索引数据失败: {e}")
            return False

    async def get_character_by_id(self, character_id: str) -> Optional[Dict]:
        """
        根据ID获取角色

        Args:
            character_id: 角色ID

        Returns:
            角色数据
        """
        return self.characters.get(character_id)

    async def get_story_by_id(self, story_id: str) -> Optional[Dict]:
        """
        根据ID获取故事

        Args:
            story_id: 故事ID

        Returns:
            故事数据
        """
        return self.memory_data.get('stories', {}).get(story_id)

    async def list_moods(self) -> List[str]:
        """
        列出所有情绪类型

        Returns:
            情绪列表
        """
        moods = set()
        for story in self.memory_data.get('stories', {}).values():
            if story.get('mood'):
                moods.add(story['mood'])
        return sorted(list(moods))

    async def list_themes(self) -> List[str]:
        """
        列出所有主题

        Returns:
            主题列表
        """
        themes = set()
        for story in self.memory_data.get('stories', {}).values():
            if story.get('theme'):
                themes.add(story['theme'])
        return sorted(list(themes))
