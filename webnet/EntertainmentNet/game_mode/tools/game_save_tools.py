"""
游戏存档管理工具
提供保存、加载、导出、导入游戏存档的功能
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def check_is_admin(user_id: int, group_id: Optional[int], onebot_client) -> bool:
    """检查用户是否是管理员"""
    try:
        if onebot_client:
            # 获取群管理员列表
            if group_id and hasattr(onebot_client, 'get_group_admin_list'):
                admins = onebot_client.get_group_admin_list(group_id)
                if user_id in admins:
                    return True

            # 检查是否是超级管理员
            if hasattr(onebot_client, 'superadmin') and user_id == onebot_client.superadmin:
                return True
        return False
    except Exception as e:
        logger.error(f"[save_game] 检查管理员权限失败: {e}")
        return False


def save_game(
    user_id: int,
    group_id: Optional[int],
    message_type: str,
    onebot_client,
    game_mode_manager,
    save_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    手动保存游戏存档

    Args:
        user_id: 用户ID
        group_id: 群号(可选)
        message_type: 消息类型
        onebot_client: OneBot客户端
        game_mode_manager: 游戏模式管理器
        save_name: 存档名称(可选)

    Returns:
        操作结果
    """
    try:
        # 权限检查:只有管理员可以保存
        if not check_is_admin(user_id, group_id, onebot_client):
            return {
                'success': False,
                'message': '只有管理员才能保存游戏存档'
            }

        # 获取聊天ID
        chat_id = str(group_id or user_id)

        # 保存游戏
        save_id = game_mode_manager.save_current_game(chat_id, save_name)

        if save_id:
            return {
                'success': True,
                'save_id': save_id,
                'save_name': save_name or '自动存档',
                'message': f'游戏已保存成功,存档ID: {save_id}'
            }
        else:
            return {
                'success': False,
                'message': '保存失败: 当前没有活跃的游戏'
            }

    except Exception as e:
        logger.error(f"[save_game] 保存游戏失败: {e}")
        return {
            'success': False,
            'message': f'保存失败: {str(e)}'
        }


