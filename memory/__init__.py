"""
弥娅记忆系统 (Miya Memory System) V4.1
=======================================

    自成一个体系的完整记忆服务子系统。

    **唯一入口: MemoryBus**

    用法:
        from memory import MemoryBus

        bus = await MemoryBus.instance()

        # 存储
        await bus.store_dialogue("你好", role="user", user_id="123")
        await bus.store_important("佳喜欢蓝色", user_id="123", tags=["偏好"])

        # 检索
        result = await bus.recall("颜色偏好", user_id="123")

        # 注入
        prompt = await bus.inject(user_id="123", user_input="我喜欢蓝色")

        # 认知
        await bus.store_cognition(thinking="佳今天好像心情不太好...")

    旧 API 仍可用但已标记 deprecated，请迁移到 MemoryBus。
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# =====================================================================
# 公共 API — 唯一入口
# =====================================================================

from memory.api import MemoryBus, RecallRequest, RecallResult, get_memory_bus, reset_memory_bus

# =====================================================================
# 数据模型 — 供类型标注
# =====================================================================

from memory.models import (
    MemoryItem,
    MemoryLevel,
    MemoryPriority,
    MemoryQuery,
    MemorySource,
)

# =====================================================================
# 内部模块 — 兼容旧代码的路由入口
# =====================================================================

from memory.core import (
    JsonBackend,
    MemoryBackend,
    MiyaMemoryCore,
    get_memory_core,
    reset_memory_core,
)

from memory.cognitive_engine import CognitiveEngine, get_cognitive_engine
from memory.memory_enhancer import (
    EmotionType,
    MemoryEnhancer,
    MemoryLink,
    get_memory_enhancer,
)
from memory.injection_pipeline import (
    CacheStrategy,
    HookContext,
    InjectionPipeline,
    InjectionPoint,
    get_injection_pipeline,
)
from memory.default_hooks import register_default_hooks
from memory.vector_index import VectorIndex, get_vector_index
try:
    from memory.vector_store import CognitiveVectorStore
except ImportError as exc:
    _VECTOR_STORE_IMPORT_ERROR = exc

    class CognitiveVectorStore:  # type: ignore[no-redef]
        """Placeholder used by minimal profiles that omit ChromaDB."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError("CognitiveVectorStore requires the full dependency profile") from _VECTOR_STORE_IMPORT_ERROR
from memory.historian import JobQueue, HistorianWorker
from memory.profile_storage import ProfileStorage
from memory.skill_manager import SkillManager, get_skill_manager
from memory.skill_models import (
    Skill,
    SkillCategory,
    SkillSource,
    SkillStatus,
    SkillStep,
    SkillTrigger,
    SkillVersion,
)
from memory.rrf_fusion import RRFusion, get_rrf_fusion
from memory.llm_extractor import LLMExtractor, get_llm_extractor
from memory.quality_scorer import QualityScorer, get_quality_scorer

logger = logging.getLogger(__name__)


def load_memory_config() -> Dict[str, Any]:
    """统一从 memory_config.json 加载记忆配置，回退到 text_config.json

    所有 memory/ 下的模块都应通过此函数获取配置，避免重复的
    "优先 memory_config.json 回退 text_config.json" 逻辑散布在各文件中。
    """
    try:
        config_dir = Path(__file__).parent.parent / "config"

        mem_config_path = config_dir / "memory_config.json"
        if mem_config_path.exists():
            with open(mem_config_path, "r", encoding="utf-8") as f:
                return json.load(f)

        text_config_path = config_dir / "text_config.json"
        if text_config_path.exists():
            with open(text_config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"[memory] 统一配置加载失败: {e}")
    return {}


# =====================================================================
# 便捷函数 — MemoryBus 直通委托
# =====================================================================


async def store_dialogue(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.store_dialogue(*args, **kwargs)


async def store_important(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.store_important(*args, **kwargs)


async def store_auto(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.store_auto(*args, **kwargs)


async def store_knowledge(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.store_knowledge(*args, **kwargs)


async def store_cognition(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.store_cognition(*args, **kwargs)


async def retrieve_cognition(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.recall_cognition(*args, **kwargs)


async def search_cognition(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.search_cognition(*args, **kwargs)


async def search_memory(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.search(*args, **kwargs)


async def get_user_memories(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.get_user_memories(*args, **kwargs)


async def get_user_dialogue(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.get_user_dialogue(*args, **kwargs)


async def get_dialogue_history(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.get_dialogue_history(*args, **kwargs)


async def get_user_profile(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.user_profile(*args, **kwargs)


async def update_memory(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.update(*args, **kwargs)


async def delete_memory(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.delete(*args, **kwargs)


async def cleanup_expired(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.cleanup_expired(*args, **kwargs)


async def get_memory_stats(*args, **kwargs):
    bus = await get_memory_bus()
    return await bus.stats(*args, **kwargs)


def get_unified_memory(data_dir=None):
    return MiyaMemoryCore(data_dir or "data/memory") if data_dir else MiyaMemoryCore()


async def init_unified_memory(data_dir=None):
    return get_unified_memory(data_dir)


# =====================================================================
# 导出
# =====================================================================

__all__ = [
    "MemoryBus",
    "RecallRequest",
    "RecallResult",
    "get_memory_bus",
    "reset_memory_bus",
    "MemoryItem",
    "MemoryLevel",
    "MemoryPriority",
    "MemoryQuery",
    "MemorySource",
    "MiyaMemoryCore",
    "get_memory_core",
    "reset_memory_core",
    "get_unified_memory",
    "init_unified_memory",
    "store_dialogue",
    "store_important",
    "store_auto",
    "store_knowledge",
    "store_cognition",
    "retrieve_cognition",
    "search_cognition",
    "search_memory",
    "get_user_memories",
    "get_user_dialogue",
    "get_dialogue_history",
    "get_user_profile",
    "update_memory",
    "delete_memory",
    "cleanup_expired",
    "get_memory_stats",
    "MemoryEnhancer",
    "get_memory_enhancer",
    "EmotionType",
    "MemoryLink",
    "RRFusion",
    "get_rrf_fusion",
    "LLMExtractor",
    "get_llm_extractor",
    "QualityScorer",
    "get_quality_scorer",
    "Skill",
    "SkillCategory",
    "SkillSource",
    "SkillStatus",
    "SkillStep",
    "SkillTrigger",
    "SkillVersion",
    "SkillManager",
    "get_skill_manager",
    "InjectionPipeline",
    "InjectionPoint",
    "CacheStrategy",
    "HookContext",
    "get_injection_pipeline",
    "register_default_hooks",
    "VectorIndex",
    "get_vector_index",
    "CognitiveVectorStore",
    "JobQueue",
    "HistorianWorker",
    "ProfileStorage",
    "CognitiveEngine",
    "get_cognitive_engine",
    "get_memory_adapter",
]


# V4.1.11: 兼容 shim — get_memory_adapter 代理到 MemoryBus
async def get_memory_adapter():
    """获取统一记忆适配器（兼容旧代码，委托到 MemoryBus）"""
    bus = await get_memory_bus()
    return bus
