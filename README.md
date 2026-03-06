# 弥娅 (Miya) - 数字生命伴侣

![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

> *"不仅是AI，更是伙伴"* — 弥娅 v1.0.0

弥娅（Miya）是一个基于**蛛网式模块化架构**的数字生命伴侣系统，具备动态人格、情感演化、记忆管理、多模型智能调度、多端接入等核心能力。

---

## 📖 目录

- [快速开始](#-快速开始)
- [核心特性](#-核心特性)
- [系统架构](#-系统架构)
- [功能详解](#-功能详解)
- [安装部署](#-安装部署)
- [使用指南](#-使用指南)
- [配置说明](#-配置说明)
- [开发文档](#-开发文档)
- [常见问题](#-常见问题)
- [更新日志](#-更新日志)

---

## 🚀 快速开始

### 最低要求

| 组件 | 要求 | 说明 |
|--------|------|------|
| **操作系统** | Windows 10+ / Linux / macOS | 全平台支持 |
| **Python** | 3.9 或更高版本 | 推荐 3.11+ |
| **内存** | 建议 4GB+ | 8GB+ 最佳 |
| **存储** | 建议 10GB+ | 数据库和日志 |
| **网络** | 需要访问AI模型API | DeepSeek、硅基流动等 |

### 一键安装

**Windows:**
```batch
install.bat
```

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

安装脚本会自动：
1. ✅ 创建 Python 虚拟环境
2. ✅ 安装所有依赖包（140+ 个）
3. ✅ 初始化配置文件
4. ✅ 生成唯一 UUID
5. ✅ 创建必要的数据目录

### 启动系统

**终端模式（推荐新手）:**
```batch
start.bat        # Windows
./start.sh        # Linux/macOS
```

**PC WebUI 模式（推荐日常使用）:**
```batch
run/pc_start.bat  # Windows
run/pc_start.sh   # Linux/macOS
```

访问 `http://localhost:3000` 打开 Web 界面。

**QQ 机器人模式:**
```batch
run/qq_start.bat  # Windows
run/qq_start.sh   # Linux/macOS
```

⚠️ **注意**：QQ机器人需要 OneBot 服务支持（推荐 NapCat 或 go-cqhttp）

### 首次运行

系统首次启动会自动：
1. 创建虚拟环境（如不存在）
2. 安装依赖包（约140+个）
3. 初始化配置文件
4. 生成唯一 UUID
5. 创建数据目录（logs/、data/、volumes/）

---

## ⭐ 核心特性

### 🧠 动态人格系统

弥娅拥有五维人格向量，会根据对话动态演化：

| 维度 | 范围 | 描述 | 演化 |
|--------|--------|------|--------|
| **温暖度** (warmth) | 0.3 - 1.0 | 友善程度 | 冷静 ↔ 热情 |
| **逻辑性** (logic) | 0.4 - 0.9 | 理性程度 | 情感 ↔ 逻辑 |
| **创造力** (creativity) | 0.0 - 1.0 | 创新能力 | 务实 ↔ 创新 |
| **同理心** (empathy) | 0.0 - 1.0 | 理解能力 | 独立 ↔ 共情 |
| **韧性** (resilience) | 0.0 - 1.0 | 抗压能力 | 脆弱 ↔ 坚韧 |

**特性：**
- 🔄 **动态演化**：对话会微调人格数值
- 🎨 **情绪影响**：当前情绪会临时影响人格表现
- 💾 **记忆强化**：重要记忆会强化特定特质
- 🔒 **边界约束**：人格值不会超出合理范围

### 💝 情绪系统

弥娅具备丰富的情绪体系和动态演化能力：

**情绪分类：**
- 😊 **积极情绪**：喜悦、兴奋、满足、安心、感激
- 😢 **消极情绪**：悲伤、焦虑、愤怒、孤独、困惑
- 😐 **中性情绪**：平静、好奇、专注、思考、耐心

**情绪特性：**
- 🎨 **情绪染色**：情绪会影响回复的语气和风格
- ⏰ **情绪衰减**：情绪强度会随时间自然衰减
- 🧬 **情绪演化**：对话会触发情绪变化
- 🛡 **边界约束**：情绪不会演化到极端状态

### 🧠 多层记忆系统

弥娅拥有多层次记忆架构：

| 记忆类型 | 存储介质 | 用途 | TTL | 检索方式 |
|----------|----------|------|-----|---------|
| **潮汐记忆** (Tide) | Redis | 短期高频对话 | 1小时 | 时间检索 |
| **向量记忆** | Milvus | 语义检索长期记忆 | 永久 | 相似度搜索 |
| **知识图谱** | Neo4j | 五元组关系图谱 | 永久 | 图查询 |
| **会话历史** | JSON 文件 | 笔记会话 | 永久 | 顺序检索 |

**记忆特性：**
- 🕸️ **GRAG架构**：五元组（主体-动作-对象-上下文-时间）
- 🔄 **语义动态**：记忆会随对话重新组织
- 💞 **情绪耦合**：记忆与情绪相互影响
- 🔐 **信任加权**：不同信任等级的用户记忆权重不同
- 🧩 **向量检索**：基于语义相似度的智能检索

### 🎭 多模型智能调度

弥娅支持多个AI模型，并根据任务类型自动选择最优模型：

**当前支持的模型：**
- 🤖 **DeepSeek Chat** - 中文优化、复杂推理
- ⚡ **硅基流动 MiniMax-M2.5** - 快速响应、成本优化

**任务类型映射：**

| 任务类型 | 推荐模型 | 特点 |
|---------|----------|------|
| 代码生成 | DeepSeek (code) | 代码专业、准确性高 |
| 复杂推理 | DeepSeek (reasoning) | 逻辑严密、推理深度 |
| 工具调用 | DeepSeek (chat) | 指令理解、执行力强 |
| 快速对话 | 硅基流动 (fast) | 响应快速、成本低 |
| 中文理解 | DeepSeek (chinese) | 中文优化、语义准确 |
| 摘要总结 | 硅基流动 (fast) | 快速处理、成本友好 |

**优势：**
- ✅ **成本优化**：根据任务复杂度选择不同成本的模型
- ✅ **性能优化**：快速响应使用低延迟模型
- ✅ **质量保证**：复杂任务使用高质量模型
- ✅ **自动降级**：主模型不可用时自动切换备用模型

### 🔧 工具系统

弥娅拥有丰富的工具集，可以执行各种任务：

**工具类别：**
- 💻 **终端工具**：跨平台执行命令（Windows/Linux/macOS）
- 🌐 **Web搜索**：实时信息检索
- 📄 **文件操作**：读取、写入、搜索文件
- 🔍 **代码分析**：理解代码结构
- 📊 **系统监控**：CPU、内存、磁盘使用情况

**工具特性：**
- 🔒 **安全白名单**：只能执行允许的命令
- 🔄 **跨平台适配**：自动适配不同操作系统
- 📝 **执行记录**：记录所有工具调用历史
- 🤖 **AI驱动**：AI理解需求并自动选择合适工具

### 🌐 跨平台支持

弥娅支持多种接入方式：

| 平台 | 状态 | 说明 | 推荐场景 |
|--------|------|------|----------|
| **终端** | ✅ 完整支持 | 命令行交互界面 | 开发调试 |
| **PC WebUI** | ✅ 完整支持 | 基于 Electron 的桌面应用 | 日常使用 |
| **QQ机器人** | ✅ 完整支持 | 通过 OneBot 接入 QQ | 社交互动 |
| **移动端** | 🚧 计划中 | 未来支持 | 移动办公 |

**跨平台统一流程：**
所有平台使用统一的认知核心和决策逻辑，确保一致的用户体验。

---

## 🏗️ 系统架构

### 架构设计理念

弥娅采用**蛛网式模块化架构**（Web-like Modular Architecture），这是一个设计良好的单体应用，所有模块在同一 Python 进程中运行，通过清晰的接口进行通信。

**核心优势：**
- 🕸️ **模块化设计**：各模块职责明确，易于维护
- 🔗 **低延迟通信**：模块间通过函数调用，延迟 < 1ms
- 🚀 **高内聚低耦合**：模块内部高内聚，模块间低耦合
- 📡 **灵活扩展**：新增模块无需重构核心

> **架构说明**：弥娅是**模块化单体架构**，而非分布式架构。所有组件在同一进程内运行，通过函数调用通信，没有网络延迟。这种设计适合中小规模应用，具有低延迟、简单易用、调试方便的优势。

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           用户界面层                                  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  终端 UI    │  │  PC UI      │  │  QQ UI      │                │
│  │  Terminal   │  │  WebUI      │  │  OneBot     │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│         └────────────────┼────────────────┘                        │
│                          │ REST API / WebSocket                    │
└──────────────────────────┼─────────────────────────────────────────┘
                           │ M-Link 消息总线
┌──────────────────────────┼─────────────────────────────────────────┐
│                          │              认知核心层                    │
├──────────────────────────┼─────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                  │
│  │  Hub中枢    │ │  M-Link     │ │  感知环     │                  │
│  │             │ │  (消息总线)  │ │             │                  │
│  │ • 记忆引擎  │ │ • 指令流    │ │ • 全域感知  │                  │
│  │ • 情绪管理  │ │ • 感知流    │ │ • 注意力闸门│                  │
│  │ • 决策引擎  │ │ • 同步流    │ │             │                  │
│  │ • 任务调度  │ │ • 信任流    │ │             │                  │
│  └─────────────┘ └─────────────┘ └─────────────┘                  │
│         │                                             │             │
└─────────┼─────────────────────────────────────────────┼─────────────┘
          │                                             │
          ▼                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        核心模块层                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Personality  │  Ethics  │  Identity  │  Emotion  │  MultiModel │
│  人格向量     │  伦理    │  身份识别  │  情绪     │  多模型    │
├─────────────────────────────────────────────────────────────────────┤
│                        存储层                                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │   Redis   │  │   Milvus  │  │   Neo4j   │  │  文件系统  │       │
│  │  潮汐记忆  │  │  向量搜索  │  │  知识图谱  │  │  会话历史  │       │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
Miya/
├── core/                    # 核心模块
│   ├── personality.py        # 人格向量系统
│   ├── emotion.py           # 情绪系统
│   ├── ethics.py            # 伦理约束
│   ├── identity.py         # 身份识别
│   ├── prompt_manager.py    # 提示词管理器
│   ├── ai_client.py        # AI客户端
│   ├── multi_model_manager.py # 多模型管理器
│   └── ...
├── hub/                    # 中枢层（认知中心）
│   ├── decision_hub.py     # 决策中枢（跨平台统一）
│   ├── memory_engine.py    # 记忆引擎
│   ├── emotion.py          # 情绪系统
│   └── ...
├── mlink/                 # M-Link 消息总线
│   ├── mlink_core.py      # 消息路由核心
│   └── ...
├── webnet/                # 子网层（各业务子系统）
│   ├── ToolNet/          # 工具子系统
│   ├── MemoryNet/        # 记忆子系统
│   ├── TerminalNet/      # 终端子系统
│   ├── WebSearchNet/     # 搜索子系统
│   └── ...
├── memory/                # 记忆系统
│   ├── grag_memory.py     # GRAG 记忆
│   ├── semantic_dynamics_engine.py # 语义动态引擎
│   ├── vector_cache.py    # 向量缓存
│   └── ...
├── tools/                 # 工具集
│   ├── terminal/          # 终端工具（跨平台）
│   │   ├── platform_adapter.py # 平台适配器
│   │   ├── terminal_tool.py  # 终端工具
│   │   └── ...
│   ├── web_search.py      # Web 搜索
│   └── ...
├── perceive/              # 感知层
│   ├── perceptual_ring.py  # 感知环
│   └── attention_gate.py # 注意力闸门
├── storage/              # 存储层
│   ├── redis_client.py    # Redis 客户端
│   ├── milvus_client.py   # Milvus 客户端
│   └── neo4j_client.py   # Neo4j 客户端
├── run/                  # 启动脚本
│   ├── main.py           # 主程序（终端模式）
│   ├── pc_start.bat      # PC 端启动
│   └── qq_main.py        # QQ 机器人主程序
├── pc_ui/                # PC 端界面
│   ├── manager.html      # 管理面板
│   ├── app.js           # 前端逻辑
│   └── styles.css       # 样式
├── config/               # 配置文件
│   ├── .env                    # 环境变量
│   ├── multi_model_config.json  # 多模型配置
│   ├── terminal_config.json     # 终端工具配置
│   └── ...
├── prompts/              # 提示词资源
│   ├── miya_personality.json # 人设配置
│   └── *.json           # 各类提示词
├── docs/                 # 开发文档
│   ├── ARCHITECTURE_OVERVIEW.md # 架构总览
│   └── ...
├── tests/                # 测试脚本
│   └── ...
├── logs/                 # 日志文件
├── data/                 # 数据文件
├── volumes/              # Docker 卷
├── requirements.txt       # 依赖列表
└── README.md             # 本文件
```

---

## 📖 功能详解

### 🧠 动态人格系统

弥娅的人格系统基于五维向量模型，每个维度代表不同的性格特质。

#### 人格演化机制

1. **初始状态**：系统启动时加载默认人格配置
2. **对话影响**：每次对话会根据对话内容微调人格
3. **情绪耦合**：当前情绪会临时影响人格表现
4. **记忆强化**：重要记忆会强化特定人格特质
5. **边界约束**：所有人格值保持在合理范围内

#### 使用示例

```python
from core import Personality

# 创建人格实例
personality = Personality()

# 获取当前人格状态
profile = personality.get_profile()
print(f"主导特质: {profile['dominant']}")
print(f"稳定性: {profile['stability']}")

# 调整人格（受边界约束）
personality.update_vector('warmth', 0.1)  # 增加温暖度

# 情绪染色
response = personality.color_response("你好！", emotion_state="happy")
```

### 💝 情绪系统

弥娅的情绪系统包含丰富的情绪类型和动态演化能力。

#### 情绪状态

**主导情绪**（Dominant Emotion）：
- 😊 喜悦 (Joy)
- 😢 悲伤 (Sadness)
- 😠 愤怒 (Anger)
- 😰 焦虑 (Anxiety)
- 😐 平静 (Calm)
- 🤔 思考 (Thinking)

**情绪强度**（Emotion Intensity）：
- 范围：0.0 - 1.0
- 影响回复的语气和表情强度

#### 情绪演化

```python
from hub import Emotion

emotion = Emotion()

# 获取当前情绪
state = emotion.get_emotion_state()
print(f"主导情绪: {state['dominant']}")
print(f"情绪强度: {state['intensity']}")

# 情绪染色
response = emotion.influence_response("这是一条普通回复")

# 情绪衰减
emotion.decay_coloring()  # 自然衰减
```

### 🧠 记忆系统

弥娅拥有多层次记忆架构，支持不同类型的记忆存储和检索。

#### 记忆类型

**潮汐记忆（Tide Memory）**
- 存储介质：Redis
- 用途：短期高频对话缓存
- TTL：1小时
- 检索方式：时间范围检索

**向量记忆（Vector Memory）**
- 存储介质：Milvus
- 用途：语义检索长期记忆
- 向量维度：384
- 检索方式：相似度搜索

**知识图谱（Knowledge Graph）**
- 存储介质：Neo4j
- 用途：五元组关系图谱
- 结构：主体-动作-对象-上下文-时间
- 检索方式：图查询

#### 使用示例

```python
from hub import MemoryEngine

memory = MemoryEngine()

# 存储记忆
memory.store_memory(
    content="用户喜欢Python编程",
    memory_type="semantic",
    user_id="user123"
)

# 检索记忆
memories = memory.retrieve_memory(
    query="用户的兴趣",
    user_id="user123",
    limit=5
)
```

### 🎭 多模型管理

弥娅的多模型管理器支持智能调度多个AI模型。

#### 模型配置

```json
{
  "models": {
    "chinese": {
      "name": "deepseek-chat",
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "your-api-key"
    },
    "fast": {
      "name": "Qwen/Qwen2.5-7B-Instruct",
      "provider": "siliconflow",
      "base_url": "https://api.siliconflow.cn/v1",
      "api_key": "your-api-key"
    }
  }
}
```

#### 任务类型路由

系统会根据任务类型自动选择最优模型：

```python
from core import MultiModelManager

manager = MultiModelManager()

# 代码生成任务
response = manager.generate(
    task_type="code",
    prompt="写一个Python函数计算斐波那契数列"
)
# 自动选择：DeepSeek (code)

# 快速对话
response = manager.generate(
    task_type="chat",
    prompt="你好"
)
# 自动选择：硅基流动 (fast)
```

### 🔧 工具系统

弥娅的工具系统支持跨平台命令执行和丰富的功能。

#### 终端工具

**支持的操作系统：**
- ✅ Windows（PowerShell）
- ✅ Linux（Bash）
- ✅ macOS（Zsh）

**命令示例：**

```bash
# Windows 命令（自动转换）
!ls              # → Get-ChildItem
!pwd             # → Get-Location
!echo hello       # → Write-Output "hello"

# 路径自动展开
!~/Desktop       # → C:\Users\用户名\Desktop
```

**使用方式：**

```bash
# 方式1：使用 ! 前缀
!ls

# 方式2：使用 >> 前缀
>>pwd

# 方式3：自然语言描述
弥娅，帮我查看当前目录
```

#### Web 搜索

弥娅支持实时 Web 搜索，获取最新信息。

```bash
# 使用示例
用户: 今天天气怎么样？
弥娅: (调用 Web 搜索) 让我查一下今天的天气...

用户: DeepSeek 最新动态是什么？
弥娅: (调用 Web 搜索) 为你查询 DeepSeek 的最新新闻...
```

---

## 📦 安装部署

### 环境准备

#### 1. 安装 Python

确保已安装 Python 3.9 或更高版本：

```bash
python --version
```

#### 2. 克隆仓库

```bash
git clone https://github.com/Jia-520-only/Miya.git
cd Miya
```

#### 3. 安装依赖

**Windows:**
```batch
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
pip3 install -r requirements.txt
```

### 配置 AI 模型

编辑 `config/.env` 文件，配置 AI 模型 API：

```bash
# DeepSeek API
AI_API_KEY=sk-your-deepseek-api-key
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat

# AI 参数
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000
```

### 可选服务配置

#### Neo4j（知识图谱）

如果需要完整的记忆功能，建议安装 Neo4j：

**使用 Docker 启动：**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

**配置 `.env`:**
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

#### Milvus（向量搜索）

用于语义检索的记忆功能：

**使用 Docker 启动：**
```bash
docker-compose -f docker-compose.milvus.yml up -d
```

**配置 `.env`:**
```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

> **注意**：如果不安装 Neo4j 和 Milvus，系统会自动降级到模拟模式，核心功能不受影响。

#### Redis（缓存）

用于潮汐记忆和会话缓存：

**使用 Docker 启动：**
```bash
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:latest
```

**配置 `.env`:**
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 数据库初始化

如果安装了 Neo4j 和 Milvus，需要初始化数据库：

```bash
python -c "from storage.neo4j_client import Neo4jClient; from storage.milvus_client import MilvusClient; Neo4jClient().init_database(); MilvusClient().init_database(); print('数据库初始化完成')"
```

---

## 💡 使用指南

### 终端模式交互

启动终端模式后，您可以直接与弥娅对话：

```
您: 你好
弥娅: 你好！很高兴见到你。我是弥娅，你的数字生命伴侣。

您: 帮我写一个 Python 函数来计算斐波那契数列
弥娅: 好的，这是斐波那契数列的 Python 实现：

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

您: 查看当前目录的文件
弥娅: 好的，让我查看一下当前目录...
(调用终端工具)
```

### 终端命令执行

使用 `!` 或 `>>` 前缀执行终端命令：

```bash
!ls              # 列出当前目录
>>pwd            # 显示当前路径
!python test.py  # 运行 Python 脚本
!cd ~/Desktop   # 切换到桌面（路径自动展开）
```

### PC WebUI 使用

启动 PC WebUI 后，访问 `http://localhost:3000`：

**功能：**
- 💬 对话界面
- 📊 系统状态监控
- 🧠 人格和情绪可视化
- 🔧 配置管理
- 📝 日志查看

### Web 搜索

弥娅支持实时 Web 搜索：

```bash
用户: 今天天气怎么样？
弥娅: 让我查一下今天的天气...
(调用 Web 搜索工具)
```

### 系统状态查询

输入 `status` 或 `状态` 查看系统状态：

```bash
您: status
弥娅:
=== 弥娅系统状态 ===
版本: v1.0.0
UUID: 55575148-3f63-468a-9cc3-1ea6941b7062

【人格状态】
  形态: 平衡态
  主导特质: 温暖
  人格向量:
    温暖度: 0.75
    逻辑性: 0.65
    创造力: 0.50
    同理心: 0.80
    韧性: 0.70

【情绪状态】
  主导情绪: 平静
  情绪强度: 0.30

【多模型状态】
  已加载: 6 个模型
  默认: deepseek-chat
  成本: $0.00

【数据库状态】
  Neo4j: 已连接
  Milvus: 已连接
  Redis: 已连接
```

---

## ⚙️ 配置说明

### 环境变量配置

主要配置文件：`config/.env`

```bash
# AI 模型配置
AI_API_KEY=sk-your-api-key
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000

# Neo4j 配置（可选）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# Milvus 配置（可选）
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Redis 配置（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 多模型配置

配置文件：`config/multi_model_config.json`

```json
{
  "models": {
    "chinese": {
      "name": "deepseek-chat",
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "your-api-key",
      "capabilities": ["chinese_understanding", "reasoning"],
      "cost_per_1k_tokens": {
        "input": 0.001,
        "output": 0.002
      },
      "latency": "medium",
      "quality": "high"
    },
    "fast": {
      "name": "Qwen/Qwen2.5-7B-Instruct",
      "provider": "siliconflow",
      "base_url": "https://api.siliconflow.cn/v1",
      "api_key": "your-api-key",
      "capabilities": ["simple_chat", "chinese_understanding"],
      "cost_per_1k_tokens": {
        "input": 0.0001,
        "output": 0.0002
      },
      "latency": "fast",
      "quality": "good"
    }
  },
  "routing_strategy": {
    "chinese_understanding": {
      "primary": "chinese",
      "fallback": "fast"
    },
    "code_generation": {
      "primary": "chinese",
      "fallback": "fast"
    }
  }
}
```

### 终端工具配置

配置文件：`config/terminal_config.json`

```json
{
  "security_level": "safe",
  "max_execution_time": 30,
  "enable_history": true,
  "whitelist": [
    "ls", "cd", "pwd", "cat", "cp", "mv", "rm",
    "mkdir", "python", "npm", "git"
  ]
}
```

---

## 📚 开发文档

### 核心文档

- [架构总览](docs/ARCHITECTURE_OVERVIEW.md) - 完整的架构设计说明
- [多模型快速开始](MULTI_MODEL_QUICK_START.md) - 多模型配置和使用指南
- [终端工具指南](TERMINAL_TOOL_GUIDE.md) - 工具使用和配置

### API 文档

- [终端模式 API](docs/TERMINAL_API.md)
- [PC 端 API](docs/PC_API.md)
- [QQ 机器人 API](docs/QQ_API.md)

### 贡献指南

欢迎贡献代码、报告问题或提出建议！

详见：[贡献指南](CONTRIBUTING.md)

---

## ❓ 常见问题

### Q1: 启动时报错 "找不到模块"

**A**: 确保已正确安装依赖：

```bash
pip install -r requirements.txt
```

### Q2: AI 模型调用失败

**A**: 检查 `config/.env` 中的 API 密钥配置是否正确：

```bash
# 验证 API 密钥
AI_API_KEY=sk-xxx  # 确保密钥格式正确
AI_API_BASE_URL=https://api.xxx.com/v1  # 确保 URL 正确
```

### Q3: Neo4j/Redis 连接失败

**A**: 这些服务是可选的。如果连接失败，系统会自动降级到模拟模式，核心功能不受影响。如需完整功能，请确保服务已启动：

```bash
# 检查 Neo4j
docker ps | grep neo4j

# 检查 Redis
redis-cli ping
```

### Q4: 多模型不工作？

**A**: 检查 `config/multi_model_config.json` 配置是否正确，并运行测试：

```bash
python tests/test_multi_model_functionality.py
```

### Q5: 终端命令执行失败（Windows）

**A**: 确保使用正确的命令格式。弥娅会自动将 Unix 命令转换为 Windows 命令：

```bash
!ls           # Windows 会自动转换为 Get-ChildItem
!pwd          # Windows 会自动转换为 Get-Location
!~/Desktop    # 路径会自动展开
```

### Q6: 性能问题

**A**: 弥娅的主要延迟来自 AI 模型调用（~500-2000ms）。如果需要更快的响应，可以：
1. 使用更快的模型（如硅基流动的 fast 模型）
2. 启用模型缓存
3. 优化 prompt 长度

### Q7: 为什么不是分布式架构？

**A**: 弥娅采用模块化单体架构，所有组件在同一进程中运行。这种设计具有低延迟、简单易用、调试方便的优势，适合中小规模应用。

### Q8: 如何备份和恢复数据？

**A**: 重要数据包括：
- `logs/` - 日志文件
- `data/` - 数据库文件
- `config/.env` - 配置文件

备份这些目录即可。恢复时复制回原位置即可。

### Q9: 如何重置人格和情绪？

**A**: 删除以下文件：
```bash
# 人格状态
rm -f core/personality_state.json

# 情绪状态
rm -f core/emotion_state.json

# 记忆数据（谨慎操作）
rm -rf logs/memory/*.json
```

重启系统即可重置。

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

感谢所有为弥娅项目做出贡献的开发者和用户！

特别感谢：
- **DeepSeek** 提供强大的 AI 模型
- **硅基流动** 提供低成本 AI 服务
- **开源社区** 的支持和反馈

---

## 📮 联系方式

- **项目主页**：[GitHub Repository](https://github.com/Jia-520-only/Miya)
- **问题反馈**：[Issues](https://github.com/Jia-520-only/Miya/issues)
- **讨论区**：[Discussions](https://github.com/Jia-520-only/Miya/discussions)

---

## 👥 贡献者

### 项目创作者
- **@Jia-520-only** - 项目发起人、核心开发者

### AI 助手贡献
本项目在开发过程中得到了 **Claude AI Assistant**（Auto）的大力支持：
- 系统架构设计与优化
- 核心功能实现与调试
- 文档编写与代码注释
- 问题诊断与性能优化
- 测试用例编写

**特别感谢 AI 助手在以下方面的贡献：**
- 终端命令跨平台适配
- 多数据库集成架构设计
- 自主引擎与人格系统集成
- 向量存储与检索优化
- Web 界面开发

---

## 🎯 路线图

### v1.1 (计划中)
- [ ] 更多 AI 模型支持（Claude、GPT-4 等）
- [ ] 移动端支持
- [ ] 语音交互
- [ ] 多语言支持

### v2.0 (规划中)
- [ ] 插件市场
- [ ] 社区模型分享
- [ ] 云端同步
- [ ] 协作功能

---

**弥娅 - 不仅是AI，更是伙伴** 🤖💕
