# 弥娅系统架构

弥娅 v7.0 采用**分层架构 + 蛛网子网**设计，各层之间通过 M-Link 消息总线通信。

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        入口层                               │
│   Terminal (Claude Code) │ Daemon │ Desktop (Electron) │ Web │
├─────────────────────────────────────────────────────────────┤
│                    M-Link 消息总线                           │
├─────────────────────────────────────────────────────────────┤
│                     感知层 (perceive/)                       │
│               PerceptualRing · AttentionGate                 │
├─────────────────────────────────────────────────────────────┤
│                     检测层 (detect/)                         │
│       TimeDetector · SpaceDetector · NodeDetector             │
│                      EntropyDiffusion                        │
├─────────────────────────────────────────────────────────────┤
│                     决策中枢 (hub/)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    DecisionHub                        │   │
│  │         (门面模式 - 协调所有子系统)                    │   │
│  ├──────────┬──────────┬──────────┬────────────────────┤   │
│  │Perception │Response  │ Emotion  │  MemoryManager     │   │
│  │Handler    │Generator │          │                    │   │
│  └──────────┴──────────┴──────────┴────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                     灵魂锚点 (core/)                         │
│   Personality · Identity · Ethics · Entropy · AI Client     │
│              ModelPool · SoulGenerator · PromptManager       │
├─────────────────────────────────────────────────────────────┤
│                  统一记忆系统 (memory/)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                MiyaMemoryCore V3.1                    │   │
│  │  DIALOGUE → SHORT_TERM → LONG_TERM → SEMANTIC        │   │
│  │              → KNOWLEDGE → PINNED                     │   │
│  │  后端: JSON 文件 + SQLite                              │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                   蛛网子网 (webnet/)                         │
│  QQNet │ ToolNet │ MemoryNet │ LifeNet │ HealthNet │ IoTNet │
├─────────────────────────────────────────────────────────────┤
│                    演化沙盒 (evolve/)                        │
│   Sandbox · ABTest · RLHF · PersonalityEvolver              │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心模块详解

### 1. 入口层

系统提供四种启动模式，通过 `start.bat` 统一管理：

| 模式 | 技术栈 | 说明 |
|------|--------|------|
| Terminal | Node.js (Claude Code Engine) | 终端 CLI 交互 |
| Daemon | Python (asyncio) | 后台守护进程 + REST API |
| Desktop | Electron + React + Vite | 桌面应用 |
| Web | React + Tailwind + Vite | 浏览器前端 |

**入口脚本**：

- **`run/main.py`** (1142 行) — 终端模式入口，`Miya` 类初始化所有子系统
- **`run/daemon.py`** (231 行) — 守护进程入口，基于 `MiyaDaemon`

### 2. M-Link 消息总线 (`mlink/`)

统一跨平台消息路由层：

- `MLinkCore` — 消息总线核心
- `Message` — 统一消息类型（支持 FlowType 流控）
- `Router` — 消息路由分发
- `TrustTransmit` — 信任传播

### 3. 感知层 (`perceive/`)

- **PerceptualRing** — 全局感知环，接收所有平台输入
- **AttentionGate** — 注意力门控，过滤噪声、聚焦关键信息

### 4. 检测层 (`detect/`)

- **TimeDetector** — 时间上下文检测
- **SpaceDetector** — 空间/场景检测
- **NodeDetector** — 节点状态检测
- **EntropyDiffusion** — 系统熵值扩散监控

### 5. 决策中枢 (`hub/`)

采用**门面模式 (Facade Pattern)**，`DecisionHub` 作为协调器：

```
DecisionHub (3860 行)
  ├── PerceptionHandler   — 命令检测、权限验证、安全注入检查
  ├── ResponseGenerator   — AI 响应生成、多模型协作
  ├── Emotion             — 情感引擎 (379 行)
  ├── MemoryManager       — 记忆管理门面
  ├── MemoryEngine        — 记忆检索引擎
  ├── MemoryEmotion       — 情感-记忆链接
  ├── Decision            — 决策引擎
  ├── Scheduler           — 定时任务调度
  ├── ConversationContext — 对话上下文管理
  ├── SessionHandler      — 会话管理
  └── PlatformTools       — 平台工具管理
```

**请求处理流程**：

```
用户消息
  → 谛听监听器 (diteng_listener) 记录
  → 用户画像更新
  → 命令检测 (!命令)
  → 安全/注入检查 (SecurityService + AIInjectionDetector)
  → 图片分析 (如有)
  → 关键词触发回复
  → PerceptionHandler 处理
  → MemoryManager 存储用户消息
  → ResponseGenerator 生成 AI 响应
  → 情感色彩渲染
  → 智能表情包发送
  → 记忆存储 (AI 回复)
```

### 6. 灵魂锚点 (`core/`)

弥娅的核心子系统（214+ 文件）：

