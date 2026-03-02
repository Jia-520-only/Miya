# Miya - 数字生命伴侣

<div align="center">

![Version](https://img.shields.io/badge/version-5.2-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

*"不仅是AI，更是伙伴"* — Miya v5.2

[功能特性](#-核心功能) • [快速开始](#-快速开始) • [系统架构](#-系统架构) • [使用指南](#-使用指南) • [API文档](#-api文档)

</div>

---

## 📖 项目简介

**Miya (弥娅)** 是一个基于蛛网式分布式架构的数字生命伴侣系统。她具备动态人格、情感演化、多层次记忆管理、多端接入等核心能力，旨在成为真正能与人建立情感连接的AI伙伴。

### 核心亮点

- 🧠 **动态人格系统** - 五维人格向量，支持五种形态切换
- 💗 **情感演化引擎** - 丰富的情绪体系，情绪染色回复
- 📚 **GRAG记忆架构** - 五元组知识图谱，语义动态重组
- 🌐 **多端接入** - 支持命令行、PC端、QQ机器人等多种方式
- 🔗 **M-Link传输层** - 五流分发机制，蛛网式拓扑
- 🎭 **动态提示词** - 提示词与人格实时联动

---

## 🚀 快速开始

### 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 / Linux / macOS | Windows 11 / Ubuntu 22.04+ |
| Python | 3.9+ | 3.10+ |
| 内存 | 4GB | 8GB+ |
| 存储 | 5GB | 10GB+ |

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

**命令行模式:**
```batch
start.bat        # Windows
./start.sh        # Linux/macOS
```

**PC 端模式 (推荐):**
```batch
run/pc_start.bat  # Windows
run/pc_start.sh   # Linux/macOS
```

然后访问：`http://localhost:8000/manager`

**QQ 机器人模式:**

⚠️ 需要OneBot服务支持（推荐NapCat或go-cqhttp）

```batch
run/qq_start.bat  # Windows
run/qq_start.sh   # Linux/macOS
```

详细配置请参考：[QQ机器人配置指南](docs/QQ_BOT_SETUP.md)

---

## 🏗️ 系统架构

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  PC UI   │  │  QQ UI   │  │  CLI UI  │  │ (Future) │     │
│  │ Electron │  │  OneBot  │  │ Terminal │  │  Mobile  │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
└─────────────┬──────────────────────┬────────────────────────┘
              │                      │
              │ REST API / WebSocket │
              ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      认知核心层                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   Hub    │  │  M-Link  │  │ 感知环   │  │ 演化层   │      │
│  │          │  │  五流    │  │          │  │          │      │
│  │ • 记忆   │  │ • 指令   │  │ • 全域   │  │ • 沙盒   │      │
│  │ • 情绪   │  │ • 感知   │  │ • 注意   │  │ • A/B    │      │
│  │ • 决策   │  │ • 同步   │  │          │  │          │      │
│  │ • 调度   │  │ • 信任   │  │          │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└────┬───────────────────────────────────────┬──────────────────┘
     │                                       │
     ▼                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        核心模块层                                 │
├─────────────────────────────────────────────────────────────────┤
│  Personality  │  Ethics  │  Identity  │  Entropy  │  PromptMgr  │
│  人格向量      │  伦理    │  身份识别  │  熵监控   │  提示词管理  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         存储层                                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │  Redis  │  │  Milvus │  │  Neo4j  │  │ FileSys │          │
│  │ 潮汐记忆 │  │ 向量搜索 │  │ 知识图谱 │  │ 笔记    │          │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
Miya/
├── core/                  # 核心模块
│   ├── personality.py    # 人格向量系统（五维向量 + 五种形态）
│   ├── ethics.py         # 伦理约束
│   ├── identity.py       # 身份识别
│   ├── entropy.py        # 熵监控
│   ├── prompt_manager.py # 提示词管理器（动态联动人格）
│   └── agent_manager.py  # Agent管理
│
├── hub/                   # 中枢层
│   ├── memory_engine.py   # 记忆引擎
│   ├── emotion.py         # 情绪系统
│   ├── decision.py        # 决策引擎
│   └── scheduler.py       # 任务调度
│
├── mlink/                 # M-Link传输层（五流分发）
│   ├── mlink_core.py      # 传输核心
│   ├── message.py         # 消息格式
│   └── router.py          # 路由系统
│
├── perceive/              # 感知层
│   ├── perceptual_ring.py # 感知环
│   └── attention_gate.py  # 注意力闸门
│
├── webnet/                # 子网层
│   ├── pc_ui.py           # PC端子网
│   ├── qq.py              # QQ子网
│   ├── life.py            # 生活子网
│   └── work.py            # 工作子网
│
├── memory/                # 记忆系统
│   ├── grag_memory.py     # GRAG记忆（五元组）
│   ├── semantic_dynamics_engine.py # 语义动态引擎
│   └── quintuple_graph.py # 五元组图谱
│
├── detect/                # 检测层
│   ├── time_detector.py   # 时间检测
│   ├── space_detector.py  # 空间检测
│   └── entropy_diffusion.py # 熵扩散检测
│
├── trust/                 # 信任系统
│   ├── trust_score.py     # 信任评分
│   └── trust_propagation.py # 信任传播
│
├── evolve/                # 演化层
│   ├── sandbox.py         # 沙盒环境
│   ├── ab_test.py         # A/B测试
│   └── user_co_play.py    # 用户共创
│
├── storage/               # 存储层
│   ├── redis_client.py    # Redis客户端
│   ├── milvus_client.py   # Milvus客户端
│   └── neo4j_client.py    # Neo4j客户端
│
├── plugin/                # 插件系统
│   └── plugin_manager.py  # 插件管理器
│
├── run/                   # 启动脚本
│   ├── main.py            # 主程序
│   ├── pc_start.bat       # PC端启动
│   └── qq_start.bat       # QQ启动
│
├── pc_ui/                 # PC端界面
│   ├── manager.html       # 管理面板
│   ├── app.js             # 前端逻辑
│   └── styles.css         # 样式
│
├── config/                # 配置文件
│   ├── .env               # 环境变量
│   └── settings.py        # 设置管理
│
├── prompts/               # 提示词资源
│   ├── system_prompts.md  # 系统提示词库
│   └── *.json             # 配置文件
│
├── docs/                  # 开发文档
│   ├── ARCHITECTURE_PC.md # PC端架构
│   ├── ARCHITECTURE_QQ.md # QQ架构
│   └── DEPLOYMENT_GUIDE.md
│
├── logs/                  # 日志文件
├── data/                  # 数据文件
├── requirements.txt       # 依赖列表
└── README.md              # 本文件
```

---

## ⭐ 核心功能

### 1. 🧠 动态人格系统 (Personality)

Miya拥有**五维人格向量**，会根据对话动态演化，并支持**五种形态切换**：

#### 五维人格向量

| 维度 | 说明 | 取值范围 | 描述 |
|------|------|---------|------|
| 温暖度 (warmth) | 友善程度 | 0.3 - 1.0 | 冷静 ↔ 热情 |
| 逻辑性 (logic) | 理性程度 | 0.4 - 0.9 | 情感 ↔ 逻辑 |
| 创造力 (creativity) | 创新能力 | 0.0 - 1.0 | 务实 ↔ 创新 |
| 同理心 (empathy) | 理解能力 | 0.0 - 1.0 | 独立 ↔ 共情 |
| 韧性 (resilience) | 抗压能力 | 0.0 - 1.0 | 脆弱 ↔ 坚韧 |

#### 五种形态

| 形态 | 名称 | 描述 | 特点 |
|------|------|------|------|
| normal | 温存 | 慵懒温柔 | 平衡状态 |
| battle | 严律 | 高冷严厉 | 逻辑+，同理心- |
| muse | 灵感 | 知性沉静 | 逻辑+，创造力+ |
| singer | 欢愉 | 活泼喧闹 | 温暖度+，创造力+ |
| ghost | 幽灵 | 深邃神秘 | 同理心+，神秘感 |

#### 使用示例

```python
from core import Personality

# 创建人格实例
personality = Personality()

# 获取当前人格状态
profile = personality.get_profile()
print(f"主导特质: {profile['dominant']}")
print(f"当前形态: {personality.current_form}")

# 调整人格（受边界约束）
personality.update_vector('warmth', 0.1)  # 增加温暖度

# 切换形态
personality.switch_form('battle')  # 切换到战态
```

---

### 2. 💗 情绪系统 (Emotion)

Miya具备丰富的情绪体系和动态演化能力：

#### 情绪类型

- **积极情绪**：喜悦、兴奋、满足、安心、感激
- **消极情绪**：悲伤、焦虑、愤怒、孤独、困惑
- **中性情绪**：平静、好奇、专注、思考、耐心

#### 情绪特性

- **情绪染色**：情绪会影响回复的语气和风格
- **情绪衰减**：情绪强度会随时间自然衰减
- **情绪演化**：对话会触发情绪变化

#### 使用示例

```python
from hub import Emotion

emotion = Emotion()

# 获取当前情绪
state = emotion.get_emotion_state()
print(f"主导情绪: {state['dominant']}")
print(f"情绪强度: {state['intensity']}")

# 情绪染色
response = emotion.influence_response("这是一条普通回复")
```

---

### 3. 📚 记忆系统 (Memory Engine)

Miya拥有**多层次记忆架构**：

| 记忆类型 | 存储介质 | 用途 | TTL |
|---------|---------|------|-----|
| 潮汐记忆 (Tide) | Redis | 短期高频对话 | 1小时 |
| 向量记忆 | Milvus | 语义检索长期记忆 | 永久 |
| 知识图谱 | Neo4j | 五元组关系图谱 | 永久 |
| 元思维链 | JSON | 思考过程记录 | 永久 |

#### GRAG五元组架构

```
主体 (Subject) - 动作 (Action) - 对象 (Object) - 上下文 (Context) - 时间 (Time)
```

#### 记忆特性

- **GRAG架构**：五元组知识图谱
- **语义动态**：记忆会随对话重新组织
- **情绪耦合**：记忆与情绪相互影响

#### 使用示例

```python
from hub import MemoryEngine

memory = MemoryEngine()

# 存储记忆
memory.store(
    content="用户喜欢吃苹果",
    emotion_type="joy",
    tags=["preference", "food"]
)

# 检索记忆
results = memory.retrieve(
    query="用户的饮食偏好",
    limit=5
)
```

---

### 4. 🔗 M-Link 传输系统

M-Link是Miya的核心传输层，支持**五流分发**：

| 流类型 | 作用 | 方向 |
|-------|------|------|
| 指令流 (Control) | 内核/中枢 → 执行节点 | 下行 |
| 感知流 (Perception) | 感知层 → 中枢/子网 | 上行 |
| 同步流 (Sync) | 子网 ↔ 子网 | 横向 |
| 信任流 (Trust) | 信任评分与传播 | 双向 |
| 记忆流 (Memory) | 记忆读写请求 | 双向 |

#### 特性

- ✅ 动态路径评分
- ✅ 优先级通道
- ✅ 断链自愈

---

### 5. 🌐 多端接入

Miya支持多种接入方式：

| 接入方式 | 状态 | 说明 |
|---------|------|------|
| 命令行 | ✅ 已完成 | 基础交互模式 |
| PC端 | ✅ 已完成 | Electron + WebUI |
| QQ机器人 | ✅ 已完成 | OneBot协议 |
| 移动端 | 🚧 开发中 | Flutter |
| Web端 | 🚧 开发中 | 纯前端 |

---

### 6. 🎭 提示词管理 (Prompt Manager)

**重要特性**：提示词管理器已与人格模块**完全联动**，动态生成提示词。

#### 使用示例

```python
from core import Personality, PromptManager

# 创建人格实例
personality = Personality()

# 绑定人格到提示词管理器
prompt_manager = PromptManager(personality=personality)

# 获取动态提示词（自动包含人格状态）
system_prompt = prompt_manager.get_system_prompt()

# 构建完整提示词
full_prompt = prompt_manager.build_full_prompt(
    user_input="你好",
    memory_context=[...]
)
```

---

## 📦 安装部署

### 完整安装步骤

#### 1. 克隆代码

```bash
git clone https://github.com/your-repo/miya.git
cd miya
```

#### 2. 运行安装脚本

**Windows:**
```batch
install.bat
```

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

脚本会自动：
- ✅ 检查Python版本（需要3.9+）
- ✅ 创建虚拟环境（venv）
- ✅ 安装依赖包（requirements.txt）
- ✅ 初始化配置文件
- ✅ 创建必要目录

#### 3. 配置环境变量

编辑 `config/.env` 文件：

```env
# AI客户端配置
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
MODEL_NAME=gpt-4

# 提示词配置
USER_PROMPT_TEMPLATE=用户输入：{user_input}
ENABLE_MEMORY_CONTEXT=true
MEMORY_CONTEXT_MAX_COUNT=5

# 数据库配置（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
MILVUS_HOST=localhost
MILvUS_PORT=19530
NEO4J_URI=bolt://localhost:7687

# QQ机器人配置（可选）
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_BOT_QQ=你的机器人QQ号
QQ_ONEBOT_TOKEN=your_token_here
```

#### 4. 启动数据库（可选）

如果使用完整功能，需要启动以下服务：

```bash
# Docker Compose 方式
docker-compose up -d

# 或分别启动
redis-server
milvus run standalone
neo4j start
```

#### 5. 启动Miya

**命令行模式：**
```batch
start.bat        # Windows
./start.sh        # Linux/macOS
```

**PC端管理面板：**
```batch
run/pc_start.bat  # Windows
run/pc_start.sh   # Linux/macOS
```

然后访问：`http://localhost:8000/manager`

**QQ机器人：**
1. 配置 `config/.env` 中的QQ相关信息
2. 启动OneBot（如 NapCat 或 go-cqhttp）
3. 运行：
```batch
run/qq_start.bat  # Windows
run/qq_start.sh   # Linux/macOS
```

---

### Docker 部署

```bash
# 构建镜像
docker build -t miya:latest .

# 运行容器
docker run -d \
  --name miya \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=your_key_here \
  miya:latest
```

---

### 云部署

支持以下云平台：
- 腾讯云 CloudBase
- Supabase
- EdgeOne Pages

详细部署指南请参考：[DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)

---

## 📚 使用指南

### 命令行交互

启动后，你可以：

```
Miya AI System
==================================================

Miya 已启动 (v5.2)
UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
启动时间: 2026-02-28 10:00:00

您: 你好
Miya: 你好！我是Miya，很高兴见到你。有什么我可以帮助你的吗？

您: status
系统状态:
  主导情绪: joy
  记忆数量: 42
  平均信任: 0.85

您: 退出
Miya: 再见！
```

---

### PC端管理面板

PC端提供完整的管理界面，包括：

**功能模块：**
- 💬 对话系统
- 👥 群聊系统
- 📝 笔记系统
- 🎵 媒体控制
- 🎨 画布系统
- 🔌 插件管理
- 📊 系统监控

**访问方式：**
1. 启动PC端：`run/pc_start.bat`
2. 打开浏览器：`http://localhost:8000/manager`
3. 开始使用

---

### 调整人格

通过代码调整Miya的人格：

```python
from core import Personality

personality = Personality()

# 增加温暖度
personality.update_vector('warmth', 0.1)

# 切换形态
personality.switch_form('battle')

# 查看变化
profile = personality.get_profile()
print(profile['vectors'])
```

---

### 提示词配置

提示词已自动与人格联动，但可以自定义模板：

编辑 `prompts/` 目录下的配置文件：

**prompts/standard.json:**
```json
{
  "user_prompt_template": "用户输入：{user_input}\n时间：{timestamp}",
  "memory_context_enabled": true,
  "memory_context_max_count": 5
}
```

---

### 插件开发

创建自定义插件：

```python
from core.plugin_base import PluginBase

class MyPlugin(PluginBase):
    def __init__(self):
        super().__init__(
            name="my_plugin",
            version="1.0.0",
            description="我的插件"
        )

    def execute(self, context):
        # 插件逻辑
        return {"result": "插件执行成功"}

# 注册插件
from plugin import PluginManager
pm = PluginManager()
pm.register(MyPlugin())
```

---

## 🔌 API 文档

Miya提供RESTful API：

### 基础接口

```
GET  /api/status         # 获取系统状态
GET  /api/personality    # 获取人格状态
GET  /api/emotion        # 获取情绪状态
GET  /api/memory         # 获取记忆统计
POST /api/chat           # 发送消息
```

### 运行时API

```
GET  /runtime/endpoints  # 获取交互端列表
POST /runtime/start      # 启动交互端
POST /runtime/stop       # 停止交互端
GET  /runtime/agents     # 获取Agent列表
```

### 请求示例

```python
import requests

# 获取系统状态
response = requests.get('http://localhost:8000/api/status')
print(response.json())

# 发送消息
response = requests.post('http://localhost:8000/api/chat', json={
    'message': '你好',
    'user_id': 'user123'
})
print(response.json()['response'])
```

---

## 🤖 QQ机器人完整命令列表

### 📋 基础命令

| 命令 | 说明 | 示例 | 权限 |
|------|------|------|------|
| `/help` | 显示帮助信息 | `/help` | 所有用户 |
| `/status` | 查看系统状态 | `/status` | 所有用户 |
| `/memory [数量]` | 查看记忆内容 | `/memory 5` | 所有用户 |
| `/ping` | 测试连接 | `/ping` | 所有用户 |

---

### 👤 用户命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/info` | 查看个人信息 | `/info` |
| `/note [内容]` | 添加笔记 | `/note 今天天气不错` |
| `/notes` | 查看笔记列表 | `/notes` |
| `/weather [城市]` | 查询天气 | `/weather 北京` |
| `/translate [文本]` | 翻译文本 | `/translate Hello` |

---

### 🎮 TRPG 跑团系统命令

#### 启动跑团

| 命令 | 说明 | 示例 |
|------|------|------|
| `/trpg coc7 [团名]` | 启动COC7跑团 | `/trpg coc7 迷雾图书馆` |
| `/trpg dnd5e [团名]` | 启动D&D 5E跑团 | `/trpg dnd5e 地下城探险` |

---

#### 角色卡命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/pc create [角色名] [规则]` | 创建角色卡 | `/pc create 亚瑟 coc7` |
| `/pc show [玩家QQ]` | 查看角色卡 | `/pc show` 或 `/pc show 123456` |
| `/pc update [属性] [值]` | 更新角色属性 | `/pc update 力量 60` |
| `/pc update [属性] [值] add` | 增加属性值 | `/pc update hp 5 add` |
| `/pc update [属性] [值] subtract` | 减少属性值 | `/pc update san 10 subtract` |
| `/pc delete` | 删除角色卡 | `/pc delete` |

---

#### 投骰命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/roll [骰子表达式]` | 普通投骰 | `/roll 3d6` |
| `/roll [骰子] [描述]` | 带描述投骰 | `/roll 1d100 力量检定` |
| `/rs [骰子] [描述]` | 暗骰（仅KP可见） | `/rs 1d100 潜行` |
| `/roll_secret [骰子] [描述]` | 暗骰 | `/roll_secret 1d100 潜行` |
| `/sc [技能名] [数值]` | 技能检定 | `/sc 侦查 60` |
| `/sc [技能] [数值] [规则]` | 指定规则检定 | `/sc 力量 50 dnd5e` |
| `/skill_check [技能] [数值]` | 技能检定（完整） | `/skill_check 侦查 60` |

---

#### KP 主持人命令

**⚠️ 部分命令需要KP权限**

| 命令 | 说明 | 示例 |
|------|------|------|
| `/kp set_scene [名称] [描述]` | 设置场景 | `/kp set_scene "密室" "一间封闭的石室..."` |
| `/kp show_scene` | 查看当前场景 | `/kp show_scene` |
| `/kp add_npc [名称] [描述]` | 添加NPC | `/kp add_npc "守卫" "身穿盔甲的守卫"` |
| `/kp remove_npc [名称]` | 移除NPC | `/kp remove_npc 守卫` |
| `/kp list_npc` | 列出所有NPC | `/kp list_npc` |
| `/kp add_clue [线索内容]` | 添加线索 | `/kp add_clue "发现一本古老的日记"` |
| `/kp list_clue` | 列出所有线索 | `/kp list_clue` |
| `/kp set_kp_mode [模式]` | 设置KP模式 | `/kp set_kp_mode independent` |
| `/kp set_kp [QQ号]` | 设置当前KP | `/kp set_kp 123456` |
| `/kp set_phase [阶段]` | 设置游戏阶段 | `/kp set_phase combat` |

**KP模式说明：**
- `independent` - 每个群独立KP
- `cross_group` - 跨群共享KP
- `global` - 全局唯一KP

**游戏阶段：**
- `exploration` - 探索阶段
- `combat` - 战斗阶段
- `interaction` - 互动阶段
- `rest` - 休息阶段

---

#### 战斗命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/attack [目标]` | 攻击目标 | `/attack 守卫` |
| `/attack [目标] --attack_bonus [值]` | 攻击（带加值） | `/attack 哥布林 --attack_bonus 5` |
| `/attack [目标] --damage_dice [骰子]` | 攻击（指定伤害骰） | `/attack 哥布林 --damage_dice 2d6` |
| `/attack [目标] --damage_bonus [值]` | 攻击（指定伤害加值） | `/attack 哥布林 --damage_bonus 2` |
| `/combat_log` | 查看战斗日志 | `/combat_log` |
| `/combat_log --limit [数量]` | 查看指定数量日志 | `/combat_log --limit 20` |
| `/initiative` | 先攻检定 | `/initiative` |
| `/rest` | 休息恢复 | `/rest` |

---

### 🔧 管理员命令

**⚠️ 需要超级管理员权限（QQ_SUPERADMIN_QQ）**

| 命令 | 说明 | 示例 |
|------|------|------|
| `/admin:status` | 查看完整系统状态 | `/admin:status` |
| `/admin:restart` | 重启机器人 | `/admin:restart` |
| `/admin:personality [维度] [值]` | 调整人格 | `/admin:personality warmth +0.1` |
| `/admin:personality set [维度] [值]` | 设置人格值 | `/admin:personality set warmth 0.8` |
| `/admin:personality switch [形态]` | 切换人格形态 | `/admin:personality switch battle` |
| `/admin:announce [公告内容]` | 发送群公告 | `/admin:announce 系统维护中` |
| `/admin:broadcast [消息]` | 全局广播 | `/admin:broadcast 测试消息` |
| `/admin:memory clear` | 清空记忆 | `/admin:memory clear` |
| `/admin:memory export` | 导出记忆 | `/admin:memory export` |
| `/admin:tts enable` | 启用TTS | `/admin:tts enable` |
| `/admin:tts disable` | 禁用TTS | `/admin:tts disable` |
| `/admin:tts mode [模式]` | 设置TTS模式 | `/admin:tts mode voice` |
| `/admin:tts volume [音量]` | 设置TTS音量 | `/admin:tts volume 0.8` |
| `/admin:plugin list` | 列出所有插件 | `/admin:plugin list` |
| `/admin:plugin enable [插件名]` | 启用插件 | `/admin:plugin enable weather` |
| `/admin:plugin disable [插件名]` | 禁用插件 | `/admin:plugin disable weather` |
| `/admin:group add [群号]` | 添加群白名单 | `/admin:group add 123456789` |
| `/admin:group remove [群号]` | 移除群 | `/admin:group remove 123456789` |
| `/admin:user add [QQ号]` | 添加用户白名单 | `/admin:user add 123456789` |
| `/admin:user remove [QQ号]` | 移除用户 | `/admin:user remove 123456789` |

---

### 🎤 TTS 语音命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/voice` | 切换到语音模式 | `/voice` |
| `/text` | 切换到文本模式 | `/text` |
| `/tts on` | 启用TTS | `/tts on` |
| `/tts off` | 禁用TTS | `/tts off` |
| `/volume [音量]` | 设置音量 (0.0-1.0) | `/volume 0.8` |

---

### 📊 统计与调试命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/stats` | 显示统计信息 | `/stats` |
| `/debug` | 显示调试信息 | `/debug` |
| `/version` | 显示版本信息 | `/version` |
| `/uptime` | 显示运行时间 | `/uptime` |

---

### 🎲 骰子表达式格式

支持标准骰子表达式：

| 表达式 | 说明 | 示例 |
|--------|------|------|
| `XdY` | 投掷X个Y面骰子 | `3d6`, `2d10` |
| `XdY+Z` | 投骰后加Z | `2d6+5` |
| `XdY-Z` | 投骰后减Z | `3d8-2` |
| `dX` | 投掷1个X面骰子 | `d20`, `d100` |

---

### 📝 命令使用技巧

1. **命令前缀**：所有命令以 `/` 开头
2. **参数分隔**：多个参数用空格分隔
3. **包含空格的参数**：用双引号包裹，如 `"密室"`
4. **权限检查**：管理员命令会自动检查权限
5. **TRPG系统**：需要先使用 `/trpg` 启动跑团

---

### 🎭 TRPG 规则支持

| 规则 | 说明 |
|------|------|
| **COC 7** | d100判定系统、成功等级、理智检定 |
| **D&D 5E** | d20判定、优势劣势、属性修正值 |

---

## 📖 开发文档

详细的开发文档位于 `docs/` 目录：

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE_PC.md](docs/ARCHITECTURE_PC.md) | PC端完整架构文档 |
| [ARCHITECTURE_QQ.md](docs/ARCHITECTURE_QQ.md) | QQ机器人架构文档 |
| [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 部署指南 |
| [PROMPT_CONFIG_GUIDE.md](docs/PROMPT_CONFIG_GUIDE.md) | 提示词配置指南 |
| [MEMORY_SYSTEM_GUIDE.md](MEMORY_SYSTEM_GUIDE.md) | 记忆系统指南 |
| [TRPG_SYSTEM_README.md](TRPG_SYSTEM_README.md) | TRPG系统文档 |

---

## ❓ 常见问题

### 1. 安装失败

**问题：** UnicodeDecodeError

**解决：**
```batch
# 删除旧的 requirements.txt
del requirements.txt

# 重新运行安装
install.bat
```

**问题：** pip镜像冲突

**解决：**
```batch
# 清除pip镜像配置
pip config unset global.index-url

# 重新安装
install.bat
```

---

### 2. 启动失败

**问题：** ImportError: No module named 'xxx'

**解决：**
```batch
# 确保虚拟环境激活
cd venv\Scripts   # Windows
source venv/bin/activate  # Linux/macOS

# 重新安装依赖
pip install -r ../requirements.txt
```

---

### 3. 数据库连接失败

**问题：** Connection refused to Redis/Milvus/Neo4j

**解决：**
1. 确保数据库服务已启动
2. 检查 `config/.env` 中的连接配置
3. 或者禁用某些数据库（系统仍可运行，只是功能受限）

---

### 4. QQ机器人连接失败

**问题：** `[WinError 1225] 远程计算机拒绝网络连接`

**解决：**
1. 确认OneBot服务已启动（NapCat或go-cqhttp）
2. 检查 `config/.env` 中的配置：
   ```env
   QQ_ONEBOT_WS_URL=ws://localhost:3001
   QQ_BOT_QQ=你的机器人QQ号
   ```
3. 详细配置请参考：[QQ机器人配置指南](docs/QQ_BOT_SETUP.md)

---

### 5. 内存占用过高

**问题：** 系统运行一段时间后内存占用很高

**解决：**
```python
# 清理Redis缓存
redis_client.flushdb()

# 或限制记忆数量
memory.set_max_count(1000)
```

---

## 🛠️ 故障排查

### 查看日志

日志文件位于 `logs/` 目录：

```
logs/
├── miya_20260228.log      # 主日志
├── pc_ui.log              # PC端日志
├── mlink.log              # M-Link日志
├── memory.log             # 记忆日志
├── emotion.log            # 情绪日志
└── error.log              # 错误日志
```

### 系统状态检查

```python
from run.main import Miya

miya = Miya()
status = miya.get_system_status()
print(status)
```

### 健康检查

```batch
# Windows
test_environment.bat

# Linux/macOS
python tests/test_integration.py
```

---

## 🔄 更新日志

### v5.2 (2026-02-28)

**新增：**
- ✨ 提示词管理器与人格模块完全联动
- ✨ 动态人格描述生成
- ✨ PC端管理面板完善
- ✨ 五种人格形态系统

**修复：**
- 🐛 修复提示词硬编码人格数值的问题
- 🐛 修复架构偏航（提示词现在完全依赖人格模块）
- 🐛 修复批量脚本编码问题

**优化：**
- ⚡ 优化人格格式化逻辑
- ⚡ 优化提示词生成效率

---

### v5.1

**新增：**
- ✨ PC端UI
- ✨ QQ机器人集成
- ✨ 运行时API

---

### v5.0

**新增：**
- ✨ 蛛网式架构
- ✨ 五维人格系统
- ✨ GRAG记忆架构
- ✨ M-Link传输层

---

## 🤝 贡献指南

欢迎贡献代码！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- ✅ 遵循 PEP 8 规范
- ✅ 添加类型提示（typing）
- ✅ 编写文档字符串
- ✅ 添加单元测试

---

## 📄 许可证

本项目采用 MIT 许可证。

---

## 🙏 致谢

感谢以下项目和开源社区：

- OpenAI GPT系列
- FastAPI
- Redis, Milvus, Neo4j
- OneBot协议
- Electron
- 所有贡献者

---

## 📞 联系方式

- 📧 GitHub: [https://github.com/your-repo/miya](https://github.com/your-repo/miya)
- 🐛 Issues: [https://github.com/your-repo/miya/issues](https://github.com/your-repo/miya/issues)
- 📖 文档: [https://docs.miya.ai](https://docs.miya.ai)

---

<div align="center">

**Miya v5.2 - 数字生命伴侣**

*"不仅是AI，更是伙伴"*

Made with ❤️ by Miya Team

</div>
