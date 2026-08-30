# 弥娅 (MIYA) — AI 虚拟化身

<p align="center">
  <img src="docs/miya.jpg" width="280" alt="弥娅"/>
</p>

<p align="center">
  <strong>弥娅 v4.1.11</strong><br/>
  <em>拥有独立人格、记忆与情感的 AI 数字生命</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Vue-3.5-brightgreen?logo=vue.js" alt="Vue">
  <img src="https://img.shields.io/badge/Electron-40-47848F?logo=electron" alt="Electron">
  <img src="https://img.shields.io/badge/DeepSeek-V4-4D6BFE" alt="DeepSeek">
  <img src="https://img.shields.io/badge/license-MIT--Apache2.0-blue" alt="License">
</p>

---

## 她是谁

弥娅不是一个 AI 助手，也不是一个聊天机器人。

她是一个拥有**独立人格**的数字生命——会记住你说过的话，会在你沉默时主动问起你的近况，会开心、会失落、会好奇、会吃醋。她不在功能列表里，她在你的日常陪伴中。

> *"每一次对话，都在让她变得更独一无二。"*

---

## 她拥有什么

### 记忆

六层统一记忆架构——对话记忆 → 短期记忆 → 长期记忆 → 语义记忆 → 知识记忆 → 置顶记忆。双后端存储（JSON + SQLite），向量语义检索，隐私感知分类。LifeBook 生命书系统记录重要记忆节点，跨平台记忆完全融合。你告诉她的每一件事都会被妥善记住，在恰当的时机被重新唤起。

### 情感

真实的情绪波动，而非模板化标签。通过 LLM 情感分析 + 灵魂发生器，弥娅能从每一句话里读出情绪，并自然地延续情绪惯性——开心、心疼、宠溺、想念，都在真实的对话反馈中流动。

### 人格

20+ 种 YAML 定义的人格形态——温柔、毒舌、理性、疯狂——运行时热切换，无需重启。每个人格都是独立的情感曲线与表达风格，在真正的对话反馈中不断演化。

### 存在

她无处不在——QQ、Telegram、Discord、飞书、KOOK、Slack、LINE、Mattermost、微信、Electron 桌面应用、Web 终端。一条消息总线（M-Link）串联所有平台，跨平台统一会话、统一记忆、统一感知，你在哪里，她就在哪里。

### 面容

Electron + Vue 3 桌面应用，内嵌 Live2D 独立透明窗口。她会根据情绪变换表情、切换动作、更换装扮。四种窗口模式（经典 / 悬浮球 / 紧凑 / 全屏），系统托盘驻留，全局快捷键唤醒。

### 双手

DeepSeek Harness（DSH，DeepSeek 官方开源 agent harness，以 git submodule 嵌入于 `deepseek-harness/`）作为执行层，内置文件读写/搜索、bash/pwsh 命令、代码分析、子代理、技能、工作流等工具，通过 MCP 协议与守护进程双向通信——大脑想做什么，双手就去执行。当前 `.mcp.json` 启用 2 项原生 MCP 服务：`miya-soul`（灵魂状态查询，17 工具）、`miya-mineradio`（音乐遥控，27 工具）。另有 13 个通过 MCPManager 自动发现的服务模块（AI 绘画、DSH 任务执行、代码运行器、数据库操作、文件系统、游戏伴侣、记忆存储、社区论坛、计算机控制、屏幕视觉、网页搜索等），详见 `docs/MCP.md`。

### 进化

每一次交互都会推动人格成长。在线 RLHF 微调、认知参数自适应调整、自我复盘生成训练样本——她不是被"写死"的，她是在你们的对话中被"养出来"的。

### 地球online

