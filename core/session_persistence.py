"""
终端会话持久化 - 弥娅V4.0

支持终端会话的保存和恢复
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class SessionPersistence:
    """会话持久化"""
    
    def __init__(self, storage_dir: str = "data/sessions"):
        self.storage_dir = storage_dir
        self.ensure_storage_dir()
    
    def ensure_storage_dir(self):
        """确保存储目录存在"""
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def save_session(
        self,
        session_id: str,
        session_data: Dict
    ):
        """保存会话
        
        Args:
            session_id: 会话ID
            session_data: 会话数据
        """
        
        session_file = os.path.join(self.storage_dir, f"{session_id}.json")
        
        # 添加时间戳
        session_data['saved_at'] = datetime.now().isoformat()
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        """加载会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据或None
        """
        
        session_file = os.path.join(self.storage_dir, f"{session_id}.json")
        
        if not os.path.exists(session_file):
            return None
        
        with open(session_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_sessions(self) -> List[str]:
        """列出所有已保存的会话
        
        Returns:
            会话ID列表
        """
        
        if not os.path.exists(self.storage_dir):
            return []
        
        session_files = [f for f in os.listdir(self.storage_dir) if f.endswith('.json')]
        
        return [f[:-5] for f in session_files]
    
    def delete_session(self, session_id: str):
        """删除会话
        
        Args:
            session_id: 会话ID
        """
        
        session_file = os.path.join(self.storage_dir, f"{session_id}.json")
        
        if os.path.exists(session_file):
            os.remove(session_file)
    
    def save_workspace(
        self,
        workspace_name: str,
        workspace_data: Dict
    ):
        """保存工作空间
        
        Args:
            workspace_name: 工作空间名称
            workspace_data: 工作空间数据
        """
        
        workspace_file = os.path.join(self.storage_dir, "workspaces.json")
        
        # 加载现有工作空间
        workspaces = {}
        if os.path.exists(workspace_file):
            with open(workspace_file, 'r', encoding='utf-8') as f:
                workspaces = json.load(f)
        
        # 更新或添加工作空间
        workspaces[workspace_name] = workspace_data
        workspaces[workspace_name]['updated_at'] = datetime.now().isoformat()
        
        with open(workspace_file, 'w', encoding='utf-8') as f:
            json.dump(workspaces, f, indent=2, ensure_ascii=False)
    
    def load_workspace(self, workspace_name: str) -> Optional[Dict]:
        """加载工作空间
        
        Args:
            workspace_name: 工作空间名称
            
        Returns:
            工作空间数据或None
        """
        
        workspace_file = os.path.join(self.storage_dir, "workspaces.json")
        
        if not os.path.exists(workspace_file):
            return None
        
        with open(workspace_file, 'r', encoding='utf-8') as f:
            workspaces = json.load(f)
        
        return workspaces.get(workspace_name)
    
    def list_workspaces(self) -> List[str]:
        """列出所有工作空间
        
        Returns:
            工作空间名称列表
        """
        
        workspace_file = os.path.join(self.storage_dir, "workspaces.json")
        
        if not os.path.exists(workspace_file):
            return []
        
        with open(workspace_file, 'r', encoding='utf-8') as f:
            workspaces = json.load(f)
        
        return list(workspaces.keys())