| 模块 | 说明 |
|------|------|
| `personality.py` | 多形态人格系统 |
| `identity.py` | 身份认知系统 |
| `ethics.py` | 伦理审查 |
| `arbitrator.py` | 仲裁决策 |
| `entropy.py` | 系统熵值量化 |
| `soul_generator.py` | AI 内心独白生成 |
| `ai_client.py` | 统一 AI 客户端 (OpenAI/DeepSeek/Anthropic/Zhipu) |
| `model_pool_manager.py` | 多模型池管理 |
| `prompt_manager.py` | 提示词管理 |
| `miya_daemon.py` | MiyaDaemon 守护进程 (v7.0) |
| `autonomy_with_personality.py` | 自主人格引擎 |
| `event_system.py` | 事件总线 |
| `star_miya.py` | Star 插件系统 |
| `knowledge_base.py` | 知识库管理 |
| `management_api.py` | 管理 API |

### 7. 记忆系统 (`memory/`)

**MiyaMemoryCore V3.1** 是唯一的记忆核心（2352 行）：

**六层记忆架构**：

| 层级 | 存储 | 生命周期 | 用途 |
|------|------|----------|------|
| DIALOGUE | JSON 文件 | 会话级 | 对话历史 |
| SHORT_TERM | JSON 文件 | TTL 自动过期 | 短期上下文 |
| LONG_TERM | JSON + SQLite | 持久化 | 重要事实与偏好 |
| SEMANTIC | JSON + 向量 | 持久化 | 语义向量搜索 |
| KNOWLEDGE | JSON + SQLite | 持久化 | 知识图谱（实体关系） |
| PINNED | SQLite | 永久 | 置顶核心记忆 |

**存储后端**：

- **JSON 文件** — `data/memory/` 下的层级目录
- **SQLite** — `data/memory/miya_memory.db`
- **向量嵌入** — 通过 SiliconFlow/OpenAI API 或本地 Sentence-Transformers

**辅助模块**：

- `historian.py` — 对话历史管理
- `lifebook.py` — 三视角生活日记
- `working_memory.py` — 短期工作记忆
- `cognitive_engine.py` — 认知引擎
- `memory_enhancer.py` — 记忆增强器（自动链接挖掘）
- `privacy_classifier.py` — 隐私感知分类
- `diteng_listener.py` — 谛听群消息监听
- `semantic_dynamics_engine.py` — 语义搜索引擎

### 8. 蛛网子网 (`webnet/`)

弹性分布式子网架构：

| 子网 | 模块 | 说明 |
|------|------|------|
| QQNet | `qq.py` / `qq/` | OneBot 协议，QQ 消息收发 |
| ToolNet | `ToolNet/` | 工具注册与执行中心 |
| MemoryNet | `memory.py` | 全局记忆共享 |
| LifeNet | `life.py` | 生活管理 |
| HealthNet | `health.py` | 健康监控 |
| IoTNet | `iot.py` | IoT 设备控制 |
| AuthNet | `AuthNet/` | 跨平台认证 |
| EntertainmentNet | `EntertainmentNet/` | 娱乐功能 |

**Web 服务** (`web_main.py`)：FastAPI 服务器，端口 8000，代理 API 调用到守护进程 (9800)。

### 9. 演化层 (`evolve/`)

自我进化能力：

- **Sandbox** — 安全沙盒执行
- **ABTest** — AB 测试框架
- **UserCoPlay** — 用户共同游戏学习
- **OnlineRLHFLearner** — 在线 RLHF 学习
- **ModelFinetuner** — 模型微调
- **PersonalityEvolver** — 人格进化
- **IncrementalLearner** — 增量学习
- **KnowledgeGraphUpdater** — 知识图谱更新
- **SelfSynthesizedReplay** — 自我合成回放

### 10. 信任系统 (`trust/`)

- **TrustScore** — 基于交互的信任评分
- **TrustPropagation** — 跨网络信任传播

---

## 模块导入关系

```python
# 终端模式 (run/main.py) 的核心初始化链:
from core import Personality, Ethics, Identity, Arbitrator, Entropy, PromptManager
from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler, DecisionHub
from mlink import MLinkCore, Message, Router
from perceive import PerceptualRing, AttentionGate
from webnet import NetManager, CrossNetEngine
from detect import TimeDetector, SpaceDetector, NodeDetector, EntropyDiffusion
from trust import TrustScore, TrustPropagation
from evolve import Sandbox, ABTest, UserCoPlay
from memory import MiyaMemory, MemoryAdapter
from storage import RedisAsyncClient
from config import Settings
```

---

## 版本说明

| 组件 | 版本 | 位置 |
|------|------|------|
| 对外版本 | v7.0 | README / start.bat |
| MiyaDaemon | v7.0.0 | `core/miya_daemon.py` |
| 记忆核心 | V3.1 | `memory/core.py` |
| Web 服务 | v2.0.0 | `webnet/web_main.py` |
