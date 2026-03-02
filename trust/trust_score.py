"""
节点信任评分
计算和管理节点的信任分数
"""
from typing import Dict, List
from datetime import datetime, timedelta


class TrustScore:
    """信任评分系统"""

    def __init__(self):
        self.trust_scores = {}  # node_id -> score
        self.interaction_history = {}  # node_id -> List[interactions]
        self.decay_rate = 0.05  # 每天衰减率

    def register_node(self, node_id: str, initial_score: float = 0.5) -> None:
        """注册节点"""
        if node_id not in self.trust_scores:
            self.trust_scores[node_id] = max(0.0, min(1.0, initial_score))
            self.interaction_history[node_id] = []

    def get_score(self, node_id: str) -> float:
        """获取信任分数"""
        return self.trust_scores.get(node_id, 0.5)

    def update_score(self, node_id: str, delta: float) -> bool:
        """
        更新信任分数

        Args:
            node_id: 节点ID
            delta: 变化量 (-1 到 1)
        """
        if node_id not in self.trust_scores:
            return False

        old_score = self.trust_scores[node_id]
        new_score = old_score + delta * 0.1  # 缩放变化量
        new_score = max(0.0, min(1.0, new_score))

        self.trust_scores[node_id] = new_score
        return True

    def record_interaction(self, node_id: str, interaction_type: str,
                          outcome: str = 'success') -> None:
        """
        记录交互

        Args:
            node_id: 节点ID
            interaction_type: 交互类型
            outcome: 结果 (success/failure)
        """
        if node_id not in self.interaction_history:
            self.interaction_history[node_id] = []

        interaction = {
            'type': interaction_type,
            'outcome': outcome,
            'timestamp': datetime.now()
        }

        self.interaction_history[node_id].append(interaction)

        # 根据结果更新信任分数
        if outcome == 'success':
            self.update_score(node_id, 0.1)
        elif outcome == 'failure':
            self.update_score(node_id, -0.2)

    def decay_scores(self, older_than_hours: int = 24) -> int:
        """信任分数衰减"""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)

        decayed_count = 0

        for node_id, interactions in self.interaction_history.items():
            # 检查是否有近期交互
            recent_interactions = [
                i for i in interactions
                if i['timestamp'] > cutoff
            ]

            if not recent_interactions:
                # 没有近期交互，衰减信任分数
                old_score = self.trust_scores.get(node_id, 0.5)
                new_score = old_score * (1 - self.decay_rate)
                self.trust_scores[node_id] = new_score
                decayed_count += 1

        return decayed_count

    def get_high_trust_nodes(self, threshold: float = 0.7) -> List[tuple]:
        """
        获取高信任节点

        Returns:
            [(node_id, score), ...]
        """
        high_trust = [
            (node_id, score)
            for node_id, score in self.trust_scores.items()
            if score >= threshold
        ]

        # 按分数排序
        high_trust.sort(key=lambda x: x[1], reverse=True)
        return high_trust

    def get_low_trust_nodes(self, threshold: float = 0.3) -> List[tuple]:
        """
        获取低信任节点

        Returns:
            [(node_id, score), ...]
        """
        low_trust = [
            (node_id, score)
            for node_id, score in self.trust_scores.items()
            if score < threshold
        ]

        low_trust.sort(key=lambda x: x[1])
        return low_trust

    def calculate_reputation(self, node_id: str) -> Dict:
        """计算节点声誉"""
        if node_id not in self.interaction_history:
            return {
                'node_id': node_id,
                'status': 'unknown',
                'trust_score': 0.5
            }

        interactions = self.interaction_history[node_id]
        total = len(interactions)
        successful = sum(1 for i in interactions if i['outcome'] == 'success')
        failed = total - successful

        success_rate = successful / total if total > 0 else 0
        trust_score = self.get_score(node_id)

        reputation = 'high'
        if trust_score < 0.3:
            reputation = 'low'
        elif trust_score < 0.7:
            reputation = 'medium'

        return {
            'node_id': node_id,
            'total_interactions': total,
            'successful': successful,
            'failed': failed,
            'success_rate': round(success_rate, 3),
            'trust_score': trust_score,
            'reputation': reputation
        }

    def get_trust_stats(self) -> Dict:
        """获取信任统计"""
        if not self.trust_scores:
            return {
                'total_nodes': 0,
                'avg_score': 0.0
            }

        scores = list(self.trust_scores.values())

        return {
            'total_nodes': len(scores),
            'avg_score': round(sum(scores) / len(scores), 3),
            'min_score': min(scores),
            'max_score': max(scores),
            'high_trust_count': len(self.get_high_trust_nodes()),
            'low_trust_count': len(self.get_low_trust_nodes())
        }
