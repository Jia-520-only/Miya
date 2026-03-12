# 工具系统架构优化报告

## 优化目标

将"**稳定、独立、可维修、故障隔离**"的理念扩展到**所有工具**，而不仅仅是游戏模式，完全符合弥娅框架设计。

---

## 核心架构设计

### 四大原则

#### 1. 稳定性 (Stability)
- **熔断器机制**：自动熔断频繁失败的工具
- **重试机制**：自动重试失败的调用
- **状态验证**：工具执行前检查健康状态

#### 2. 独立性 (Independence)
- **工具实例隔离**：每个工具有独立的熔断器和统计
- **错误隔离**：一个工具失败不影响其他工具
- **上下文隔离**：工具执行有独立的上下文

#### 3. 可维修性 (Maintainability)
- **集中监控**：统一的工具健康监控
- **详细日志**：完整的执行日志和错误追踪
- **诊断工具**：工具级别的诊断报告

#### 4. 故障隔离 (Fault Isolation)
- **自动熔断**：频繁失败的工具自动禁用
- **降级策略**：失败时返回友好提示
- **恢复机制**：半开状态自动探测恢复

---

## 新增模块

### 1. `tool_instance.py` - 工具实例管理器

#### ToolCircuitBreaker（熔断器）
```python
class ToolCircuitBreaker:
    FAILURE_THRESHOLD = 3           # 失败次数阈值
    FAILURE_RATE_THRESHOLD = 0.5   # 失败率阈值
    RECOVERY_TIMEOUT = 60          # 恢复超时（秒）
    WINDOW_SIZE = 60               # 统计窗口（秒）
```

**熔断器状态**：
- `CLOSED` - 关闭（正常）：所有请求通过
- `OPEN` - 打开（熔断）：所有请求拒绝
- `HALF_OPEN` - 半开（探测）：允许部分请求通过测试

#### ToolInstance（工具实例）
```python
class ToolInstance:
    def __init__(self, tool_name, tool_class, tool_config):
        self.circuit_breaker = ToolCircuitBreaker(tool_name)
        self.enabled = True
        self.fallback_message = None
        self.priority = 0
```

**核心方法**：
- `should_execute()` - 检查是否应该执行工具
- `record_success()` - 记录成功
- `record_failure()` - 记录失败
- `get_metrics()` - 获取指标统计

---

### 2. `tool_monitor.py` - 工具监控器

#### ToolMonitor
```python
class ToolMonitor:
    def get_all_statistics() -> List[ToolStatistics]
    def get_problematic_tools(failure_rate_threshold=0.3) -> List[ToolStatistics]
    def get_broken_tools() -> List[str]
    def get_health_summary() -> Dict[str, Any]
    def generate_report() -> str
    def diagnose_tool(tool_name) -> Dict
```

#### 工具健康状态
- `HEALTHY` - 健康：失败率 < 10%
- `DEGRADED` - 降级：10% ≤ 失败率 < 30%
- `UNSTABLE` - 不稳定：30% ≤ 失败率 < 50%
- `BROKEN` - 损坏：失败率 ≥ 50% 或熔断器打开

---

### 3. 升级 `base.py` - 工具基类和注册表

#### BaseTool 新增功能
```python
class BaseTool:
    # 新增：安全执行（带重试和降级）
    async def safe_execute(self, args, context) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                return await self.execute(args, context)
            except Exception as e:
                if attempt == self.max_retries:
                    return self._get_fallback_result(e)
                await asyncio.sleep(0.5 * (attempt + 1))
```

#### ToolRegistry 新增功能
```python
class ToolRegistry:
    # 新增：工具实例管理
    self.tool_instances: Dict[str, ToolInstance] = {}

    # 新增：自动过滤不健康的工具
    def get_tools_schema(self, tool_names=None) -> list:
        # 自动过滤已熔断的工具
        for name in names_to_fetch:
            instance = self.get_tool_instance(name)
            if instance and not instance.is_healthy:
                continue  # 跳过不健康的工具

    # 新增：健康状态查询
    def get_tool_health(self, tool_name) -> Dict
    def get_all_tools_health(self) -> Dict[str, Dict]
    def reset_tool(self, tool_name) -> bool
    def disable_tool(self, tool_name) -> bool
    def enable_tool(self, tool_name) -> bool

    # 升级：执行工具（带熔断）
    async def execute_tool(self, tool_name, args, context) -> str:
        instance = self.get_tool_instance(tool_name)
        if not instance.should_execute():
            return "⚠️ 工具暂时不可用，请稍后重试"

        result = await tool.safe_execute(args, context)
        if "暂时不可用" in result:
            instance.record_failure("工具执行失败")
        else:
            instance.record_success()
```

