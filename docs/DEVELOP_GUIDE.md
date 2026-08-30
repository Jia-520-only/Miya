# 弥娅开发指南

面向开发者的模块详解、扩展开发和调试指南。

---

## 目录

- [项目结构总览](#项目结构总览)
- [核心模块详解](#核心模块详解)
- [扩展开发](#扩展开发)
- [调试与测试](#调试与测试)
- [代码规范](#代码规范)

---

## 项目结构总览

```
Miya/
├── run/           # 入口脚本
├── core/          # 灵魂锚点 (214+ 文件)
├── hub/           # 决策中枢
├── memory/        # 统一记忆系统
├── webnet/        # 蛛网子网
├── mlink/         # M-Link 消息总线
├── perceive/      # 感知层
├── detect/        # 检测层
├── evolve/        # 演化层
├── trust/         # 信任系统
├── config/        # 配置文件
├── miya_frontend/ # Electron 桌面应用
├── deepseek-harness/ # DeepSeek Harness（弥娅之手引擎）
├── data/          # 运行时数据
├── docs/          # 文档
├── scripts/       # 实用脚本
├── tests/         # 测试
├── setup/         # 安装依赖
├── storage/       # 存储抽象
├── utils/         # 工具函数
└── astrbot/       # AstrBot 框架集成
```

---

## 核心模块详解

### run/ — 系统入口

#### `run/main.py` — 终端模式

- `Miya` 类 (1142 行) 协调所有子系统
- 初始化顺序：Settings → Core → Hub → MLink → Perceive → WebNet → Detect → Trust → Evolve → Memory
- 使用 Claude Code Engine 提供 CLI 交互

```python
class Miya:
    def __init__(self):
        self.settings = Settings()
        self.personality = Personality()
        self.ethics = Ethics()
        self.identity = Identity()
        self.arbitrator = Arbitrator()
        self.entropy = Entropy()
        # ... 更多初始化
        self.decision_hub = DecisionHub(...)
```

#### `run/daemon.py` — 守护进程

- 基于 `core/miya_daemon.py` 的 `MiyaDaemon` 类
- 可选管理 API (REST + WebSocket，端口 9800)
- 支持热插拔平台

```bash
python run/daemon.py                  # 启动
python run/daemon.py --api-port 9800  # 指定端口
python run/daemon.py --platforms qqofficial,telegram
```

---

### hub/ — 决策中枢

核心是 `DecisionHub` (3860 行)，门面模式设计：

```python
class DecisionHub:
    def __init__(self):
        self.perception = PerceptionHandler()
        self.response = ResponseGenerator()
        self.emotion = Emotion()
        self.memory_manager = MemoryManager()
        self.scheduler = Scheduler()
        # 协调各子系统处理消息
```

**关键方法**：

| 方法 | 说明 |
|------|------|
| `process_perception_cross_platform()` | 跨平台消息处理入口 |
| `_detect_commands()` | 命令检测 |
| `_security_check()` | 安全注入检测 |
| `_handle_image()` | 图片分析 |
| `_generate_response()` | AI 响应生成 |
| `_apply_emotion_color()` | 情感色彩渲染 |

---

### memory/ — 记忆系统

#### MiyaMemoryCore (V3.1)

核心记忆引擎，六层架构：

```python
from memory import MiyaMemoryCore, MemoryLevel, MemoryItem

# 单例初始化
core = await MiyaMemoryCore.get_instance(data_dir="data/memory")

# 存储
await core.store(
    content="我喜欢喝咖啡", level=MemoryLevel.LONG_TERM, user_id="user_123", tags=["偏好", "饮食"], priority=0.7
)

# 检索
results = await core.retrieve(query="咖啡", user_id="user_123", limit=10)

# 语义搜索
results = await core.semantic_search("用户喜欢什么饮品？")
```

**便捷存储函数**：

```python
from memory import (
    store_dialogue,  # 存储对话
    store_important,  # 存储重要记忆
    store_auto,  # 自动提取存储
    store_knowledge,  # 存储知识图谱
    store_cognition,  # 存储认知记忆
    search_memory,  # 搜索记忆
    get_user_profile,  # 获取用户画像
    get_memory_stats,  # 获取统计
)
```

---

### webnet/ — 蛛网子网

#### 子网架构

```
WebNet
  ├── NetManager      — 子网生命周期管理
  ├── CrossNetEngine  — 跨子网通信
  ├── QQNet           — QQ 消息收发
  ├── ToolNet         — 工具注册/执行
  ├── MemoryNet       — 全局记忆共享
  ├── LifeNet         — 生活管理
  └── HealthNet       — 健康监控
```

#### 创建新子网

```python
from webnet.subnet_base import BaseSubnet


class MyNet(BaseSubnet):
    def __init__(self):
        super().__init__(name="MyNet")

    async def on_start(self):
        await super().on_start()

    async def on_message(self, msg):
        # 处理消息
        pass


# 注册到 NetManager
net_manager.register(MyNet())
```

#### Web 服务

`webnet/web_main.py` — FastAPI 服务器：
- 端口：8000 (自动查找)
- 代理 API 到守护进程 (端口优先 9800)
- 服务 React 前端静态文件
- 健康检查 `/api/health`

---

### core/ — 灵魂锚点

#### AI 客户端 (`ai_client.py`)

```python
from core.ai_client import AIClientFactory

# 创建客户端
client = AIClientFactory.create("deepseek")

# 发送消息
response = await client.chat([{"role": "system", "content": "你是弥娅"}, {"role": "user", "content": "你好"}])
```

支持的客户端：`OpenAIClient`, `DeepSeekClient`, `AnthropicClient`, `ZhipuAIClient`

#### 人格系统 (`personality.py`)

```python
from core.personality import Personality

personality = Personality()
personality.set("kafka")  # 切换人格
current = personality.get_current()  # 获取当前人格
traits = personality.get_traits()  # 获取性格特征
```

人格文件位于 `config/personalities/*.yaml`。

#### 模型池 (`model_pool_manager.py`)

```python
from core.model_pool_manager import ModelPoolManager

pool = ModelPoolManager()
model = await pool.get_best_model(complexity=0.8)
response = await model.generate(prompt)
```

---

### mlink/ — 消息总线

```python
from mlink import MLinkCore, Message, Router

# 创建消息
msg = Message(type="chat", content="你好", sender="user_123", platform="qq")

# 发送到总线
await mlink.send(msg)


# 订阅消息
@mlink.on("chat")
async def handle_chat(msg: Message):
    pass
```

---

### perceive/ — 感知层

```python
from perceive import PerceptualRing, AttentionGate

ring = PerceptualRing()
gate = AttentionGate(threshold=0.5)

# 感知输入
percepts = ring.perceive(raw_input)

# 注意力过滤
focused = gate.filter(percepts)
```

---

### evolve/ — 演化层

```python
from evolve import Sandbox, ABTest

# 沙盒执行
sandbox = Sandbox()
result = await sandbox.execute(code)

# AB 测试
ab = ABTest()
ab.register_variant("A", handler_a)
ab.register_variant("B", handler_b)
result = await ab.run(input_data)
```

---

## 扩展开发

### 添加新人格

1. 在 `config/personalities/` 创建 YAML 文件：

```yaml
name: "my_persona"
display_name: "我的自定义人格"
traits:
  warmth: 0.9
  logic: 0.6
  creativity: 0.8
  empathy: 0.85
speech_style: "热情、开放、富有想象力"
```

2. 在 `config/personality_config.json` 中注册。

### 添加新平台

1. 创建平台适配器，继承 `core/unified_platform.py` 中的 `BasePlatform`
2. 在 `config/platforms_config.py` 中注册
3. 实现 `on_message()` 和 `send_message()` 方法

### 添加新工具

1. 在 `webnet/ToolNet/tools/` 创建工具函数
2. 使用装饰器注册：

```python
from webnet.ToolNet import get_tool_registry


@get_tool_registry().register("my_tool")
async def my_tool(param: str) -> str:
    """工具描述"""
    return f"处理结果: {param}"
```

---

## 调试与测试

### 运行测试

```bash
# 全部测试
pytest tests/

# 特定模块
pytest tests/test_memory.py

# 带日志
pytest tests/ -v -s
```

### 日志

日志配置在 `config/.env`：

```env
LOG_LEVEL=DEBUG    # 详细日志
LOG_LEVEL=INFO     # 正常 (默认)
LOG_LEVEL=WARNING  # 精简
```

日志文件：`logs/miya.log`

### 常用脚本

```bash
# 记忆初始化
python scripts/init_memory.py

# 模型池测试
python scripts/test_model_pool.py

# 表情包管理
python scripts/emoji_manager.py
```

---

## 代码规范

### Python

- Python 3.10+
- 使用 `ruff` 进行代码检查
- 类型注解 (type hints) 推荐使用

### 检查命令

```bash
ruff check .           # 代码检查
ruff format .          # 代码格式化
```

### 命名约定

- 模块文件：`snake_case.py`
- 类名：`PascalCase`
- 函数/方法：`snake_case()`
- 常量：`UPPER_CASE`
- 私有方法：`_private_method()`

### Git 提交

- 提交前运行 `pre-commit` 钩子
- 配置：`.pre-commit-config.yaml`
- Pylint 检查：`.pylintrc`

---

## 构建与发布流水线

### 产物概览

| 产物 | 路径 | 说明 |
|------|------|------|
| 独立后端 | `release/Miya/Miya.exe` | Python 守护进程，API 服务 |
| 桌面便携版 | `miya_frontend/release/Miya 1.0.0.exe` | Electron 前端 + 后端，双击即用 |
| 桌面解压版 | `miya_frontend/release/win-unpacked/` | 已解压的 Electron 应用（调试用） |

### 一键构建

```bash
# 仅构建独立后端
python build_release.py --clean

# 构建桌面应用（后端 + Electron 前端）
python build_release.py --clean --desktop
```

### 流水线步骤

```
[0] 清理 → 删除 dist/ build/ release/
[1] 编译 → PyInstaller (Miya.spec) → dist/Miya/
[2] 组装 → 复制 dist/Miya/ → release/Miya/ + 创建启动脚本 + .env 安全处理
[3] 同步 → release/Miya/ → miya_frontend/resources/backend/ (miya-backend.exe)
[4] 构建 → npm run build (Vite) + npx electron-builder --win portable
[5] 清理 → 删除中间产物 dist/ build/
```

### 关键配置

| 文件 | 作用 |
|------|------|
| `Miya.spec` | PyInstaller 编译配置 (入口、排除模块、数据文件) |
| `miya_frontend/package.json` | Electron-builder 配置 (extraResources、图标、目标) |
| `miya_frontend/vite.config.ts` | Vite 构建配置 (别名、Electron 插件) |
| `miya_frontend/electron/main.ts` | Electron 主进程 (窗口管理、后端启动) |
| `miya_frontend/electron/modules/backend.ts` | 后端 spawn 逻辑 |

### 已知问题与解决方案

| 问题 | 原因 | 解决 |
|------|------|------|
| ToolNet 初始化失败 `No module named 'unittest'` | PyInstaller excludes 了 `unittest`，但 `pyparsing.testing` 需要它 | `Miya.spec` excludes 移除 `unittest`，保留 `test` |
| `config/permissions.json` 找不到 | CWD 设为 `resources/backend/`，但配置文件在 `_internal/config/` | `backend.ts` 将 spawn CWD 设为 `resources/backend/_internal/` |
| DSH 运行时缺失 | 打包时未生成 DSH 自包含运行时 | `build_release.py` 用 `pnpm --filter @deepseek-ai/dsh deploy --prod` 部署到 `_internal/deepseek-harness/apps/cli/` |
| 独立版 config/data 冗余副本 | 外层与 `_internal/` 下的 config/data 是两份独立副本，用户编辑外层不生效 | `build_release.py` 将 `_internal/config`, `_internal/data`, `_internal/logs` 替换为目录联结（junction）→ `../config` 等，实现单一数据源 |
| NSIS / portable 打包失败 | 7z 文件过大 (5.9GB+)，NSIS makensis mmap 失败 | 改用 `electron-builder --win zip`，产出自解压 ZIP |
| DeepSeek API 401 认证失败 | `.env` 中密钥为占位符（安全设计） | 发布前替换 `_internal/config/.env` 中的 `DEEPSEEK_API_KEY` |

### 分发

```bash
# 独立后端 — 压缩 release/Miya/ 为 ZIP/7z
# 注意：目录联结（junction）无法被打包进 ZIP，若需分发 ZIP 请使用 --portable-zip 回退到复制模式
# 接收者解压后编辑 config/.env 即可运行

# 桌面应用 — 直接分发 miya_frontend/release/Miya 1.0.0.exe
# 接收者双击运行，首次启动后在 _internal/config/.env 填入 API key
```
