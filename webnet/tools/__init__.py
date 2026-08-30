"""
工具系统（符合弥娅框架）
稳定、独立、可维修、故障隔离
"""

from .base import (
    BaseTool,
    ToolContext,
    ToolRegistry
)
from .tool_instance import (
    ToolInstance,
    ToolHealthState,
    ToolCircuitBreaker,
    ToolMetrics
)
from .tool_monitor import (
    ToolMonitor,
    ToolStatistics,
    get_tool_monitor
)

__all__ = [
    # 核心类
    'BaseTool',
    'ToolContext',
    'ToolRegistry',

    # 工具实例
    'ToolInstance',
    'ToolHealthState',
    'ToolCircuitBreaker',
    'ToolMetrics',

    # 监控和统计
    'ToolMonitor',
    'ToolStatistics',
    'get_tool_monitor',
]

"""
弥娅框架 - 工具系统架构
========================

核心原则
--------

1. 稳定性 (Stability)
   - 熔断器机制：自动熔断故障工具
   - 重试机制：自动重试失败的调用
   - 状态验证：工具执行前检查健康状态

2. 独立性 (Independence)
   - 工具实例隔离：每个工具有独立的熔断器和统计
   - 错误隔离：一个工具失败不影响其他工具
   - 上下文隔离：工具执行有独立的上下文

3. 可维修性 (Maintainability)
   - 集中监控：统一的工具健康监控
   - 详细日志：完整的执行日志和错误追踪
   - 诊断工具：工具级别的诊断报告

4. 故障隔离 (Fault Isolation)
   - 自动熔断：频繁失败的工具自动禁用
   - 降级策略：失败时返回友好提示
   - 恢复机制：半开状态自动探测恢复

架构层次
---------

┌─────────────────────────────────────┐
│       ToolRegistry                  │  ← 工具注册表（统一入口）
│   • 工具注册和发现                   │
│   • 工具执行（带熔断）                │
│   • 健康状态查询                     │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       ToolInstance                 │  ← 工具实例（隔离层）
│   • 熔断器                         │
│   • 健康状态                         │
│   • 指标统计                         │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       BaseTool                    │  ← 工具基类（实现层）
│   • 安全执行（重试+降级）              │
│   • 参数验证                         │
│   • 日志记录                         │
└─────────────────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       ToolMonitor                 │  ← 监控层
│   • 健康监控                        │
│   • 统计分析                        │
│   • 诊断报告                        │
└─────────────────────────────────────┘

使用示例
--------

# 1. 注册工具（自动创建实例）
from webnet.tools import ToolRegistry, BaseTool

registry = ToolRegistry()

class MyTool(BaseTool):
    @property
    def config(self):
        return {
            "name": "my_tool",
            "description": "我的工具",
            "parameters": {"type": "object", "properties": {}}
        }

    async def execute(self, args, context):
        return "工具执行成功"

registry.register(MyTool())

# 2. 执行工具（自动熔断和降级）
result = await registry.execute_tool("my_tool", {}, context)

# 3. 查询工具健康状态
health = registry.get_tool_health("my_tool")
print(health['health_state'])  # healthy / degraded / unstable / broken

# 4. 监控所有工具
from webnet.tools import get_tool_monitor

monitor = get_tool_monitor(registry)
report = monitor.generate_report()
print(report)

# 5. 重置工具（恢复熔断器）
registry.reset_tool("my_tool")

熔断器配置
----------

ToolCircuitBreaker.FAILURE_THRESHOLD = 3        # 失败次数阈值
ToolCircuitBreaker.FAILURE_RATE_THRESHOLD = 0.5  # 失败率阈值
ToolCircuitBreaker.RECOVERY_TIMEOUT = 60          # 恢复超时（秒）
ToolCircuitBreaker.WINDOW_SIZE = 60              # 统计窗口（秒）

熔断器状态
----------

CLOSED    - 关闭（正常）：所有请求通过
OPEN      - 打开（熔断）：所有请求拒绝
HALF_OPEN - 半开（探测）：允许部分请求通过测试

工具健康状态
------------

HEALTHY   - 健康：失败率 < 10%
DEGRADED  - 降级：10% ≤ 失败率 < 30%
UNSTABLE  - 不稳定：30% ≤ 失败率 < 50%
BROKEN    - 损坏：失败率 ≥ 50% 或熔断器打开

与弥娅框架集成
--------------

1. DecisionHub 集成
   - 自动过滤不健康的工具
   - 根据工具健康状态调整 AI 选择

2. ToolNet 集成
   - 统一的工具注册表
   - 工具执行统一入口

3. 游戏模式集成
   - 游戏工具也享受相同的熔断和监控
   - 游戏实例独立于工具实例

最佳实践
--------

1. 工具实现
   - 继承 BaseTool
   - 实现 config 和 execute 方法
   - 设置合适的 fallback_message

2. 错误处理
   - 使用 try-except 捕获异常
   - 记录详细的错误日志
   - 返回友好的错误信息

3. 监控告警
   - 定期检查工具健康状态
   - 失败率超过阈值时告警
   - 定期生成监控报告

4. 工具维护
   - 定期重置熔断器
   - 分析工具错误日志
   - 优化工具性能
"""