---

## 弥娅框架集成

### DecisionHub 集成

```python
# 【新架构】使用工具健康监控自动过滤不健康的工具
if self.tool_registry:
    # 获取所有可用工具（自动过滤已熔断的工具）
    tools_to_use = self.tool_registry.get_tools_schema()

    # 游戏模式工具过滤（通过适配器）
    if game_mode:
        filtered_tools = self.game_mode_adapter.filter_tools(
            {tool['function']['name']: tool for tool in tools_to_use},
            chat_id
        )
        # 转换回列表格式
        tools_to_use = [
            {"type": "function", "function": v.to_dict() if hasattr(v, 'to_dict') else v}
            for v in filtered_tools.values()
        ]
```

**集成点**：
1. 工具列表获取时自动过滤不健康的工具
2. AI 调用工具时自动熔断和降级
3. 游戏模式工具过滤与新架构兼容

---

## 架构层次

```
┌─────────────────────────────────────┐
│       DecisionHub                  │  ← 决策层（弥娅核心）
│   • 工具列表过滤（自动过滤不健康工具）  │
│   • AI 工具调用（带熔断和降级）       │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       ToolRegistry                 │  ← 工具注册表（统一入口）
│   • 工具注册和发现                   │
│   • 工具执行（带熔断）                │
│   • 健康状态查询                     │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       ToolInstance                 │  ← 工具实例（隔离层）
│   • ToolCircuitBreaker（熔断器）     │
│   • ToolMetrics（指标统计）           │
│   • 健康状态                       │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       BaseTool                    │  ← 工具基类（实现层）
│   • safe_execute（重试+降级）         │
│   • execute（工具逻辑）               │
│   • validate_args（参数验证）           │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       ToolMonitor                 │  ← 监控层
│   • 健康监控                        │
│   • 统计分析                        │
│   • 诊断报告                        │
└─────────────────────────────────────┘
```

---

## 使用示例

### 1. 创建新工具（自动享受熔断和监控）

```python
from webnet.tools import BaseTool, ToolContext

class MyTool(BaseTool):
    @property
    def config(self):
        return {
            "name": "my_tool",
            "description": "我的工具",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args, context):
        # 工具逻辑
        return "执行成功"

# 自动享受熔断、降级、监控
registry.register(MyTool())
```

### 2. 查询工具健康状态

```python
# 查询单个工具
health = registry.get_tool_health("my_tool")
print(health['health_state'])  # healthy / degraded / unstable / broken

# 查询所有工具
all_health = registry.get_all_tools_health()
for tool_name, info in all_health.items():
    print(f"{tool_name}: {info['health_state']}")
```

### 3. 生成监控报告

```python
from webnet.tools import get_tool_monitor

monitor = get_tool_monitor(registry)
report = monitor.generate_report()
print(report)
```

**报告示例**：
```
📊 工具监控报告
==================================================

🏥 健康状态:
  总工具数: 50
  健康: 45 ✅
  降级: 3 ⚠️
  不稳定: 1 ⚡
  损坏: 1 ❌

📈 调用统计:
  总调用次数: 1000
  成功: 980 ✅
  失败: 20 ❌
  整体成功率: 98.00%

🚨 已熔断工具:
  • bilibili_video

⚠️ 问题工具:
  • python_interpreter: 成功率 85.00%, 调用 100 次
  • knowledge_search: 成功率 92.00%, 调用 50 次

🕐 报告时间: 2026-03-02 12:00:00
```

### 4. 工具维护

```python
# 重置工具（恢复熔断器）
registry.reset_tool("bilibili_video")

# 禁用工具
registry.disable_tool("problematic_tool")

# 启用工具
registry.enable_tool("problematic_tool")
```

