# 游戏模式架构优化报告

## 优化目标

根据您提出的三个核心需求：
- **稳定性**：防止系统崩溃和不可预测的行为
- **独立性**：一个游戏失败不影响其他游戏
- **可维护性**：易于修改和扩展

## 优化成果

### 1. 创建的新模块

#### 1.1 `tool_permission_config.py` - 工具权限配置器
**解决的问题**：
- 工具权限逻辑散落在多个文件中
- 修改权限规则需要改多个地方
- 硬编码的工具白名单难以扩展

**实现方案**：
```python
class ToolPermissionConfig:
    BASE_TOOLS: Set[str] = {...}        # 基础工具
    SAVE_TOOLS: Set[str] = {...}         # 存档工具
    MODE_TOOL_WHITELIST: Dict[...] = {...} # 各模式工具白名单

    @classmethod
    def is_tool_allowed(cls, tool_name, mode_type, game_state, tool_whitelist):
        # 统一的权限检查逻辑
```

**优势**：
- 集中配置，修改权限规则只需改一处
- 支持动态扩展（`register_custom_tool`）
- 状态感知：根据游戏状态动态调整权限

---

#### 1.2 `state_transition_validator.py` - 状态转换验证器
**解决的问题**：
- 状态转换缺乏验证，可能出现非法状态
- 状态转换原因不清晰，难以排查问题
- 没有状态转换的钩子机制

**实现方案**：
```python
class StateTransitionValidator:
    VALID_TRANSITIONS: Dict[GameState, Set[GameState]] = {
        GameState.NOT_STARTED: {GameState.LOADING, GameState.IN_PROGRESS},
        GameState.LOADING: {GameState.IN_PROGRESS, GameState.NOT_STARTED},
        # ...
    }

    @classmethod
    def validate(cls, from_state, to_state):
        # 验证状态转换是否合法

    @classmethod
    def register_hook(cls, from_state, to_state, hook):
        # 注册状态转换钩子
```

**优势**：
- 禁止非法状态转换
- 状态转换原因明确
- 支持扩展钩子函数

---

#### 1.3 `game_instance_manager.py` - 游戏实例管理器
**解决的问题**：
- 所有游戏共享同一个管理器，单点故障风险
- 缺少实例级别的错误隔离
- 没有实例健康监控

**实现方案**：
```python
class GameInstance:
    def __init__(self, chat_id, mode_type, game_mode):
        self.error_count = 0          # 错误计数
        self.is_healthy = True        # 健康状态
        self.last_active_at = ...      # 最后活跃时间

    def record_error(self):
        # 记录错误

    def is_active(self):
        # 检查是否活跃

class GameInstanceManager:
    def create_instance(self, chat_id, mode_type, game_mode):
        # 创建独立实例

    def cleanup_inactive_instances(self):
        # 自动清理不活跃实例
```

**优势**：
- 每个游戏实例独立管理
- 实例级别的错误计数
- 自动清理不活跃实例
- 一个实例失败不影响其他实例

---

#### 1.4 `error_handler.py` - 错误处理器
**解决的问题**：
- 错误处理分散，缺乏统一机制
- 没有错误统计和监控
- 没有降级策略

**实现方案**：
```python
class ErrorHandler:
    error_stats: Dict[str, int] = {}

    @classmethod
    def handle_tool_error(cls, chat_id, tool_name, error):
        # 统一处理工具错误

    @classmethod
    def safe_execute(cls, chat_id, func, fallback_value):
        # 安全执行函数

@with_error_handling(chat_id_param="chat_id")
async def my_function(chat_id: str):
    # 自动错误处理
```

**优势**：
- 统一错误捕获和日志
- 错误统计和监控
- 自动降级机制
- 装饰器支持

---

### 2. 重构的现有文件

#### 2.1 `mode_state.py`
- 移除硬编码的工具权限逻辑
- 委托给 `ToolPermissionConfig`
- 保持向后兼容

#### 2.2 `mode_manager.py`
- 集成 `GameInstanceManager`
- 使用 `ToolPermissionConfig` 获取工具白名单
- 添加状态变更回调

#### 2.3 `tools/load_save.py`
- 使用 `StateTransitionValidator` 验证状态
- 添加错误恢复机制
- 降级处理

#### 2.4 `tools/create_save.py`
- 使用 `StateTransitionValidator` 验证状态
- 统一错误处理

---

## 架构层次

