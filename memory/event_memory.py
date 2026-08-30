"""
事件记忆系统
记录重要事件（生日、成就、危机等），支持情感连接
"""
from typing import Dict, List, Optional
import uuid
import time


class EventMemory:
    """事件记忆系统"""

    EVENT_TYPES = {
        'birthday': '用户生日',
        'achievement': '用户成就',
        'crisis': '危机事件',
        'bonding': '情感连接时刻',
        'preference': '用户偏好',
        'milestone': '里程碑事件'
    }

    def __init__(self, storage_backend=None):
        self.storage = storage_backend
        self.events = {}

    def record_event(self, event_type: str, timestamp: float,
                    details: Dict, importance: float = 0.8) -> str:
        """记录事件"""
        event_id = str(uuid.uuid4())
        event = {
            'id': event_id,
            'type': event_type,
            'timestamp': timestamp,
            'details': details,
            'importance': importance,
            'recalled_count': 0
        }
        self.events[event_id] = event
        return event_id

    def get_event(self, event_id: str) -> Optional[Dict]:
        """获取事件"""
        return self.events.get(event_id)

    def get_relevant_events(self, context: str, limit: int = 3) -> List[Dict]:
        """根据上下文检索相关事件"""
        # 简化实现：返回最重要的事件
        sorted_events = sorted(
            self.events.values(),
            key=lambda e: e['importance'],
            reverse=True
        )
        return sorted_events[:limit]

    def get_events_by_type(self, event_type: str) -> List[Dict]:
        """按类型获取事件"""
        return [e for e in self.events.values()
                if e['type'] == event_type]

    def get_upcoming_events(self, days: int = 7) -> List[Dict]:
        """获取未来N天内的事件"""
        import datetime
        upcoming = []
        now = datetime.datetime.now()

        for event in self.events.values():
            # 简化实现：只处理生日等周期性事件
            if event['type'] == 'birthday':
                birth_month = event['details'].get('month')
                birth_day = event['details'].get('day')

                if birth_month and birth_day:
                    # 计算下一个生日
                    next_birthday = datetime.datetime(
                        now.year, birth_month, birth_day
                    )
                    if next_birthday < now:
                        next_birthday = datetime.datetime(
                            now.year + 1, birth_month, birth_day
                        )

                    days_until = (next_birthday - now).days
                    if 0 <= days_until <= days:
                        upcoming.append({
                            **event,
                            'next_date': next_birthday.strftime('%Y-%m-%d'),
                            'days_until': days_until
                        })

        return upcoming
