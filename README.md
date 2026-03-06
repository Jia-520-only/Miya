# 弥娅 (Miya) - 数字生命伴侣

[![Version](https://img.shields.io/badge/version-5.2-blue.svg)](https://github.com/your-repo/miya)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> *"不仅是AI，更是伙伴"* — 弥娅 v5.2

弥娅（Miya）是一个基于**蛛网式模块化架构**的数字生命伴侣系统，具备动态人格、情感演化、记忆管理、多模型智能调度、多端接入等核心能力。

---

## 📖 目录

- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [安装部署](#安装部署)
- [使用指南](#使用指南)
- [多模型配置](#多模型配置)
- [开发文档](#开发文档)
- [常见问题](#常见问题)

---

## 🚀 快速开始

### 最低要求

- **操作系统**: Windows 10+ / Linux / macOS
- **Python**: 3.9 或更高版本
- **内存**: 建议 4GB+
- **存储**: 建议 10GB+
- **网络**: 需要访问AI模型API（DeepSeek、硅基流动等）

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

### 启动系统

**终端模式（命令行交互）:**
```batch
start.bat        # Windows
./start.sh        # Linux/macOS
```

**PC 端模式（推荐）:**
```batch
run/pc_start.bat  # Windows
run/pc_start.sh   # Linux/macOS
```

**QQ 机器人模式:**

⚠️ **注意：QQ机器人需要OneBot服务支持**

启动前需要：
1. 安装OneBot实现（推荐 NapCat 或 go-cqhttp）
2. 配置 `config/.env` 中的QQ相关设置
3. 启动OneBot服务

详细配置请参考：[QQ机器人配置指南](docs/QQ_BOT_SETUP.md)

```batch
run/qq_start.bat  # Windows
run/qq_start.sh   # Linux/macOS
```

### 首次运行

系统首次启动会自动：
1. 创建虚拟环境
2. 安装依赖包（约140+个）
3. 初始化配置文件
4. 生成唯一 UUID
5. 创建数据目录

---

## 🏗️ 系统架构

### 架构设计理念

弥娅采用**蛛网式模块化架构**（Web-like Modular Architecture），这是一个设计良好的单体应用，所有模块在同一Python进程中运行，通过清晰的接口进行通信。

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
│  Personality  │  Ethics  │  Identity  │  Entropy  │  PromptManager │
│  人格向量     │  伦理    │  身份识别  │  熵监控   │  提示词管理    │
├─────────────────────────────────────────────────────────────────────┤
│                      多模型管理层 (NEW)                              │
├─────────────────────────────────────────────────────────────────────┤
│  MultiModelManager  │  DeepSeek  │  硅基流动  │  (可扩展)          │
│  智能模型调度       │  AI客户端   │  AI客户端   │  ...               │
├─────────────────────────────────────────────────────────────────────┤
│                        存储层                                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │   Redis   │  │   Milvus  │  │   Neo4j   │  │  文件系统  │       │
│  │  潮汐记忆  │  │  向量搜索  │  │  知识图谱  │  │  笔记会话  │       │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
Miya/
├── core/              # 核心模块
│   ├── personality.py      # 人格向量系统
│   ├── ethics.py           # 伦理约束
│   ├── identity.py         # 身份识别
│   ├── arbitrator.py       # 仲裁器
│   ├── entropy.py          # 熵监控
│   ├── prompt_manager.py   # 提示词管理器
│   ├── ai_client.py        # AI客户端
│   ├── multi_model_manager.py  # 多模型管理器（NEW）
│   └── ...
├── hub/               # 中枢层（认知中心）
│   ├── decision_hub.py     # 决策中枢（跨平台统一）
│   ├── memory_engine.py    # 记忆引擎
│   ├── emotion.py          # 情绪系统
│   ├── decision.py         # 决策引擎
│   ├── scheduler.py        # 任务调度
│   └── ...
├── mlink/             # M-Link消息总线
│   ├── mlink_core.py       # 消息路由核心
│   ├── message.py          # 消息格式
│   └── ...
├── webnet/            # 子网层（各业务子系统）
│   ├── ToolNet/            # 工具子系统
│   │   ├── registry.py     # 工具注册表
│   │   ├── tools/          # 各种工具
│   │   └── ...
│   ├── memory/             # 记忆子系统
│   ├── QQNet/              # QQ机器人子系统
│   ├── pc_ui.py            # PC端子系统
│   └── ...
├── perceive/          # 感知层
│   ├── perceptual_ring.py  # 感知环
│   └── attention_gate.py   # 注意力闸门
├── memory/            # 记忆系统
│   ├── grag_memory.py     # GRAG记忆
│   ├── semantic_dynamics_engine.py  # 语义动态引擎
│   └── ...
├── detect/            # 检测层
│   ├── time_detector.py   # 时间检测
│   ├── space_detector.py  # 空间检测
│   └── ...
├── trust/             # 信任系统
│   ├── trust_score.py     # 信任评分
│   └── ...
├── evolve/            # 演化层
│   ├── sandbox.py         # 沙盒环境
│   └── ab_test.py         # A/B测试
├── storage/           # 存储层
│   ├── redis_client.py    # Redis客户端
│   ├── milvus_client.py   # Milvus客户端
│   └── neo4j_client.py    # Neo4j客户端
├── tools/             # 工具集
│   ├── terminal/          # 终端工具（跨平台）
│   ├── web_search.py      # Web搜索（NEW）
│   └── ...
├── run/               # 启动脚本
│   ├── main.py             # 主程序（终端模式）
│   ├── pc_start.bat        # PC端启动
│   └── qq_main.py          # QQ机器人主程序
├── pc_ui/             # PC端界面
│   ├── manager.html        # 管理面板
│   ├── app.js              # 前端逻辑
│   └── styles.css          # 样式
├── config/            # 配置文件
│   ├── .env                # 环境变量
│   ├── multi_model_config.json  # 多模型配置（NEW）
│   ├── terminal_config.json     # 终端工具配置
│   └── ...
├── prompts/           # 提示词资源
│   ├── README.md           # 提示词使用指南
│   └── *.json              # 配置文件
├── docs/              # 开发文档
│   ├── ARCHITECTURE_OVERVIEW.md  # 架构总览
│   ├── MULTI_MODEL_QUICK_START.md # 多模型快速开始
│   └── ...
├── tests/             # 测试脚本
│   └── test_multi_model_functionality.py  # 多模型测试
├── logs/              # 日志文件
├── data/              # 数据文件
├── venv/              # 虚拟环境
├── requirements.txt   # 依赖列表
└── README.md          # 本文件
```

---

## ⭐ 核心功能

### 1. 动态人格系统 (Personality)

弥娅拥有五维人格向量，会根据对话动态演化：

| 维度 | 说明 | 取值范围 | 描述 |
|------|------|---------|------|
| 温暖度 (warmth) | 友善程度 | 0.3 - 1.0 | 冷静 ↔ 热情 |
| 逻辑性 (logic) | 理性程度 | 0.4 - 0.9 | 情感 ↔ 逻辑 |
| 创造力 (creativity) | 创新能力 | 0.0 - 1.0 | 务实 ↔ 创新 |
| 同理心 (empathy) | 理解能力 | 0.0 - 1.0 | 独立 ↔ 共情 |
| 韧性 (resilience) | 抗压能力 | 0.0 - 1.0 | 脆弱 ↔ 坚韧 |

**特性：**
- 边界约束：人格值不会超出合理范围
- 动态演化：对话会微调人格数值
- 情绪影响：当前情绪会临时影响人格表现
- 记忆强化：重要记忆会强化特定特质

**示例代码：**
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
```

### 2. 情绪系统 (Emotion)

弥娅具备丰富的情绪体系和动态演化能力：

**情绪类型：**
- 积极情绪：喜悦、兴奋、满足、安心、感激
- 消极情绪：悲伤、焦虑、愤怒、孤独、困惑
- 中性情绪：平静、好奇、专注、思考、耐心

**情绪特性：**
- **情绪染色**：情绪会影响回复的语气和风格
- **情绪衰减**：情绪强度会随时间自然衰减
- **情绪演化**：对话会触发情绪变化
- **边界约束**：情绪不会演化到极端状态

**示例代码：**
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

### 3. 记忆系统 (Memory Engine)

弥娅拥有多层次记忆架构：

| 记忆类型 | 存储介质 | 用途 | TTL |
|---------|---------|------|-----|
| 潮汐记忆 (Tide) | Redis | 短期高频对话 | 1小时 |
| 向量记忆 | Milvus | 语义检索长期记忆 | 永久 |
| 知识图谱 | Neo4j | 五元组关系图谱 | 永久 |
| 元思维链 | JSON | 思考过程记录 | 永久 |

**记忆特性：**
- **GRAG架构**：五元组（主体-动作-对象-上下文-时间）
- **语义动态**：记忆会随对话重新组织
- **情绪耦合**：记忆与情绪相互影响
- **信任加权**：不同信任等级的用户记忆权重不同

**示例代码：**
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

### 4. 多模型智能调度 (Multi-Model Management) 🆕

弥娅支持多个AI模型，并根据任务类型自动选择最优模型：

**当前支持的模型：**
- DeepSeek Chat - 中文优化、复杂推理
- 硅基流动 MiniMax-M2.5 - 快速响应、成本优化

**任务类型映射：**
- 代码生成 → DeepSeek (code模型)
- 复杂推理 → DeepSeek (reasoning模型)
- 工具调用 → DeepSeek (chat模型)
- 快速对话 → 硅基流动 (fast模型)
- 中文理解 → DeepSeek (chinese模型)
- 摘要总结 → 硅基流动 (fast模型)

**优势：**
- ✅ 成本优化：根据任务复杂度选择不同成本的模型
- ✅ 性能优化：快速响应使用低延迟模型
- ✅ 质量保证：复杂任务使用高质量模型
- ✅ 自动降级：主模型不可用时自动切换备用模型

**配置示例：**
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
      "name": "siliconflow",
      "provider": "openai",
      "base_url": "https://api.siliconflow.cn/v1",
      "api_key": "your-api-key"
    }
  }
}
```

详见：[多模型配置指南](#多模型配置)

### 5. 工具系统 (ToolNet)

弥娅拥有丰富的工具集，可以执行各种任务：

**工具类别：**
- **终端工具**：跨平台执行命令（Windows/Linux/macOS）
- **Web搜索**：实时信息检索
- **文件操作**：读取、写入、搜索文件
- **代码分析**：理解代码结构
- **系统监控**：CPU、内存、磁盘使用情况

**工具特性：**
- 🔒 安全白名单：只能执行允许的命令
- 🔄 跨平台适配：自动适配不同操作系统
- 📝 执行记录：记录所有工具调用历史
- 🤖 AI驱动：AI理解需求并自动选择合适工具

**使用示例：**
```
用户: 帮我查看当前目录
弥娅: (自动调用终端工具执行ls命令)

用户: 搜索今天的新闻
弥娅: (自动调用Web搜索工具查询最新信息)

用户: 分析这个Python文件
弥娅: (自动调用代码分析工具)
```

### 6. 跨平台支持

弥娅支持多种接入方式：

| 平台 | 状态 | 说明 |
|------|------|------|
| 终端 | ✅ 完整支持 | 命令行交互界面 |
| PC WebUI | ✅ 完整支持 | 基于Electron的桌面应用 |
| QQ机器人 | ✅ 完整支持 | 通过OneBot接入QQ |
| 移动端 | 🚧 计划中 | 未来支持 |

**跨平台统一流程：**
所有平台使用统一的认知核心和决策逻辑，确保一致的用户体验。

---

## 📦 安装部署

### 环境准备

#### 1. 安装Python

确保已安装 Python 3.9 或更高版本：

```bash
python --version
```

#### 2. 安装依赖

**Windows:**
```batch
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
pip3 install -r requirements.txt
```

### 配置AI模型

编辑 `config/.env` 文件，配置AI模型API：

```bash
# DeepSeek API
AI_API_KEY=sk-your-deepseek-api-key
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat

# 或使用硅基流动
# AI_API_KEY=sk-your-siliconflow-api-key
# AI_API_BASE_URL=https://api.siliconflow.cn/v1
# AI_MODEL=Pro/MiniMaxAI/MiniMax-M2.5

# AI参数
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000
```

### 可选服务配置

#### Neo4j（知识图谱）

如果需要完整的记忆功能，建议安装Neo4j：

```bash
# 使用Docker启动Neo4j
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

配置 `.env`:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

#### Milvus（向量搜索）

用于语义检索的记忆功能：

```bash
# 使用Docker启动Milvus
docker-compose -f docker-compose.milvus.yml up -d
```

配置 `.env`:
```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

> **注意**：如果不安装Neo4j和Milvus，系统会自动降级到模拟模式，核心功能不受影响。

### 数据库初始化

如果安装了Neo4j和Milvus，需要初始化数据库：

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

您: 帮我写一个Python函数来计算斐波那契数列
弥娅: (使用code模型) 好的，这是斐波那契数列的Python实现：

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

您: 查看当前目录的文件
弥娅: (调用终端工具) 好的，让我查看一下当前目录...
```

### 终端命令执行

使用 `!` 或 `>>` 前缀执行终端命令：

```
!ls              # 列出当前目录
>>pwd            # 显示当前路径
!python test.py  # 运行Python脚本
```

### Web搜索

弥娅支持实时Web搜索：

```
用户: 今天天气怎么样？
弥娅: (调用Web搜索) 让我查一下今天的天气...
```

### 系统状态查询

输入 `status` 或 `状态` 查看系统状态：

```
您: status
弥娅:
=== 弥娅系统状态 ===
版本: v5.2
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
  当前情绪:
    平静: 0.70
    好奇: 0.30

【多模型状态】
  已加载: 6个模型
  默认: deepseek-chat
  成本: $0.00
```

---

## 🔧 多模型配置

### 配置文件位置

`config/multi_model_config.json`

### 添加新模型

编辑配置文件，添加新模型配置：

```json
{
  "models": {
    "your_model": {
      "name": "your-model-name",
      "provider": "openai",
      "base_url": "https://your-api-endpoint.com/v1",
      "api_key": "your-api-key",
      "capabilities": [
        "simple_chat",
        "chinese_understanding"
      ],
      "cost_per_1k_tokens": {
        "input": 0.001,
        "output": 0.002
      },
      "latency": "fast",
      "quality": "good"
    }
  },
  "routing_strategy": {
    "your_capability": {
      "primary": "your_model",
      "fallback": "chinese",
      "cost_priority": 0.5,
      "speed_priority": 0.8,
      "quality_priority": 0.9
    }
  }
}
```

### 测试多模型功能

运行测试脚本验证配置：

```bash
python tests/test_multi_model_functionality.py
```

### 支持的提供商

- `deepseek` - DeepSeek API
- `openai` - OpenAI兼容API（包括硅基流动等）
- 可轻松扩展其他提供商

详见：[多模型架构文档](MULTI_MODEL_QUICK_START.md)

---

## 📚 开发文档

### 核心文档

- [架构总览](docs/ARCHITECTURE_OVERVIEW.md) - 完整的架构设计说明
- [多模型快速开始](MULTI_MODEL_QUICK_START.md) - 多模型配置和使用指南
- [多模型架构说明](MULTI_MODEL_ORCHESTRATION.md) - 多模型管理器详解
- [工具系统指南](TERMINAL_TOOL_GUIDE.md) - 工具使用和配置

### API文档

- [终端模式API](docs/TERMINAL_API.md)
- [PC端API](docs/PC_API.md)
- [QQ机器人API](docs/QQ_API.md)

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

### Q2: AI模型调用失败

**A**: 检查 `config/.env` 中的API密钥配置是否正确：
```bash
# 验证API密钥
AI_API_KEY=sk-xxx  # 确保密钥格式正确
AI_API_BASE_URL=https://api.xxx.com/v1  # 确保URL正确
```

### Q3: Neo4j/Redis连接失败

**A**: 这些服务是可选的。如果连接失败，系统会自动降级到模拟模式，核心功能不受影响。如需完整功能，请确保服务已启动：
```bash
# 检查Neo4j
docker ps | grep neo4j

# 检查Redis
redis-cli ping
```

### Q4: 多模型不工作？

**A**: 检查 `config/multi_model_config.json` 配置是否正确，并运行测试：
```bash
python tests/test_multi_model_functionality.py
```

### Q5: 终端命令执行失败（Windows）

**A**: 确保使用正确的命令格式。弥娅会自动将Unix命令转换为Windows命令：
```
!ls           # Windows会自动转换为 Get-ChildItem
!pwd          # Windows会自动转换为 Get-Location
```

### Q6: 性能问题

**A**: 弥娅的主要延迟来自AI模型调用（~500-2000ms）。如果需要更快的响应，可以：
1. 使用更快的模型（如硅基流动的fast模型）
2. 启用模型缓存
3. 优化prompt长度

### Q7: 为什么不是分布式架构？

**A**: 弥娅采用模块化单体架构，所有组件在同一进程中运行。这种设计具有低延迟、简单易用、调试方便的优势，适合中小规模应用。详见：[架构澄清文档](ARCHITECTURE_CLARIFICATION.md)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

感谢所有为弥娅项目做出贡献的开发者和用户！

特别感谢：
- DeepSeek 提供强大的AI模型
- 硅基流动 提供低成本AI服务
- 所有开源社区的支持

---

## 📮 联系方式

- 项目主页：[GitHub Repository](https://github.com/your-repo/miya)
- 问题反馈：[Issues](https://github.com/your-repo/miya/issues)
- 讨论区：[Discussions](https://github.com/your-repo/miya/discussions)

---

## 🎯 路线图

### v5.3 (计划中)
- [ ] 更多AI模型支持（Claude、GPT-4等）
- [ ] 移动端支持
- [ ] 语音交互
- [ ] 多语言支持

### v6.0 (规划中)
- [ ] 插件市场
- [ ] 社区模型分享
- [ ] 云端同步
- [ ] 协作功能

---

**弥娅 - 不仅是AI，更是伙伴** 🤖💕
