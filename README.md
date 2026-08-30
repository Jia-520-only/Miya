# 弥娅 MIYA - 多模态智能AI系统

<div align="center">

![MIYA Logo](https://img.shields.io/badge/MIYA-V4.0-blue)
![Python](https://img.shields.io/badge/Python-3.9+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

**下一代智能AI伴侣系统 - 支持多终端、多模型、多平台**

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [安装配置](#-安装配置) • [使用文档](#-使用文档) • [API文档](#api文档)

[English](README_EN.md) | [简体中文](README.md)

</div>

---

## 📖 项目简介

弥娅（MIYA）是一个高度可扩展的多模态AI系统，旨在为用户提供全方位的智能助手体验。系统集成了先进的记忆管理、工具调用、终端控制、Web交互等功能，支持多平台部署和多模型智能调度。

### 🎯 设计理念

弥娅不仅仅是一个聊天机器人，她是一个**具有感知、记忆、学习和执行能力的智能生命体**：

- **感知系统** - 通过多渠道感知用户需求和环境变化
- **记忆系统** - 构建完整的记忆网络，包括短期记忆、长期记忆和知识图谱
- **执行系统** - 智能调用工具和命令，完成实际任务
- **决策系统** - 基于人格和上下文进行智能决策
- **演化系统** - 动态调整人格参数，实现持续进化

### 🌟 核心优势

| 特性 | 说明 | 优势 |
|------|------|------|
| **多模型智能调度** | 支持9+个AI模型，自动选择最优模型 | 成本优化、性能提升 |
| **四层记忆架构** | Redis(潮汐) + Milvus(向量) + Neo4j(图谱) + LifeBook(手动) | 记忆持久化、智能检索 |
| **多终端管理** | 同时控制多个终端窗口，支持并行执行 | 开发效率提升、任务自动化 |
| **多平台支持** | QQ机器人 + Web界面 + 桌面应用 | 随时随地访问 |
| **动态人格系统** | 五维人格向量，实时演化 | 个性化交互体验 |
| **自主决策引擎** - 基于感知和记忆自动决策 | 减少人工干预 |

---

## ✨ 功能特性

### 🤖 多模型智能调度

弥娅支持集成多个AI模型，并根据任务类型智能选择最优模型：

#### 支持的模型

| 模型类型 | 推荐模型 | 适用场景 | 特点 |
|---------|---------|---------|------|
| **快速响应** | Qwen2.5-7B, GPT-4o-mini | 简单对话、文本分类 | 速度快、成本低 |
| **通用对话** | DeepSeek-V3, GPT-4o | 日常聊天、任务规划 | 平衡性能和成本 |
| **复杂推理** | DeepSeek-R1, Claude-3.5-Sonnet | 代码分析、逻辑推理 | 推理能力强 |
| **代码生成** | DeepSeek-Coder, GPT-4 | 编程、代码审查 | 代码质量高 |
| **中文优化** | Qwen2.5-72B, GLM-4 | 中文理解、写作 | 中文语境好 |
| **视觉理解** | GPT-4-Vision, Claude-3-Vision | 图像分析、OCR | 多模态能力 |

#### 智能路由策略

```
用户输入 → 任务分析 → 模型选择 → 智能调度 → 输出响应
           ↓
      [任务类型识别]
      - 简单聊天 → 快速模型
      - 复杂推理 → 推理模型
      - 代码生成 → 代码模型
      - 多模态 → 视觉模型
```

### 🧠 四层记忆架构

弥娅拥有业界领先的四级记忆系统：

```
┌─────────────────────────────────────────────────────────────┐
│                   弥娅记忆系统                         │
├─────────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Redis      │  │    Milvus    │  │    Neo4j     │  │
│  │ 潮汐记忆     │  │  向量记忆    │  │  知识图谱    │  │
│  │ (短期/活跃)  │  │  (长期/检索)  │  │  (关系网络)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────┐       │
│  │         Undefined Memory (手动记忆)              │       │
│  │         data/memory/undefined_memory.json        │       │
│  └──────────────────────────────────────────────────┘       │
│                                                           │
└─────────────────────────────────────────────────────────────┘
```

#### 记忆流转机制

1. **实时对话** → 存入Redis (潮汐记忆)
2. **超过阈值** → 压缩摘要，存入Milvus (向量记忆)
3. **实体关系** → 提取并存入Neo4j (知识图谱)
4. **重要信息** → 可手动标记为Undefined Memory (长期记忆)
5. **智能检索** → 根据上下文检索相关记忆

### 🖥️ 多终端管理系统

弥娅V4.0革命性的多终端管理功能：

#### 核心能力

- ✅ **单机多终端** - 同时管理CMD、PowerShell、WSL、Bash等多个终端
- ✅ **可见窗口** - 真实的终端窗口，支持交互式操作
- ✅ **智能编排** - AI自动分配任务到最优终端
- ✅ **并行执行** - 多终端同时执行不同命令
- ✅ **协同工作** - 多终端配合完成复杂任务
- ✅ **自动选择** - 根据操作系统自动选择合适的终端类型

#### 使用场景

```
场景1: 多项目开发
终端1: 项目A (Python开发)    → 运行测试
终端2: 项目B (Node.js开发)  → 启动服务
终端3: 项目C (Docker运维)   → 查看日志

场景2: 系统监控
终端1: 系统资源监控       → htop
终端2: 网络监控            → netstat
终端3: 日志查看            → tail -f

场景3: 批量操作
终端1: 数据处理  → python process.py data1.csv
终端2: 数据处理  → python process.py data2.csv
终端3: 数据处理  → python process.py data3.csv
```

### 🌐 多平台支持

#### QQ机器人
- 全功能QQ聊天机器人
- 支持群聊和私聊
- 权限管理系统
- 图片、文件处理

#### Web界面
- 现代化React前端
- 完整的聊天界面
- 系统状态监控
- 博客系统集成
- 代码编辑器

#### 桌面应用
- Electron桌面应用
- Live2D虚拟形象
- 本地快速启动
- 系统托盘集成

### 🎨 动态人格系统

#### 五维人格向量

| 维度 | 范围 | 影响 |
|------|------|------|
| **温暖度** | 0.0-1.0 | 回复的亲和力和亲切感 |
| **逻辑性** | 0.0-1.0 | 推理的严谨度和准确性 |
| **创造力** | 0.0-1.0 | 回复的多样性和新颖性 |
| **共情力** | 0.0-1.0 | 情感理解和共鸣能力 |
| **韧性** | 0.0-1.0 | 面对困难和压力的应对 |

#### 人格演化

```
用户交互 → 情绪感知 → 人格参数调整 → 行为变化
   ↓              ↓                ↓              ↓
  反馈        情绪强度         参数微调        回复风格
```

### 🛠️ 工具系统

弥娅内置丰富的工具，可以执行各种任务：

| 工具类别 | 工具列表 | 功能说明 |
|---------|---------|---------|
| **文件操作** | 文件读取、文件写入、目录遍历 | 读写文件、管理目录 |
| **系统命令** | 终端命令、Shell脚本 | 执行系统级操作 |
| **网络操作** | Web搜索、HTTP请求 | 获取网络信息 |
| **数据处理** | 文本处理、数据分析 | 处理结构化数据 |
| **开发工具** | Git操作、代码执行 | 辅助开发工作 |
| **记忆管理** | 记忆查询、记忆添加 | 管理个人记忆 |

### 🔐 权限系统

弥娅内置完善的权限管理系统：

#### 权限模型

```
用户 → 用户组 → 权限节点 → 资源访问
 ↓        ↓           ↓            ↓
识别    分组        授权          控制
```

#### 权限节点示例

- `tool.web_search` - Web搜索工具
- `tool.terminal_command` - 终端命令工具
- `agent.chat` - 聊天Agent
- `*` - 超级管理员（所有权限）

---

## 🚀 快速开始

### 前置要求

- Python 3.9+
- Node.js 16+ (仅Web UI需要)
- Docker (可选，用于数据库)

### 一键安装

#### Windows

```batch
# 克隆项目
git clone https://github.com/Jia-520-only/Miya.git
cd Miya

# 自动安装
install.bat
```

#### Linux/Mac

```bash
# 克隆项目
git clone https://github.com/Jia-520-only/Miya.git
cd Miya

# 自动安装
chmod +x install.sh
./install.sh
```

### 配置API密钥

复制示例配置文件：

```batch
# Windows
copy config\.env.example config\.env

# Linux/Mac
cp config/.env.example config/.env
```

编辑 `config/.env` 文件，至少配置一个AI模型：

#### 最简配置（仅需DeepSeek）

```env
# 主模型配置
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=sk-your-deepseek-api-key-here
AI_MODEL=deepseek-chat
```

#### 推荐配置（DeepSeek + SiliconFlow）

```env
# DeepSeek官方（推荐）
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 硅基流动（可选，新用户免费2000万Tokens）
SILICONFLOW_API_KEY=sk-your-siliconflow-api-key-here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
```

> 💡 **提示**: 获取API密钥
> - DeepSeek: https://platform.deepseek.com/
> - SiliconFlow: https://cloud.siliconflow.cn/i/pEXepR3y (注册即送2000万Tokens)

### 启动系统

#### Windows

```batch
start.bat
```

#### Linux/Mac

```bash
./start.sh
```

### 选择启动模式

启动后会显示菜单：

```
========================================
  MIYA - Launch Menu
========================================

1. Start Main Program (Full Mode)
2. Start QQ Bot
3. Start Web UI (Frontend + Backend)
4. Start Desktop UI (Electron)
5. Start Runtime API Server
6. Start Health Check
7. Check System Status
0. Exit

Select mode (0-7):
```

#### 推荐选择

- **新手用户** → 选择 `3` (Web UI) - 图形界面，易于上手
- **QQ用户** → 选择 `2` (QQ Bot) - 配置OneBot后可在QQ聊天
- **开发者** → 选择 `1` (Main Program) - 完整功能，适合开发

#### Web UI启动后

- 前端界面: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

---

## 📦 安装配置

### 详细安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/Jia-520-only/Miya.git
cd Miya
```

#### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

#### 3. 安装Python依赖

```bash
# 安装核心依赖
pip install -r requirements.txt

# (可选) 安装开发依赖
pip install -r requirements-dev.txt
```

#### 4. 配置环境变量

```bash
# 复制配置文件
cp config/.env.example config/.env

# 编辑配置文件（使用你喜欢的编辑器）
nano config/.env
# 或
vim config/.env
# 或
code config/.env
```

**必须配置的项**：

```env
# 主模型配置
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=sk-your-api-key-here
AI_MODEL=deepseek-chat
```

**可选配置的项**：

```env
# 数据库配置（默认可选，系统会自动降级）
REDIS_HOST=localhost
REDIS_PORT=6379

MILVUS_HOST=localhost
MILVUS_PORT=19530

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
```

#### 5. 数据库配置（可选）

弥娅支持三种数据库，都是可选的：

##### Redis（潮汐记忆）

```bash
# Docker启动
docker run -d --name redis -p 6379:6379 redis:latest

# 或使用docker-compose
docker-compose up -d redis
```

##### Milvus（向量记忆）

```bash
# 使用docker-compose启动Milvus
docker-compose -f docker-compose.milvus.yml up -d
```

##### Neo4j（知识图谱）

```bash
# Docker启动
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

> 💡 **提示**: 数据库都是可选的！如果数据库连接失败，系统会自动降级到模拟模式，核心功能不受影响。

#### 6. 配置QQ机器人（可选）

如果需要使用QQ机器人，需要配置OneBot：

```env
# OneBot配置
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_ONEBOT_TOKEN=your-onebot-token
QQ_BOT_QQ=your-bot-qq-number
QQ_SUPERADMIN_QQ=your-admin-qq-number
```

推荐使用 [NapCat](https://github.com/NapNeko/NapCatQQ) 或 [LLOneBot](https://github.com/LLOneBot/LLOneBot) 作为OneBot实现。

### Docker部署（推荐）

#### 一键启动所有服务

```bash
# 启动所有数据库服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

#### 独立启动Web UI

```bash
# 构建镜像
docker build -t miya .

# 运行容器
docker run -d \
  --name miya \
  -p 8000:8000 \
  -p 3000:3000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  miya
```

### 公网部署

使用 Cloudflare Tunnel 或 frp 实现公网访问：

```bash
# 使用Cloudflare Tunnel
cloudflared tunnel --url http://localhost:3000

# 使用frp
# 在frp服务端配置vhost_http_port = 3000
```

详细公网部署指南请参考 [docs/PUBLIC_DEPLOYMENT_GUIDE.md](docs/PUBLIC_DEPLOYMENT_GUIDE.md)

---

## 📚 使用文档

### Web界面使用

#### 访问Web UI

启动后打开浏览器访问：http://localhost:3000

#### 功能模块

1. **聊天界面**
   - 发送消息与弥娅对话
   - 查看对话历史
   - 执行终端命令（在消息前加 `!`）
   - AI智能分析（在消息前加 `?`）

2. **系统监控**
   - 查看系统资源使用
   - 监控AI模型调用
   - 查看记忆系统状态
   - 检查工具调用记录

3. **终端管理**
   - 创建新终端窗口
   - 查看终端列表
   - 切换活动终端
   - 并行执行命令
   - 查看命令历史

4. **模型管理**
   - 查看已配置模型
   - 切换当前模型
   - 查看模型使用统计
   - 配置新模型

5. **博客系统**
   - 查看博客文章
   - 创建新文章
   - 编辑文章
   - 管理文章标签

6. **设置面板**
   - 配置系统参数
   - 调整人格向量
   - 管理权限
   - 查看系统日志

### 终端命令使用

#### 基础命令

```
!help           # 显示帮助信息
!status         # 查看系统状态
!clear          # 清除对话历史
!exit           # 退出当前会话
```

#### 终端管理

```
!create <name> [-t type]  # 创建新终端
    示例：!create 测试终端 -t powershell

!list                   # 列出所有终端
!switch <session_id>     # 切换到指定终端
!close <session_id>      # 关闭指定终端
!status                 # 显示终端状态
```

#### 执行模式

```
!parallel <sid:cmd>...   # 多终端并行执行
    示例：!parallel term1:dir term2:ls

!sequence <sid> <cmd>... # 单终端顺序执行
    示例：!sequence term1 cd .. dir

!collab <task>           # 多终端协同任务
    示例：!collab 检查所有项目状态
```

#### AI智能

```
?<task>           # 让AI智能执行任务
    示例：?帮我在GitHub上搜索Python项目

?analyze <task>   # 让AI分析任务并规划
    示例：?analyze 部署这个项目需要做什么
```

### QQ机器人使用

#### 基础命令

```
/help            # 显示帮助菜单
/status          # 查看机器人状态
/models          # 查看可用模型
/setmodel <name> # 切换AI模型
```

#### 群聊命令

```
@机器人 <消息>    # @机器人进行对话
!status          # 查看系统状态（仅管理员）
!admin add/remove <QQ> # 管理员管理（仅超级管理员）
```

#### 私聊命令

所有命令都支持私聊，不受权限限制。

### 桌面应用使用

#### 启动桌面应用

```batch
# 选择启动菜单中的选项4
start.bat
# 选择 4 - Start Desktop UI
```

#### 桌面应用功能

- Live2D虚拟形象
- 系统托盘图标
- 快捷键支持
- 本地数据存储
- 离线模式（部分功能）

---

## 🔄 多模型配置

### 配置多个AI模型

弥娅支持同时配置多个AI模型，系统会根据任务类型智能选择。

#### 使用配置助手（推荐）

```bash
python setup_multi_model.py
```

配置助手菜单：

```
========================================
  弥娅多模型配置助手
========================================

1. 配置 DeepSeek 官方 API
2. 配置 OpenAI API
3. 配置 Anthropic (Claude) API
4. 配置 硅基流动 SiliconFlow API
5. 快速配置硅基流动（推荐新手）
6. 查看当前配置
7. 测试所有模型
8. 重置配置
0. 退出

请选择操作 (0-8):
```

#### 手动配置

编辑 `config/multi_model_config.json`：

```json
{
  "models": {
    "deepseek_v3": {
      "name": "deepseek-chat",
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-your-deepseek-key",
      "capabilities": ["chat", "reasoning", "code"],
      "latency": "fast",
      "quality": "excellent"
    },
    "gpt4": {
      "name": "gpt-4",
      "provider": "openai",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your-openai-key",
      "capabilities": ["chat", "vision"],
      "latency": "medium",
      "quality": "excellent"
    }
  },
  "routing_strategy": {
    "simple_chat": {
      "primary": "deepseek_v3",
      "fallback": "gpt4"
    }
  }
}
```

### 模型路由策略

弥娅根据任务类型自动选择模型：

| 任务类型 | 首选模型 | 回退模型 | 策略 |
|---------|---------|---------|------|
| 简单聊天 | fast模型 | chat模型 | 优先速度 |
| 复杂推理 | reasoning模型 | chat模型 | 优先质量 |
| 代码生成 | code模型 | reasoning模型 | 优先准确性 |
| 多模态 | vision模型 | chat模型 | 功能必需 |

---

## 🗄️ 数据库配置

### Redis（潮汐记忆）

Redis用于存储短期对话和活跃记忆。

#### 配置

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password
REDIS_MAX_CONNECTIONS=10
```

#### 启动

```bash
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:latest
```

### Milvus（向量记忆）

Milvus用于存储长期向量记忆，支持语义检索。

#### 配置

```env
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory
MILVUS_DIMENSION=1536
MILVUS_INDEX_TYPE=IVF_FLAT

# 使用Milvus Lite（本地文件模式，无需Docker）
MILVUS_USE_LITE=false
```

#### 启动

```bash
docker-compose -f docker-compose.milvus.yml up -d
```

### Neo4j（知识图谱）

Neo4j用于存储知识图谱和实体关系。

#### 配置

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

#### 启动

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

#### 访问Neo4j Browser

打开浏览器访问：http://localhost:7474

用户名：`neo4j`
密码：你设置的密码

---

## 🛡️ 权限管理

### 用户配置

编辑 `data/auth/users.json`：

```json
{
  "users": [
    {
      "user_id": "qq_123456789",
      "username": "test_user",
      "platform": "qq",
      "permission_groups": ["Default", "VIP"],
      "permissions": ["tool.web_search"],
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### 用户组配置

编辑 `data/auth/groups.json`：

```json
{
  "groups": {
    "Default": {
      "description": "默认用户组",
      "permissions": [
        "agent.chat",
        "tool.web_search"
      ]
    },
    "VIP": {
      "description": "VIP用户组",
      "permissions": [
        "tool.*",
        "agent.*"
      ]
    },
    "Admin": {
      "description": "管理员组",
      "permissions": ["*"]
    }
  }
}
```

### 权限检查流程

```
用户请求 → 识别用户 → 查找用户组 → 检查权限 → 允许/拒绝
   ↓           ↓           ↓            ↓            ↓
会话ID     user_id    groups.json   permission   执行/拦截
```

---

## 🔧 高级配置

### 人格调优

编辑 `config/.env` 调整人格参数：

```env
# 人格向量（0.0-1.0）
PERSONALITY_WARMTH=0.8      # 温暖度
PERSONALITY_LOGIC=0.7       # 逻辑性
PERSONALITY_CREATIVITY=0.6  # 创造力
PERSONALITY_EMPATHY=0.75    # 共情力
PERSONALITY_RESILIENCE=0.7  # 韧性
```

### 情绪配置

```env
# 情绪系统配置
EMOTION_DECAY_RATE=0.1              # 情绪衰减率
EMOTION_COLORING_THRESHOLD=0.7      # 情绪染色阈值
EMOTION_MAX_INTENSITY=1.0           # 最大情绪强度
EMOTION_PROPAGATION_COEFF=0.3       # 情绪传播系数
```

### 记忆配置

```env
# 记忆系统配置
MEMORY_TIDE_TTL=3600                  # 潮汐记忆TTL（秒）
MEMORY_DREAM_THRESHOLD=100           # 梦境压缩阈值
MEMORY_SHORT_TERM_CAPACITY=20         # 短期记忆容量
MEMORY_LONG_TERM_RETRIEVAL=10        # 长期记忆检索数量
```

### 日志配置

```env
# 日志配置
LOG_LEVEL=INFO                         # 日志级别
LOG_FILE_PATH=logs/miya.log           # 日志文件路径
LOG_MAX_SIZE=100                      # 日志最大大小（MB）
LOG_BACKUP_COUNT=10                   # 日志备份数量
LOG_TTY_ENABLED=true                  # 终端日志启用
```

---

## 🐛 故障排查

### 常见问题

#### 1. ImportError: No module named 'xxx'

**原因**: Python依赖未安装

**解决**:

```bash
# 重新安装依赖
pip install -r requirements.txt

# 或单独安装缺失的模块
pip install xxx
```

#### 2. 连接数据库失败

**原因**: 数据库未启动或配置错误

**解决**:

```bash
# 检查数据库是否运行
docker ps | grep -E "redis|milvus|neo4j"

# 查看数据库日志
docker-compose logs

# 检查配置文件
cat config/.env
```

> 💡 **提示**: 数据库是可选的！即使数据库连接失败，系统也能正常运行（会降级到模拟模式）

#### 3. API密钥错误

**原因**: API密钥无效或未配置

**解决**:

```bash
# 检查配置文件
cat config/.env | grep API_KEY

# 确认密钥格式
# DeepSeek: sk-xxxxxxxx
# OpenAI: sk-xxxxxxxx
# SiliconFlow: sk-xxxxxxxx

# 重新配置
python setup_multi_model.py
```

#### 4. 端口被占用

**原因**: 端口已被其他程序使用

**解决**:

```bash
# Windows查看端口占用
netstat -ano | findstr :8000

# Linux/Mac查看端口占用
lsof -i :8000

# 修改配置文件中的端口
vim config/.env
# 修改 WEB_API_PORT=8001
```

#### 5. 终端窗口不可见

**原因**: Windows终端配置问题

**解决**:

```bash
# 确保使用正确的终端类型
!create 测试终端 -t powershell

# 查看终端状态
!status
```

### 诊断工具

#### 运行健康检查

```bash
# Windows
start.bat
# 选择 6 - Start Health Check

# Linux/Mac
./start.sh
# 选择 6 - Start Health Check
```

#### 查看系统状态

```bash
# Windows
start.bat
# 选择 7 - Check System Status

# Linux/Mac
./start.sh
# 选择 7 - Check System Status
```

#### 查看日志

```bash
# 查看主日志
tail -f logs/miya.log

# 查看特定模块日志
grep "ERROR" logs/miya.log
grep "DecisionHub" logs/miya.log
```

### 获取帮助

- 📖 查看文档: [docs/](docs/)
- 🐛 提交Issue: [GitHub Issues](https://github.com/Jia-520-only/Miya/issues)
- 💬 交流讨论: [GitHub Discussions](https://github.com/Jia-520-only/Miya/discussions)

---

## 📊 API文档

### Web API

弥娅提供RESTful API，支持第三方集成。

#### 启动API服务器

```bash
# 选择启动菜单中的选项3或5
start.bat
# 选择 3 - Start Web UI 或 5 - Start Runtime API
```

#### API端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/chat` | POST | 发送消息 | 可选 |
| `/api/terminal/create` | POST | 创建终端 | 必需 |
| `/api/terminal/execute` | POST | 执行命令 | 必需 |
| `/api/terminal/list` | GET | 终端列表 | 必需 |
| `/api/memory/query` | GET | 查询记忆 | 必需 |
| `/api/memory/add` | POST | 添加记忆 | 必需 |
| `/api/system/status` | GET | 系统状态 | 必需 |
| `/api/models/list` | GET | 模型列表 | 必需 |

#### 完整API文档

启动后访问：http://localhost:8000/docs

#### API示例

##### 聊天

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好弥娅",
    "session_id": "user_123"
  }'
```

响应：

```json
{
  "response": "你好！我是弥娅，很高兴见到你！",
  "session_id": "user_123",
  "model_used": "deepseek-chat",
  "tokens_used": 156
}
```

##### 创建终端

```bash
curl -X POST http://localhost:8000/api/terminal/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_key" \
  -d '{
    "name": "测试终端",
    "type": "powershell",
    "work_dir": "D:\\project"
  }'
```

响应：

```json
{
  "session_id": "a1b2c3d4",
  "name": "测试终端",
  "type": "powershell",
  "work_dir": "D:\\project",
  "status": "idle"
}
```

##### 执行命令

```bash
curl -X POST http://localhost:8000/api/terminal/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_key" \
  -d '{
    "session_id": "a1b2c3d4",
    "command": "dir"
  }'
```

响应：

```json
{
  "session_id": "a1b2c3d4",
  "command": "dir",
  "output": "Directory of D:\\project\n...",
  "exit_code": 0,
  "execution_time": 0.05
}
```

### WebSocket API

弥娅支持WebSocket实时通信。

#### 连接

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
  console.log('Connected to MIYA');

  // 发送消息
  ws.send(JSON.stringify({
    type: 'chat',
    message: '你好弥娅',
    session_id: 'user_123'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Response:', data.response);
};
```

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 贡献方式

1. **报告Bug** - 在Issues中提交详细的Bug报告
2. **提出建议** - 在Discussions中分享你的想法
3. **提交代码** - Fork项目，创建分支，提交PR
4. **改进文档** - 修正错误，完善文档
5. **分享使用经验** - 分享你的使用案例和技巧

### 开发流程

#### 1. Fork项目

```bash
# 在GitHub上Fork项目到你的账号
git clone https://github.com/your-username/Miya.git
cd Miya
```

#### 2. 创建分支

```bash
git checkout -b feature/your-feature-name
```

#### 3. 提交更改

```bash
git add .
git commit -m "Add your feature"
```

#### 4. 推送到Fork

```bash
git push origin feature/your-feature-name
```

#### 5. 创建Pull Request

在GitHub上创建Pull Request，描述你的更改。

### 代码规范

- 遵循PEP 8 Python代码规范
- 添加适当的注释和文档字符串
- 编写单元测试（如果有）
- 确保所有测试通过

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

```
MIT License

Copyright (c) 2024 Jia-520-only

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 致谢

感谢以下开源项目和社区：

- **[DeepSeek](https://github.com/deepseek-ai)** - 优秀的AI模型
- **[OpenAI](https://github.com/openai)** - GPT系列模型
- **[LangChain](https://github.com/langchain-ai/langchain)** - AI应用框架
- **[FastAPI](https://github.com/tiangolo/fastapi)** - 高性能Web框架
- **[React](https://github.com/facebook/react)** - 前端框架
- **[Electron](https://github.com/electron/electron)** - 桌面应用框架
- **[Live2D](https://www.live2d.com/)** - 虚拟形象技术

特别感谢所有贡献者和支持者！

---

## 📞 联系方式

- **GitHub**: [Jia-520-only/Miya](https://github.com/Jia-520-only/Miya)
- **Issues**: [GitHub Issues](https://github.com/Jia-520-only/Miya/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Jia-520-only/Miya/discussions)

---

## 🗺️ 路线图

### 已完成 ✅

- ✅ 多模型智能调度系统
- ✅ 四层记忆架构
- ✅ 多终端管理系统
- ✅ Web UI界面
- ✅ QQ机器人
- ✅ 桌面应用
- ✅ 权限管理系统
- ✅ 动态人格系统
- ✅ 工具调用系统

### 进行中 🚧

- 🚧 语音识别和合成
- 🚧 图像理解增强
- 🚧 多语言支持
- 🚧 移动端应用

### 计划中 📋

- 📋 自主学习能力
- 📋 多模态输入输出
- 📋 云端部署方案
- 📋 插件系统

---

<div align="center">

**如果弥娅对你有帮助，请给个⭐️Star支持一下！**

Made with ❤️ by [Jia-520-only](https://github.com/Jia-520-only)

</div>
