# 弥娅 (Miya) - 数字生命伴侣

[![Version](https://img.shields.io/badge/version-5.2-blue.svg)](https://github.com/your-repo/miya)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> *"不仅是AI，更是伙伴"* — 弥娅 v5.2

弥娅（Miya）是一个基于蛛网式分布式架构的数字生命伴侣系统，具备动态人格、情感演化、记忆管理、多端接入等核心能力。

---

## 📖 目录

- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [安装部署](#安装部署)
- [使用指南](#使用指南)
- [开发文档](#开发文档)
- [常见问题](#常见问题)

---

## 🚀 快速开始

### 最低要求

- **操作系统**: Windows 10+ / Linux / macOS
- **Python**: 3.9 或更高版本
- **内存**: 建议 4GB+
- **存储**: 建议 10GB+

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

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           用户界面层                                  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  PC UI      │  │  QQ UI      │  │  (未来)     │                │
│  │  Electron   │  │  OneBot     │  │  Mobile UI  │                │
│  └─────────────┘  └─────────────┘  └─────────────┘                │
│         │                 │                                        │
│         └────────┬────────┘                                        │
│                  │ REST API / WebSocket                            │
└──────────────────┼─────────────────────────────────────────────────┘
                   │ M-Link 五流传输
┌──────────────────┼─────────────────────────────────────────────────┐
│                   │              认知核心层                            │
├──────────────────┼─────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                  │
│  │  Hub中枢    │ │  M-Link     │ │  感知环     │                  │
│  │             │ │  (传输)     │ │             │                  │
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
├── core/              # 核心模块（灵魂锚点）
│   ├── personality.py      # 人格向量系统
│   ├── ethics.py           # 伦理约束
│   ├── identity.py         # 身份识别
│   ├── arbitrator.py       # 仲裁器
│   ├── entropy.py          # 熵监控
│   ├── prompt_manager.py   # 提示词管理器（动态联动人格）
│   ├── agent_manager.py    # Agent管理
│   └── ...
├── hub/               # 中枢层（认知中心）
│   ├── memory_engine.py    # 记忆引擎
│   ├── emotion.py          # 情绪系统
│   ├── decision.py         # 决策引擎
│   ├── scheduler.py        # 任务调度
│   └── ...
├── mlink/             # M-Link传输层
│   ├── mlink_core.py       # 传输核心
│   ├── message.py          # 消息格式
│   ├── router.py           # 路由系统
│   └── ...
├── perceive/          # 感知层
│   ├── perceptual_ring.py  # 感知环
│   └── attention_gate.py   # 注意力闸门
├── webnet/            # 子网层（各业务子网）
│   ├── pc_ui.py           # PC端子网
│   ├── qq.py              # QQ子网
│   ├── life.py            # 生活子网
│   ├── work.py            # 工作子网
│   └── ...
├── memory/            # 记忆系统
│   ├── grag_memory.py     # GRAG记忆
│   ├── semantic_dynamics_engine.py  # 语义动态引擎
│   ├── quintuple_graph.py # 五元组图谱
│   └── ...
├── detect/            # 检测层
│   ├── time_detector.py   # 时间检测
│   ├── space_detector.py  # 空间检测
│   ├── node_detector.py   # 节点检测
│   └── entropy_diffusion.py  # 熵扩散检测
├── trust/             # 信任系统
│   ├── trust_score.py     # 信任评分
│   └── trust_propagation.py  # 信任传播
├── evolve/            # 演化层
│   ├── sandbox.py         # 沙盒环境
│   ├── ab_test.py         # A/B测试
│   └── user_co_play.py    # 用户共创
├── storage/           # 存储层
│   ├── redis_client.py    # Redis客户端
│   ├── milvus_client.py   # Milvus客户端
│   └── neo4j_client.py    # Neo4j客户端
├── plugin/            # 插件系统
│   └── plugin_manager.py  # 插件管理器
├── run/               # 启动脚本
│   ├── main.py             # 主程序
│   ├── pc_start.bat        # PC端启动
│   └── qq_start.bat        # QQ启动
├── pc_ui/             # PC端界面
│   ├── manager.html        # 管理面板
│   ├── app.js              # 前端逻辑
│   └── styles.css          # 样式
├── config/            # 配置文件
│   ├── .env                # 环境变量
│   ├── settings.py         # 设置管理
│   └── grag_config.py      # GRAG配置
├── prompts/           # 提示词资源
│   ├── README.md           # 提示词使用指南
│   ├── system_prompts.md   # 系统提示词库
│   └── *.json              # 配置文件
├── docs/              # 开发文档
│   ├── ARCHITECTURE_PC.md  # PC端架构
│   ├── ARCHITECTURE_QQ.md  # QQ架构
│   └── ...
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

**示例代码：**
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

### 4. M-Link 传输系统

M-Link是弥娅的核心传输层，支持五流分发：

| 流类型 | 作用 | 方向 |
|-------|------|------|
| 指令流 (Control) | 内核/中枢 → 执行节点 | 下行 |
| 感知流 (Perception) | 感知层 → 中枢/子网 | 上行 |
| 同步流 (Sync) | 子网 ↔ 子网 | 横向 |
| 信任流 (Trust) | 信任评分与传播 | 双向 |
| 记忆流 (Memory) | 记忆读写请求 | 双向 |

**特性：**
- 动态路径评分
- 优先级通道
- 断链自愈

### 5. 多端接入

弥娅支持多种接入方式：

| 接入方式 | 状态 | 说明 |
|---------|------|------|
| 命令行 | ✅ 已完成 | 基础交互模式 |
| PC端 | ✅ 已完成 | Electron + WebUI |
| QQ机器人 | ✅ 已完成 | OneBot协议 |
| 移动端 | 🚧 开发中 | Flutter |
| Web端 | 🚧 开发中 | 纯前端 |

### 6. 提示词管理 (Prompt Manager)

**重要更新**：提示词管理器已与人格模块完全联动，动态生成提示词。

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
- 检查Python版本（需要3.9+）
- 创建虚拟环境（venv）
- 安装依赖包（requirements.txt）
- 初始化配置文件
- 创建必要目录

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

# 数据库配置
REDIS_HOST=localhost
REDIS_PORT=6379
MILVUS_HOST=localhost
MILvUS_PORT=19530
NEO4J_URI=bolt://localhost:7687
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

#### 5. 启动弥娅

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

然后访问：`http://localhost:8000`

**QQ机器人：**
1. 配置 `config/.env` 中的QQ相关信息
2. 启动OneBot（如 go-cqhttp）
3. 运行：
```batch
run/qq_start.bat  # Windows
run/qq_start.sh   # Linux/macOS
```

### Docker部署

```bash
# 构建镜像
docker build -t miya:latest .

# 运行容器
docker run -d \
  --name miya \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  miya:latest
```

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

```text
弥娅 AI 系统
Miya AI System
==================================================

弥娅 已启动 (v5.2)
UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
启动时间: 2026-02-28 10:00:00

您: 你好
弥娅: 你好！我是弥娅，很高兴见到你。有什么我可以帮助你的吗？

您: status
系统状态:
  主导情绪: joy
  记忆数量: 42
  平均信任: 0.85

您: 退出
弥娅: 再见！
```

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

### 调整人格

通过代码调整弥娅的人格：

```python
from core import Personality

personality = Personality()

# 增加温暖度
personality.update_vector('warmth', 0.1)

# 查看变化
profile = personality.get_profile()
print(profile['vectors'])
```

### 配置提示词

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

## 📖 开发文档

详细的开发文档位于 `docs/` 目录：

### 数据库系统文档
| 文档 | 说明 |
|------|------|
| [DATABASE_COMPLETE_GUIDE.md](docs/DATABASE_COMPLETE_GUIDE.md) | 数据库系统完整指南（推荐） |
| [DATABASE_QUICK_REFERENCE.md](docs/DATABASE_QUICK_REFERENCE.md) | 数据库快速参考 |
| [DATABASE_DEPLOYMENT_CHECKLIST.md](docs/DATABASE_DEPLOYMENT_CHECKLIST.md) | 数据库部署检查清单 |

### 系统架构文档
| 文档 | 说明 |
|------|------|
| [ARCHITECTURE_PC.md](docs/ARCHITECTURE_PC.md) | PC端完整架构文档 |
| [ARCHITECTURE_QQ.md](docs/ARCHITECTURE_QQ.md) | QQ机器人架构文档 |
| [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 部署指南 |
| [COMPLETE_INTEGRATION_REPORT.md](docs/COMPLETE_INTEGRATION_REPORT.md) | 完整集成报告 |
| [PROMPT_CONFIG_GUIDE.md](docs/PROMPT_CONFIG_GUIDE.md) | 提示词配置指南 |
| [UNDEFINED_ANALYSIS_REPORT.md](docs/UNDEFINED_ANALYSIS_REPORT.md) | Undefined系统分析 |

### API文档

弥娅提供RESTful API：

**基础接口：**
```
GET  /api/status         # 获取系统状态
GET  /api/personality    # 获取人格状态
GET  /api/emotion        # 获取情绪状态
GET  /api/memory         # 获取记忆统计
POST /api/chat           # 发送消息
```

**运行时API：**
```
GET  /runtime/endpoints  # 获取交互端列表
POST /runtime/start      # 启动交互端
POST /runtime/stop       # 停止交互端
GET  /runtime/agents     # 获取Agent列表
```

详细API文档请参考 `core/runtime_api_server.py` 的注释。

### 核心模块说明

**人格模块 (core/personality.py):**
- 五维人格向量管理
- 人格边界约束
- 人格稳定性计算

**情绪模块 (hub/emotion.py):**
- 情绪类型定义
- 情绪染色机制
- 情绪衰减算法

**记忆模块 (hub/memory_engine.py):**
- 多层次记忆存储
- 语义检索
- GRAG五元组

**传输模块 (mlink/mlink_core.py):**
- 五流分发
- 动态路由
- 断链自愈

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

**问题：** NameError: name 'Dict' is not defined

**解决：**
这是旧版本的问题，已修复。请确保使用最新代码。

### 3. 提示词不生效

**问题：** 修改提示词后没有变化

**原因：** 提示词现在由人格模块动态生成

**解决：**
```python
# 调整人格，提示词会自动更新
personality.update_vector('warmth', 0.1)

# 或自定义模板（仅修改用户提示词）
prompt_manager.set_user_prompt_template("自定义模板")
```

### 4. 数据库连接失败

**问题：** Connection refused to Redis/Milvus/Neo4j

**解决：**
1. 确保数据库服务已启动
2. 检查 `config/.env` 中的连接配置
3. 或者禁用某些数据库（系统仍可运行，只是功能受限）

### 5. QQ机器人连接失败

**问题：** `[WinError 1225] 远程计算机拒绝网络连接`

**原因：** OneBot服务未启动或配置错误

**解决：**
1. 确认OneBot服务已启动（NapCat或go-cqhttp）
2. 检查 `config/.env` 中的配置：
   ```env
   QQ_ONEBOT_WS_URL=ws://localhost:3001
   QQ_BOT_QQ=你的机器人QQ号
   ```
3. 详细配置请参考：[QQ机器人配置指南](docs/QQ_BOT_SETUP.md)

**常见错误：**
- ❌ OneBot未启动 → 启动OneBot服务
- ❌ 端口配置错误 → 检查OneBot的WebSocket端口
- ❌ QQ号未配置 → 设置 `QQ_BOT_QQ`
- ❌ Token不匹配 → 检查 `QQ_ONEBOT_TOKEN`

### 6. 内存占用过高

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

**修复：**
- 🐛 修复提示词硬编码人格数值的问题
- 🐛 修复架构偏航（提示词现在完全依赖人格模块）
- 🐛 修复批量脚本编码问题

**优化：**
- ⚡ 优化人格格式化逻辑
- ⚡ 优化提示词生成效率

### v5.1

**新增：**
- ✨ PC端UI
- ✨ QQ机器人集成
- ✨ 运行时API

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

- 遵循 PEP 8 规范
- 添加类型提示（typing）
- 编写文档字符串
- 添加单元测试

---

## 📄 许可证

本项目采用 MIT 许可证。

---

## 🙏 致谢

感谢以下项目：
- OpenAI GPT系列
- FastAPI
- Redis, Milvus, Neo4j
- OneBot协议
- Electron

---

## 📞 联系方式

- GitHub: https://github.com/your-repo/miya
- Issues: https://github.com/your-repo/miya/issues
- 文档: https://docs.miya.ai

---

**弥娅 v5.2 - 数字生命伴侣**

*"不仅是AI，更是伙伴"*
