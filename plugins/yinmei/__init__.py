"""
吟美虚拟主播插件 - 深度嵌入弥娅系统

提供完整的虚拟主播功能：
- 聚合弹幕 (B站/抖音/快手等)
- OBS 场景控制
- AI 唱歌 / 绘画
- 跳舞 / 表情视频
- 搜图 / 搜索
- 鉴黄过滤
- 摄像头 / 电脑控制
"""

from .tools.singleton_mode import singleton
from .config import YinmeiConfig
from .core.live_stream_hub import LiveStreamHub

__all__ = ["singleton", "YinmeiConfig", "LiveStreamHub"]