```
┌─────────────────────────────────────────┐
│         GameModeManager                 │  ← 兼容层（向后兼容）
│   管理所有游戏模式                       │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     GameInstanceManager                 │  ← 独立层（实例隔离）
│   管理每个游戏实例                       │
│   • 错误计数                             │
│   • 健康检查                             │
│   • 自动清理                             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   StateTransitionValidator               │  ← 规则层（状态机）
│   验证状态转换                           │
│   • 合法性验证                           │
│   • 转换钩子                             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   ToolPermissionConfig                  │  ← 配置层（权限控制）
│   配置工具权限                           │
│   • 基础工具                             │
│   • 存档工具                             │
│   • 模式白名单                           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   ErrorHandler                          │  ← 安全层（错误处理）
│   统一错误处理                           │
│   • 错误统计                             │
│   • 降级策略                             │
│   • 装饰器支持                           │
└─────────────────────────────────────────┘
```

---

## 三大优化成果

### 稳定性 ✅

**问题**：
- 重复调用 `load_game_save` 导致状态混乱
- 缺少状态验证，可能出现非法状态

**解决方案**：
1. **状态机驱动**：`StateTransitionValidator` 禁止非法状态转换
2. **状态感知权限**：`ToolPermissionConfig` 根据状态动态调整权限
3. **错误恢复**：出错时自动重置到安全状态

**效果**：
- 游戏中禁止加载存档
- 加载中禁止任何操作
- 出错后自动恢复

---

### 独立性 ✅

**问题**：
- 所有游戏共享同一个管理器
- 一个游戏失败影响所有游戏

**解决方案**：
1. **实例隔离**：每个游戏有独立的 `GameInstance`
2. **错误计数**：实例级别的错误统计
3. **健康检查**：不健康实例自动降级
4. **自动清理**：24小时不活跃实例自动删除

**效果**：
```
群A的TRPG失败 → 不影响群B的酒馆游戏
群C的工具频繁错误 → 自动禁用该群C的工具
群D24小时不活跃 → 自动清理释放资源
```

---

### 可维护性 ✅

**问题**：
- 工具权限逻辑散落多处
- 修改需要改多个文件
- 代码重复

**解决方案**：
1. **集中配置**：`ToolPermissionConfig` 集中管理权限
2. **统一验证**：所有工具使用 `StateTransitionValidator`
3. **装饰器支持**：`@with_error_handling` 简化错误处理
4. **清晰文档**：每个模块都有详细文档

**效果**：
```python
# 修改工具权限，只需改一处
ToolPermissionConfig.BASE_TOOLS.add('new_tool')

# 所有工具自动应用统一验证
StateTransitionValidator.validate(old_state, new_state)

# 新增工具只需添加错误处理装饰器
@with_error_handling(chat_id_param="chat_id")
async def my_tool(chat_id: str):
    # ...
```

---

## 文件清单

### 新增文件
- `tool_permission_config.py` (140 行)
- `state_transition_validator.py` (190 行)
- `game_instance_manager.py` (240 行)
- `error_handler.py` (280 行)

### 修改文件
- `mode_state.py` (精简至 95 行)
- `mode_manager.py` (集成新架构)
- `tools/load_save.py` (使用统一验证器)
- `tools/create_save.py` (使用统一验证器)
- `__init__.py` (完善接口和文档)

---

## 兼容性保证

✅ **完全向后兼容**：
- `GameMode` 类保留所有原有方法
- `GameModeManager` 保留所有原有接口
- 旧数据自动迁移到新架构
- 现有工具无需修改（已更新）

---

## 性能影响

⚡ **性能优化**：
- 实例自动清理，减少内存占用
- 错误工具自动禁用，减少无效调用
- 状态验证在内存中完成，开销极小

---

## 使用示例

```python
from webnet.EntertainmentNet.game_mode import (
    get_game_mode_manager,
    GameModeType,
    GameState,
    ErrorHandler
)

# 1. 启动游戏
manager = get_game_mode_manager()
mode = manager.set_mode(
    chat_id="123456",
    mode_type=GameModeType.TRPG
)

# 2. 转换状态（自动验证）
manager.set_game_state("123456", GameState.IN_PROGRESS)

# 3. 检查权限（统一规则）
mode.is_tool_allowed("load_game_save")  # False（游戏中禁止）

# 4. 错误处理
stats = ErrorHandler.get_error_stats("123456")
```

---

## 总结

这次优化实现了：
- ✅ **稳定性**：状态机驱动，禁止非法操作
- ✅ **独立性**：实例隔离，故障不扩散
- ✅ **可维护性**：集中配置，修改一处生效

符合弥娅框架原则，完全向后兼容，可以安全部署。