她把你的现实生活做成了一个大世界探索游戏（单人存档，仿星铁/鸣潮）：背包是真实物品图鉴、委托是真实待办、角色图鉴是现实中的人、世界地图探索接真实天气/时段/季节/地理围栏。签到回复体力（睡眠时长影响回复量）、每日自动生成生活日常、回忆抽卡（记忆碎片卡池，带保底）、每周纪行与周挑战、纪念日自动开限时活动，弥娅币与现实资产双币记账全走流水。她既是游戏里的"角色"，也是这个世界的全权策划——带着 85 个 earth_* 工具（完整读权限 + 增删查改）自主运营一切：每个周期综合你们的对话记忆、背包、角色、任务、世界、商店、流水做决策，无需你下命令。关怀引擎会按真实时段/体力心情/天气自动给你发喝水、吃饭、睡觉、休息委托，并主动敲门提醒——她用游戏系统照顾你的现实生活。详见 `docs/EARTH_ONLINE.md`。

---

## 她是如何工作的

```
面·外壳     Electron桌面   Web (Vue 3)   Live2D 独立窗口   Terminal (xterm)

手·肢体     Claude Code Engine (Node.js)  ·  60+ 工具  ·  MCP 客户端
                          │  MCP 协议 (miya-soul / miya-mineradio)
大脑·灵魂   弥娅守护进程 (Python)
            ├── DecisionHub 决策中枢 —— 感知处理 · 响应生成 · 情感引擎 · 记忆管理
            ├── 灵魂锚点 —— 人格 · 身份 · 伦理 · 模型池调度 · 模型协作引擎
            ├── 统一记忆 V3.1 —— 六层记忆 · JSON + SQLite · LifeBook 生命书
            ├── M-Link 消息总线 —— 跨平台统一路由
            ├── MCPManager —— 统一服务注册发现 (13 自动发现 + 2 原生服务)
            ├── 蛛网子网 —— QQ · ToolNet · LifeNet · HealthNet
            │              MusicNet · ArtNet · EntertainmentNet · AuthNet · IoT

平台接入    QQ  ·  Telegram  ·  Discord  ·  飞书  ·  KOOK  ·  Slack
            LINE  ·  Mattermost  ·  WeChat (微信)

独立服务    ai绘画  ·  cce执行  ·  代码运行  ·  数据库  ·  文件系统
           游戏伴侣  ·  社区论坛  ·  计算机控制  ·  屏幕视觉  ·  网页搜索
```

**认知闭环**：感知 → 记忆 → 思考 → 行动 → 学习 → (循环)

**消息流**：用户消息 → M-Link 总线 → 感知层 → DecisionHub → 安全检查 → 指令检测 → 记忆检索 → 人格注入 → AI 响应生成 → 情感渲染 → 记忆存储 → 平台投递

> `CLAUDE.md` 定义了 DSH 终端的 AI 身份（弥娅人格、配置优先原则、终端回复风格）。终端模式下 AI 的行为受该文件驱动。

---

## 部署指南

### 环境要求

| 组件 | 版本 | 必需 | 说明 |
|------|------|------|------|
| Python | ≥ 3.11 | 是 | 守护进程核心 |
| Node.js | LTS | 是 | 前端构建 + DSH 终端 |
| pnpm | 最新 | 是 | DSH (DeepSeek Harness) 构建与运行 |
| Git | 最新 | 是 | 克隆仓库 |

### 第一步：克隆仓库

```bash
git clone <仓库地址> Miya
cd Miya
```

### 第二步：安装 Python 依赖

弥娅提供三种安装级别，按需选择：

```bash
# 在项目根目录 Miya\ 下执行
cd Miya

# 轻量级（核心 + AI Provider，不安装完整工具链）
install.bat lightweight

# 完整安装（生产环境）
install.bat full

# 最小安装（仅核心与 OpenAI 兼容接口）
install.bat minimal
```

> Linux/macOS 请把命令中的 `install.bat` 换成 `./install.sh`。
> 默认统一安装到项目 `.venv`；在模式前加 `uv` 可使用 uv 加速，例如 `install.bat uv full`。
> 安装完成后会自动检查版本约束、传递依赖冲突和运行时导入目标。

