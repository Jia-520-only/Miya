"""
娱乐网络查询模块
提供专门针对跑团和酒馆故事的查询系统
"""

from .tavern_query_system import TavernQuerySystem
from .trpg_query_system import TRPGQuerySystem

__all__ = [
    'TavernQuerySystem',
    'TRPGQuerySystem',
]
