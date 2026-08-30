"""
空间环绕检测
检测空间维度上的环绕和异常
"""
from typing import Dict, List, Tuple, Optional


class SpaceDetector:
    """空间检测器"""

    def __init__(self):
        self.spatial_events = []
        self.spatial_patterns = {}
        self.anomalies = []

    def record_position(self, entity_id: str, position: Tuple[float, float, float],
                         timestamp: str = None) -> None:
        """
        记录空间位置

        Args:
            entity_id: 实体ID
            position: 三维坐标 (x, y, z)
            timestamp: 时间戳
        """
        if not timestamp:
            from datetime import datetime
            timestamp = datetime.now().isoformat()

        event = {
            'entity_id': entity_id,
            'position': position,
            'timestamp': timestamp
        }

        self.spatial_events.append(event)

    def detect_loop(self, distance_threshold: float = 1.0,
                    time_window: float = 60.0) -> List[Dict]:
        """
        检测空间环绕

        Args:
            distance_threshold: 距离阈值
            time_window: 时间窗口（秒）

        Returns:
            检测到的环绕
        """
        loops = []

        if len(self.spatial_events) < 2:
            return loops

        # 按实体分组
        entity_events = {}
        for event in self.spatial_events:
            eid = event['entity_id']
            if eid not in entity_events:
                entity_events[eid] = []
            entity_events[eid].append(event)

        # 检测每个实体的环绕
        for eid, events in entity_events.items():
            for i, event1 in enumerate(events):
                for event2 in events[i+1:]:
                    # 计算时间差
                    time_diff = self._calculate_time_diff(event1['timestamp'], event2['timestamp'])

                    if time_diff <= time_window:
                        # 计算距离
                        distance = self._calculate_distance(event1['position'], event2['position'])

                        if distance < distance_threshold:
                            loops.append({
                                'entity_id': eid,
                                'position1': event1['position'],
                                'position2': event2['position'],
                                'distance': distance,
                                'time_diff': time_diff,
                                'loop_detected': True
                            })

        return loops

    def detect_anomaly(self, z_score_threshold: float = 3.0) -> List[Dict]:
        """
        检测空间异常

        Args:
            z_score_threshold: Z分数阈值

        Returns:
            检测到的异常
        """
        if len(self.spatial_events) < 10:
            return []

        anomalies = []

        # 提取所有坐标
        x_coords = [e['position'][0] for e in self.spatial_events]
        y_coords = [e['position'][1] for e in self.spatial_events]
        z_coords = [e['position'][2] for e in self.spatial_events]

        # 计算每个维度的统计量
        import statistics
        coords_stats = [
            ('x', x_coords),
            ('y', y_coords),
            ('z', z_coords)
        ]

        for dim_name, coords in coords_stats:
            mean = statistics.mean(coords)
            if len(coords) > 1:
                stdev = statistics.stdev(coords)
            else:
                stdev = 0

            # 检测异常点
            for i, coord in enumerate(coords):
                if stdev > 0:
                    z_score = abs(coord - mean) / stdev
                    if z_score > z_score_threshold:
                        anomalies.append({
                            'event_index': i,
                            'dimension': dim_name,
                            'value': coord,
                            'mean': mean,
                            'z_score': z_score,
                            'anomaly_type': 'spatial_outlier'
                        })

        self.anomalies = anomalies
        return anomalies

    def _calculate_distance(self, pos1: Tuple[float, float, float],
                            pos2: Tuple[float, float, float]) -> float:
        """计算欧几里得距离"""
        import math
        return math.sqrt(
            (pos1[0] - pos2[0])**2 +
            (pos1[1] - pos2[1])**2 +
            (pos1[2] - pos2[2])**2
        )

    def _calculate_time_diff(self, time1: str, time2: str) -> float:
        """计算时间差"""
        from datetime import datetime
        t1 = datetime.fromisoformat(time1)
        t2 = datetime.fromisoformat(time2)
        return abs((t2 - t1).total_seconds())

    def get_spatial_stats(self) -> Dict:
        """获取空间统计"""
        if not self.spatial_events:
            return {'status': 'no_events'}

        # 计算范围
        x_coords = [e['position'][0] for e in self.spatial_events]
        y_coords = [e['position'][1] for e in self.spatial_events]
        z_coords = [e['position'][2] for e in self.spatial_events]

        return {
            'total_events': len(self.spatial_events),
            'x_range': (min(x_coords), max(x_coords)),
            'y_range': (min(y_coords), max(y_coords)),
            'z_range': (min(z_coords), max(z_coords)),
            'anomalies_detected': len(self.anomalies)
        }