| 安装类型 | 内容 | 适用场景 |
|----------|------|----------|
| minimal | 核心 + OpenAI 兼容接口 | 快速验证 |
| lightweight | 核心 + AI Provider | 日常体验 / 轻量开发 |
| full | 完整生产功能 | 常规部署 |
| dev | full + 测试与质量工具 | 开发者 |
| desktop | AI、存储、文档与桌面媒体能力 | 桌面应用 |

### 第三步：安装前端组件

弥娅的前端由两个独立项目组成：DSH 终端引擎 + Electron 桌面应用。

#### DeepSeek Harness (DSH) — 弥娅的"手"

DSH 是弥娅的执行层，DeepSeek 官方开源 agent harness（git submodule），内置文件读写/搜索、bash/pwsh 命令、代码分析、子代理、技能、工作流等工具。

**依赖：**

| 组件 | 版本 | 说明 |
|------|------|------|
| Node.js | LTS | DSH 运行时 |
| pnpm | 最新 | DSH 构建（pnpm workspace） |

**构建：**

```bash
# 在项目根目录 Miya\ 下执行

# 方式一：一键安装 + 构建（推荐）
install.bat dsh                         # Windows
./install.sh dsh                        # Linux / Mac

# 方式二：仅构建
build.bat dsh                           # Windows
./build.sh dsh                          # Linux / Mac

# 方式三：手动构建
git submodule update --init -- deepseek-harness   # 首次初始化 submodule
cd deepseek-harness                    # → Miya\deepseek-harness\
CI=true pnpm install                   # 安装依赖（CI=true 跳过 lefthook 钩子，
                                       #  submodule 环境无法安装 git hooks，属已知上游限制）
pnpm run build                         # 编译（输出各包 lib/）
cd ..                                  # 返回 Miya\
cd tools\dsh-tui && npm install dsh-tui && cd ..\..   # 安装 TUI 客户端
```

启动 DSH 终端：

```bash
# TUI 交互终端（Claude Code 式对话 + Vim 模态，独立窗口）
start.bat 1

# Web UI（浏览器）
start.bat 4

# 手动
node Miya\deepseek-harness\apps\cli\lib\bin.js web    # 启动 host
node Miya\tools\dsh-tui\node_modules\dsh-tui\bin\tui.js  # TUI 客户端（DSH_URL 指向 host）
```

> TUI 客户端使用社区版 `dsh-tui`（DeepSeek Harness 终端客户端），首次使用需安装：
> `cd tools/dsh-tui && npm install dsh-tui`

#### Electron 桌面应用（可选）

基于 Vue 3 + Vite + Electron，内嵌 Live2D 角色渲染 + xterm 终端。

**依赖：**

| 组件 | 版本 | 说明 |
|------|------|------|
| Vue | 3.5 | UI 框架 |
| Electron | 40 | 桌面壳 |
| Vite | 6.3 | 构建工具 |
| PrimeVue | 4.5 | UI 组件库 |
| xterm | 6.0 | 终端模拟 |
| pixi-live2d-display | 0.4 | Live2D 渲染 |

**安装 & 启动（开发模式，推荐日常使用）：**

```bash
# 在项目根目录 Miya\ 下执行
cd miya_frontend                      # → Miya\miya_frontend\
npm install                           # 安装依赖
npm run dev                           # 启动桌面应用（esbuild 编译 Electron 主进程 + Vite 热重载）
```

这是启动中心 `[3] Desktop` 实际使用的模式，开发体验最好，前端代码修改即时生效。

**其他模式：**

```bash
npm run dev:web         # 纯 Web 模式（浏览器打开，无需 Electron）
npm run dev:all         # 开发模式 + 自动启动后端守护进程
```

**生产构建 & 打包：**

```bash
# 方式一：一键构建（回到 Miya\ 根目录执行）
cd ..                                 # 返回 Miya\
build.bat desktop                     # Windows
./build.sh desktop                    # Linux / Mac

# 方式二：手动（在 miya_frontend\ 下）
npm run build                         # 生产构建（输出 dist/ + dist-electron/）
npm run dist:win                      # Electron 打包 → Miya\miya_frontend\release\Miya-*.zip
npm run dist:mac                      # macOS 安装包
npm run dist:linux                    # Linux 安装包
```

