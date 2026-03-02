"""
动态路径评分
实现消息路由和路径评分
"""
from typing import Dict, List, Optional
from .message import Message


class Router:
    """路由系统"""

    def __init__(self):
        # 路径缓存
        self.path_cache = {}
        # 节点状态
        self.node_status = {}

    def route(self, message: Message, available_nodes: List[str]) -> Optional[str]:
        """
        路由消息到目标节点

        Args:
            message: 待路由消息
            available_nodes: 可用节点列表

        Returns:
            选中的目标节点
        """
        if not available_nodes:
            return None

        # 如果有指定目标，直接返回
        if message.destination and message.destination in available_nodes:
            return message.destination

        # 否则使用动态评分选择
        scores = self._score_nodes(message, available_nodes)
        best_node = max(scores.items(), key=lambda x: x[1])[0]
        return best_node

    def _score_nodes(self, message: Message, nodes: List[str]) -> Dict[str, float]:
        """对节点进行评分"""
        scores = {}

        for node in nodes:
            score = 0.0

            # 基础可用性评分
            base_score = self.node_status.get(node, {}).get('available', 1.0)
            score += base_score * 0.3

            # 负载评分
            load_score = self._calculate_load_score(node)
            score += load_score * 0.3

            # 匹配度评分
            match_score = self._calculate_match_score(message, node)
            score += match_score * 0.4

            scores[node] = round(score, 3)

        return scores

    def _calculate_load_score(self, node: str) -> float:
        """计算负载评分"""
        status = self.node_status.get(node, {})
        load = status.get('load', 0.5)
        # 负载越低，评分越高
        return max(0, 1.0 - load)

    def _calculate_match_score(self, message: Message, node: str) -> float:
        """计算匹配度评分"""
        node_capabilities = self.node_status.get(node, {}).get('capabilities', [])

        if message.flow_type in node_capabilities:
            return 1.0
        elif 'general' in node_capabilities:
            return 0.5
        else:
            return 0.3

    def update_node_status(self, node: str, status: Dict) -> None:
        """更新节点状态"""
        if node not in self.node_status:
            self.node_status[node] = {}

        self.node_status[node].update(status)

    def get_routing_stats(self) -> Dict:
        """获取路由统计"""
        return {
            'total_nodes': len(self.node_status),
            'active_nodes': sum(
                1 for status in self.node_status.values()
                if status.get('available', False)
            )
        }