---

## 熔断器配置

```python
# 全局配置
ToolCircuitBreaker.FAILURE_THRESHOLD = 3        # 失败次数阈值
ToolCircuitBreaker.FAILURE_RATE_THRESHOLD = 0.5  # 失败率阈值
ToolCircuitBreaker.RECOVERY_TIMEOUT = 60          # 恢复超时（秒）
ToolCircuitBreaker.WINDOW_SIZE = 60              # 统计窗口（秒）
```

---

## 工具健康状态详解

| 状态 | 条件 | 行为 |
|------|------|------|
| HEALTHY | 失败率 < 10% | 正常使用 |
| DEGRADED | 10% ≤ 失败率 < 30% | 正常使用，监控告警 |
| UNSTABLE | 30% ≤ 失败率 < 50% | 正常使用，严重告警 |
| BROKEN | 失败率 ≥ 50% 或熔断器打开 | 自动熔断，拒绝调用 |

---

## 故障隔离机制

### 场景 1：单个工具失败
```
群A调用 bilibili_video → 失败
    ↓
bilibili_video 熔断器打开
    ↓
群B调用 bilibili_video → 自动拒绝
    ↓
返回友好提示："⚠️ 工具 bilibili_video 暂时不可用"
```

### 场景 2：工具自动恢复
```
60秒后 → bilibili_video 进入半开状态
    ↓
允许 1 个请求通过 → 成功
    ↓
熔断器关闭，恢复正常
```

---

## 文件清单

### 新增文件
- `webnet/tools/tool_instance.py` (350 行)
- `webnet/tools/tool_monitor.py` (280 行)

### 修改文件
- `webnet/tools/base.py` (升级 BaseTool 和 ToolRegistry)
- `webnet/tools/__init__.py` (更新导出和文档)
- `hub/decision_hub.py` (集成工具健康监控)

---

## 兼容性

✅ **完全向后兼容**：
- `BaseTool` 保留所有原有方法
- `ToolRegistry` 保留所有原有接口
- 旧工具无需修改即可享受新特性

✅ **符合弥娅框架**：
- 与 DecisionHub 无缝集成
- 与游戏模式架构协同工作
- 不破坏现有架构

---

## 性能影响

⚡ **性能优化**：
- 工具熔断减少无效调用
- 实例级别的指标统计
- 内存占用优化（自动清理不活跃实例）

---

## 最佳实践

### 1. 工具实现
```python
class GoodTool(BaseTool):
    @property
    def config(self):
        return {
            "name": "good_tool",
            "description": "符合最佳实践的工具",
            "parameters": {"type": "object", "properties": {}}
        }

    async def execute(self, args, context):
        try:
            # 1. 参数验证
            # 2. 执行逻辑
            # 3. 返回结果
            return "成功"
        except Exception as e:
            # 4. 记录错误日志
            self.logger.error(f"执行失败: {e}", exc_info=True)
            # 5. 抛出异常（由 safe_execute 处理降级）
            raise
```

### 2. 设置降级消息
```python
class RobustTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.fallback_message = "⚠️ 网络繁忙，请稍后重试"
```

### 3. 监控告警
```python
# 定期检查工具健康
monitor = get_tool_monitor(registry)
problematic = monitor.get_problematic_tools(failure_rate_threshold=0.3)

if problematic:
    # 发送告警通知
    send_alert(f"发现 {len(problematic)} 个问题工具")
```

---

## 总结

这次优化实现了：

✅ **稳定性**：
- 熔断器自动熔断故障工具
- 重试机制提高成功率
- 状态验证防止无效调用

✅ **独立性**：
- 每个工具独立熔断和统计
- 错误隔离，不影响其他工具
- 实例级别的健康监控

✅ **可维修性**：
- 集中监控和诊断
- 详细日志和错误追踪
- 一键重置和恢复

✅ **故障隔离**：
- 自动熔断频繁失败的工具
- 降级策略保证系统稳定
- 半开状态自动探测恢复

✅ **符合弥娅框架**：
- 与 DecisionHub 无缝集成
- 与游戏模式架构协同工作
- 不破坏现有架构

**一个工具坏了，不影响所有工具！**
