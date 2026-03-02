"""
戴森球全域感知
实现全域感知系统
"""
from typing import Dict, List, Optional
from datetime import datetime


class PerceptualRing:
    """感知环系统"""

    def __init__(self):
        # 感知维度
        self.dimensions = {
            'internal': {},      # 内部状态感知
            'external': {},      # 外部输入感知
            'temporal': {},      # 时间维度感知
            'social': {},        # 社交维度感知
            'emotional': {}      # 情绪维度感知
        }

        # 感知历史
        self.perception_history = []

        # 感知阈值
        self.thresholds = {
            'internal': 0.5,
            'external': 0.3,
            'temporal': 0.4,
            'social': 0.4,
            'emotional': 0.5
        }

    def perceive(self, dimension: str, data: Dict) -> Dict:
        """
        感知指定维度的信息

        Args:
            dimension: 感知维度
            data: 感知数据

        Returns:
            感知结果
        """
        if dimension not in self.dimensions:
            return {'error': 'Invalid dimension'}

        # 计算感知强度
        intensity = self._calculate_intensity(dimension, data)

        # 检查是否超过阈值
        threshold = self.thresholds[dimension]
        is_significant = intensity >= threshold

        # 更新维度状态
        self.dimensions[dimension] = {
            'data': data,
            'intensity': intensity,
            'significant': is_significant,
            'timestamp': datetime.now()
        }

        # 记录历史
        self._record_perception(dimension, data, intensity, is_significant)

        return {
            'dimension': dimension,
            'intensity': intensity,
            'significant': is_significant,
            'data': data
        }

    def get_global_state(self) -> Dict:
        """获取全局感知状态"""
        global_state = {
            'timestamp': datetime.now().isoformat(),
            'dimensions': {},
            'significant_events': []
        }

        # 汇总各维度状态
        for dim_name, dim_state in self.dimensions.items():
            global_state['dimensions'][dim_name] = {
                'intensity': dim_state.get('intensity', 0),
                'significant': dim_state.get('significant', False)
            }

            if dim_state.get('significant', False):
                global_state['significant_events'].append(dim_name)

        # 计算整体感知强度
        global_state['overall_intensity'] = self._calculate_overall_intensity()

        return global_state

    def _calculate_intensity(self, dimension: str, data: Dict) -> float:
        """计算感知强度"""
        # 简化实现：基于数据复杂度计算强度
        data_size = len(str(data))
        normalized_size = min(1.0, data_size / 1000)
        return round(normalized_size, 3)

    def _calculate_overall_intensity(self) -> float:
        """计算整体感知强度"""
        intensities = [
            dim.get('intensity', 0)
            for dim in self.dimensions.values()
        ]

        if not intensities:
            return 0.0

        return round(sum(intensities) / len(intensities), 3)

    def _record_perception(self, dimension: str, data: Dict,
                           intensity: float, significant: bool) -> None:
        """记录感知历史"""
        self.perception_history.append({
            'dimension': dimension,
            'data': data,
            'intensity': intensity,
            'significant': significant,
            'timestamp': datetime.now()
        })

        # 只保留最近200条
        if len(self.perception_history) > 200:
            self.perception_history = self.perception_history[-200:]

    def get_perception_stats(self) -> Dict:
        """获取感知统计"""
        if not self.perception_history:
            return {'total': 0}

        significant_count = sum(
            1 for p in self.perception_history
            if p['significant']
        )

        dimension_counts = {}
        for p in self.perception_history:
            dim = p['dimension']
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1

        return {
            'total': len(self.perception_history),
            'significant': significant_count,
            'dimension_distribution': dimension_counts
        }
