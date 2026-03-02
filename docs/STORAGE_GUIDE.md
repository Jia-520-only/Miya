# 弥娅数据存储说明

## 📋 当前数据存储状态

### 对话历史数据

**存储方式：** 内存临时存储（未持久化到文件）

**位置：**
- **运行时内存**：`webnet/qq.py` 中的 `message_history` 字典
- **存储结构**：`{group_id/user_id: [messages]}`
- **存储限制**：每个对话保留最近 100 条消息
- **丢失风险**：⚠️ **程序重启后全部丢失**

**问题：**
- 对话历史只存储在内存中
- 没有持久化到文件或数据库
- 重启后所有历史对话都会丢失

### 记忆系统

#### 1. Undefined 轻量记忆系统

**存储文件：** `data/memory.json`

**当前状态：** ❌ **文件不存在**

**用途：**
- 手动添加的备忘录
- 用户显式要求记录的内容
- 简单高效的 JSON 文件存储

**特点：**
- 自动去重（相同内容不重复）
- 数量限制（默认 500 条）
- UUID 精确管理

#### 2. LifeBook 记忆管理系统

**存储目录：** `data/lifebook/`

**目录结构：**
```
data/lifebook/
├── diaries/          # 日记
├── weekly/           # 周记
├── monthly/          # 月报
├── quarterly/        # 季报
├── yearly/           # 年鉴
├── nodes/            # 节点（角色、阶段）
└── profiles/         # 用户档案
```

**当前状态：** ❌ **目录不存在**

**用途：**
- 层级化记忆管理（日/周/月/季/年）
- 角色节点、阶段节点管理
- 时间滚动记忆压缩
- 一键获取核心上下文

#### 3. 向量记忆系统

**存储方式：** 可选的数据库（需配置）

**支持的数据库：**

1. **ChromaDB**（认知记忆）
   - **配置位置**：`config/.env` - `COGNITIVE_VECTOR_STORE_PATH`
   - **默认路径**：`data/cognitive/chromadb/`
   - **状态**：❌ 未配置，不存在

2. **Redis**（涨潮记忆）
   - **配置位置**：`config/.env`
   - **默认配置**：
     ```
     REDIS_HOST=localhost
     REDIS_PORT=6379
     REDIS_DB=0
     ```
   - **状态**：❌ 未启动

3. **Milvus**（向量长期记忆）
   - **配置位置**：`config/.env`
   - **默认配置**：
     ```
     MILVUS_HOST=localhost
     MILVUS_PORT=19530
     MILVUS_COLLECTION=miya_memory
     ```
   - **状态**：❌ 未启动

4. **Neo4j**（知识图谱）
   - **配置位置**：`config/.env`
   - **默认配置**：
     ```
     NEO4J_URI=bolt://localhost:7687
     NEO4J_USER=neo4j
     NEO4J_PASSWORD=your_neo4j_password
     ```
   - **状态**：❌ 未启动

### 系统日志

**存储目录：** `logs/`

**日志文件：**
- `miya_YYYYMMDD.log` - 主系统日志
- `miya_qq_YYYYMMDD.log` - QQ 机器人日志

**当前状态：** ✅ 存在

**用途：**
- 系统运行日志
- 调试信息
- 错误记录
- ⚠️ **不包含对话历史，只包含系统日志**

## 🔍 关键问题

### 对话历史丢失

**问题描述：**
- 对话历史只存储在内存中
- 程序重启后全部丢失
- 无法查看历史对话记录

**影响：**
- 用户无法查看之前的对话
- AI 无法回忆之前的对话内容
- 记忆不连贯

### 记忆系统未启用

**问题描述：**
- Undefined 轻量记忆未初始化
- LifeBook 记忆管理未初始化
- 向量数据库未配置

**影响：**
- 无法长期记忆用户信息
- 无法进行语义检索
- 无法进行智能召回

## 💡 解决方案

### 方案 1：启用对话历史持久化

创建对话历史存储模块：

