"""
记忆系统模块

提供多种记忆存储和检索功能
"""

# 认知记忆系统
from .cognitive_memory_system import (
    CognitiveMemorySystem,
    get_cognitive_memory,
    MemoryType,
    MemoryEvent,
    CognitiveJob,
)

# 统一记忆接口（第一阶段）
from .memory_interface import (
    MemoryType as UnifiedMemoryType,
    MemoryItem,
    BaseMemoryInterface,
    MemoryManager,
    get_memory_manager,
)

# 认知记忆适配器
from .cognitive_adapter import (
    CognitiveMemoryAdapter,
    create_cognitive_adapter,
)

# 向量缓存
from .vector_cache import (
    VectorCacheManager,
    get_vector_cache_manager,
)

# 其他记忆模块
from .event_memory import EventMemory
from .grag_memory import GRAGMemoryManager
from .multimodal_memory_store import MultiModalMemoryStore
from .memory_compressor import MemoryCompressor
from .memory_replay import MemoryReplayScheduler
from .memory_scorer import MemoryImportanceScorer

__all__ = [
    # 认知记忆系统
    'CognitiveMemorySystem',
    'get_cognitive_memory',
    'MemoryType',
    'MemoryEvent',
    'CognitiveJob',
    
    # 统一记忆接口
    'UnifiedMemoryType',
    'MemoryItem',
    'BaseMemoryInterface',
    'MemoryManager',
    'get_memory_manager',
    
    # 认知记忆适配器
    'CognitiveMemoryAdapter',
    'create_cognitive_adapter',
    
    # 向量缓存
    'VectorCacheManager',
    'get_vector_cache_manager',
    
    # 其他记忆模块
    'EventMemory',
    'GRAGMemoryManager',
    'MultiModalMemoryStore',
    'MemoryCompressor',
    'MemoryReplayScheduler',
    'MemoryImportanceScorer',
]