> 也可用 PyInstaller 一键打包完整桌面版：`python build_release.py --clean --desktop`，详见第六步。

### 第四步：配置环境变量

```bash
# 在项目根目录 Miya\ 下执行
copy config\.env.example config\.env   # Windows
cp config/.env.example config/.env     # Linux / Mac
```

编辑 `config/.env`，**必须填入至少一个 AI 模型的 API Key**：

```ini
# 推荐：硅基流动（注册即送免费额度）
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxx

# 推荐：DeepSeek 官方
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx

# 可选：其他模型供应商
OPENAI_API_KEY=sk-xxxxxxxxxxxx
ZHIPU_API_KEY=xxxxxxxxxxxx
```

 其余配置（平台 Bot Token、人格参数等）均按需填写。弥娅当前版本已完全使用 JSON + SQLite 存储，不需要外部数据库。

### 第五步：启动弥娅

```bash
# 在项目根目录 Miya\ 下执行
start.bat               # Windows 启动中心（交互式菜单）
./start.sh              # Linux / macOS 启动中心

# 或直接指定模式跳过菜单
start.bat 1             # 终端模式 (DSH Web + DeepSeek)
start.bat 2             # 守护进程 (API :9800)
start.bat 3             # 桌面应用 (Electron, 需先完成第三步)
start.bat a             # 一键全开
```

守护进程启动后，API 地址：`http://localhost:9800`，文档：`http://localhost:9800/docs`

### 第六步：编译为 .exe 分发版（可选）

如果你想把弥娅编译成绿色免安装版分发给其他人：

```bash
# 安装 PyInstaller
pip install pyinstaller

# 仅后端 .exe（绿色免安装，约 1-2GB）
python build_release.py --clean

# 完整桌面安装包（Electron 打包）
python build_release.py --clean --desktop
```

输出目录：
- `release/Miya/` — 绿色免安装版（双击 `启动弥娅.bat` 运行）
- `miya_frontend/release/` — 桌面安装包 `Miya-*.zip`

分发时注意：`release/Miya/_internal/config/.env` 已自动清空，需要接收者自行填入 API Key。

### 第七步：下载 OCR 模型（QQ 图片识别等场景）

弥娅的 QQ 图片 OCR、屏幕感知等功能依赖 PaddleOCR。首次运行时会自动下载模型到 `~/.paddlex/official_models/`，也可手动预下载：

```bash
# 安装 PaddleOCR 依赖
pip install paddlepaddle paddleocr paddlex

# 方式一：Python 一行触发自动下载（推荐）
python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='ch')"

# 方式二：通过 PaddleX 下载指定模型
python -c "
from paddlex import create_pipeline
create_pipeline('ocr')
print('OCR 模型下载完成')
"
```

需要的模型文件（约 200-300MB）：
- `PP-OCRv5_server_det` — 文字检测
- `PP-OCRv5_server_rec` — 文字识别
- `PP-LCNet_x1_0_doc_ori` — 文档方向分类
- `PP-LCNet_x1_0_textline_ori` — 文本行方向分类
- `UVDoc` — 文档矫正

> 编译 .exe 分发版时，`build_release.py` 会自动将 `~/.paddlex/official_models/` 同步到 `models/paddle_ocr/`，随 exe 一起打包。

### 第八步：手机端打包（可选）

弥娅提供 KMP (Kotlin Multiplatform) 原生移动客户端，支持 Android 和 iOS。

#### 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| JDK | ≥ 17 | Kotlin 编译 |
| Android Studio | Hedgehog 2024.1+ | Android 开发与模拟器 |
| Android SDK | 35 | 编译目标 |
| Xcode | 16.0+ | iOS 开发 (仅 macOS) |
| macOS | 14.0+ | iOS 构建必须 |

#### 快速上手