def export_game_archive(
    user_id: int,
    group_id: Optional[int],
    message_type: str,
    onebot_client,
    game_mode_manager,
    archive_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    导出游戏存档

    Args:
        user_id: 用户ID
        group_id: 群号(可选)
        message_type: 消息类型
        onebot_client: OneBot客户端
        game_mode_manager: 游戏模式管理器
        archive_name: 存档名称(可选)

    Returns:
        操作结果
    """
    try:
        # 权限检查:只有管理员可以导出
        if not check_is_admin(user_id, group_id, onebot_client):
            return {
                'success': False,
                'message': '只有管理员才能导出游戏存档'
            }

        # 获取聊天ID
        chat_id = str(group_id or user_id)

        # 获取当前游戏
        mode = game_mode_manager.get_mode(chat_id)
        if not mode or not mode.game_id:
            return {
                'success': False,
                'message': '导出失败: 当前没有活跃的游戏'
            }

        # 导出存档
        archive_path = game_mode_manager.game_memory_manager.export_archive(
            mode.game_id,
            archive_name
        )

        if archive_path:
            return {
                'success': True,
                'archive_path': archive_path,
                'message': f'存档已导出: {archive_path}'
            }
        else:
            return {
                'success': False,
                'message': '导出失败'
            }

    except Exception as e:
        logger.error(f"[export_game_archive] 导出存档失败: {e}")
        return {
            'success': False,
            'message': f'导出失败: {str(e)}'
        }


def import_game_archive(
    user_id: int,
    group_id: Optional[int],
    message_type: str,
    onebot_client,
    game_mode_manager,
    archive_path: str
) -> Dict[str, Any]:
    """
    导入游戏存档

    Args:
        user_id: 用户ID
        group_id: 群号(可选)
        message_type: 消息类型
        onebot_client: OneBot客户端
        game_mode_manager: 游戏模式管理器
        archive_path: 归档文件路径

    Returns:
        操作结果
    """
    try:
        # 权限检查:只有管理员可以导入
        if not check_is_admin(user_id, group_id, onebot_client):
            return {
                'success': False,
                'message': '只有管理员才能导入游戏存档'
            }

        # 获取聊天ID
        chat_id = str(group_id or user_id)

        # 检查是否已有游戏
        existing_mode = game_mode_manager.get_mode(chat_id)
        if existing_mode:
            return {
                'success': False,
                'message': '导入失败: 当前已有活跃的游戏,请先退出'
            }

        # 导入存档
        game_id = game_mode_manager.game_memory_manager.import_archive(
            archive_path,
            target_group_id=group_id,
            target_user_id=user_id if message_type == 'private' else None
        )

        if game_id:
            return {
                'success': True,
                'game_id': game_id,
                'message': f'存档已导入成功,游戏ID: {game_id}'
            }
        else:
            return {
                'success': False,
                'message': '导入失败: 文件不存在或格式错误'
            }

    except Exception as e:
        logger.error(f"[import_game_archive] 导入存档失败: {e}")
        return {
            'success': False,
            'message': f'导入失败: {str(e)}'
        }


def set_character_visibility(
    user_id: int,
    group_id: Optional[int],
    message_type: str,
    onebot_client,
    game_mode_manager,
    character_id: str,
    is_public: bool
) -> Dict[str, Any]:
    """
    设置角色卡可见性

    Args:
        user_id: 用户ID
        group_id: 群号(可选)
        message_type: 消息类型
        onebot_client: OneBot客户端
        game_mode_manager: 游戏模式管理器
        character_id: 角色卡ID
        is_public: 是否公开

    Returns:
        操作结果
    """
    try:
        # 权限检查:只有管理员或角色卡拥有者可以修改
        chat_id = str(group_id or user_id)
        mode = game_mode_manager.get_mode(chat_id)

        if not mode or not mode.game_id:
            return {
                'success': False,
                'message': '设置失败: 当前没有活跃的游戏'
            }

        # 获取角色卡
        character = game_mode_manager.game_memory_manager.get_character(
            mode.game_id,
            character_id
        )

        if not character:
            return {
                'success': False,
                'message': '设置失败: 角色卡不存在'
            }

        # 检查权限
        is_admin = check_is_admin(user_id, group_id, onebot_client)
        if not is_admin and character.player_id != user_id:
            return {
                'success': False,
                'message': '设置失败: 你没有权限修改此角色卡'
            }

        # 更新可见性
        success = game_mode_manager.game_memory_manager.update_character(
            mode.game_id,
            character_id,
            is_public=is_public
        )

        if success:
            visibility = "公开" if is_public else "私密"
            return {
                'success': True,
                'message': f'角色卡已设置为{visibility}'
            }
        else:
            return {
                'success': False,
                'message': '设置失败'
            }

    except Exception as e:
        logger.error(f"[set_character_visibility] 设置可见性失败: {e}")
        return {
            'success': False,
            'message': f'设置失败: {str(e)}'
        }


def list_game_saves(
    user_id: int,
    group_id: Optional[int],
    message_type: str,
    onebot_client,
    game_mode_manager
) -> Dict[str, Any]:
    """
    列出游戏存档

    Args:
        user_id: 用户ID
        group_id: 群号(可选)
        message_type: 消息类型
        onebot_client: OneBot客户端
        game_mode_manager: 游戏模式管理器

    Returns:
        操作结果
    """
    try:
        chat_id = str(group_id or user_id)
        mode = game_mode_manager.get_mode(chat_id)

        if not mode or not mode.game_id:
            return {
                'success': False,
                'message': '当前没有活跃的游戏'
            }

        # 获取游戏存档
        save_data = game_mode_manager.game_memory_manager.load_game(mode.game_id)

        if save_data:
            return {
                'success': True,
                'save_data': {
                    'save_id': save_data.save_id,
                    'save_name': save_data.save_name,
                    'created_at': save_data.created_at,
                    'characters_count': len(save_data.characters),
                    'game_state': save_data.game_state
                },
                'message': f'当前存档: {save_data.save_name}'
            }
        else:
            return {
                'success': False,
                'message': '没有找到存档'
            }

    except Exception as e:
        logger.error(f"[list_game_saves] 列出存档失败: {e}")
        return {
            'success': False,
            'message': f'列出存档失败: {str(e)}'
        }
