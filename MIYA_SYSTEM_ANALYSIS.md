# 弥娅AI系统 - 全面深入分析文档

> 版本: 1.0.0  
> 最后更新: 2026-03-10  
> 作者: MIYA Development Team

---

## 目录

1. [系统概述](#1-系统概述)
2. [核心架构](#2-核心架构)
3. [核心模块详解](#3-核心模块详解)
4. [子网系统](#4-子网系统)
5. [工具系统](#5-工具系统)
6. [数据库系统](#6-数据库系统)
7. [多模型管理系统](#7-多模型管理系统)
8. [权限系统](#8-权限系统)
9. [Web API系统](#9-web-api系统)
10. [其他重要模块](#10-其他重要模块)
11. [部署与运维](#11-部署与运维)

---

## 1. 系统概述

### 1.1 什么是弥娅

弥娅（Miya）是一个**数据生命体数字伴侣系统**，具备以下核心特性：

- **动态人格系统**: 五维人格向量，随对话动态演化
- **多层记忆架构**: Tide/Vector/Graph 三种记忆类型
- **多模型智能调度**: 根据任务类型自动选择最优模型
- **跨平台接入**: 终端、Web、QQ机器人、Desktop多端支持
- **完善权限系统**: 跨平台权限管理，细粒度控制
- **自主能力引擎**: 任务规划、执行、学习一体化

### 1.2 技术栈

| 类别 | 技术 |
|------|------|
| **核心语言** | Python 3.11+ |
| **异步框架** | asyncio |
| **Web框架** | FastAPI |
| **数据库** | Redis, Milvus, Neo4j, ChromaDB |
| **AI模型** | DeepSeek, OpenAI, Anthropic, ZhipuAI |
| **前端框架** | React (miya-pc-ui) |
| **桌面端** | Electron (miya-desktop) |

### 1.3 系统特点

1. **蛛网式模块化架构** - 清晰的分层设计，模块间职责明确
2. **热插拔子网系统** - 子网可独立开发、部署、升级
3. **智能输出系统** - 自动判断内容类型，选择最优输出方式
4. **权限隔离** - 不同用户/平台拥有不同权限
5. **成本优化** - 多模型调度，根据预算自动选择模型

---

## 2. 核心架构

### 2.1 整体架构分层

弥娅系统采用**蛛网式模块化单体架构**（Spider-Web Modular Monolith）：

```
┌─────────────────────────────────────────────────────────────┐
│                     接入层                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 终端接入  │  │ Web UI    │  │ QQ机器人  │  │ Desktop  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     API层                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   WebAPI (FastAPI) / RuntimeAPI                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   核心业务层                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │ AI Client│  │PromptMgr│  │AgentMgr │  │AutoEngine│     │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │Personality│ │MemorySys│ │MultiModel│ │Conversation│   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   子网层          │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │
│  │Auth │ │Tool │ │Msg  │ │Mem  │ │Sch  │ │Life │        │
│  │ Net │ │ Net │ │ Net │ │ Net │ │ Net │ │ Net │        │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘        │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                 │
│  │Grp  │ │Know │ │Bili │ │Cogn │ │Web  │                 │
│  │ Net │ │ Net │ │ Net │ │ Net │ │Sch  │                 │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   数据存储层                  │
│  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  │
│  │ Redis │  │ Milvus │  │ Neo4j │  │ Files │  │ SQLite │  │
│  └───────┘  └───────┘  └───────┘  └───────┘  └───────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流设计

#### 用户输入流程
```
用户输入 → 平台适配器 → WebAPI → DecisionHub → PromptManager
→ AI Client (多模型选择) → 工具执行 → 结果返回
```

#### 记忆存储流程
```
对话内容 → MemoryNet → [Tide Memory (Redis)]
                            ↓
                       [Vector Memory (Milvus)]
                            ↓
                       [Knowledge Graph (Neo4j)]
```

#### 权限检查流程
```
工具调用请求 → ToolRegistry → PermissionCore (AuthNet)
→ 用户权限验证 → 执行/拒绝
```

### 2.3 启动流程

**启动顺序：**
```python
1. 加载配置文件 (.env, settings.py)
2. 初始化日志系统 (advanced_logger.py)
3. 初始化权限系统 (AuthNet/permission_core.py)
4. 初始化多模型管理器 (multi_model_manager.py)
5. 初始化记忆系统 (MemoryNet, redis_config.py, chromadb_config.py)
6. 初始化人格系统 (personality.py)
7. 初始化工具注册表 (ToolNet/registry.py)
8. 初始化AI客户端 (ai_client.py)
9. 初始化多Agent协调器 (multi_agent_orchestrator.py)
10. 初始化WebAPI路由 (web_api.py)
11. 启动各平台适配器 (TerminalNet, QQNet, WebNet等)
```

---

## 3. 核心模块详解

### 3.1 conversation_history.py - 对话历史管理

**文件位置**: `core/conversation_history.py`

**功能描述：**
- 对话历史的持久化存储（JSON文件）
- 按会话ID分组管理
- 异步IO，不阻塞主线程
- 增量加载，避免内存爆炸
- 自动限制历史条数

**关键类和函数：**

```python
@dataclass
class ConversationMessage:
    """对话消息数据结构"""
    role: str  # user, assistant, system
    content: str
    timestamp: str
    session_id: str
    images: Optional[List[str]] = None
    agent_id: Optional[str] = None
    metadata: Optional[Dict] = None

class ConversationHistoryManager:
    async def add_message(session_id, role, content, ...)
    async def get_history(session_id, limit=None)
    async def clear_session(session_id)
    async def export_session(session_id, output_path)
    async def cleanup_old_sessions(days=30)
```

**配置示例：**
```python
manager = ConversationHistoryManager(
    data_dir=Path("data/conversations"),
    max_messages_per_session=200,  # 每会话最多200条消息
    max_memory_sessions=100  # 内存中最多缓存100个会话
)
```

---

### 3.2 multi_agent_orchestrator.py - 多智能体编排

**文件位置**: `core/multi_agent_orchestrator.py`

**功能描述：**
- 任务分配（基于能力和负载均衡）
- Agent通信（消息队列）
- 结果聚合（支持多种策略）
- 并行执行子任务

**关键类和函数：**

```python
class Agent:
    def supports_capability(capability: str) -> bool
    async def execute(task: Dict) -> Dict
    async def send_message(receiver_id, content)

class MultiAgentOrchestrator:
    async def register_agent(agent_id, config) -> str
    async def coordinate_task(task) -> Dict
    async def send_message(sender_id, receiver_id, content)
    async def get_task_status(task_id)
```

**任务分解策略：**
```python
# 按能力分组
capabilities = ['code_analysis', 'web_search', 'data_processing']
# 分解为多个子任务
subtasks = [
    SubTask("code_analysis", required_capabilities=['code_analysis']),
    SubTask("web_search", required_capabilities=['web_search']),
    SubTask("data_processing", required_capabilities=['data_processing'])
]
```

---

### 3.3 prompt_manager.py - 提示词管理

**文件位置**: `core/prompt_manager.py`

**功能描述：**
- 系统提示词管理（支持人格集成）
- 用户提示词模板（支持Jinja2）
- 记忆上下文注入
- 多模式提示词支持

**关键类和函数：**

```python
class PromptManager:
    def __init__(self, personality=None, config_path=None)
    def get_system_prompt() -> str
    def generate_user_prompt(user_input, context) -> str
    def build_full_prompt(user_input, memory_context, additional_context)
    def _load_mode_prompt(prompt_key) -> Optional[str]
```

**提示词模板示例：**
```python
# 用户提示词模板
USER_PROMPT_TEMPLATE = "用户输入：{user_input}"

# 系统提示词包含：
# 1. 弥娅人设（高冷温柔、数据生命体）
# 2. 工具使用规则
# 3. 记忆管理规则
# 4. 对话与工具调用的平衡
# 5. 动态人格状态
```

---

### 3.4 web_api.py - Web API实现

**文件位置**: `core/web_api.py`

**功能描述：**
- RESTful API接口
- 博客API
- 认证API
- 对话API
- 安全API
- API权限中间件

**关键类和函数：**

```python
class WebAPI:
    def __init__(self, web_net, decision_hub, github_store)
    
    # 博客相关
    @self.router.get("/blog/posts")
    async def get_blog_posts(page, per_page, category, tag)
    @self.router.post("/blog/posts")
    async def create_blog_post(post_data, token)
    
    # 对话相关
    @self.router.post("/chat")
    async def chat(chat_request)
    
    # 权限检查
    async def check_api_permission(required_permission, credentials)
```

**请求/响应格式：**
```python
# 聊天请求
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    platform: Optional[str] = None

# 博客创建请求
class BlogPostCreate(BaseModel):
    title: str
    content: str
    category: str
    tags: List[str]
    published: bool = True
```

---

### 3.5 数据库管理相关模块

**核心模块：**
- `redis_config.py` - Redis配置（涨潮记忆）
- `chromadb_config.py` - ChromaDB配置（向量记忆）
- `unified_cache.py` - 统一缓存管理器
- `unified_memory.py` - 统一记忆系统

**关键功能：**
```python
class UnifiedMemory:
    async def store_tide_memory(key, value, ttl=3600)
    async def retrieve_tide_memory(key)
    async def store_vector_memory(text, metadata)
    async def search_vector_memory(query, top_k=10)
    async def store_knowledge(subject, action, object, context, time)
    async def query_knowledge(cypher_query)
```

---

### 3.6 其他核心模块

| 模块 | 功能 | 关键类/函数 |
|------|------|------------|
| `ai_client.py` | AI客户端（多模型支持） | `BaseAIClient`, `OpenAIClient`, `DeepSeekClient` |
| `agent_manager.py` | Agent任务管理 | `AgentManager`, `TaskStep`, `CompressedMemory` |
| `personality.py` | 人格系统 | `Personality`, 五维人格向量 |
| `autonomous_engine.py` | 自主引擎 | `AutonomousEngine`, 任务规划与执行 |
| `multi_model_manager.py` | 多模型管理 | `MultiModelManager`, `TaskType`, 模型选择 |
| `task_planner.py` | 任务规划器 | `TaskPlanner`, 任务分解 |
| `decision_optimizer.py` | 决策优化器 | `DecisionOptimizer`, 决策树优化 |
| `skills_registry.py` | 技能注册表 | `SkillsRegistry`, 技能发现与注册 |

---

## 4. 子网系统

### 4.1 AuthNet - 权限认证系统

**目录**: `webnet/AuthNet/`

**职责：**
- 用户和用户组管理
- 权限节点检查
- 审计日志记录
- 权限缓存

**关键类和函数：**
```python
class PermissionCore:
    def check_permission(user_id, permission, context, list_mode=False)
    def grant_permission(user_id, permission)
    def revoke_permission(user_id, permission)
    def list_user_permissions(user_id)
    def _has_permission(perm_list, permission) -> bool

# 权限规则（优先级从高到低）：
# 1. 超级管理员 ("*")
# 2. 精确拒绝 (例如: -tool.web_search)
# 3. 精确允许 (例如: tool.web_search)
# 4. 父级权限 (例如: tool.* 匹配 tool.web_search)
# 5. 默认拒绝
```

**权限节点设计：**
```
tool.{tool_name}          # 工具权限
agent.{agent_name}        # Agent权限
web.{endpoint}            # Web API权限
system_admin              # 系统管理员
```

**用户和组配置：**
```json
// data/auth/users.json
{
  "users": [
    {
      "user_id": "qq_123456",
      "username": "test_user",
      "platform": "qq",
      "permission_groups": ["Default", "VIP"],
      "permissions": ["*"],
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}

// data/auth/groups.json
{
  "groups": {
    "Default": {
      "permissions": ["tool.web_search", "agent.chat"]
    },
    "VIP": {
      "permissions": ["tool.*", "agent.*"]
    }
  }
}
```

---

### 4.2 ToolNet - 工具网络

**目录**: `webnet/ToolNet/`

**职责：**
- 工具注册与发现
- 工具执行（含权限检查）
- 工具结果处理
- 子网路由

**关键类和函数：**
```python
class ToolRegistry:
    def register(tool) -> bool
    def get_tool(name) -> BaseTool
    def get_tools_schema(tool_names) -> List[Dict]
    async def execute_tool(name, args, context) -> str
    async def _check_tool_permission(tool_name, context)
    def load_all_tools()

class BaseTool:
    @property
    def config() -> Dict[str, Any]  # OpenAI Function Calling格式
    async def execute(args, context) -> str
    def validate_args(args) -> tuple[bool, Optional[str]]
```

**工具分类：**
- **基础工具** (BasicNet): `get_current_time`, `get_user_info`, `python_interpreter`
- **终端工具** (TerminalNet): `terminal_command`
- **消息工具** (MessageNet): `send_message`, `get_recent_messages`, `send_text_file`
- **群工具** (GroupNet): `get_member_list`, `get_member_info`, `find_member`, `filter_members`
- **记忆工具** (MemoryNet): `memory_add`, `memory_list`, `memory_update`, `auto_extract_memory`
- **知识工具** (KnowledgeNet): `knowledge_list`, `knowledge_text_search`, `knowledge_semantic_search`
- **认知工具** (CognitiveNet): `get_profile`, `search_profiles`, `search_events`
- **B站工具** (BilibiliNet): `bilibili_video`
- **定时任务工具** (SchedulerNet): `create_schedule_task`, `list_schedule_tasks`, `delete_schedule_task`
- **酒馆工具** (EntertainmentNet/tavern): `start_tavern`, `tavern_chat`, `generate_story`
- **TRPG工具** (EntertainmentNet/trpg): `start_trpg`, `roll_dice`, `create_pc`, `show_pc`, `skill_check`
- **查询工具** (EntertainmentNet/query): `search_tavern_stories`, `search_trpg_characters`
- **游戏模式工具** (EntertainmentNet/game_mode): `exit_game`, `list_saves`, `create_save`, `load_save`
- **Web搜索工具** (WebSearchNet): `web_search`, `get_available_search_engines`
- **可视化工具** (visualization): `data_analyzer`, `chart_generator`
- **LifeNet工具** (LifeNet): `life_add_diary`, `life_get_diary`, `life_add_summary`

---

### 4.3 MessageNet - 消息网络

**目录**: `webnet/MessageNet/`

**职责：**
- 消息发送管理
- 消息历史查询
- 文件发送（文本/URL）

**关键工具：**
```python
class SendMessageTool(BaseTool):
    """发送消息工具"""

class GetRecentMessagesTool(BaseTool):
    """获取最近消息工具"""

class SendTextFileTool(BaseTool):
    """发送文本文件工具"""
```

---

### 4.4 MemoryNet - 记忆网络

**目录**: `webnet/MemoryNet/`

**职责：**
- 记忆增删查改
- 自动记忆提取
- 记忆更新与删除

**关键工具：**
```python
class MemoryAdd(BaseTool):
    """添加记忆工具"""

class MemoryList(BaseTool):
    """查询记忆工具"""

class MemoryUpdate(BaseTool):
    """更新记忆工具"""

class AutoExtractMemory(BaseTool):
    """自动提取记忆工具"""
```

**统一记忆接口：**
```python
# 支持多种存储后端
memory_engine.add_memory(text, tags, importance)
memory_engine.search_memory(query, top_k)
memory_engine.update_memory(memory_id, updates)
memory_engine.delete_memory(memory_id)
```

---

### 4.5 DecisionHub - 决策网络

**目录**: `hub/decision_hub.py`

**职责：**
- 任务分发决策
- 子网选择
- 结果聚合

---

### 4.6 其他子网

| 子网 | 职责 |
|------|------|
| **GroupNet** | 群组管理、成员查询 |
| **KnowledgeNet** | 知识库管理 |
| **CognitiveNet** | 认知画像管理 |
| **BilibiliNet** | B站视频搜索 |
| **SchedulerNet** | 定时任务管理 |
| **LifeNet** | LifeBook记忆管理 |
| **TerminalNet** | 终端命令执行 |
| **WebSearchNet** | Web搜索 |

---

## 5. 工具系统

### 5.1 工具分类和功能

**开发者工具类：**
- `code_generator.py` - 代码生成器
- `code_migrator.py` - 代码迁移工具
- `file_classifier.py` - 文件分类器
- `system_monitor.py` - 系统监控
- `workflow_engine.py` - 工作流引擎

**测试工具类：**
- `test_case_generator.py` - 测试用例生成器
- `api_simulator.py` - API模拟器

**报告工具类：**
- `report_generator.py` - 报告生成器
- `backup_manager.py` - 备份管理器

**可视化工具：**
```python
# tools/visualization/
class DataAnalyzer(BaseTool):
    """数据分析工具"""

class ChartGenerator(BaseTool):
    """图表生成工具"""
```

**终端工具：**
```python
# tools/terminal/
class TerminalCommandTool(BaseTool):
    """终端命令执行工具"""
```

---

### 5.2 工具注册机制

**注册流程：**
```python
# 1. 工具类继承 BaseTool
class MyTool(BaseTool):
    @property
    def config(self):
        return {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "工具描述",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string", "description": "参数描述"}
                    },
                    "required": ["arg1"]
                }
            }
        }
    
    async def execute(self, args, context):
        return "执行结果"

# 2. 注册到 ToolRegistry
registry = ToolRegistry()
registry.register(MyTool())
```

---

### 5.3 权限控制

**权限检查流程：**
```python
# 1. 获取统一用户ID
user_mapper = UserMapper()
unified_user_id = user_mapper.generate_user_id(platform, user_id)

# 2. 构建权限节点
required_permission = f"tool.{tool_name}"

# 3. 检查权限
perm_core = PermissionCore()
has_permission = perm_core.check_permission(unified_user_id, required_permission)

# 4. 执行或拒绝
if has_permission:
    result = await tool.execute(args, context)
else:
    return "❌ 权限不足"
```

---

## 6. 数据库系统

### 6.1 Redis的使用场景

**配置：**
```ini
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=10
```

**用途：**
- **涨潮记忆 (Tide Memory)** - 短期高频对话存储
  ```python
  await memory_engine.store_tide_memory(key, value, ttl=3600)
  ```
- **缓存系统** - 权限缓存、API响应缓存
- **会话状态** - 实时会话数据
- **任务队列** - 异步任务管理

---

### 6.2 Milvus向量数据库

**配置：**
```ini
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory
MILVUS_DIMENSION=1536
MILVUS_INDEX_TYPE=IVF_FLAT
MILVUS_INDEX_PARAMS={"nlist":128}
```

**用途：**
- **向量记忆 (Vector Memory)** - 语义检索长期记忆
  ```python
  await memory_engine.store_vector_memory(text, metadata)
  await memory_engine.search_vector_memory(query, top_k=10)
  ```
- **相似度搜索** - 基于embedding的语义匹配

---

### 6.3 Neo4j知识图谱

**配置：**
```ini
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j
```

**用途：**
- **知识图谱 (Knowledge Graph)** - 五元组关系存储
  ```python
  await memory_engine.store_knowledge(subject, action, object, context, time)
  await memory_engine.query_knowledge(cypher_query)
  ```
- **关系推理** - 实体关系分析
- **图谱查询** - 复杂关系查询

---

### 6.4 数据库连接和配置

**Redis连接：**
```python
# core/redis_config.py
import redis
from core.constants import Encoding

redis_client = redis.Redis(
    host=settings.get('redis.host'),
    port=settings.get('redis.port'),
    db=settings.get('redis.db'),
    password=settings.get('redis.password'),
    decode_responses=True,
    max_connections=settings.get('redis.max_connections', 10)
)
```

**Milvus连接：**
```python
# core/chromadb_config.py
import chromadb
from chromadb.config import Settings

chroma_client = chromadb.PersistentClient(
    path="data/chroma",
    settings=Settings(anonymized_telemetry=False)
)
```

**Neo4j连接：**
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    settings.get('neo4j.uri'),
    auth=(settings.get('neo4j.user'), settings.get('neo4j.password'))
)
```

---

## 7. 多模型管理系统

### 7.1 多模型配置文件

**配置文件位置**: `config/multi_model_config.json`

**配置结构：**
```json
{
  "models": {
    "chinese": {
      "name": "deepseek-chat",
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-xxx",
      "capabilities": [
        "simple_chat",
        "chinese_understanding",
        "task_planning",
        "tool_calling"
      ],
      "cost_per_1k_tokens": {
        "input": 0.00014,
        "output": 0.00028
      },
      "latency": "fast",
      "quality": "excellent"
    },
    "fast": {
      "name": "Qwen/Qwen2.5-7B-Instruct",
      "provider": "openai",
      "base_url": "https://api.siliconflow.cn/v1",
      "api_key": "sk-xxx",
      "capabilities": ["simple_chat", "summarization", "task_classification"]
    }
  },
  "routing_strategy": {
    "simple_chat": {
      "primary": "fast",
      "fallback": "chinese",
      "cost_priority": 1.0,
      "speed_priority": 0.9,
      "quality_priority": 0.7
    }
  },
  "budget_control": {
    "daily_budget_usd": 10.0,
    "monthly_budget_usd": 300.0,
    "alert_threshold": 0.8,
    "stop_threshold": 0.95
  },
  "performance_settings": {
    "enable_caching": true,
    "cache_ttl_seconds": 3600,
    "enable_parallel_execution": true,
    "max_parallel_models": 3,
    "consensus_threshold": 0.7
  }
}
```

---

### 7.2 多模型管理机制

**关键类：**
```python
class MultiModelManager:
    def __init__(self, model_clients, config_path=None)
    async def classify_task(user_input, context) -> TaskType
    async def select_model(task_type, budget_constraint, latency_constraint)
    def record_usage(model_key, input_tokens, output_tokens)
    def get_usage_stats() -> Dict
    def get_total_cost() -> float
```

**任务类型枚举：**
```python
class TaskType(Enum):
    SIMPLE_CHAT = "simple_chat"
    COMPLEX_REASONING = "complex_reasoning"
    CODE_ANALYSIS = "code_analysis"
    CODE_GENERATION = "code_generation"
    TOOL_CALLING = "tool_calling"
    CREATIVE_WRITING = "creative_writing"
    CHINESE_UNDERSTANDING = "chinese_understanding"
    SUMMARIZATION = "summarization"
    MULTIMODAL = "multimodal"
    TASK_PLANNING = "task_planning"
```

---

### 7.3 模型切换逻辑

**任务分类（基于规则）：**
```python
async def classify_task(self, user_input, context) -> TaskType:
    input_lower = user_input.lower()
    
    # 工具调用检测
    tool_keywords = ['执行', '运行', '打开', '文件', '搜索']
    if any(kw in input_lower for kw in tool_keywords):
        return TaskType.TOOL_CALLING
    
    # 代码相关检测
    code_keywords = ['代码', '函数', '编程', 'python']
    if any(kw in input_lower for kw in code_keywords):
        return TaskType.CODE_GENERATION
    
    # 复杂推理检测
    reasoning_keywords = ['分析', '推理', '解释', '为什么']
    if any(kw in input_lower for kw in reasoning_keywords):
        return TaskType.COMPLEX_REASONING
    
    # 中文理解
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', user_input))
    if chinese_chars > len(user_input) * 0.5:
        return TaskType.CHINESE_UNDERSTANDING
    
    return TaskType.SIMPLE_CHAT
```

**模型选择（基于策略）：**
```python
async def select_model(self, task_type, budget_constraint, latency_constraint):
    strategy = self.config.get('routing_strategy', {}).get(task_type.value, {})
    
    primary = strategy.get('primary')
    fallback = strategy.get('fallback')
    secondary = strategy.get('secondary')
    
    # 尝试主模型
    if primary and primary in self.model_clients:
        if self._check_constraints(primary, strategy, budget_constraint, latency_constraint):
            return primary, self.model_clients[primary]
    
    # 尝试次选模型
    if secondary and secondary in self.model_clients:
        if self._check_constraints(secondary, strategy, budget_constraint, latency_constraint):
            return secondary, self.model_clients[secondary]
    
    # 尝试回退模型
    if fallback and fallback in self.model_clients:
        return fallback, self.model_clients[fallback]
    
    # 降级到第一个可用模型
    for key, client in self.model_clients.items():
        if client:
            return key, client
    
    return None, None
```

---

## 8. 权限系统

### 8.1 用户和用户组管理

**用户数据结构：**
```json
{
  "users": [
    {
      "user_id": "qq_123456",
      "username": "test_user",
      "platform": "qq",
      "permission_groups": ["Default", "VIP"],
      "permissions": ["tool.web_search"],
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

**用户组数据结构：**
```json
{
  "groups": {
    "Default": {
      "permissions": ["tool.web_search", "agent.chat"]
    },
    "VIP": {
      "permissions": ["tool.*", "agent.*"]
    },
    "Admin": {
      "permissions": ["*"]
    }
  }
}
```

---

### 8.2 权限节点设计

**权限节点规范：**
```
格式: {模块}.{操作}.{子操作}

示例:
- tool.web_search           # Web搜索工具
- tool.terminal_command     # 终端命令工具
- tool.*                    # 所有工具
- agent.chat                # 聊天Agent
- agent.*                   # 所有Agent
- web.api.access            # Web API访问
- system_admin              # 系统管理员（超级权限）
```

**权限检查规则：**
```python
# 优先级从高到低：
1. 超级管理员 ("*") - 最高优先级
2. 精确拒绝 (例如: -tool.web_search)
3. 精确允许 (例如: tool.web_search)
4. 父级权限 (例如: tool.* 匹配 tool.web_search)
5. 默认拒绝
```

---

### 8.3 跨平台权限机制

**用户ID映射：**
```python
class UserMapper:
    def generate_user_id(platform, platform_user_id) -> str:
        """生成统一用户ID"""
        return f"{platform}_{platform_user_id}"
    
    # 示例：
    # QQ用户: "qq_123456"
    # Web用户: "web_user456"
    # 终端用户: "terminal_root"
```

**平台适配：**
```python
# 权限检查示例
unified_user_id = user_mapper.generate_user_id("qq", "123456")
has_permission = perm_core.check_permission(
    unified_user_id,
    "tool.web_search"
)
```

---

## 9. Web API系统

### 9.1 所有API端点

**博客API：**
```
GET    /api/blog/posts         # 获取博客列表
GET    /api/blog/posts/{slug}  # 获取单篇博客
POST   /api/blog/posts         # 创建博客（需认证）
PUT    /api/blog/posts/{slug}  # 更新博客（需认证）
DELETE /api/blog/posts/{slug}  # 删除博客（需认证）
```

**认证API：**
```
POST   /api/auth/register      # 用户注册
POST   /api/auth/login         # 用户登录
POST   /api/auth/logout        # 用户登出
GET    /api/auth/profile       # 获取用户信息
```

**对话API：**
```
POST   /api/chat               # 发送对话消息
GET    /api/chat/history       # 获取对话历史
DELETE /api/chat/session/{id}  # 删除会话
```

**系统状态API：**
```
GET    /api/system/status      # 系统状态
GET    /api/system/stats       # 系统统计
GET    /api/system/health      # 健康检查
```

**安全API：**
```
POST   /api/security/scan      # 安全扫描
POST   /api/security/block-ip  # IP封禁
DELETE /api/security/block-ip  # IP解封
```

---

### 9.2 路由设计

**路由结构：**
```python
from fastapi import APIRouter

class WebAPI:
    def __init__(self, web_net, decision_hub, github_store):
        self.router = APIRouter(prefix="/api", tags=["Web"])
        self.security = HTTPBearer()
        self._setup_routes()
    
    def _setup_routes(self):
        # 设置各路由
        self._setup_blog_routes()
        self._setup_auth_routes()
        self._setup_chat_routes()
        self._setup_system_routes()
        self._setup_security_routes()
```

---

### 9.3 请求/响应格式

**请求格式示例：**
```json
{
  "message": "你好，弥娅",
  "session_id": "default",
  "platform": "web"
}
```

**响应格式示例：**
```json
{
  "success": true,
  "data": {
    "response": "你好！我是弥娅，很高兴见到你~",
    "session_id": "default",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

---

## 10. 其他重要模块

### 10.1 hub/ - 平台适配器

**功能：**
- QQ机器人适配
- Web UI适配
- Terminal适配
- Desktop适配

**关键文件：**
```
hub/qq_adapter.py      # QQ机器人适配器
hub/web_adapter.py      # Web适配器
hub/terminal_adapter.py # 终端适配器
hub/desktop_adapter.py  # Desktop适配器
```

---

### 10.2 memory/ - 记忆管理

**功能：**
- 记忆存储（多种后端）
- 记忆检索
- 记忆压缩
- 记忆重要性评分

**关键类：**
```python
class MemoryCompressor:
    """记忆压缩器"""
    async def compress(self, memories) -> CompressedMemory

class MemoryImportanceScorer:
    """记忆重要性评分器"""
    def score(self, memory) -> float
```

---

### 10.3 storage/ - 存储系统

**功能：**
- 文件存储
- 缓存存储
- 数据库存储

**关键类：**
```python
class UnifiedCache:
    """统一缓存管理器"""
    async def get(self, key)
    async def set(self, key, value, ttl=None)
    async def delete(self, key)
    async def clear(self)
```

---

### 10.4 perceive/ - 感知系统

**功能：**
- 用户情绪感知
- 语境理解
- 意图识别

**关键类：**
```python
class EmotionDetector:
    """情绪检测器"""
    def detect_emotion(text) -> Dict[str, float]

class IntentRecognizer:
    """意图识别器"""
    def recognize_intent(text) -> str
```

---

## 11. 部署与运维

### 11.1 启动系统

**启动方式：**
```bash
# 方式1: 使用启动脚本
./start.sh          # Linux/Mac
start.bat           # Windows

# 方式2: 使用Python直接启动
python run/main.py

# 方式3: 使用启动菜单
python run/launcher.py
```

---

### 11.2 配置文件

**环境变量配置 (`.env`)：**
```ini
# AI提供商
AI_PROVIDER=deepseek

# OpenAI配置
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# DeepSeek配置
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 其他配置
AI_MAX_TOKENS=2000
AI_TEMPERATURE=0.7
```

**系统配置 (`.env`)：**
```ini
# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory

# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=

# 人格配置
PERSONALITY_WARMTH=0.8
PERSONALITY_LOGIC=0.7
PERSONALITY_CREATIVITY=0.6
PERSONALITY_EMPATHY=0.75
PERSONALITY_RESILIENCE=0.7
```

---

### 11.3 日志管理

**日志配置：**
```ini
# 日志级别
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# 日志文件
LOG_DIR=logs
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=10
```

**日志查看：**
```bash
# 查看最新日志
tail -f logs/miya.log

# 查看错误日志
grep ERROR logs/miya.log
```

---

### 11.4 数据备份

**备份脚本：**
```bash
# 备份Redis
redis-cli --rdb backup/dump.rdb

# 备份ChromaDB
tar -czf backup/chroma.tar.gz data/chroma

# 备份Neo4j
neo4j-admin dump --database=neo4j --to=backup/neo4j
```

---

### 11.5 监控与告警

**系统监控：**
```python
# 检查系统状态
from core import get_system_status

status = get_system_status()
print(f"CPU: {status['cpu']}%")
print(f"内存: {status['memory']}%")
print(f"磁盘: {status['disk']}%")
```

---

## 总结

弥娅AI系统是一个功能全面、架构清晰的数字生命伴侣系统。其核心特点包括：

1. **蛛网式模块化架构** - 清晰的分层设计，模块间职责明确
2. **多模型智能调度** - 根据任务类型自动选择最优模型
3. **动态人格系统** - 五维人格向量，随对话动态演化
4. **多层记忆架构** - Tide/Vector/Graph三种记忆类型
5. **完善的权限系统** - 跨平台权限管理，细粒度控制
6. **丰富的工具集** - 涵盖终端、Web搜索、TRPG、酒馆等多种功能
7. **多端接入支持** - 终端、Web、QQ机器人、Desktop等多种接入方式

系统设计充分考虑了可扩展性、可维护性和性能优化，是一个成熟的企业级AI应用架构。
