"""
记忆回放调度器
定期回顾重要记忆，强化关键信息
"""
from typing import Dict, List
import time


class MemoryReplayScheduler:
    """记忆回放调度器"""

    def __init__(self, event_memory):
        self.event_memory = event_memory
        self.replay_intervals = {
            'birthday': 365,
            'achievement': 90,
            'bonding': 30,
            'crisis': 7,
            'preference': 14
        }

    def should_replay_today(self, event: Dict) -> bool:
        """判断今天是否应该回放事件"""
        import datetime
        now = datetime.datetime.now()
        event_time = datetime.datetime.fromtimestamp(event['timestamp'])

        # 计算距离上次回放的天数
        days_since = (now - event_time).days

        event_type = event['type']
        interval = self.replay_intervals.get(event_type, 30)

        return days_since > 0 and days_since % interval == 0

    def get_replay_events(self) -> List[Dict]:
        """获取今天需要回放的事件"""
        today_events = []
        for event in self.event_memory.events.values():
            if self.should_replay_today(event):
                today_events.append(event)

        return today_events

    def get_replay_context(self, events: List[Dict]) -> str:
        """生成回放上下文"""
        if not events:
            return ""

        context_lines = ["【记忆回放】", ""]
        for event in events:
            event_type = event['type']
            details = event['details']

            context_lines.append(f"事件类型：{event_type}")
            context_lines.append(f"详情：{details}")
            context_lines.append("")

        return "\n".join(context_lines)
