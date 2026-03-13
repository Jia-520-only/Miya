# 弥娅(MIYA)系统重构指南

## 目录
1. [系统概述](#1-系统概述)
2. [架构设计](#2-架构设计)
3. [模块详解](#3-模块详解)
4. [从零开始搭建](#4-从零开始搭建)
5. [核心代码解析](#5-核心代码解析)
6. [数据流与通信](#6-数据流与通信)
7. [扩展开发](#7-扩展开发)

---

## 1. 系统概述

### 1.1 什么是弥娅？

弥娅(MIYA)是一个高度模块化的AI伴侣系统，具有以下特性：
- **多模型支持**: 内置9+大语言模型切换
- **四层记忆架构**: Redis(短期) + Milvus(向量) + Neo4j(图谱) + JSON(持久)
- **多终端协作**: 支持终端、Web、QQ Desktop多种交互方式
- **动态人格演化**: 具备自我学习和人格进化能力
- **工具生态**: 95+工具函数供AI调用

### 1.2 技术栈

```
Python 3.11+
├── FastAPI/Uvicorn    # Web服务
├── Redis              # 缓存/短期记忆
├── Milvus             # 向量数据库
├── Neo4j              # 图数据库
├── Electron           # 桌面应用
└── Vite + Vue3       # 前端框架
```

---

## 2. 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ 终端    │  │ Web UI  │  │ QQ Bot  │  │Desktop  │           │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
└───────┼────────────┼────────────┼────────────┼─────────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       M-Link 消息路由层                          │
│              (消息路由、队列管理、通信协调)                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   感知层       │    │   决策层       │    │   执行层       │
│  Perceive     │    │    Hub        │    │   ToolNet     │
│  - 注意力门控  │    │  - Decision   │    │  - 95+工具    │
│  - 输入分类    │    │  - Emotion    │    │  - 权限检查    │
└───────────────┘    └───────┬───────┘    └───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌──────────┐    ┌──────────┐    ┌──────────┐
       │  记忆层   │    │  核心层   │    │  演化层   │
       │ Memory   │    │   Core    │    │ Evolve   │
       │ - Redis  │    │- Personality│  │ - 自主学习 │
       │ - Milvus │    │ - Ethics  │    │ - AB测试  │
       │ - Neo4j  │    │ - Identity│   └──────────┘
       └──────────┘    └──────────┘
```

### 2.2 核心模块职责

| 模块 | 目录 | 职责 |
|------|------|------|
| **core** | `core/` | 灵魂内核：人格、伦理、身份、仲裁、AI客户端 |
| **hub** | `hub/` | 认知中枢：记忆引擎、情感、决策、调度器 |
| **memory** | `memory/` | 四层记忆架构：短期/向量/图谱/持久 |
| **webnet** | `webnet/` | 多平台网络：QQ/Web/Desktop子网 |
| **mlink** | `mlink/` | 消息通信：路由、队列、跨进程 |
| **storage** | `storage/` | 存储适配器：Redis/Milvus/Neo4j |
| **perceive** | `perceive/` | 感知系统：注意力、输入处理 |
| **detect** | `detect/` | 检测器：时间/空间/熵监控 |
| **trust** | `trust/` | 信任系统：分数评估、传播 |
| **evolve** | `evolve/` | 演化系统：学习、人格进化 |
| **tools** | `tools/` | 工具集：终端/Web搜索/调度 |

---

## 3. 模块详解

### 3.1 core - 核心层

**文件列表** (30个核心文件):
- `personality.py` - 人格系统
- `ethics.py` - 伦理规范
- `identity.py` - 身份管理
- `arbitrator.py` - 仲裁者
- `entropy.py` - 熵值管理
- `ai_client.py` - AI客户端封装
- `prompt_manager.py` - 提示词管理
- `autonomy_with_personality.py` - 自主能力

**核心类初始化顺序**:
```python
# run/main.py 中的初始化顺序
self.personality = Personality()      # 1. 人格
self.ethics = Ethics()                 # 2. 伦理
self.identity = Identity()              # 3. 身份
self.arbitrator = Arbitrator(...)      # 4. 仲裁
self.entropy = Entropy()               # 5. 熵
self.prompt_manager = PromptManager()  # 6. 提示词
self.ai_client = create_ai_client()    # 7. AI客户端
```

### 3.2 hub - 认知中枢

**文件列表** (12个文件):
- `decision_hub.py` - 统一决策入口 (65KB, 最大文件)
- `decision.py` - 决策逻辑
- `emotion.py` - 情感系统
- `memory_engine.py` - 记忆引擎
- `memory_emotion.py` - 情感记忆
- `scheduler.py` - 任务调度
- `token_manager.py` - Token管理
- `queue_manager.py` - 队列管理
- `platform_adapters.py` - 平台适配器

### 3.3 memory - 记忆系统

**四层架构**:
```
┌────────────────────────────────────────┐
│           手动记忆 (JSON)               │
│   data/memory/undefined_memory.json    │
├────────────────────────────────────────┤
│           知识图谱 (Neo4j)             │
│   关系网络、实体连接                    │
├────────────────────────────────────────┤
│           向量记忆 (Milvus)            │
│   语义检索、相似度匹配                  │
├────────────────────────────────────────┤
│           短期记忆 (Redis)             │
│   潮汐记忆、会话缓存                    │
└────────────────────────────────────────┘
```

### 3.4 webnet - 网络层

**子网架构**:
- `AuthNet/` - 鉴权系统
- `ToolNet/` - 工具网络
- `TerminalNet/` - 终端网络
- `SchedulerNet/` - 调度网络
- `CognitiveNet/` - 认知网络
- `EntertainmentNet/` - 娱乐网络

---

## 4. 从零开始搭建

### 4.1 环境准备

```bash
# 1. 克隆项目
git clone https://github.com/Jia-520-only/Miya.git
cd Miya

# 2. 安装 Python 3.11+
# Windows: 下载安装 python-3.11.x
# Linux: sudo apt install python3.11

# 3. 创建虚拟环境
python -m venv venv

# 4. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 5. 安装依赖 (自动)
# Windows:
install_deps_fixed.ps1
# Linux:
bash install.sh
```

### 4.2 数据库启动

```bash
# 使用 Docker 启动所有数据库服务
docker-compose up -d

# 或分别启动:
docker run -d -p 6379:6379 redis:alpine
docker run -d -p 19530:19530 milvusdb/milvus
docker run -d -p 7687:7687 -p 7474:7474 neo4j:latest
```

### 4.3 配置环境变量

复制并编辑 `config/.env`:
```bash
cp config/.env.example config/.env
# 编辑填入API密钥
```

### 4.4 初始化鉴权系统

```bash
python init_auth.py
# 选择 1. 初始化鉴权系统
```

### 4.5 启动系统

```bash
# Windows: 双击 start.bat
# 或命令行:
python run/main.py

# 选择启动模式:
# 1. 主程序(终端模式)
# 2. QQ机器人
# 3. Web界面
# 4. 桌面应用
```

---

## 5. 核心代码解析

### 5.1 主程序入口 (run/main.py)

```python
class Miya:
    def __init__(self):
        # 第一阶段: 系统环境检测
        self.system_detector = get_system_detector()
        
        # 第二阶段: 核心层初始化
        self.personality = Personality()
        self.ethics = Ethics()
        self.identity = Identity()
        
        # 第三阶段: 中枢层初始化
        self.memory_emotion = MemoryEmotion()
        self.memory_engine = MemoryEngine()
        self.emotion = Emotion()
        self.decision = Decision(...)
        
        # 第四阶段: 网络层初始化
        self.mlink = MLinkCore(...)
        self.memory_net = MemoryNet(...)
        self.tool_subnet = ToolNet(...)
        
        # 第五阶段: API服务器
        self.web_api = create_web_api()
```

### 5.2 消息处理流程

```
用户输入 → Perceive(感知) → DecisionHub(决策) → ToolNet(执行) → 返回响应
                ↓
         MemoryNet(记忆)
                ↓
         Personality(人格) → 影响回复风格
```

### 5.3 决策流程 (hub/decision_hub.py)

```python
async def process_perception_cross_platform(self, message):
    # 1. 权限检查
    if not check_permission(user_id, 'api.access'):
        return "抱歉，您没有权限"
    
    # 2. 提取输入
    content = message.content
    
    # 3. 获取对话历史
    history = await self._get_conversation_context(session_id)
    
    # 4. 构建提示词
    prompt = self.prompt_manager.build_full_prompt(
        user_input=content,
        memory_context=history
    )
    
    # 5. AI生成
    response = await self.ai_client.chat_with_system_prompt(...)
    
    # 6. 存储记忆
    await self._store_unified_memory(...)
    
    return response
```

---

## 6. 数据流与通信

### 6.1 进程间通信

```
┌────────────────┐    HTTP API    ┌────────────────┐
│  主进程        │ ◄───────────► │  Web API       │
│  (main.py)    │               │  (uvicorn)     │
└───────┬────────┘               └───────┬────────┘
        │                                │
        │  WS / HTTP                    │ HTTP
        ▼                                ▼
┌────────────────┐               ┌────────────────┐
│  终端代理      │               │  桌面端        │
│ terminal_agent │               │  Electron      │
└────────────────┘               └────────────────┘
```

### 6.2 数据库连接

```python
# storage/redis_client.py
class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )

# storage/milvus_client.py  
class MilvusClient:
    def __init__(self):
        self.client = MilvusClient(
            host='localhost',
            port='19530'
        )

# storage/neo4j_client.py
class Neo4jClient:
    def __init__(self):
        self.driver = neo4j.GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )
```

---

## 7. 扩展开发

### 7.1 添加新工具

1. 在 `tools/` 目录创建新工具文件
2. 在 `webnet/ToolNet/registry.py` 注册
3. 配置权限到 `config/permissions.json`

```python
# tools/my_tool.py
class MyTool:
    def execute(self, param):
        return {"result": "success"}

# webnet/ToolNet/registry.py
def get_tools_schema(self):
    return {
        "my_tool": {
            "name": "my_tool",
            "description": "我的工具",
            "parameters": {...}
        }
    }
```

### 7.2 添加新平台

1. 在 `hub/platform_adapters.py` 添加适配器
2. 在 `webnet/` 添加对应子网
3. 配置消息路由

### 7.3 自定义人格

编辑 `data/personality/` 目录下的配置文件:
- `traits.json` - 人格特质
- `responses.json` - 响应模板

---

## 附录

### A. 端口映射

| 服务 | 端口 | 说明 |
|------|------|------|
| Web API | 8000 | 主API服务 |
| Web UI | 5173 | Vite开发服务器 |
| Redis | 6379 | 缓存/短期记忆 |
| Milvus | 19530 | 向量数据库 |
| Neo4j | 7687 | 图数据库 |
| Neo4j HTTP | 7474 | Neo4j浏览器 |

### B. 配置文件说明

| 文件 | 用途 |
|------|------|
| `config/.env` | 主配置(API密钥等) |
| `config/settings.py` | Python配置模块 |
| `config/multi_model_config.json` | 多模型配置 |
| `config/permissions.json` | 权限配置 |

### C. 日志位置

- `logs/` - 系统运行日志
- `logs/terminal_history.json` - 终端对话历史

---

*文档版本: 2026-03-13*
*项目地址: https://github.com/Jia-520-only/Miya*
