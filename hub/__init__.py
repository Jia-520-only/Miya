"""
蛛网主中枢 - 认知核心

v4.1.11 架构：
- MiyaOrchestrator: 轻量级编排器（替代 DecisionHub 门面）
- 独立服务层：Perception → Cognition → Decision → Generation → Memory
- DecisionHub: 兼容保留（逐步迁移到 MiyaOrchestrator）
"""

from .decision import Decision
from .decision_hub import DecisionHub
from .emotion import Emotion
from .memory_manager import MemoryManager
from .perception_handler import PerceptionHandler
from .response_generator import ResponseGenerator
from .scheduler import Scheduler

from core.memory_engine_shim import MemoryEngineShim as MemoryEngine
from core.memory_engine_shim import MemoryEngineShim as MemoryEmotion

from hub.services import (
    MiyaOrchestrator,
    PerceptionService,
    CognitionService,
    DecisionService,
    GenerationService,
    MemoryService,
    ProcessRequest,
    ProcessResult,
    ProcessState,
)

__all__ = [
    "MemoryEmotion",
    "MemoryEngine",
    "Emotion",
    "Decision",
    "Scheduler",
    "DecisionHub",
    "PerceptionHandler",
    "ResponseGenerator",
    "MemoryManager",
    "MiyaOrchestrator",
    "PerceptionService",
    "CognitionService",
    "DecisionService",
    "GenerationService",
    "MemoryService",
    "ProcessRequest",
    "ProcessResult",
    "ProcessState",
]
