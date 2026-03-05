"""
会话管理系统
支持三种 KP 模式：independent（独立）、cross_group（跨群）、global（全局）
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from core.constants import Encoding


@dataclass
class TRPGSession:
    """TRPG 会话配置"""

    session_id: str           # 会话 ID
    group_id: int             # 群号

    # KP 模式配置
    kp_mode: str = "independent"  # independent, cross_group, global

    # 独立 KP 模式
    kp_id: int = 0            # 当前群的 KP

    # 跨群 KP 模式
    allowed_groups: List[int] = field(default_factory=list)  # 允许跨群的群列表
    shared_kp_id: int = 0     # 跨群的统一 KP

    # 全局 KP 模式
    global_kp_id: int = 0     # 全局唯一 KP

    # 会话信息
    rule_system: str = "coc7"  # 规则系统
    session_name: str = "未命名团"  # 团名称

    # 玩家列表
    players: List[int] = field(default_factory=list)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def get_kp_id(self) -> int:
        """获取当前会话的 KP"""
        if self.kp_mode == "independent":
            return self.kp_id
        elif self.kp_mode == "cross_group":
            return self.shared_kp_id
        elif self.kp_mode == "global":
            return self.global_kp_id
        return 0

    def set_kp_mode(self, mode: str, kp_id: int = 0, allowed_groups: List[int] = None):
        """设置 KP 模式"""
        self.kp_mode = mode
        self.updated_at = datetime.now()

        if mode == "independent":
            self.kp_id = kp_id
        elif mode == "cross_group":
            self.shared_kp_id = kp_id
            if allowed_groups:
                self.allowed_groups = allowed_groups
        elif mode == "global":
            self.global_kp_id = kp_id

    def add_player(self, player_id: int):
        """添加玩家"""
        if player_id not in self.players:
            self.players.append(player_id)
            self.updated_at = datetime.now()

    def remove_player(self, player_id: int):
        """移除玩家"""
        if player_id in self.players:
            self.players.remove(player_id)
            self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'group_id': self.group_id,
            'kp_mode': self.kp_mode,
            'kp_id': self.kp_id,
            'allowed_groups': self.allowed_groups,
            'shared_kp_id': self.shared_kp_id,
            'global_kp_id': self.global_kp_id,
            'rule_system': self.rule_system,
            'session_name': self.session_name,
            'players': self.players,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class SessionManager:
    """会话管理器"""

    def __init__(self, data_path: str = "data/trpg_sessions.json"):
        self.data_path = Path(data_path)
        self.sessions: Dict[int, TRPGSession] = {}  # group_id -> TRPGSession
        self.global_kp_id: int = 0
        self.load()

    def load(self):
        """加载会话数据"""
        if self.data_path.exists():
            try:
                with open(self.data_path, 'r', encoding=Encoding.UTF8) as f:
                    data = json.load(f)
                    for session_data in data:
                        session = TRPGSession(
                            session_id=session_data['session_id'],
                            group_id=session_data['group_id'],
                            kp_mode=session_data.get('kp_mode', 'independent'),
                            kp_id=session_data.get('kp_id', 0),
                            allowed_groups=session_data.get('allowed_groups', []),
                            shared_kp_id=session_data.get('shared_kp_id', 0),
                            global_kp_id=session_data.get('global_kp_id', 0),
                            rule_system=session_data.get('rule_system', 'coc7'),
                            session_name=session_data.get('session_name', '未命名团'),
                            players=session_data.get('players', [])
                        )
                        self.sessions[session.group_id] = session
                    print(f"[SessionManager] 加载了 {len(self.sessions)} 个会话")
            except Exception as e:
                print(f"[SessionManager] 加载失败: {e}")

    def save(self):
        """保存会话数据"""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            data = [session.to_dict() for session in self.sessions.values()]
            with open(self.data_path, 'w', encoding=Encoding.UTF8) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SessionManager] 保存失败: {e}")

    def get_or_create(self, group_id: int) -> TRPGSession:
        """获取或创建会话"""
        if group_id not in self.sessions:
            session = TRPGSession(
                session_id=f"session_{group_id}",
                group_id=group_id
            )
            self.sessions[group_id] = session
            self.save()
        return self.sessions[group_id]

    def get(self, group_id: int) -> Optional[TRPGSession]:
        """获取会话"""
        return self.sessions.get(group_id)

    def delete(self, group_id: int):
        """删除会话"""
        if group_id in self.sessions:
            del self.sessions[group_id]
            self.save()

    def set_global_kp(self, user_id: int):
        """设置全局 KP"""
        self.global_kp_id = user_id
        # 更新所有使用全局模式的会话
        for session in self.sessions.values():
            if session.kp_mode == "global":
                session.global_kp_id = user_id
        self.save()

    def list_sessions(self) -> List[TRPGSession]:
        """列出所有会话"""
        return list(self.sessions.values())


# 全局单例
_session_manager = None


def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
