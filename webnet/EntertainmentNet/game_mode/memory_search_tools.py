"""
记忆检索工具
提供从普通记忆和游戏记忆中检索的功能
"""

import logging
from typing import Optional, Dict, Any

from .memory_retriever import MemoryRetriever


logger = logging.getLogger(__name__)


async def search_normal_memory(
    user_id: int,
    memory_net,
    limit: int = 10,
    days_back: int = 7,
    keywords: Optional[list] = None
) -> Dict[str, Any]:
    """
    检索普通模式下的对话历史记忆

    Args:
        user_id: 用户ID
        memory_net: MemoryNet 实例
        limit: 返回数量限制
        days_back: 检索最近几天的记忆
        keywords: 关键词列表(可选)

    Returns:
        检索结果
    """
    try:
        retriever = MemoryRetriever(memory_net=memory_net)

        result = await retriever.retrieve_memories(
            user_id=user_id,
            game_mode=False,
            limit=limit,
            days_back=days_back,
            keywords=keywords
        )

        return result

    except Exception as e:
        logger.error(f"[search_normal_memory] 检索失败: {e}")
        return {
            'success': False,
            'mode': 'normal',
            'memories': [],
            'summary': f'检索失败: {str(e)}',
            'total_count': 0
        }


async def search_game_memory(
    user_id: int,
    group_id: Optional[int],
    game_mode_manager,
    limit: int = 10,
    keywords: Optional[list] = None
) -> Dict[str, Any]:
    """
    检索游戏模式下的记忆

    Args:
        user_id: 用户ID
        group_id: 群号
        game_mode_manager: GameModeManager 实例
        limit: 返回数量限制
        keywords: 关键词列表(可选)

    Returns:
        检索结果
    """
    try:
        retriever = MemoryRetriever(game_mode_manager=game_mode_manager)

        result = await retriever.retrieve_memories(
            user_id=user_id,
            group_id=group_id,
            game_mode=True,
            limit=limit,
            keywords=keywords
        )

        return result

    except Exception as e:
        logger.error(f"[search_game_memory] 检索失败: {e}")
        return {
            'success': False,
            'mode': 'game',
            'memories': [],
            'summary': f'检索失败: {str(e)}',
            'total_count': 0
        }


def format_memory_report(result: Dict[str, Any], retriever: MemoryRetriever) -> str:
    """
    格式化记忆检索结果为报告

    Args:
        result: 记忆检索结果
        retriever: MemoryRetriever 实例

    Returns:
        格式化的报告文本
    """
    try:
        return retriever.format_memories_for_report(result)
    except Exception as e:
        logger.error(f"[format_memory_report] 格式化失败: {e}")
        return f"报告生成失败: {str(e)}"


async def search_and_report_normal_memory(
    user_id: int,
    memory_net,
    limit: int = 10,
    days_back: int = 7,
    keywords: Optional[list] = None
) -> str:
    """
    检索普通记忆并生成报告

    Args:
        user_id: 用户ID
        memory_net: MemoryNet 实例
        limit: 返回数量限制
        days_back: 检索最近几天的记忆
        keywords: 关键词列表(可选)

    Returns:
        格式化的记忆报告
    """
    result = await search_normal_memory(
        user_id=user_id,
        memory_net=memory_net,
        limit=limit,
        days_back=days_back,
        keywords=keywords
    )

    retriever = MemoryRetriever(memory_net=memory_net)
    return retriever.format_memories_for_report(result)


async def search_and_report_game_memory(
    user_id: int,
    group_id: Optional[int],
    game_mode_manager,
    limit: int = 10,
    keywords: Optional[list] = None
) -> str:
    """
    检索游戏记忆并生成报告

    Args:
        user_id: 用户ID
        group_id: 群号
        game_mode_manager: GameModeManager 实例
        limit: 返回数量限制
        keywords: 关键词列表(可选)

    Returns:
        格式化的记忆报告
    """
    result = await search_game_memory(
        user_id=user_id,
        group_id=group_id,
        game_mode_manager=game_mode_manager,
        limit=limit,
        keywords=keywords
    )

    retriever = MemoryRetriever(game_mode_manager=game_mode_manager)
    return retriever.format_memories_for_report(result)