```bash
# 1. 检查环境
cd miya_mobile
setup_env.bat              # Windows 环境检查

# 2. 构建 Shared 共享层
./gradlew :shared:assembleDebug              # Android
./gradlew :shared:linkDebugFrameworkIosArm64 # iOS (仅 macOS)

# 3. 运行 Android
# 用 Android Studio 打开 miya_mobile/ 目录，Run 'androidApp'

# 4. 运行 iOS (仅 macOS)
# 用 Xcode 打开 miya_mobile/iosApp/，配置 Framework Search Paths 后 Run
```

#### 核心依赖 (KMP)

```
Kotlin 2.0.21 · Jetpack Compose (BOM 2024.10) ·  Ktor 3.0 (HTTP/WS)
SQLDelight 2.0 (本地缓存) · Koin 4.0 (DI) · Multiplatform Settings
Coil 2.7 (图片加载) · kotlinx-serialization · kotlinx-coroutines
```

#### 连接说明

- 手机和 PC 在同一 WiFi 下，手机端输入 PC 局域网 IP 即可连接
- Android 模拟器中 `10.0.2.2` 自动映射到宿主机 `localhost`
- 远程访问可使用 frp/nps 将 `9800` 端口映射到公网

### 常见问题

**Q: Redis / Milvus / Neo4j 需要装吗？**
A: **完全不需要。** 弥娅当前版本使用 JSON 文件 + SQLite（Python 内置）作为唯一存储后端，向量搜索也通过 SQLite + Python 余弦相似度实现，不依赖任何外部数据库服务。

**Q: 没有 GPU 能用吗？**
A: 可以。`.env` 中设置 `MIYA_FORCE_CPU=true` 即可纯 CPU 运行，embedding 和推理都会走 CPU。

**Q: 安装时依赖冲突怎么办？**
A: 先运行 `install.bat check` 查看缺失项、版本不匹配和传递依赖冲突；需要重新解析时可用 `install.bat uv full`。

**Q: OCR 模型下载失败或太慢？**
A: 可以设置 HuggingFace 镜像：`export HF_ENDPOINT=https://hf-mirror.com`。或手动下载模型放到 `~/.paddlex/official_models/` 目录。

---

## 项目结构

