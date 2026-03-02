"""
节点交叉检测
检测节点之间的交叉和冲突
"""
from typing import Dict, List, Set


class NodeDetector:
    """节点检测器"""

    def __init__(self):
        self.nodes = {}
        self.connections = []
        self.crossings = []

    def register_node(self, node_id: str, node_type: str,
                     position: tuple = None, attributes: Dict = None) -> None:
        """注册节点"""
        self.nodes[node_id] = {
            'type': node_type,
            'position': position or (0, 0),
            'attributes': attributes or {}
        }

    def add_connection(self, node1: str, node2: str,
                      connection_type: str = 'general') -> None:
        """添加连接"""
        if node1 not in self.nodes or node2 not in self.nodes:
            return

        self.connections.append({
            'node1': node1,
            'node2': node2,
            'type': connection_type
        })

    def detect_crossing(self) -> List[Dict]:
        """检测节点交叉"""
        crossings = []
        nodes_list = list(self.nodes.keys())

        # 检测重叠位置
        position_map = {}
        for node_id, node_info in self.nodes.items():
            pos = node_info['position']
            if pos in position_map:
                position_map[pos].append(node_id)
            else:
                position_map[pos] = [node_id]

        # 发现重叠节点
        for pos, node_ids in position_map.items():
            if len(node_ids) > 1:
                crossings.append({
                    'type': 'position_overlap',
                    'position': pos,
                    'nodes': node_ids,
                    'count': len(node_ids)
                })

        # 检测循环依赖
        cycles = self._detect_cycles()
        crossings.extend(cycles)

        # 检测多重连接
        multi_connections = self._detect_multi_connections()
        crossings.extend(multi_connections)

        self.crossings = crossings
        return crossings

    def _detect_cycles(self) -> List[Dict]:
        """检测循环依赖"""
        cycles = []

        # 构建邻接表
        adj = {nid: [] for nid in self.nodes}
        for conn in self.connections:
            adj[conn['node1']].append(conn['node2'])

        # DFS检测环
        visited = set()
        recursion_stack = set()

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)

            for neighbor in adj[node]:
                if neighbor in recursion_stack:
                    # 发现环
                    cycle_start = path.index(neighbor)
                    cycles.append({
                        'type': 'cycle',
                        'nodes': path[cycle_start:] + [neighbor]
                    })
                elif neighbor not in visited:
                    dfs(neighbor, path.copy())

            recursion_stack.remove(node)
            return False

        for node in self.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def _detect_multi_connections(self) -> List[Dict]:
        """检测多重连接"""
        connection_counts = {}

        for conn in self.connections:
            key = tuple(sorted((conn['node1'], conn['node2'])))
            connection_counts[key] = connection_counts.get(key, 0) + 1

        multi = []
        for (n1, n2), count in connection_counts.items():
            if count > 1:
                multi.append({
                    'type': 'multi_connection',
                    'nodes': (n1, n2),
                    'count': count
                })

        return multi

    def analyze_connectivity(self) -> Dict:
        """分析连接性"""
        if not self.nodes:
            return {'status': 'no_nodes'}

        # 计算度
        degrees = {nid: 0 for nid in self.nodes}
        for conn in self.connections:
            degrees[conn['node1']] += 1
            degrees[conn['node2']] += 1

        # 检测孤立节点
        isolated = [nid for nid, deg in degrees.items() if deg == 0]

        # 检测中心节点
        if degrees:
            max_degree = max(degrees.values())
            centers = [nid for nid, deg in degrees.items() if deg == max_degree]
        else:
            centers = []

        return {
            'total_nodes': len(self.nodes),
            'total_connections': len(self.connections),
            'isolated_nodes': isolated,
            'center_nodes': centers,
            'crossings_detected': len(self.crossings)
        }

    def get_crossing_stats(self) -> Dict:
        """获取交叉统计"""
        crossing_types = {}
        for crossing in self.crossings:
            ctype = crossing.get('type', 'unknown')
            crossing_types[ctype] = crossing_types.get(ctype, 0) + 1

        return {
            'total_crossings': len(self.crossings),
            'by_type': crossing_types
        }
