"""
记忆检索工具
支持从普通记忆和游戏记忆中检索信息
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class MemoryRetriever:
    """
    记忆检索器
    统一检索普通记忆和游戏记忆
    """

    def __init__(self, memory_net=None, game_mode_manager=None):
        """
        初始化记忆检索器

        Args:
            memory_net: MemoryNet 实例
            game_mode_manager: GameModeManager 实例
        """
        self.memory_net = memory_net
        self.game_mode_manager = game_mode_manager

    async def retrieve_memories(
        self,
        user_id: int,
        group_id: Optional[int] = None,
        game_mode: bool = False,
        limit: int = 10,
        days_back: int = 7,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        检索记忆

        Args:
            user_id: 用户ID
            group_id: 群号(可选)
            game_mode: 是否游戏模式
            limit: 返回数量限制
            days_back: 检索最近几天的记忆
            keywords: 关键词列表(可选)

        Returns:
            记忆检索结果
        """
        result = {
            'success': True,
            'mode': 'game' if game_mode else 'normal',
            'memories': [],
            'summary': '',
            'total_count': 0
        }

        try:
            if game_mode:
                # 检索游戏记忆
                result = await self._retrieve_game_memories(
                    user_id=user_id,
                    group_id=group_id,
                    limit=limit,
                    keywords=keywords
                )
            else:
                # 检索普通记忆
                result = await self._retrieve_normal_memories(
                    user_id=user_id,
                    limit=limit,
                    days_back=days_back,
                    keywords=keywords
                )

        except Exception as e:
            logger.error(f"[MemoryRetriever] 检索记忆失败: {e}")
            result = {
                'success': False,
                'mode': 'game' if game_mode else 'normal',
                'memories': [],
                'summary': f'检索失败: {str(e)}',
                'total_count': 0
            }

        return result

    async def _retrieve_normal_memories(
        self,
        user_id: int,
        limit: int = 10,
        days_back: int = 7,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        检索普通记忆

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            days_back: 检索最近几天的记忆
            keywords: 关键词列表(可选)

        Returns:
            记忆检索结果
        """
        result = {
            'success': True,
            'mode': 'normal',
            'memories': [],
            'summary': '',
            'total_count': 0
        }

        try:
            if not self.memory_net or not hasattr(self.memory_net, 'get_recent_conversations'):
                return result

            # 获取对话历史
            memories = await self.memory_net.get_recent_conversations(
                user_id=user_id,
                limit=limit * 2  # 获取更多,方便筛选
            )

            # 筛选时间范围
            cutoff_time = datetime.now() - timedelta(days=days_back)
            filtered_memories = []

            for mem in memories:
                # 检查时间
                mem_time = datetime.fromisoformat(mem.get('timestamp', ''))
                if mem_time < cutoff_time:
                    continue

                # 检查关键词
                if keywords:
                    content = mem.get('content', '').lower()
                    if not any(kw.lower() in content for kw in keywords):
                        continue

                filtered_memories.append(mem)

            # 限制数量
            filtered_memories = filtered_memories[:limit]

            # 生成摘要
            result['memories'] = filtered_memories
            result['total_count'] = len(filtered_memories)
            result['summary'] = self._generate_normal_summary(filtered_memories)

            logger.debug(f"[MemoryRetriever] 检索到 {len(filtered_memories)} 条普通记忆")

        except Exception as e:
            logger.error(f"[MemoryRetriever] 检索普通记忆失败: {e}")
            result['success'] = False
            result['summary'] = f'检索失败: {str(e)}'

        return result

    async def _retrieve_game_memories(
        self,
        user_id: int,
        group_id: Optional[int],
        limit: int = 10,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        检索游戏记忆

        Args:
            user_id: 用户ID
            group_id: 群号
            limit: 返回数量限制
            keywords: 关键词列表(可选)

        Returns:
            记忆检索结果
        """
        result = {
            'success': True,
            'mode': 'game',
            'memories': [],
            'summary': '',
            'total_count': 0
        }

        try:
            if not self.game_mode_manager:
                return result

            chat_id = str(group_id or user_id)
            game_memory = self.game_mode_manager.load_game_memory(chat_id)

            if not game_memory:
                result['summary'] = '当前没有游戏记忆'
                return result

            # 收集游戏记忆
            game_memories = []

            # 角色卡信息
            if game_memory.get('characters'):
                for char in game_memory['characters']:
                    char_info = {
                        'type': 'character',
                        'content': f"角色: {char.get('character_name')} (玩家: {char.get('player_name')})",
                        'timestamp': char.get('updated_at', ''),
                        'details': char
                    }
                    game_memories.append(char_info)

            # 故事进度
            if game_memory.get('story_progress'):
                story_info = {
                    'type': 'story',
                    'content': f"故事进度: {str(game_memory['story_progress'])}",
                    'timestamp': game_memory.get('save_id', ''),
                    'details': game_memory['story_progress']
                }
                game_memories.append(story_info)

            # 存档信息
            if game_memory.get('save_name'):
                save_info = {
                    'type': 'save',
                    'content': f"存档: {game_memory['save_name']} (ID: {game_memory['save_id']})",
                    'timestamp': game_memory.get('created_at', ''),
                    'details': {
                        'save_name': game_memory['save_name'],
                        'save_id': game_memory['save_id']
                    }
                }
                game_memories.append(save_info)

            # 筛选关键词
            if keywords:
                filtered_memories = []
                for mem in game_memories:
                    content = mem.get('content', '').lower()
                    if any(kw.lower() in content for kw in keywords):
                        filtered_memories.append(mem)
                game_memories = filtered_memories

            # 限制数量
            game_memories = game_memories[:limit]

            # 生成摘要
            result['memories'] = game_memories
            result['total_count'] = len(game_memories)
            result['summary'] = self._generate_game_summary(game_memories, game_memory)

            logger.debug(f"[MemoryRetriever] 检索到 {len(game_memories)} 条游戏记忆")

        except Exception as e:
            logger.error(f"[MemoryRetriever] 检索游戏记忆失败: {e}")
            result['success'] = False
            result['summary'] = f'检索失败: {str(e)}'

        return result

    def _generate_normal_summary(self, memories: List[Dict]) -> str:
        """生成普通记忆摘要"""
        if not memories:
            return "没有找到相关记忆"

        count = len(memories)
        time_range = "最近" if count > 0 else ""

        # 统计角色
        senders = set()
        for mem in memories:
            sender = mem.get('sender', '')
            if sender:
                senders.add(sender)

        summary_parts = [f"找到{count}条{time_range}对话记忆"]

        if senders:
            summary_parts.append(f"涉及{len(senders)}位用户")

        return "，".join(summary_parts) + "。"

    def _generate_game_summary(self, memories: List[Dict], game_memory: Dict) -> str:
        """生成游戏记忆摘要"""
        if not memories:
            return "没有找到游戏记忆"

        count = len(memories)

        # 统计类型
        types_count = {}
        for mem in memories:
            mem_type = mem.get('type', 'unknown')
            types_count[mem_type] = types_count.get(mem_type, 0) + 1

        summary_parts = [f"找到{count}条游戏记忆"]

        if types_count:
            type_desc = []
            if types_count.get('character'):
                type_desc.append(f"{types_count['character']}个角色")
            if types_count.get('story'):
                type_desc.append("故事进度")
            if types_count.get('save'):
                type_desc.append("存档信息")

            if type_desc:
                summary_parts.append("，".join(type_desc))

        return "，".join(summary_parts) + "。"

    def format_memories_for_report(self, result: Dict[str, Any]) -> str:
        """
        格式化记忆检索结果为报告

        Args:
            result: 记忆检索结果

        Returns:
            格式化的报告文本
        """
        if not result['success']:
            return f"记忆检索失败: {result['summary']}"

        mode = "游戏记忆" if result['mode'] == 'game' else "普通记忆"
        lines = [f"## {mode}检索报告", ""]

        # 摘要
        lines.append(f"**摘要**: {result['summary']}")
        lines.append("")

        if not result['memories']:
            lines.append("没有找到相关记忆。")
            return "\n".join(lines)

        # 详细内容
        lines.append("**详细内容**:")
        lines.append("")

        for i, mem in enumerate(result['memories'], 1):
            lines.append(f"{i}. {mem.get('content', '无内容')}")

            # 添加详细信息
            if result['mode'] == 'game' and mem.get('details'):
                details = mem['details']
                if mem.get('type') == 'character':
                    # 显示角色属性
                    if details.get('attributes'):
                        lines.append(f"   属性: {str(details['attributes'])}")
                    if details.get('skills'):
                        lines.append(f"   技能: {str(details['skills'])}")

            # 添加时间
            timestamp = mem.get('timestamp', '')
            if timestamp:
                lines.append(f"   时间: {timestamp}")

            lines.append("")

        return "\n".join(lines)
