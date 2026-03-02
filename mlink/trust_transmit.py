"""
信任传播算法
实现信任值的传播和衰减
"""
from typing import Dict, List
from datetime import datetime, timedelta


class TrustTransmit:
    """信任传播系统"""

    def __init__(self, decay_rate: float = 0.05):
        self.decay_rate = decay_rate
        self.trust_matrix = {}  # (source, target) -> trust_value
        self.propagation_history = []

    def set_trust(self, source: str, target: str, value: float) -> None:
        """设置信任值"""
        key = (source, target)
        self.trust_matrix[key] = max(0.0, min(1.0, value))

    def get_trust(self, source: str, target: str) -> float:
        """获取信任值"""
        key = (source, target)
        return self.trust_matrix.get(key, 0.5)

    def propagate_trust(self, path: List[str], initial_trust: float = 1.0) -> float:
        """
        沿路径传播信任

        Args:
            path: 节点路径 [A, B, C, ...]
            initial_trust: 初始信任值

        Returns:
            最终传播后的信任值
        """
        if len(path) < 2:
            return initial_trust

        current_trust = initial_trust

        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]
            edge_trust = self.get_trust(source, target)

            # 信任传播：当前信任 * 边信任
            current_trust *= edge_trust

            # 记录传播
            self.propagation_history.append({
                'path': path[:i+2],
                'trust': current_trust,
                'timestamp': datetime.now()
            })

        return current_trust

    def decay_trust(self, older_than_hours: int = 24) -> int:
        """信任值衰减"""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)

        # 查找需要衰减的信任关系
        keys_to_update = [
            key for key, value in self.trust_matrix.items()
            if self._should_decay(key, cutoff)
        ]

        for key in keys_to_update:
            old_value = self.trust_matrix[key]
            new_value = max(0.0, old_value - self.decay_rate)
            self.trust_matrix[key] = new_value

        return len(keys_to_update)

    def _should_decay(self, key: tuple, cutoff: datetime) -> bool:
        """判断是否应该衰减"""
        # 简化实现：所有信任关系都会衰减
        return True

    def calculate_path_trust(self, path: List[str]) -> float:
        """计算路径的整体信任值"""
        return self.propagate_trust(path)

    def get_high_trust_nodes(self, source: str, threshold: float = 0.7) -> List[str]:
        """获取高信任节点"""
        high_trust_nodes = []

        for (s, t), value in self.trust_matrix.items():
            if s == source and value >= threshold:
                high_trust_nodes.append((t, value))

        # 按信任值排序
        high_trust_nodes.sort(key=lambda x: x[1], reverse=True)
        return [node for node, _ in high_trust_nodes]

    def get_trust_stats(self) -> Dict:
        """获取信任统计"""
        if not self.trust_matrix:
            return {
                'total_relations': 0,
                'avg_trust': 0.0
            }

        trust_values = list(self.trust_matrix.values())
        return {
            'total_relations': len(self.trust_matrix),
            'avg_trust': sum(trust_values) / len(trust_values),
            'min_trust': min(trust_values),
            'max_trust': max(trust_values)
        }
