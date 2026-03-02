"""
酒馆记忆系统
TavernMemory - 管理酒馆对话和偏好记忆
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class TavernMemory:
    """酒馆记忆管理器"""

    def __init__(self, storage_path: str = "data/tavern_memory.json"):
        self.storage_path = storage_path
        self._data = {
            "sessions": {},  # 会话记忆
            "players": {},   # 玩家偏好
            "stories": {}    # 故事历史
        }
        self._load()

    def _load(self):
        """加载记忆数据"""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {
                "sessions": {},
                "players": {},
                "stories": {}
            }

    def _save(self):
        """保存记忆数据"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存酒馆记忆失败: {e}")

    # 会话记忆
    def add_message(self, chat_id: str, role: str, content: str):
        """添加消息到会话记忆"""
        if chat_id not in self._data["sessions"]:
            self._data["sessions"][chat_id] = []

        self._data["sessions"][chat_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        # 限制会话长度（保留最近 50 条）
        if len(self._data["sessions"][chat_id]) > 50:
            self._data["sessions"][chat_id] = self._data["sessions"][chat_id][-50:]

        self._save()

    def get_recent_messages(self, chat_id: str, limit: int = 10) -> List[Dict]:
        """获取最近的对话"""
        if chat_id not in self._data["sessions"]:
            return []
        return self._data["sessions"][chat_id][-limit:]

    def clear_session(self, chat_id: str):
        """清除会话记忆"""
        if chat_id in self._data["sessions"]:
            del self._data["sessions"][chat_id]
            self._save()

    # 玩家偏好记忆
    def remember_player_trait(self, user_id: str, trait: str, value: str):
        """记住玩家性格特点"""
        if user_id not in self._data["players"]:
            self._data["players"][user_id] = {
                "traits": {},
                "preferences": [],
                "first_visit": datetime.now().isoformat()
            }

        self._data["players"][user_id]["traits"][trait] = value
        self._save()

    def remember_preference(self, user_id: str, preference: str):
        """记住玩家偏好"""
        if user_id not in self._data["players"]:
            self._data["players"][user_id] = {
                "traits": {},
                "preferences": [],
                "first_visit": datetime.now().isoformat()
            }

        self._data["players"][user_id]["preferences"].append({
            "preference": preference,
            "timestamp": datetime.now().isoformat()
        })

        # 保留最近 20 条偏好
        if len(self._data["players"][user_id]["preferences"]) > 20:
            self._data["players"][user_id]["preferences"] = \
                self._data["players"][user_id]["preferences"][-20:]

        self._save()

    def get_player_info(self, user_id: str) -> Dict:
        """获取玩家信息"""
        return self._data["players"].get(user_id, {})

    # 故事记忆
    def save_story(self, story_id: str, theme: str, content: str):
        """保存故事"""
        self._data["stories"][story_id] = {
            "theme": theme,
            "content": content,
            "created_at": datetime.now().isoformat()
        }
        self._save()

    def get_story(self, story_id: str) -> Optional[Dict]:
        """获取故事"""
        return self._data["stories"].get(story_id)

    def list_stories(self, limit: int = 10) -> List[Dict]:
        """列出故事"""
        stories = list(self._data["stories"].values())
        # 按时间倒序
        stories.sort(key=lambda x: x["created_at"], reverse=True)
        return stories[:limit]

    # 模式和情绪
    def set_mode(self, chat_id: str, mode: str):
        """设置模式"""
        if chat_id not in self._data["sessions"]:
            self._data["sessions"][chat_id] = []

        self._data["sessions"][chat_id].append({
            "role": "system",
            "content": f"[系统] 模式切换为: {mode}",
            "timestamp": datetime.now().isoformat()
        })
        self._save()

    def set_mood(self, chat_id: str, mood: str):
        """设置情绪氛围"""
        if chat_id not in self._data["sessions"]:
            self._data["sessions"][chat_id] = []

        self._data["sessions"][chat_id].append({
            "role": "system",
            "content": f"[系统] 情绪氛围切换为: {mood}",
            "timestamp": datetime.now().isoformat()
        })
        self._save()
