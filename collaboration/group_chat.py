"""
弥娅 - 群聊协作系统
从VCPChat整合而来，提供多Agent群聊功能
"""

import os
import logging
import json
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import aiofiles
from core.constants import Encoding

logger = logging.getLogger(__name__)


class AgentGroup:
    """Agent群组"""
    
    def __init__(self, group_id: str, config: dict):
        self.group_id = group_id
        self.name = config.get('name', '未命名群组')
        self.members = config.get('members', [])
        self.mode = config.get('mode', 'sequential')
        self.group_prompt = config.get('groupPrompt', '')
        self.invite_prompt = config.get('invitePrompt', '')
        self.topics = config.get('topics', [])
        self.created_at = config.get('createdAt', datetime.now().timestamp())
        
        # 扩展属性
        self.tag_match_mode = config.get('tagMatchMode', 'strict')
        self.member_tags = config.get('memberTags', {})
        self.use_unified_model = config.get('useUnifiedModel', False)
        self.unified_model = config.get('unifiedModel', '')
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.group_id,
            "name": self.name,
            "members": self.members,
            "mode": self.mode,
            "tagMatchMode": self.tag_match_mode,
            "memberTags": self.member_tags,
            "groupPrompt": self.group_prompt,
            "invitePrompt": self.invite_prompt,
            "useUnifiedModel": self.use_unified_model,
            "unifiedModel": self.unified_model,
            "createdAt": self.created_at,
            "topics": self.topics
        }


class Topic:
    """群聊话题"""
    
    def __init__(self, topic_id: str, config: dict):
        self.topic_id = topic_id
        self.name = config.get('name', '新话题')
        self.created_at = config.get('createdAt', datetime.now().timestamp())
        self.group_id = config.get('groupId', '')
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.topic_id,
            "name": self.name,
            "groupId": self.group_id,
            "createdAt": self.created_at
        }