```python
# storage/conversation_storage.py
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

class ConversationStorage:
    """对话历史持久化存储"""

    def __init__(self, base_dir: Path = Path("data/conversations")):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_message(self, chat_id: int, message: Dict):
        """保存单条消息"""
        chat_file = self.base_dir / f"{chat_id}.json"

        if chat_file.exists():
            with open(chat_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
        else:
            messages = []

        messages.append(message)

        # 保留最近 1000 条
        if len(messages) > 1000:
            messages = messages[-1000:]

        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    def get_history(self, chat_id: int, limit: int = 100) -> List[Dict]:
        """获取对话历史"""
        chat_file = self.base_dir / f"{chat_id}.json"

        if not chat_file.exists():
            return []

        with open(chat_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)

        return messages[-limit:]
```

### 方案 2：启用 Undefined 轻量记忆

```python
# 初始化记忆系统
from memory.undefined_memory import UndefinedMemoryAdapter

memory = UndefinedMemoryAdapter()

# 添加记忆
await memory.add("佳喜欢吃草莓蛋糕", tags=["食物", "喜好"])

# 搜索记忆
memories = await memory.search("蛋糕")
```

### 方案 3：配置 Redis 作为记忆后端

```bash
# 启动 Redis
redis-server --port 6379
```

修改 `config/.env`：
```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 方案 4：配置 ChromaDB 向量存储

修改 `config/.env`：
```
COGNITIVE_VECTOR_STORE_PATH=data/cognitive/chromadb
COGNITIVE_QUEUE_PATH=data/cognitive/queues
COGNITIVE_PROFILES_PATH=data/cognitive/profiles
```

## 📊 当前存储状态总结

| 数据类型 | 存储位置 | 持久化 | 当前状态 |
|---------|----------|---------|---------|
| 对话历史 | 内存 | ❌ 否 | 丢失风险 |
| Undefined 记忆 | data/memory.json | ✅ 是 | 未初始化 |
| LifeBook 记忆 | data/lifebook/ | ✅ 是 | 未初始化 |
| ChromaDB | data/cognitive/chromadb/ | ✅ 是 | 未配置 |
| Redis | localhost:6379 | ✅ 是 | 未启动 |
| Milvus | localhost:19530 | ✅ 是 | 未启动 |
| Neo4j | localhost:7687 | ✅ 是 | 未启动 |
| 系统日志 | logs/*.log | ✅ 是 | ✅ 正常 |

## 🎯 建议优先级

### 高优先级（立即执行）

1. **启用对话历史持久化**
   - 创建 `storage/conversation_storage.py`
   - 修改 `webnet/qq.py` 集成持久化
   - 确保重启后不丢失

2. **初始化 Undefined 记忆系统**
   - 运行初始化脚本
   - 启用自动记忆功能

### 中优先级（可选执行）

3. **配置 Redis 记忆后端**
   - 启动 Redis 服务
   - 配置连接参数
   - 启用涨潮记忆

4. **初始化 LifeBook 记忆管理**
   - 创建必要目录
   - 配置自动总结

### 低优先级（长期规划）

5. **配置向量数据库**
   - 选择 ChromaDB/Milvus
   - 配置嵌入模型
   - 启用语义检索

## 📁 数据目录结构

```
Miya/
├── data/                    # 数据目录
│   ├── memory.json          # Undefined 记忆（未初始化）
│   ├── lifebook/           # LifeBook 记忆（未初始化）
│   ├── conversations/       # 对话历史（建议创建）
│   └── cognitive/          # 向量存储（建议创建）
├── logs/                   # 系统日志
│   ├── miya_YYYYMMDD.log
│   └── miya_qq_YYYYMMDD.log
└── config/
    └── .env               # 配置文件
```

## ✅ 总结

**当前状态：**
- ✅ 系统日志正常记录
- ❌ 对话历史未持久化（重启丢失）
- ❌ 记忆系统未初始化
- ❌ 向量数据库未配置

**下一步：**
1. 创建对话历史持久化模块
2. 初始化 Undefined 记忆系统
3. 可选：配置 Redis/ChromaDB

**logs 目录说明：**
- logs 目录只存储**系统日志**，不包含对话历史
- 对话历史当前只存在于**运行时内存**
- 重启后内存中的对话会全部丢失
