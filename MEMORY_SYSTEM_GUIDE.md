# 弥娅记忆系统详细说明

## 目录
1. [系统概述](#系统概述)
2. [架构设计](#架构设计)
3. [数据存储](#数据存储)
4. [核心组件](#核心组件)
5. [使用方式](#使用方式)
6. [API 接口](#api-接口)
7. [配置选项](#配置选项)
8. [高级功能](#高级功能)
9. [故障排查](#故障排查)

---

## 系统概述

弥娅的记忆系统是一个基于 M-Link 消息路由的全局记忆管理框架，实现了跨平台（QQ、PC UI）的统一记忆存储。

### 核心特性
- ✅ **全局记忆**：无论在 QQ 还是 PC UI 对话，都使用同一个记忆库
- ✅ **对话历史持久化**：所有对话自动保存，重启不丢失
- ✅ **手动记忆管理**：支持添加、更新、删除重要记忆事实
- ✅ **多会话支持**：每个对话会话独立存储，支持私聊和群聊
- ✅ **内存缓存**：最近使用的会话缓存在内存中，提升访问速度
- ✅ **灵活扩展**：支持 Redis、Milvus、Neo4j 等外部存储

### 设计原则
1. **五流统一**：通过 M-Link 的 `memory_flow` 统一访问
2. **数据本地化**：默认使用 JSON 文件存储，无需外部数据库
3. **渐进式增强**：从简单 JSON 开始，逐步支持高级存储

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    弥娅核心系统                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ M-Link (memory_flow)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   MemoryNet 全局记忆子网                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │     MemorySystemInitializer 记忆系统初始化器      │  │
│  └───────────────────────────────────────────────────┘  │
│           │                    │                        │
│           ▼                    ▼                        │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 对话历史管理  │    │ 手动记忆管理  │               │
│  │              │    │              │               │
│  │ JSON 存储     │    │ JSON 存储     │               │
│  │ 内存缓存     │    │ 标签系统     │               │
│  └──────────────┘    └──────────────┘               │
│           │                    │                        │
│           ▼                    ▼                        │
│  ┌───────────────────────────────────────────┐        │
│  │     可选高级存储 (Redis/Milvus/Neo4j)    │        │
│  └───────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌────────┐    ┌────────┐
              │  QQ    │    │ PC UI  │
              └────────┘    └────────┘
```

### 组件关系

```
MiyaQQBot / MiyaPCUI
    │
    ├── 初始化 M-Link
    │
    ├── 初始化 MemoryNet
    │   │
    │   ├── MemorySystemInitializer
    │   │   ├── ConversationHistoryManager (对话历史)
    │   │   └── UndefinedMemoryAdapter (手动记忆)
    │   │
    │   ├── Redis (可选)
    │   ├── Milvus (可选)
    │   └── Neo4j (可选)
    │
    └── 传递 memory_net 给子网
        │
        ├── QQNet
        │   └── 直接调用 memory_net.conversation_history
        │
        └── PCUINet
            └── 直接调用 memory_net.conversation_history
```

---

## 数据存储

### 存储位置

```
Miya/
├── data/
│   ├── conversations/          # 对话历史
│   │   ├── session_<uuid>.json
│   │   └── ...
│   └── memory/              # 手动记忆
│       └── undefined_memory.json
```

### 对话历史格式

**文件路径**：`data/conversations/session_<会话ID>.json`

**会话 ID 规则**：
- QQ 私聊：`private_<QQ号>`
- QQ 群聊：`group_<群号>`
- PC UI：`pc_ui_<会话ID>`

**消息格式**：
```json
[
  {
    "role": "user",
    "content": "你好，弥娅",
    "timestamp": "2026-02-28T22:19:34.156149",
    "session_id": "private_1523878699",
    "images": [],
    "agent_id": "miya_default",
    "metadata": {
      "source": "qq",
      "msg_type": "private",
      "sender_id": 1523878699,
      "sender_name": "佳",
      "group_name": ""
    }
  },
  {
    "role": "assistant",
    "content": "你好！我是弥娅...",
    "timestamp": "2026-02-28T22:19:35.234567",
    "session_id": "private_1523878699",
    "images": [],
    "agent_id": "miya_default",
    "metadata": {
      "source": "qq",
      "msg_type": "private"
    }
  }
]
```

**字段说明**：
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| role | string | 是 | 消息角色：`user` 或 `assistant` |
| content | string | 是 | 消息内容 |
| timestamp | string | 是 | ISO 8601 格式时间戳 |
| session_id | string | 是 | 所属会话 ID |
| images | array | 是 | 图片列表（暂未使用） |
| agent_id | string | 是 | AI 代理 ID |
| metadata | object | 是 | 元数据信息 |

**元数据字段**：
| 字段 | 类型 | 说明 |
|------|------|------|
| source | string | 消息来源：`qq`、`pc_ui` |
| msg_type | string | 消息类型：`private`、`group` |
| sender_id | integer | 发送者 ID（QQ 号等） |
| sender_name | string | 发送者昵称 |
| group_name | string | 群名称（群聊时有效） |

### 手动记忆格式

**文件路径**：`data/memory/undefined_memory.json`

**记忆格式**：
```json
[
  {
    "uuid": "4a2de619-5c3b-4236-a755-522fe4fbd59f",
    "fact": "用户喜欢使用 Python 编程",
    "created_at": "2026-02-28T22:04:19.379713",
    "tags": ["编程", "Python", "偏好"]
  },
  {
    "uuid": "4c08f891-c161-4ad5-b422-aa7e8b25859d",
    "fact": "用户喜欢吃巧克力",
    "created_at": "2026-02-28T22:04:19.381711",
    "tags": ["食物", "偏好"]
  }
]
```

**字段说明**：
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| uuid | string | 是 | 唯一标识符（自动生成） |
| fact | string | 是 | 记忆事实内容 |
| created_at | string | 是 | 创建时间（ISO 8601 格式） |
| tags | array | 是 | 标签列表，便于检索和分类 |

---

## 核心组件

### 1. ConversationHistoryManager（对话历史管理器）

**文件**：`core/conversation_history.py`

**功能**：
- 管理所有对话会话
- 增量加载，避免内存溢出
- 自动持久化到 JSON 文件
- 内存缓存最近使用的会话

**关键方法**：

```python
# 添加消息到会话
await add_message(
    session_id: str,      # 会话 ID
    role: str,           # "user" 或 "assistant"
    content: str,        # 消息内容
    agent_id: str = "miya_default",
    metadata: dict = None
)

# 获取会话历史
await get_history(
    session_id: str,
    limit: int = 20
) -> List[dict]

# 获取所有会话 ID
await get_all_session_ids() -> List[str]

# 获取统计信息
await get_stats() -> dict
```

**配置参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_MESSAGES_PER_SESSION` | 200 | 每个会话最大消息数 |
| `DATA_DIR` | `data/conversations` | 数据存储目录 |
| `CACHE_SIZE` | 100 | 内存缓存会话数 |

### 2. UndefinedMemoryAdapter（手动记忆适配器）

**文件**：`memory/undefined_memory.py`

**功能**：
- 管理手动添加的记忆事实
- 支持标签系统
- JSON 文件持久化

**关键方法**：

```python
# 添加记忆
await add_memory(
    fact: str,           # 记忆内容
    tags: List[str]      # 标签列表
) -> str  # 返回记忆 UUID

# 获取所有记忆
await get_all_memories() -> List[dict]

# 搜索记忆
async search_memories(
    keyword: str         # 搜索关键词
) -> List[dict]

# 更新记忆
await update_memory(
    uuid: str,          # 记忆 UUID
    fact: str = None,
    tags: List[str] = None
)

# 删除记忆
await delete_memory(uuid: str)
```

### 3. MemorySystemInitializer（记忆系统初始化器）

**文件**：`core/memory_system_initializer.py`

**功能**：
- 统一初始化所有记忆组件
- 管理可选的扩展存储（Redis、Milvus、Neo4j）
- 提供系统状态检查

**初始化流程**：
```
1. 创建数据目录
2. 初始化 ConversationHistoryManager
3. 初始化 UndefinedMemoryAdapter
4. 初始化 Redis (可选)
5. 初始化 Milvus (可选)
6. 初始化 Neo4j (可选)
7. 输出系统状态
```

### 4. MemoryNet（全局记忆子网）

**文件**：`webnet/memory.py`

**功能**：
- 作为 M-Link 上的记忆节点
- 统一暴露记忆操作接口
- 管理记忆系统生命周期

**注册到 M-Link**：
```python
mlink.register_node("memory", [
    "conversation_history",
    "undefined_memory",
    "memory_flow"
])
```

---

## 使用方式

### 在代码中使用

#### 初始化记忆系统

```python
from core.memory_system_initializer import get_memory_system_initializer

# 获取初始化器
memory_system = await get_memory_system_initializer()

# 获取对话历史管理器
history_manager = await memory_system.get_conversation_history_manager()

# 获取手动记忆管理器
undefined_memory = await memory_system.get_undefined_memory()
```

#### 保存对话消息

```python
# 添加用户消息
await history_manager.add_message(
    session_id="private_123456",
    role="user",
    content="你好，弥娅",
    metadata={
        "source": "qq",
        "sender_id": 123456,
        "sender_name": "用户"
    }
)

# 添加 AI 回复
await history_manager.add_message(
    session_id="private_123456",
    role="assistant",
    content="你好！有什么我可以帮助你的吗？",
    metadata={
        "source": "qq"
    }
)
```

#### 获取对话历史

```python
# 获取最近 20 条消息
history = await history_manager.get_history(
    session_id="private_123456",
    limit=20
)

for msg in history:
    print(f"[{msg['role']}]: {msg['content']}")
```

#### 管理手动记忆

```python
# 添加记忆
uuid = await undefined_memory.add_memory(
    fact="用户喜欢使用 Python 编程",
    tags=["编程", "Python", "偏好"]
)

# 搜索记忆
memories = await undefined_memory.search_memories("Python")

# 更新记忆
await undefined_memory.update_memory(
    uuid=uuid,
    fact="用户精通 Python 和 JavaScript 编程",
    tags=["编程", "Python", "JavaScript", "偏好"]
)

# 删除记忆
await undefined_memory.delete_memory(uuid)
```

### 通过 QQ 工具使用

弥娅 QQ Bot 提供了以下记忆相关工具：

#### memory_add - 添加记忆
```
用法：记忆 用户喜欢吃巧克力
功能：将事实添加到手动记忆系统
```

#### memory_list - 列出记忆
```
用法：查看所有记忆
功能：显示所有手动添加的记忆
```

#### memory_update - 更新记忆
```
用法：更新记忆 <UUID> <新内容>
功能：更新指定 UUID 的记忆内容
```

#### memory_delete - 删除记忆
```
用法：删除记忆 <UUID>
功能：删除指定 UUID 的记忆
```

---

## API 接口

### ConversationHistoryManager

```python
class ConversationHistoryManager:
    """对话历史管理器"""

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_id: str = "miya_default",
        images: List[str] = None,
        metadata: Dict = None
    ) -> None:
        """添加消息到会话"""

    async def get_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """获取会话历史"""

    async def get_all_session_ids(self) -> List[str]:
        """获取所有会话 ID"""

    async def get_stats(self) -> Dict:
        """获取统计信息"""

    async def delete_session(self, session_id: str) -> None:
        """删除会话"""

    async def clear_cache(self) -> None:
        """清空内存缓存"""
```

### UndefinedMemoryAdapter

```python
class UndefinedMemoryAdapter:
    """手动记忆适配器"""

    async def add_memory(
        self,
        fact: str,
        tags: List[str] = None
    ) -> str:
        """添加记忆，返回 UUID"""

    async def get_all_memories(self) -> List[Dict]:
        """获取所有记忆"""

    async def search_memories(
        self,
        keyword: str
    ) -> List[Dict]:
        """搜索记忆"""

    async def update_memory(
        self,
        uuid: str,
        fact: str = None,
        tags: List[str] = None
    ) -> None:
        """更新记忆"""

    async def delete_memory(self, uuid: str) -> None:
        """删除记忆"""
```

---

## 配置选项

### 基础配置

**文件**：`core/conversation_history.py`

```python
# 对话历史配置
MAX_MESSAGES_PER_SESSION = 200  # 每会话最大消息数
CACHE_SIZE = 100               # 内存缓存会话数
DATA_DIR = "data/conversations" # 数据存储目录
```

### Redis 配置（可选）

**文件**：`core/redis_config.py`

**环境变量**：
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

**功能**：将对话历史缓存到 Redis，提升多实例访问性能。

### Milvus 配置（可选）

**文件**：`core/milvus_config.py`

**环境变量**：
```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memories
```

**功能**：向量语义搜索，支持智能记忆检索。

### Neo4j 配置（可选）

**文件**：`core/neo4j_config.py`

**环境变量**：
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

**功能**：图数据库存储记忆关系，支持复杂查询。

---

## 高级功能

### 1. 潮汐记忆/梦境压缩

**概念**：定期清理旧记忆，只保留重要信息。

**实现计划**：
- 基于时间窗口的自动清理
- 基于重要性的记忆压缩
- 将短对话合并为摘要

**当前状态**：框架已实现，具体逻辑待完善。

### 2. 向量语义搜索

**功能**：使用 Milvus 进行语义搜索，而不仅是关键词匹配。

**使用示例**：
```python
# 语义搜索
memories = await milvus_adapter.semantic_search(
    query="用户喜欢什么编程语言？",
    top_k=5
)
```

**当前状态**：配置已就绪，需要 Milvus 服务。

### 3. 图关系记忆

**功能**：使用 Neo4j 存储记忆之间的关系网络。

**使用示例**：
```python
# 创建关系图
await neo4j_adapter.create_relation(
    source="用户喜欢 Python",
    relation="原因",
    target="Python 简单易学"
)

# 关系查询
related = await neo4j_adapter.find_relations(
    node="用户喜欢 Python"
)
```

**当前状态**：配置已就绪，需要 Neo4j 服务。

---

## 故障排查

### 问题 1：对话历史未保存

**症状**：重启后对话记录丢失

**检查项**：
1. 确认 `data/conversations` 目录存在
2. 检查文件写入权限
3. 查看日志是否有错误信息

**解决方法**：
```bash
# 创建数据目录
mkdir -p data/conversations

# 检查权限
ls -la data/
```

### 问题 2：手动记忆丢失

**症状**：添加的记忆无法找回

**检查项**：
1. 确认 `data/memory/undefined_memory.json` 存在
2. 检查文件内容是否正确
3. 验证 JSON 格式是否有效

**解决方法**：
```bash
# 检查文件
cat data/memory/undefined_memory.json

# 验证 JSON 格式
python -m json.tool data/memory/undefined_memory.json
```

### 问题 3：多平台记忆不同步

**症状**：QQ 和 PC UI 对话记录分离

**原因**：未正确初始化全局记忆系统

**解决方法**：
确认代码中正确传递了 `memory_net`：
```python
# 正确
self.qq_net = QQNet(self, memory_net=self.memory_net)

# 错误
self.qq_net = QQNet(self)
```

### 问题 4：内存占用过高

**症状**：长时间运行后内存占用增加

**原因**：会话缓存累积过多

**解决方法**：
```python
# 定期清理缓存
await history_manager.clear_cache()

# 或调整缓存大小
CACHE_SIZE = 50  # 减少缓存会话数
```

---

## 最佳实践

### 1. 会话 ID 命名规范

```
QQ 私聊：private_<QQ号>
QQ 群聊：group_<群号>
PC UI：pc_ui_<UUID>
Web UI：web_ui_<UUID>
```

### 2. 元数据使用规范

```python
metadata = {
    "source": "qq",           # 消息来源
    "msg_type": "private",    # 消息类型
    "sender_id": 123456,      # 发送者 ID
    "sender_name": "用户",     # 发送者昵称
    "group_name": "测试群"      # 群名称（群聊时）
}
```

### 3. 标签使用规范

```python
tags = [
    "类别",        # 主类别（如：编程、食物、偏好）
    "具体项",      # 具体项（如：Python、巧克力）
    "属性"         # 属性（如：喜欢、讨厌）
]
```

### 4. 性能优化建议

1. **限制会话大小**：每会话保留最近 200 条消息
2. **定期清理缓存**：避免内存泄漏
3. **使用 Redis 缓存**：多实例部署时推荐
4. **索引会话 ID**：频繁查询时考虑建立索引

---

## 总结

弥娅的记忆系统提供了一个简单而强大的全局记忆解决方案：

✅ **开箱即用**：默认 JSON 存储，无需配置
✅ **全局统一**：跨平台共享记忆库
✅ **灵活扩展**：支持 Redis、Milvus、Neo4j
✅ **易于维护**：数据格式清晰，便于查看和修改
✅ **性能优化**：内存缓存 + 增量加载

通过这个记忆系统，弥娅可以记住用户的偏好、历史对话，并提供更加个性化的交互体验。