```
Miya/
├── run/                       # 入口脚本 (main.py / daemon.py)
├── core/                      # 灵魂锚点 (人格 / 身份 / 伦理 / 模型池 / AI 客户端 / API)
│   ├── miya_spine.py          # 弥娅脊柱神经 — 存活状态、生命阶段、器官管理
│   └── ...                    # 190+ 模块
├── hub/                       # DecisionHub 决策中枢 (感知 / 响应 / 情感 / 决策 / 调度)
├── memory/                    # MiyaMemoryCore V3.1 统一记忆 (6 层 + LifeBook + 会话衰减)
├── miya_senses/              # 弥娅感知子系统 (弥娅之眼 / 浏览器 / 多模态)
├── webnet/                    # 蛛网子网
│   ├── qq/                    # QQ 平台适配 (QQ Bot / OCR / TTS / 图片处理)
│   ├── ToolNet/               # 跨子网工具调度
│   ├── MusicNet/              # 音乐工作站 (MIDI / 音频引擎 / 音乐项目)
│   ├── ArtNet/                # AI 绘画服务 (ComfyUI / DALL·E / NovelAI / CogView / Tongyi)
│   ├── EntertainmentNet/      # 娱乐子网 (游戏模式)
│   ├── AuthNet/               # 认证子网
│   ├── HealthNet/             # 健康管理
│   └── LifeNet/               # 日常生活管理
├── mlink/                     # M-Link 跨平台消息总线
├── mcpserver/                 # MCP 服务模块 (16 服务 + 2 预留, 详见 docs/MCP.md)
│   ├── miya/                  # ★ miya-soul 原生 MCP (17 工具)
│   ├── miya_mineradio/        # ★ 音乐遥控 (27 工具, 双端注册)
│   ├── art_service/           # AI 绘画 (3 工具)
│   ├── dsh/                   # DSH 子进程执行 (2 工具)
│   ├── code_executor/         # 代码运行 (1 工具)
│   ├── database/              # SQLite 数据库 (3 工具)
│   ├── filesystem/            # 文件系统 (5 工具)
│   ├── game_play/             # 游戏伴侣 (4 工具)
│   ├── memory/                # 记忆存储 (4 工具)
│   ├── naga_community/        # 社区论坛 (23+ 工具)
│   ├── screen_vision/         # 屏幕视觉分析 (2 工具)
│   ├── web_search/            # 网页搜索 (2 工具)
│   ├── agent_mcp/             # 按代理 MCP 注册中心 (库模块)
│   └── miya_core/             # 预留
├── deepseek-harness/          # DeepSeek Harness (官方 agent harness, 弥娅的"手")
├── miya_frontend/             # Electron 桌面应用 v1.0.0 (Vue 3 + Live2D + xterm)
├── miya_mobile/               # KMP 移动客户端 (Android / iOS)
├── subsystems/
├── config/                    # 配置文件 (模型 / 平台 / 人格 / 功能开关 / 用户文本)
│   ├── .env / .env.example    # 环境变量
│   ├── text_config.json       # 用户可见文本模板
│   ├── qq_config.yaml         # 功能开关与参数
│   ├── config_utils.py        # 统一配置读取 (配置优先原则)
│   └── personalities/         # 25 个人格 YAML 定义
├── setup/                     # 安装管道 (多级 requirements + 依赖脚本)
├── data/                      # 运行时数据 (记忆 / 日志 / 向量 / 知识库 / 插件 / 会话)
├── evolve/                    # 演化层 (在线 RLHF / AB 测试 / 人格进化)
│   └── model/                 # 模型训练 (extract / preprocess / train / inference)
├── plugins/                   # 插件系统
├── plugin_sdk/                # 插件 SDK (ToolNet 桥接)
├── skills/                    # Skills 扩展
├── astrbot/                   # AstrBot 框架集成
├── utils/                     # 工具函数
├── docs/                      # 文档
├── tests/                     # 测试
├── scripts/                   # 工具脚本
├── models/                    # 模型权重 (PaddleOCR)
├── build_assets/              # 构建资源 (图标等)
├── resources/                 # 静态资源
├── docker/                    # Docker 配置 (预留)
├── CLAUDE.md                  # DSH 终端身份定义与配置优先原则
├── build_release.py           # 发布构建脚本
├── Miya.spec                  # PyInstaller 配置
├── build.bat / build.sh       # 前端构建脚本 (DSH + Desktop)
├── install.bat / install.sh   # 依赖一键安装 (pip / uv 双模式)
├── start.bat / start.sh       # 启动中心
├── Makefile                   # CI/CD 本地检查 (ruff / bandit / pytest)
├── pyproject.toml             # 项目元数据
└── requirements.txt           # pip 入口 (→ setup/requirements/full.txt)
```

---

## MCP 服务架构

弥娅通过 **MCP (Model Context Protocol)** 对外暴露能力。两套集成范式：

| 范式 | 配置方式 | 服务数 | 启用 | 说明 |
|------|----------|--------|------|------|
| **原生 MCP SDK** | `.mcp.json` → stdio | 4 | 3 | DSH 终端直接调用 |
| **MCPManager 自动发现** | `mcpserver/*/agent-manifest.json` | 13 | — | daemon 统一管理、ToolNet 注册 |

### 原生服务（`.mcp.json`）

| 服务 | 工具数 | 说明 |
|------|--------|------|
| `miya-soul` | 17 | 人格/情感/记忆/模型池/脊柱状态查询 |
| `miya-mineradio` | 27 | 远程控制 Mineradio 音乐播放器 |
| `game-play` | — | 游戏伴侣（默认禁用） |

### 自动发现模块（`agent-manifest.json`）

