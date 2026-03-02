# 工具系统架构说明

> 本文档说明当前工具系统的架构定位和未来重构计划

---

## 当前状态

### 架构定位

当前 `tools/` 系统是从 **Undefined** 迁移的**兼容层实现**：

```
工具系统（兼容层）
├── base.py              # 基类和注册表
├── tools/               # 26个工具实现
│   ├── 基础工具 (3)
│   ├── 消息工具 (4)
│   ├── 群工具 (5)
│   ├── 记忆工具 (4) ⚠️
│   ├── 知识库工具 (3)
│   ├── 认知工具 (3)
│   ├── B站工具 (1)
│   └── 定时任务 (3)
```

### 与弥娅架构的关系

| 特性 | 弥娅原生理念 | 当前实现 | 兼容性 |
|------|-------------|----------|--------|
| 架构模式 | 蛛网式分布式 | 集中式工具注册表 | ⚠️ 兼容层 |
| 通信机制 | M-Link 五流 | 直接函数调用 | ⚠️ 兼容层 |
| 工具执行 | 子网层执行 | 工具注册表 | ⚠️ 兼容层 |
| 记忆系统 | CognitiveMemory | Tools 记忆工具 | ⚠️ 功能重叠 |

---

## 问题分析

### 1. 架构理念不一致

弥娅的蛛网式架构要求：

```
用户请求
  ↓
感知层 (perceive/)
  ↓ [M-Link 感知流]
中枢层 (hub/) 决策
  ↓ [M-Link 指令流]
子网层 (webnet/) 执行
  ↓ [M-Link 感知流]
返回结果
```

当前实现：

```
用户请求 → AI决策 → ToolRegistry.execute() → 直接调用 → 返回
```

**问题**：绕过了 M-Link 传输层，缺少感知层的预处理

### 2. 记忆系统冗余

**当前记忆系统**：

```
hub/memory_engine.py              # 潮汐/梦境记忆
memory/cognitive_memory_system.py # 三层认知记忆
memory/semantic_dynamics_engine.py # 语义动态引擎
memory/grag_memory.py            # GRAG图谱记忆

tools/tools/memory_*.py           # Tools 记忆工具（冗余）
```

**功能重叠**：
- `memory_add` 与 `MemoryEngine.store_tide()`
- `memory_list` 与 `CognitiveMemory.search()`
- `search_events` 与 `SemanticDynamicsEngine`

---

## 重构计划

### Phase 1: 标记兼容层（当前）

- ✅ 在 `tools/__init__.py` 添加架构说明
- ✅ 保持工具系统可用性
- 📝 文档化兼容层设计

### Phase 2: 记忆系统统一（短期）

**目标**：消除记忆系统冗余

```python
# 方案：Tools 记忆工具调用原生系统

async def execute(self, args, context):
    # 优先使用 CognitiveMemorySystem
    if hasattr(context, 'cognitive_memory'):
        return await context.cognitive_memory.add_memo(...)

    # 降级到 MemoryEngine
    if context.memory_engine:
        return context.memory_engine.store_tide(...)

    # 兜底：返回友好提示
    return "⚠️ 记忆系统未初始化"
```

**任务**：
- [ ] 修改 `memory_add.py` 调用 `CognitiveMemorySystem`
- [ ] 修改 `memory_list.py` 调用认知记忆系统搜索
- [ ] 修改 `memory_update.py` 调用原生更新接口
- [ ] 修改 `memory_delete.py` 调用原生删除接口
- [ ] 更新文档说明记忆工具为"统一接口"

### Phase 3: 子网架构迁移（长期）

**目标**：将工具系统迁移到弥娅原生子网架构

```
webnet/
├── ToolNet/              # 工具子网
│   ├── __init__.py
│   ├── registry.py       # 工具注册（兼容层）
│   ├── handlers/         # 工具处理器
│   │   ├── basic.py
│   │   ├── message.py
│   │   ├── group.py
│   │   └── ...
│   └── adapters/         # M-Link 适配器
│       └── mlink_adapter.py
│
├── QQNet/                # QQ 子网
│   ├── handlers/
│   │   ├── group.py      # 群操作
│   │   ├── message.py    # 消息处理
│   │   └── member.py     # 成员管理
│   └── adapters/
│       └── onebot_adapter.py
│
└── MemoryNet/            # 记忆子网
    ├── handlers/
    │   ├── tide.py       # 潮汐记忆
    │   ├── dream.py      # 梦境记忆
    │   └── cognitive.py  # 认知记忆
    └── adapters/
        └── memory_adapter.py
```

**通信流程**：

```python
# 子网通过 M-Link 通信
from mlink.protocol import StreamType

class ToolNet(Subnet):
    async def handle_tool_request(self, tool_name, args):
        # 通过 M-Link 指令流执行工具
        result = await self.mlink.send(
            stream_type=StreamType.COMMAND,
            target=f"webnet.QQNet",
            action=tool_name,
            data=args
        )
        return result
```

### Phase 4: 完全对齐（最终）

- 移除 `tools/` 兼容层
- 所有功能通过子网层和 M-Link 通信
- 工具完全符合弥娅蛛网式架构

---

## 临时建议（当前可接受）

**如果需要快速使用**：

1. **保留当前工具系统**，但理解其架构定位
2. **记忆工具改为统一接口**，调用原生系统
3. **文档说明**：tools/ 是兼容层，未来会重构

**参考实现**：

```python
# 修改 memory_add.py 统一调用原生系统
async def execute(self, args, context):
    content = args.get("content")
    priority = args.get("priority", 0.5)
    tags = args.get("tags", [])

    # 优先使用认知记忆系统（弥娅原生）
    cognitive_memory = getattr(context, 'cognitive_memory', None)
    if cognitive_memory:
        await cognitive_memory.add_memo(content, priority, tags)
        return f"✅ 已添加记忆（认知记忆系统）"

    # 降级到记忆引擎（hub/）
    memory_engine = context.memory_engine
    if memory_engine:
        memory_engine.store_tide(
            memory_id=f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            content={'content': content, 'tags': tags},
            priority=priority
        )
        return f"✅ 已添加记忆（记忆引擎）"

    # 兜底
    return "⚠️ 记忆系统未初始化"
```

---

## 总结

- ✅ **工具功能完整**：26个工具全部实现，可用性良好
- ⚠️ **架构理念不完全对齐**：当前为兼容层，需要长期重构
- ⚠️ **记忆系统存在冗余**：建议统一到弥娅原生系统

**建议行动**：
1. **短期**：保持工具系统可用，修改记忆工具调用原生系统
2. **中期**：规划子网架构迁移
3. **长期**：完全对齐弥娅蛛网式架构

---

**文档版本**: 1.0
**更新日期**: 2026-02-28
**维护者**: Miya AI Assistant
