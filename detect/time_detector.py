"""
时间环绕检测
检测时间维度上的环绕和异常
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class TimeDetector:
    """时间检测器"""

    def __init__(self):
        self.time_events = []
        self.time_patterns = {}
        self.anomalies = []

    def record_event(self, event_id: str, timestamp: str,
                     event_type: str = 'general') -> None:
        """记录时间事件"""
        event = {
            'id': event_id,
            'timestamp': timestamp,
            'type': event_type,
            'parsed_time': datetime.fromisoformat(timestamp)
        }

        self.time_events.append(event)
        self._detect_time_loop(event)

    def detect_loop(self, time_window: int = 3600) -> List[Dict]:
        """
        检测时间环绕

        Args:
            time_window: 时间窗口（秒）

        Returns:
            检测到的环绕
        """
        loops = []

        if len(self.time_events) < 2:
            return loops

        # 查找重复的时间模式
        for i, event1 in enumerate(self.time_events):
            for event2 in self.time_events[i+1:]:
                time_diff = abs((event2['parsed_time'] - event1['parsed_time']).total_seconds())

                if time_diff < time_window and event1['type'] == event2['type']:
                    loops.append({
                        'event1': event1,
                        'event2': event2,
                        'time_diff': time_diff,
                        'loop_detected': True
                    })

        return loops

    def _detect_time_loop(self, event: Dict) -> None:
        """内部时间环绕检测"""
        # 简化实现
        pass

    def detect_anomaly(self, threshold: float = 2.0) -> List[Dict]:
        """
        检测时间异常

        Args:
            threshold: 异常阈值（标准差倍数）

        Returns:
            检测到的异常
        """
        if len(self.time_events) < 5:
            return []

        anomalies = []

        # 计算时间间隔
        intervals = []
        for i in range(1, len(self.time_events)):
            diff = (self.time_events[i]['parsed_time'] -
                   self.time_events[i-1]['parsed_time']).total_seconds()
            intervals.append(diff)

        # 计算统计量
        import statistics
        mean_interval = statistics.mean(intervals)
        if len(intervals) > 1:
            stdev = statistics.stdev(intervals)
        else:
            stdev = 0

        # 检测异常
        for i, interval in enumerate(intervals):
            if stdev > 0 and abs(interval - mean_interval) > threshold * stdev:
                anomalies.append({
                    'event_index': i + 1,
                    'interval': interval,
                    'mean': mean_interval,
                    'deviation': abs(interval - mean_interval) / stdev,
                    'anomaly_type': 'time_interval'
                })

        self.anomalies = anomalies
        return anomalies

    def get_time_stats(self) -> Dict:
        """获取时间统计"""
        if not self.time_events:
            return {'status': 'no_events'}

        timestamps = [e['parsed_time'] for e in self.time_events]
        time_range = max(timestamps) - min(timestamps)

        # 按类型统计
        type_counts = {}
        for event in self.time_events:
            etype = event['type']
            type_counts[etype] = type_counts.get(etype, 0) + 1

        return {
            'total_events': len(self.time_events),
            'time_range_seconds': time_range.total_seconds(),
            'type_distribution': type_counts,
            'anomalies_detected': len(self.anomalies)
        }
