"""
决策层辅助方法
"""
from typing import Dict, List


def count_memory_types(memory_context: List[Dict]) -> Dict[str, int]:
    """
    统计记忆类型分布

    Args:
        memory_context: 记忆上下文列表

    Returns:
        记忆类型统计
    """
    counts = {'dialogue': 0, 'fact': 0, 'tide': 0, 'graph': 0, 'unknown': 0}
    for mem in memory_context:
        source = mem.get('source', 'unknown')
        if source == 'conversation' or source in ['qq', 'pc_ui']:
            counts['dialogue'] += 1
        elif source == 'undefined':
            counts['fact'] += 1
        elif source == 'tide':
            counts['tide'] += 1
        elif source == 'neo4j' or source == 'graph':
            counts['graph'] += 1
        else:
            counts['unknown'] += 1
    return counts
