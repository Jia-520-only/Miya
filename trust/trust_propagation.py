"""
信任传播与衰减
实现信任值在节点网络中的传播
"""
from typing import Dict, List, Tuple
from .trust_score import TrustScore


class TrustPropagation:
    """信任传播系统"""

    def __init__(self, trust_score: TrustScore):
        self.trust_score = trust_score
        self.propagation_history = []

    def propagate(self, source: str, path: List[str], decay_factor: float = 0.9) -> float:
        """
        沿路径传播信任

        Args:
            source: 源节点
            path: 路径节点列表
            decay_factor: 衰减因子

        Returns:
            传播后的信任值
        """
        if not path:
            return 0.0

        # 获取源节点信任
        source_trust = self.trust_score.get_score(source)

        # 沿路径传播
        propagated_trust = source_trust

        for i, node in enumerate(path):
            # 节点自身信任
            node_trust = self.trust_score.get_score(node)

            # 传播信任 = 当前信任 * 节点信任 * 衰减
            propagated_trust = propagated_trust * node_trust * decay_factor

            # 记录传播步骤
            self.propagation_history.append({
                'source': source,
                'path': path[:i+1],
                'trust_at_step': propagated_trust,
                'timestamp': self._get_timestamp()
            })

        return propagated_trust

    def propagate_bfs(self, source: str, max_depth: int = 3,
                     min_threshold: float = 0.1) -> Dict[str, float]:
        """
        BFS信任传播

        Args:
            source: 源节点
            max_depth: 最大深度
            min_threshold: 最小阈值

        Returns:
            {node_id: propagated_trust}
        """
        propagated = {}
        queue = [(source, 0, self.trust_score.get_score(source))]

        while queue:
            current, depth, current_trust = queue.pop(0)

            if depth >= max_depth or current_trust < min_threshold:
                continue

            # 获取交互历史中的相关节点
            neighbors = self._get_neighbors(current)

            for neighbor in neighbors:
                neighbor_trust = self.trust_score.get_score(neighbor)
                propagated_trust = current_trust * neighbor_trust * 0.9

                if propagated_trust >= min_threshold:
                    if neighbor not in propagated or propagated_trust > propagated[neighbor]:
                        propagated[neighbor] = propagated_trust
                        queue.append((neighbor, depth + 1, propagated_trust))

        return propagated

    def _get_neighbors(self, node_id: str) -> List[str]:
        """获取邻居节点"""
        # 简化实现：从交互历史中提取相关节点
        neighbors = []

        if node_id in self.trust_score.interaction_history:
            for interaction in self.trust_score.interaction_history[node_id]:
                # 这里应该根据实际数据结构提取邻居
                # 简化实现：返回空列表
                pass

        return neighbors

    def calculate_network_trust(self) -> Dict:
        """计算网络整体信任度"""
        stats = self.trust_score.get_trust_stats()

        if stats['total_nodes'] == 0:
            return {
                'status': 'no_nodes',
                'network_trust': 0.0
            }

        # 网络信任度 = 平均信任 * 高信任节点比例
        avg_score = stats['avg_score']
        high_trust_ratio = stats['high_trust_count'] / stats['total_nodes']

        network_trust = avg_score * (0.7 + 0.3 * high_trust_ratio)

        return {
            'network_trust': round(network_trust, 3),
            'avg_score': avg_score,
            'high_trust_ratio': round(high_trust_ratio, 3),
            'node_count': stats['total_nodes']
        }

    def find_trust_path(self, source: str, target: str,
                       min_trust: float = 0.5) -> List[str]:
        """
        查找信任路径

        Returns:
            路径节点列表，找不到则返回空列表
        """
        # 简化实现：直接返回
        if self.trust_score.get_score(source) >= min_trust and \
           self.trust_score.get_score(target) >= min_trust:
            return [source, target]

        return []

    def get_propagation_stats(self) -> Dict:
        """获取传播统计"""
        if not self.propagation_history:
            return {
                'total_propagations': 0,
                'avg_trust_reached': 0.0
            }

        total = len(self.propagation_history)
        avg_trust = sum(
            h['trust_at_step']
            for h in self.propagation_history
        ) / total

        return {
            'total_propagations': total,
            'avg_trust_reached': round(avg_trust, 3),
            'last_propagation': self.propagation_history[-1]['timestamp']
        }

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