class GroupChatManager:
    """群聊管理器"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent / "storage" / "groups"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 群组存储
        self.groups: Dict[str, AgentGroup] = {}
        self.user_data_dir = self.base_dir.parent / "user_data"
        self.user_data_dir.mkdir(exist_ok=True)
        
        logger.info(f"群聊管理器初始化完成: {self.base_dir}")
    
    async def load_groups(self):
        """加载所有群组"""
        try:
            group_folders = [f for f in self.base_dir.iterdir() if f.is_dir()]
            
            for group_folder in group_folders:
                config_path = group_folder / "config.json"
                if not config_path.exists():
                    continue
                
                try:
                    async with aiofiles.open(config_path, 'r', encoding=Encoding.UTF8) as f:
                        config = json.loads(await f.read())
                    
                    group = AgentGroup(group_folder.name, config)
                    self.groups[group.group_id] = group
                    
                    logger.info(f"加载群组: {group.name}")
                    
                except Exception as e:
                    logger.error(f"加载群组失败 {group_folder.name}: {e}")
            
            logger.info(f"共加载 {len(self.groups)} 个群组")
            
        except Exception as e:
            logger.error(f"加载群组列表失败: {e}")
    
    async def create_group(
        self, 
        group_name: str,
        members: List[dict] = None,
        mode: str = 'sequential',
        group_prompt: str = ''
    ) -> dict:
        """创建新群组"""
        try:
            # 生成唯一ID
            group_id = f"group_{uuid.uuid4().hex[:12]}"
            
            # 创建群组目录
            group_dir = self.base_dir / group_id
            group_dir.mkdir(exist_ok=True)
            
            # 配置
            config = {
                "id": group_id,
                "name": group_name,
                "members": members or [],
                "mode": mode,
                "tagMatchMode": "strict",
                "memberTags": {},
                "groupPrompt": group_prompt,
                "invitePrompt": "现在轮到你{{agent_name}}发言了。",
                "useUnifiedModel": False,
                "unifiedModel": "",
                "createdAt": datetime.now().timestamp(),
                "topics": [
                    {
                        "id": f"topic_{uuid.uuid4().hex[:12]}",
                        "name": "主要群聊",
                        "groupId": group_id,
                        "createdAt": datetime.now().timestamp()
                    }
                ]
            }
            
            # 保存配置
            config_path = group_dir / "config.json"
            async with aiofiles.open(config_path, 'w', encoding=Encoding.UTF8) as f:
                await f.write(json.dumps(config, ensure_ascii=False, indent=2))
            
            # 创建默认话题
            topic_id = config['topics'][0]['id']
            topic_dir = self.user_data_dir / group_id / "topics" / topic_id
            topic_dir.mkdir(parents=True, exist_ok=True)
            
            history_path = topic_dir / "history.json"
            async with aiofiles.open(history_path, 'w', encoding=Encoding.UTF8) as f:
                await f.write(json.dumps([], ensure_ascii=False, indent=2))
            
            # 创建群组对象
            group = AgentGroup(group_id, config)
            self.groups[group_id] = group
            
            logger.info(f"创建群组成功: {group_name} ({group_id})")
            
            return {
                "success": True,
                "group": group.to_dict()
            }
            
        except Exception as e:
            logger.error(f"创建群组失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_group(self, group_id: str) -> Optional[AgentGroup]:
        """获取群组"""
        return self.groups.get(group_id)
    
    async def delete_group(self, group_id: str) -> bool:
        """删除群组"""
        try:
            if group_id not in self.groups:
                logger.warning(f"群组不存在: {group_id}")
                return False
            
            # 删除群组目录
            group_dir = self.base_dir / group_id
            import shutil
            shutil.rmtree(group_dir)
            
            # 删除群组数据
            user_group_dir = self.user_data_dir / group_id
            if user_group_dir.exists():
                shutil.rmtree(user_group_dir)
            
            # 从内存删除
            del self.groups[group_id]
            
            logger.info(f"删除群组成功: {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除群组失败: {e}")
            return False
    
    async def create_topic(
        self, 
        group_id: str,
        topic_name: str = "新话题"
    ) -> dict:
        """创建新话题"""
        try:
            group = self.groups.get(group_id)
            if not group:
                return {
                    "success": False,
                    "error": "群组不存在"
                }
            
            topic_id = f"topic_{uuid.uuid4().hex[:12]}"
            
            # 创建话题对象
            topic = Topic(topic_id, {
                "id": topic_id,
                "name": topic_name,
                "groupId": group_id,
                "createdAt": datetime.now().timestamp()
            })
            
            # 添加到群组
            group.topics.append(topic.to_dict())
            
            # 更新群组配置
            group_dir = self.base_dir / group_id
            config_path = group_dir / "config.json"
            async with aiofiles.open(config_path, 'w', encoding=Encoding.UTF8) as f:
                await f.write(json.dumps(group.to_dict(), ensure_ascii=False, indent=2))
            
            # 创建话题历史文件
            topic_dir = self.user_data_dir / group_id / "topics" / topic_id
            topic_dir.mkdir(parents=True, exist_ok=True)
            
            history_path = topic_dir / "history.json"
            async with aiofiles.open(history_path, 'w', encoding=Encoding.UTF8) as f:
                await f.write(json.dumps([], ensure_ascii=False, indent=2))
            
            logger.info(f"创建话题成功: {topic_name} ({topic_id})")
            
            return {
                "success": True,
                "topic": topic.to_dict()
            }
            
        except Exception as e:
            logger.error(f"创建话题失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def add_message(
        self,
        group_id: str,
        topic_id: str,
        sender: str,
        content: str,
        message_type: str = "text"
    ) -> dict:
        """添加消息到群聊历史"""
        try:
            group = self.groups.get(group_id)
            if not group:
                return {
                    "success": False,
                    "error": "群组不存在"
                }
            
            # 检查话题是否存在
            topic_exists = any(t['id'] == topic_id for t in group.topics)
            if not topic_exists:
                return {
                    "success": False,
                    "error": "话题不存在"
                }
            
            # 创建消息
            message = {
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "sender": sender,
                "content": content,
                "type": message_type,
                "timestamp": datetime.now().isoformat()
            }
            
            # 添加到历史
            history_path = self.user_data_dir / group_id / "topics" / topic_id / "history.json"
            
            # 读取现有历史
            if history_path.exists():
                async with aiofiles.open(history_path, 'r', encoding=Encoding.UTF8) as f:
                    history = json.loads(await f.read())
            else:
                history = []
            
            # 添加新消息
            history.append(message)
            
            # 保存历史
            async with aiofiles.open(history_path, 'w', encoding=Encoding.UTF8) as f:
                await f.write(json.dumps(history, ensure_ascii=False, indent=2))
            
            return {
                "success": True,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_history(
        self,
        group_id: str,
        topic_id: str,
        limit: int = 100
    ) -> list:
        """获取群聊历史"""
        try:
            history_path = self.user_data_dir / group_id / "topics" / topic_id / "history.json"
            
            if not history_path.exists():
                return []
            
            async with aiofiles.open(history_path, 'r', encoding=Encoding.UTF8) as f:
                history = json.loads(await f.read())
            
            # 返回最新的N条消息
            return history[-limit:] if limit > 0 else history
            
        except Exception as e:
            logger.error(f"获取历史失败: {e}")
            return []
    
    def get_all_groups(self) -> List[dict]:
        """获取所有群组"""
        return [group.to_dict() for group in self.groups.values()]


# 全局群聊管理器实例
_group_chat_manager: Optional[GroupChatManager] = None


def get_group_chat_manager(base_dir: str = None) -> GroupChatManager:
    """获取全局群聊管理器实例"""
    global _group_chat_manager
    if _group_chat_manager is None:
        _group_chat_manager = GroupChatManager(base_dir)
    return _group_chat_manager
