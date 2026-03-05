"""
子网热插拔管理器
管理子网的注册、注销和状态
"""
from typing import Dict, List, Optional
from datetime import datetime


class NetNode:
    """子网节点"""

    def __init__(self, net_id: str, net_type: str, config: Dict = None):
        self.net_id = net_id
        self.net_type = net_type
        self.config = config or {}
        self.status = 'registered'
        self.registered_at = datetime.now()
        self.last_active = datetime.now()
        self.health_score = 1.0


class NetManager:
    """子网管理器"""

    def __init__(self):
        self.networks = {}  # net_id -> NetNode
        self.type_index = {}  # net_type -> List[net_id]

    def register(self, net_id: str, net_type: str,
                 config: Dict = None) -> bool:
        """注册子网"""
        if net_id in self.networks:
            return False

        node = NetNode(net_id, net_type, config)
        self.networks[net_id] = node

        # 更新类型索引
        if net_type not in self.type_index:
            self.type_index[net_type] = []
        self.type_index[net_type].append(net_id)

        node.status = 'active'
        return True

    def unregister(self, net_id: str) -> bool:
        """注销子网"""
        if net_id not in self.networks:
            return False

        node = self.networks[net_id]
        net_type = node.net_type

        # 从类型索引中移除
        if net_type in self.type_index:
            self.type_index[net_type].remove(net_id)

        # 标记为已注销
        node.status = 'unregistered'
        del self.networks[net_id]

        return True

    def get_network(self, net_id: str) -> Optional[NetNode]:
        """获取子网"""
        return self.networks.get(net_id)

    def get_networks_by_type(self, net_type: str) -> List[NetNode]:
        """按类型获取子网列表"""
        net_ids = self.type_index.get(net_type, [])
        return [self.networks[nid] for nid in net_ids if nid in self.networks]

    def update_health(self, net_id: str, health_score: float) -> bool:
        """更新子网健康度"""
        if net_id not in self.networks:
            return False

        self.networks[net_id].health_score = max(0.0, min(1.0, health_score))
        self.networks[net_id].last_active = datetime.now()
        return True

    def get_active_networks(self) -> List[NetNode]:
        """获取活跃子网"""
        return [
            node for node in self.networks.values()
            if node.status == 'active'
        ]

    def get_network_stats(self) -> Dict:
        """获取子网统计"""
        total = len(self.networks)
        active = len(self.get_active_networks())

        type_counts = {
            net_type: len(net_ids)
            for net_type, net_ids in self.type_index.items()
        }

        avg_health = 0.0
        if self.networks:
            avg_health = sum(n.health_score for n in self.networks.values()) / total

        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'by_type': type_counts,
            'avg_health': round(avg_health, 3)
        }