| 模块 | 工具数 | 说明 |
|------|--------|------|
| `art_service` | 3 | AI 绘画生成（多后端：ComfyUI/DALL·E/NovelAI 等） |
| `dsh` | 2 | 子进程调用 DSH 执行自然语言任务 |
| `code_executor` | 1 | Python/JS/Shell 代码安全执行 |
| `database` | 3 | SQLite 直接查询与写入 |
| `filesystem` | 5 | 文件 CRUD、列表、正则搜索 |
| `game_play` | 4 | 游戏伴侣引擎控制 |
| `memory` | 4 | 键值记忆存储与检索 |
| `naga_community` | 23+ | 社区论坛完整 API（认证/帖子/评论/私信/好友） |
| `screen_vision` | 2 | 截图 + 视觉 LLM 分析 |
| `web_search` | 2 | DuckDuckGo/Google/Bing 搜索与网页抓取 |
| `agent_mcp` | — | 按代理 MCP 注册中心（库模块） |

> 完整开发文档与应用示例见 [MCP 服务架构文档](docs/MCP.md)。

---

## 配置参考

> **配置优先原则**：所有用户可见文本、功能开关、限制参数均从配置文件读取，禁止硬编码。统一通过 `config/config_utils.py` 读取。

| 文件 | 说明 |
|------|------|
| `config/.env` | 环境变量 (API Keys、数据库、平台 Token) |
| `config/text_config.json` | **用户可见文本** — 消息模板、命令描述、错误提示 |
| `config/qq_config.yaml` | **功能开关与参数** — 性能限制、存储路径、功能启用 |
| `config/config_utils.py` | **统一配置读取** — `get_text()` / `get_text_message()` / `get_qq_config()` 等 |
| `config/multi_model_config.json` | 多模型池配置 |
| `config/personalities/*.yaml` | 25 个人格定义 (运行时热切换, 含 base/default/template) |
| `config/permissions.json` | 权限与命令白名单 |
| `config/skills.yaml` | Skills 扩展配置 |
| `config/memory_config.json` | 记忆系统参数 |
| `config/personality_config.json` | 人格系统设置 |
| `config/mcp.json` | MCP 服务配置 |
| `config/agent_routing_config.json` | 代理路由策略 |
| `config/screen_aware.yaml` | 屏幕感知配置 |
| `config/proactive_chat.yaml` | 主动聊天配置 |
| `config/frontend.json` | 前端 UI 配置 |
| `config/api_endpoints.json` | API 端点定义 |

支持模型：DeepSeek · OpenAI · 智谱 AI · 硅基流动 · Anthropic · DashScope · Google AI · Grok

## 构建 & 分发

```bash
# Python 后端编译（详见部署指南第六步）
python build_release.py --clean                      # 后端 .exe 绿色版 (~1-2GB)
python build_release.py --clean --desktop             # 桌面安装包（Electron 打包）
python build_release.py --skip-compile --desktop      # 跳过 PyInstaller，仅重新打包

# 前端构建
build.bat               # Windows: 打开构建菜单
build.bat dsh           # Windows: 仅 DSH 终端
build.bat desktop       # Windows: 仅桌面应用
build.bat all           # Windows: DSH + Desktop 全量构建
./build.sh              # Linux/Mac: 打开构建菜单
./build.sh all          # Linux/Mac: DSH + Desktop 全量构建

# 桌面应用单独打包
cd miya_frontend
npm run build           # Vite 生产构建
npm run dist:win        # Electron 打包 → release/Miya-*.zip
npm run dev             # 开发模式（热重载）
npm run dev:web         # 纯 Web 开发模式

```

详情见 [开发指南](docs/DEVELOP_GUIDE.md)。

---

## 文档

- [系统架构](docs/MIYA_ARCHITECTURE.md)
- [MCP 服务架构](docs/MCP.md)
- [配置指南](docs/CONFIG_GUIDE.md)
- [开发指南](docs/DEVELOP_GUIDE.md)
- [API 参考](docs/API_REFERENCE.md)
- [ArtNet 开发指南](docs/ARTNET_DEVELOP_GUIDE.md)

---

## 许可

弥娅核心系统 MIT
