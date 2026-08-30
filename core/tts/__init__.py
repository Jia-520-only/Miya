"""
MIYA TTS 系统 - 模块化文本转语音子系统

结构说明：
- base.py: TTSEngine 抽象基类（定义TTS引擎的统一接口）
- manager.py: TTSRegistry 注册管理器（管理多个TTS引擎）
- providers.py: 具体TTS引擎实现
  - APITTSEngine: OpenAI/Azure/讯飞/百度/阿里API
  - SystemTTSEngine: 系统TTS (Windows/macOS/Linux)
  - GPTSoviTSEngine: GPT-SoVITS v2 引擎
- utils.py: 文本处理工具函数
- subnet.py: M-Link 网络集成层

推荐使用方式：
```python
# 1. 快速使用全局注册表
from core.tts import get_tts_registry
registry = get_tts_registry()
audio = await registry.synthesize("你好", engine_name="gpt_sovits")

# 2. M-Link集成
from core.tts import TTSNet
tts_net = TTSNet(mlink=mlink_core)

# 3. 直接使用具体引擎
from core.tts import GPTSoviTSEngine
engine = GPTSoviTSEngine()
engine.initialize({"api_url": "http://localhost:5000"})
audio = await engine.synthesize("你好")
```

版本历史：
v2.1.0: 模块化重构，统一TTS系统架构，实现Subnet设计模式
"""

# 基础抽象层
from .base import TTSEngine

# 管理层 - 包含全局注册表helper
from .manager import TTSRegistry, get_tts_registry

# 提供者实现层
from .providers import (
    APITTSEngine,  # OpenAI/Azure/讯飞/百度/阿里 API
    GPTSoviTSEngine,  # GPT-SoVITS v2
    SystemTTSEngine,  # Windows SAPI / macOS say / Linux espeak
)

# M-Link网络集成
from .subnet import TTSNet

# 工具函数
from .utils import (
    filter_text,  # 文本过滤
    split_text_for_qq,  # QQ文本分割
)

__all__ = [
    # 抽象基类
    "TTSEngine",
    # 管理器
    "TTSRegistry",
    "get_tts_registry",
    # 具体实现
    "APITTSEngine",
    "SystemTTSEngine",
    "GPTSoviTSEngine",
    # 工具函数
    "filter_text",
    "split_text_for_qq",
    # 子网
    "TTSNet",
]

__version__ = "2.1.0"
