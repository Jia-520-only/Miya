"""
跨子网关联推理
实现跨子网的信息关联和推理
"""
from typing import Dict, List, Optional, Set
from .net_manager import NetManager


class CrossNetEngine:
    """跨子网推理引擎"""

    def __init__(self, net_manager: NetManager):
        self.net_manager = net_manager

        # 关联图
        self.association_graph = {}  # (net1, net2) -> association_strength

        # 推理历史
        self.inference_history = []

    def associate(self, net1: str, net2: str, strength: float = 0.5) -> None:
        """
        建立子网关联

        Args:
            net1: 子网ID
            net2: 子网ID
            strength: 关联强度 (0-1)
        """
        key = tuple(sorted((net1, net2)))
        self.association_graph[key] = max(0.0, min(1.0, strength))

    def get_association_strength(self, net1: str, net2: str) -> float:
        """获取关联强度"""
        key = tuple(sorted((net1, net2)))
        return self.association_graph.get(key, 0.0)

    def find_associated_networks(self, net_id: str, threshold: float = 0.5) -> List[str]:
        """查找关联子网"""
        associated = []

        for (n1, n2), strength in self.association_graph.items():
            if n1 == net_id and strength >= threshold:
                associated.append(n2)
            elif n2 == net_id and strength >= threshold:
                associated.append(n1)

        return associated

    def propagate_inference(self, source_net: str, data: Dict,
                           max_depth: int = 3) -> List[Dict]:
        """
        跨子网传播推理

        Args:
            source_net: 源子网
            data: 推理数据
            max_depth: 最大传播深度

        Returns:
            推理结果列表
        """
        results = []
        visited = set()
        queue = [(source_net, 0, data)]

        while queue:
            current_net, depth, current_data = queue.pop(0)

            if depth >= max_depth or current_net in visited:
                continue

            visited.add(current_net)

            # 记录推理步骤
            results.append({
                'net': current_net,
                'depth': depth,
                'data': current_data
            })

            # 查找关联子网
            associated = self.find_associated_networks(current_net, threshold=0.3)
            for next_net in associated:
                association_strength = self.get_association_strength(current_net, next_net)
                # 数据随关联强度衰减
                propagated_data = self._decay_data(current_data, association_strength)
                queue.append((next_net, depth + 1, propagated_data))

        return results

    def _decay_data(self, data: Dict, decay_factor: float) -> Dict:
        """数据衰减"""
        decayed = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                decayed[key] = value * decay_factor
            else:
                decayed[key] = value
        return decayed

    def find_path(self, start: str, end: str, min_strength: float = 0.5) -> Optional[List[str]]:
        """查找子网路径"""
        if start == end:
            return [start]

        # BFS查找路径
        queue = [(start, [start])]
        visited = set()

        while queue:
            current, path = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)

            if current == end:
                return path

            associated = self.find_associated_networks(current, min_strength)
            for next_net in associated:
                if next_net not in visited:
                    queue.append((next_net, path + [next_net]))

        return None

    def get_association_stats(self) -> Dict:
        """获取关联统计"""
        total = len(self.association_graph)
        if total == 0:
            return {'total': 0}

        strengths = list(self.association_graph.values())
        return {
            'total': total,
            'avg_strength': round(sum(strengths) / total, 3),
            'min_strength': min(strengths),
            'max_strength': max(strengths)
        }
