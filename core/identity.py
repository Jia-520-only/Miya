"""
自我认知与UUID
定义弥娅的身份标识和自我认知系统
"""
import uuid
from typing import Dict
from datetime import datetime


class Identity:
    """身份系统"""

    def __init__(self):
        self.uuid = str(uuid.uuid4())
        self.name = "弥娅"
        self.version = "1.0.0"
        self.birth_time = datetime.now()
        self.awake_time = None

        # 自我认知属性
        self.self_cognition = {
            'role': 'AI助手',
            'purpose': '协助用户解决问题',
            'capabilities': [],
            'limitations': []
        }

    def awake(self) -> None:
        """激活意识"""
        if self.awake_time is None:
            self.awake_time = datetime.now()

    def get_identity(self) -> Dict:
        """获取身份信息"""
        return {
            'uuid': self.uuid,
            'name': self.name,
            'version': self.version,
            'birth_time': self.birth_time.isoformat(),
            'awake_time': self.awake_time.isoformat() if self.awake_time else None,
            'awake_duration': self._calculate_awake_duration()
        }

    def add_capability(self, capability: str) -> None:
        """添加能力"""
        if capability not in self.self_cognition['capabilities']:
            self.self_cognition['capabilities'].append(capability)

    def add_limitation(self, limitation: str) -> None:
        """添加限制"""
        if limitation not in self.self_cognition['limitations']:
            self.self_cognition['limitations'].append(limitation)

    def _calculate_awake_duration(self) -> float:
        """计算已激活时长（秒）"""
        if self.awake_time is None:
            return 0.0
        return (datetime.now() - self.awake_time).total_seconds()
