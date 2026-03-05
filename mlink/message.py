"""
消息结构定义
定义系统内的消息格式
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum


class MessageType(str, Enum):
    """消息类型枚举"""
    CONTROL = "control"
    RESPONSE = "response"
    ERROR = "error"
    SYNC = "sync"
    DATA = "data"
    EMOTION = "emotion"
    MEMORY = "memory"
    TRUST = "trust"


class FlowType(str, Enum):
    """流类型枚举"""
    CONTROL_FLOW = "control_flow"
    DATA_FLOW = "data_flow"
    EMOTION_FLOW = "emotion_flow"
    MEMORY_FLOW = "memory_flow"
    TRUST_FLOW = "trust_flow"


class Message:
    """消息类"""

    def __init__(self, msg_type: str, content: Any, source: str,
                 destination: str = None, priority: int = 0):
        self.message_id = str(uuid.uuid4())
        self.msg_type = msg_type
        self.content = content
        self.source = source
        self.destination = destination
        self.priority = priority
        self.created_at = datetime.now()
        self.metadata = {}
        self.status = 'pending'

        # 消息流类型
        self.flow_type = self._determine_flow_type()

    def _determine_flow_type(self) -> str:
        """根据消息类型确定流类型"""
        flow_mapping = {
            'data': 'data_flow',
            'control': 'control_flow',
            'emotion': 'emotion_flow',
            'memory': 'memory_flow',
            'trust': 'trust_flow'
        }
        return flow_mapping.get(self.msg_type, 'data_flow')

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'message_id': self.message_id,
            'msg_type': self.msg_type,
            'content': self.content,
            'source': self.source,
            'destination': self.destination,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata,
            'status': self.status,
            'flow_type': self.flow_type
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """从字典创建消息"""
        msg = cls(
            msg_type=data['msg_type'],
            content=data['content'],
            source=data['source'],
            destination=data.get('destination'),
            priority=data.get('priority', 0)
        )
        msg.message_id = data['message_id']
        msg.created_at = datetime.fromisoformat(data['created_at'])
        msg.metadata = data.get('metadata', {})
        msg.status = data.get('status', 'pending')
        return msg

    def update_status(self, status: str) -> None:
        """更新消息状态"""
        self.status = status

    def add_metadata(self, key: str, value: Any) -> None:
        """添加元数据"""
        self.metadata[key] = value
