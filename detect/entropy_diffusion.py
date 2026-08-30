"""
熵扩散·系统内感
监控系统的熵扩散和内感状态
"""
from typing import Dict, List
from datetime import datetime
import numpy as np


class EntropyDiffusion:
    """熵扩散监控系统"""

    def __init__(self):
        self.entropy_history = []
        self.diffusion_coefficient = 0.1
        self.thresholds = {
            'warning': 0.6,
            'critical': 0.8
        }

        # 各子系统熵
        self.subsystem_entropies = {}

    def record_entropy(self, entropy_value: float, subsystem: str = 'global') -> None:
        """
        记录熵值

        Args:
            entropy_value: 熵值 (0-1)
            subsystem: 子系统名称
        """
        record = {
            'timestamp': datetime.now(),
            'entropy': entropy_value,
            'subsystem': subsystem
        }

        self.entropy_history.append(record)

        # 更新子系统熵
        self.subsystem_entropies[subsystem] = entropy_value

    def calculate_diffusion(self, current_entropy: float,
                           time_steps: int = 10) -> List[float]:
        """
        计算熵扩散

        Args:
            current_entropy: 当前熵值
            time_steps: 时间步数

        Returns:
            扩散后的熵值序列
        """
        diffusion_sequence = [current_entropy]

        for _ in range(time_steps):
            # 简化的扩散方程
            prev_entropy = diffusion_sequence[-1]

            # 扩散项：邻近子系统的平均熵
            neighbor_entropy = self._calculate_neighbor_entropy(prev_entropy)

            # 扩散更新
            new_entropy = prev_entropy + self.diffusion_coefficient * (neighbor_entropy - prev_entropy)
            new_entropy = max(0.0, min(1.0, new_entropy))

            diffusion_sequence.append(new_entropy)

        return diffusion_sequence

    def _calculate_neighbor_entropy(self, current: float) -> float:
        """计算邻近子系统的平均熵"""
        if not self.subsystem_entropies:
            return current

        values = list(self.subsystem_entropies.values())
        return sum(values) / len(values)

    def detect_diffusion_anomaly(self) -> Dict:
        """检测扩散异常"""
        if len(self.entropy_history) < 5:
            return {'status': 'insufficient_data'}

        recent = self.entropy_history[-5:]
        entropies = [r['entropy'] for r in recent]

        # 计算趋势
        trend = entropies[-1] - entropies[0]

        # 计算变化率
        changes = [entropies[i+1] - entropies[i] for i in range(len(entropies)-1)]
        avg_change = sum(changes) / len(changes) if changes else 0

        # 确定状态
        current = entropies[-1]
        if current > self.thresholds['critical']:
            status = 'critical'
        elif current > self.thresholds['warning']:
            status = 'warning'
        else:
            status = 'normal'

        return {
            'status': status,
            'current_entropy': current,
            'trend': trend,
            'avg_change': avg_change,
            'is_increasing': trend > 0
        }

    def get_internal_sense(self) -> Dict:
        """
        获取系统内感

        Returns:
            系统内感状态
        """
        if not self.entropy_history:
            return {'status': 'no_data'}

        anomaly = self.detect_diffusion_anomaly()

        # 计算系统协调度
        coordination = self._calculate_coordination()

        # 计算稳定性
        stability = self._calculate_stability()

        return {
            'entropy_status': anomaly['status'],
            'coordination': coordination,
            'stability': stability,
            'subsystem_entropies': self.subsystem_entropies.copy(),
            'timestamp': datetime.now().isoformat()
        }

    def _calculate_coordination(self) -> float:
        """计算系统协调度"""
        if not self.subsystem_entropies:
            return 1.0

        values = list(self.subsystem_entropies.values())
        variance = np.var(values)
        coordination = max(0.0, 1.0 - variance)

        return round(coordination, 3)

    def _calculate_stability(self) -> float:
        """计算系统稳定性"""
        if len(self.entropy_history) < 10:
            return 1.0

        recent = self.entropy_history[-10:]
        entropies = [r['entropy'] for r in recent]

        variance = np.var(entropies)
        stability = max(0.0, 1.0 - variance)

        return round(stability, 3)

    def get_diffusion_report(self) -> Dict:
        """获取扩散报告"""
        internal_sense = self.get_internal_sense()
        anomaly = self.detect_diffusion_anomaly()

        return {
            'internal_sense': internal_sense,
            'anomaly_detection': anomaly,
            'total_records': len(self.entropy_history),
            'subsystem_count': len(self.subsystem_entropies)
        }
