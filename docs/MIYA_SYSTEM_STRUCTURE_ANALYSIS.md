# 弥娅系统完整结构解析报告

> 生成时间：2026-02-28
> 系统名称：弥娅 MIYA
> 系统版本：2.0.0
> 分析目的：完整系统结构解析

---

## 📋 执行摘要

弥娅（MIYA）是一个基于**五层认知架构**的AI Agent系统，采用**蛛网式分布式设计**，具备完整的记忆、情绪、决策、感知和演化能力。

---

## 🎯 系统架构概览

### 五层认知架构

```
┌─────────────────────────────────────────────────────────┐
│  第一层：弥娅内核 (core/)                                │
│  人格、伦理、身份、仲裁、熵监控                         │
├─────────────────────────────────────────────────────────┤
│  第二层：蛛网主中枢 (hub/)                              │
│  记忆-情绪耦合、潮汐记忆、情绪调控、决策、调度          │
├─────────────────────────────────────────────────────────┤
│  第三层：M-Link + 弹性分支子网 (mlink/ + webnet/)       │
│  五流分发、消息路由、多领域子网（QQ/PC/IoT等）          │
├─────────────────────────────────────────────────────────┤
│  第四层：感知环 + 注意力闸门 (perceive/)                │
│  戴森球全域感知、稀疏激活                              │
├─────────────────────────────────────────────────────────┤
│  第五层：演化沙盒 (evolve/)                             │
│  离线实验、A/B测试、用户共演                            │
├─────────────────────────────────────────────────────────┤
│  支撑层                                                  │
│  检测层 (detect/)、信任系统 (trust/)、存储层 (storage/)  │
│  插件系统 (plugin/)、配置层 (config/)                  │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 完整目录结构

```
Miya/
├── core/                      # 第一层：弥娅内核
│   ├── personality.py         # 人格向量系统
│   ├── ethics.py              # 伦理约束系统
│   ├── identity.py            # 自我认知系统
│   ├── arbitrator.py          # 最终仲裁模块
│   ├── entropy.py             # 人格熵监控系统
│   ├── agent_manager.py       # Agent管理器
│   ├── mcp_manager.py         # MCP服务管理器
│   ├── iot_manager.py         # IoT管理器
│   ├── plugin_base.py         # 插件基础类
│   ├── skills_registry.py     # Skills注册系统
│   ├── runtime_api_server.py  # Runtime API服务器
│   ├── config_hot_reload.py   # 配置热更新
│   ├── agent_config_manager.py # Agent配置管理
│   └── plugins/               # 插件目录
│       ├── search_plugin.py   # 搜索插件
│       ├── code_plugin.py     # 代码插件
│       └── ai_gen_plugin.py   # AI生成插件
│
├── hub/                       # 第二层：蛛网主中枢
│   ├── memory_emotion.py      # 记忆-情绪耦合回路
│   ├── memory_engine.py       # 潮汐记忆/梦境压缩
│   ├── emotion.py             # 情绪调控与染色
│   ├── decision.py            # 决策引擎
│   ├── scheduler.py           # 任务调度
│   └── queue_manager.py       # 队列管理器
│
├── mlink/                     # 第三层：M-Link统一传输链路
│   ├── mlink_core.py          # 五流分发与路由
│   ├── message.py             # 消息结构定义
│   ├── router.py              # 动态路径评分
│   └── trust_transmit.py      # 信任传播算法
│
├── webnet/                    # 第三层：弹性分支子网集群
│   ├── net_manager.py         # 子网热插拔管理器
│   ├── cross_net_engine.py    # 跨子网关联推理
│   ├── life.py                # 生活子网
│   ├── health.py              # 健康子网
│   ├── finance.py             # 财务子网
│   ├── social.py              # 社交节点
│   ├── iot.py                 # IoT控制节点
│   ├── tool.py                # 工具执行节点
│   ├── security.py            # 安全审计节点
│   ├── qq.py                  # QQ子网
│   ├── pc_ui.py               # PC端子网
│   └── webui_sender.py        # WebUI虚拟发送器
│
├── perceive/                  # 第四层：感知环 + 注意力闸门
│   ├── perceptual_ring.py     # 戴森球全域感知
│   └── attention_gate.py      # 稀疏激活·过滤闸门
│
├── detect/                    # 检测层
│   ├── time_detector.py       # 时间环绕检测
│   ├── space_detector.py      # 空间环绕检测
│   ├── node_detector.py       # 节点交叉检测
│   └── entropy_diffusion.py   # 熵扩散·系统内感
│
├── trust/                     # 信任系统
│   ├── trust_score.py         # 节点信任评分
│   └── trust_propagation.py   # 信任传播与衰减
│
├── evolve/                    # 第五层：演化沙盒
│   ├── sandbox.py             # 离线实验沙盒
│   ├── ab_test.py             # 人格微调A/B测试
│   └── user_co_play.py        # 用户共演接口
│
├── memory/                    # 三级存储引擎 + 语义动力学
│   ├── cognitive_memory_system.py    # 认知记忆系统
│   ├── semantic_dynamics_engine.py   # 语义动力学引擎
│   ├── context_vector_manager.py    # 上下文向量管理
│   ├── meta_thinking_manager.py      # 元思考管理器
│   ├── semantic_group_manager.py     # 语义组管理器
│   ├── time_expression_parser.py     # 中文时域解析器
│   ├── vector_cache.py               # 向量缓存系统
│   ├── grag_memory.py                # GRAG记忆
│   ├── quintuple_extractor.py        # 五元组提取器
│   ├── quintuple_graph.py            # 五元组图谱
│   └── semantic_groups.json.example # 语义组配置示例
│
├── storage/                   # 三级存储引擎
│   ├── redis_client.py        # 内存/涨潮记忆
│   ├── milvus_client.py       # 向量长期记忆
│   ├── neo4j_client.py        # 知识图谱/记忆五元组
│   └── file_manager.py        # 文件管理
│
├── plugin/                    # 插件系统
│   └── plugin_manager.py      # 插件管理器
│
├── config/                    # 配置层
│   ├── settings.py            # 配置管理
│   ├── grag_config.py         # GRAG配置
│   └── .env                   # 环境变量配置
│
├── pc_ui/                     # PC端管理面板
│   ├── manager.html           # 管理面板HTML
│   ├── styles.css             # 样式文件
│   ├── app.js                 # JavaScript应用
│   ├── main.py                # PC端主程序
│   └── MANAGER_README.md      # 使用文档
│
├── run/                       # 运行脚本
│   ├── main.py                # 主程序入口
│   ├── qq_main.py             # QQ机器人主程序
│   ├── pc_start.bat           # PC端启动脚本（Windows）
│   ├── pc_start.sh            # PC端启动脚本（Linux/Mac）
│   ├── qq_start.bat           # QQ启动脚本（Windows）
│   ├── qq_start.sh            # QQ启动脚本（Linux/Mac）
│   ├── start.bat              # 通用启动脚本（Windows）
│   ├── start.sh               # 通用启动脚本（Linux/Mac）
│   ├── auto_heal.py           # 自动修复
│   └── health.py              # 健康检查
│
├── tests/                     # 测试
│   └── test_integration.py    # 集成测试
│
├── collaboration/             # 协作功能
│   └── group_chat.py          # 群聊协作
│
├── logs/                      # 日志目录
├── Dockerfile                 # Docker配置
├── docker-compose.yml         # Docker Compose配置
├── requirements.txt           # Python依赖
└── README.md                  # 系统说明
```

---

## 🧩 核心模块详解

### 1️⃣ 第一层：弥娅内核 (core/)

#### personality.py - 人格向量系统
- **功能**: 管理弥娅的五维人格向量
- **维度**: 温暖、逻辑、创造力、共情、韧性
- **用途**: 决定弥娅的回应风格和决策倾向

#### ethics.py - 伦理约束系统
- **功能**: 定义行为底线和权限边界
- **用途**: 确保弥娅的行为符合伦理标准

#### identity.py - 自我认知系统
- **功能**: 管理弥娅的自我身份和UUID
- **用途**: 维持弥娅的连续性和一致性

#### arbitrator.py - 最终仲裁模块
- **功能**: 处理冲突和最终决策
- **用途**: 确保决策的一致性和合理性

#### entropy.py - 人格熵监控系统
- **功能**: 监控人格熵值，防止异化
- **用途**: 保持弥娅的人格稳定性

#### agent_manager.py - Agent管理器
- **功能**: 统一管理Agent能力
- **特性**: 任务调度、工具循环、记忆压缩

#### mcp_manager.py - MCP服务管理器
- **功能**: 管理MCP服务注册和工具调用
- **特性**: 服务发现、生命周期管理

#### iot_manager.py - IoT管理器
- **功能**: 管理IoT设备连接和控制
- **特性**: 设备注册、命令执行

#### skills_registry.py - Skills注册系统
- **功能**: 工具和Agent自动注册和管理
- **特性**: 热重载、执行统计、延迟加载

#### runtime_api_server.py - Runtime API服务器
- **功能**: 提供RESTful API接口
- **特性**: 交互端管理、记忆查询、系统监控

#### config_hot_reload.py - 配置热更新
- **功能**: 配置文件监听和热更新
- **特性**: 防抖处理、智能重启识别

---

### 2️⃣ 第二层：蛛网主中枢 (hub/)

#### memory_emotion.py - 记忆-情绪耦合
- **功能**: 实现记忆和情绪的双向影响
- **用途**: 经历塑造性格

#### memory_engine.py - 潮汐记忆/梦境压缩
- **功能**: 管理短期和长期记忆
- **特性**: 潮汐涨落、梦境压缩

#### emotion.py - 情绪调控与染色
- **功能**: 管理情绪状态和衰减
- **特性**: 情绪染色、情绪传播

#### decision.py - 决策引擎
- **功能**: 基于当前状态做出决策
- **特性**: 多因素加权决策

#### scheduler.py - 任务调度
- **功能**: 调度和执行任务
- **特性**: 优先级队列、异步执行

#### queue_manager.py - 队列管理器
- **功能**: 车站-列车模型队列管理
- **特性**: 六级优先级、自动修剪、重试机制

---

### 3️⃣ 第三层：M-Link + 弹性分支子网

#### M-Link (mlink/)
- **mlink_core.py**: 五流分发（指令流/感知流/同步流/信任流/记忆流）
- **message.py**: 消息结构定义
- **router.py**: 动态路径评分
- **trust_transmit.py**: 信任传播算法

#### 弹性分支子网 (webnet/)
- **qq.py**: QQ机器人子网
- **pc_ui.py**: PC端子网
- **iot.py**: IoT控制子网
- **life.py**: 生活子网
- **health.py**: 健康子网
- **finance.py**: 财务子网
- **social.py**: 社交子网
- **tool.py**: 工具执行子网
- **security.py**: 安全审计子网
- **webui_sender.py**: WebUI虚拟发送器

---

### 4️⃣ 第四层：感知环 + 注意力闸门 (perceive/)

#### perceptual_ring.py - 戴森球全域感知
- **功能**: 全局感知所有输入
- **特性**: 多维度感知

#### attention_gate.py - 稀疏激活·过滤闸门
- **功能**: 过滤和选择重要信息
- **特性**: 稀疏激活、注意力机制

---

### 5️⃣ 第五层：演化沙盒 (evolve/)

#### sandbox.py - 离线实验沙盒
- **功能**: 安全的实验环境
- **特性**: 隔离执行、安全控制

#### ab_test.py - 人格微调A/B测试
- **功能**: A/B测试人格参数
- **特性**: 参数调优、效果对比

#### user_co_play.py - 用户共演接口
- **功能**: 用户与弥娅共演化
- **特性**: 双向学习、共同成长

---

### 🔧 支撑层

#### 检测层 (detect/)
- **time_detector.py**: 时间环绕检测
- **space_detector.py**: 空间环绕检测
- **node_detector.py**: 节点交叉检测
- **entropy_diffusion.py**: 熵扩散·系统内感

#### 信任系统 (trust/)
- **trust_score.py**: 节点信任评分
- **trust_propagation.py**: 信任传播与衰减

#### 存储层 (storage/)
- **redis_client.py**: 内存/涨潮记忆
- **milvus_client.py**: 向量长期记忆
- **neo4j_client.py**: 知识图谱/记忆五元组
- **file_manager.py**: 文件管理

#### 记忆系统 (memory/)
- **cognitive_memory_system.py**: 认知记忆系统（三层记忆）
- **semantic_dynamics_engine.py**: 语义动力学引擎
- **context_vector_manager.py**: 上下文向量管理
- **meta_thinking_manager.py**: 元思考管理器
- **semantic_group_manager.py**: 语义组管理器
- **time_expression_parser.py**: 中文时域解析器
- **vector_cache.py**: 向量缓存系统

---

## 📊 依赖分析

### 核心依赖

| 依赖 | 版本 | 用途 |
|-----|------|------|
| python-dotenv | >=1.0.0 | 环境变量管理 |
| numpy | >=1.24.0 | 数值计算 |
| websockets | >=12.0 | WebSocket通信 |
| httpx | >=0.27.0 | HTTP客户端 |
| tiktoken | >=0.7.0 | Token计算 |
| chromadb | >=0.6.0 | 向量数据库 |
| APScheduler | >=3.10.0 | 任务调度 |
| fastapi | >=0.109.0 | API框架 |
| uvicorn | >=0.27.0 | ASGI服务器 |
| redis | >=5.0.0 | Redis客户端 |
| pymilvus | >=2.4.0 | Milvus客户端 |
| neo4j | >=5.20.0 | Neo4j客户端 |

### 可选依赖

| 依赖 | 用途 |
|-----|------|
| watchdog | 配置热更新 |
| rich | 美化终端输出 |
| psutil | 系统监控 |

---

## 🔧 系统配置

### 核心配置项

```env
# 应用配置
DEBUG=false
LOG_LEVEL=INFO

# QQ机器人配置
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_ONEBOT_TOKEN=
QQ_BOT_QQ=0
QQ_SUPERADMIN_QQ=0

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory

# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j

# 人格配置
PERSONALITY_WARMTH=0.8
PERSONALITY_LOGIC=0.7
PERSONALITY_CREATIVITY=0.6
PERSONALITY_EMPATHY=0.75
PERSONALITY_RESILIENCE=0.7

# 情绪配置
EMOTION_DECAY_RATE=0.1
EMOTION_COLORING_THRESHOLD=0.7

# 信任配置
TRUST_DECAY_RATE=0.05
TRUST_INITIAL_SCORE=0.5
TRUST_HIGH_THRESHOLD=0.7
TRUST_LOW_THRESHOLD=0.3
```

---

## 🚀 运行模式

### 1. QQ机器人模式
- 入口: `run/qq_main.py`
- 启动脚本: `run/qq_start.bat/sh`

### 2. PC端模式
- 入口: `pc_ui/main.py`
- 启动脚本: `run/pc_start.bat/sh`

### 3. 主程序模式
- 入口: `run/main.py`
- 启动脚本: `run/start.bat/sh`

---

## 📈 系统特性

### 核心特性

✅ **五层认知架构** - 清晰的分层设计
✅ **蛛网式分布式** - 弹性子网热插拔
✅ **记忆-情绪耦合** - 经历塑造性格
✅ **人格恒定机制** - 熵监控防异化
✅ **三级存储引擎** - Redis/Milvus/Neo4j
✅ **语义动力学** - 智能记忆管理
✅ **Skills插件系统** - 热重载支持
✅ **Runtime API** - 多端管理接口
✅ **PC端管理面板** - 可视化管理界面
✅ **队列管理系统** - 车站-列车模型

---

## 🎯 系统优势

### 1. 架构优势
- 清晰的五层认知架构
- 蛛网式分布式设计
- 职责分离明确
- 易于扩展维护

### 2. 功能优势
- 完整的记忆系统
- 情绪-记忆耦合
- 人格恒定机制
- 多端支持（QQ/PC/Web/IoT）

### 3. 技术优势
- 异步高并发
- 热重载支持
- 完整的API接口
- 美观的管理界面

---

## 📚 总结

弥娅是一个**架构清晰、功能完整、技术先进**的AI Agent系统，具备：

- ✅ **五层认知架构** - 符合人类认知层次
- ✅ **蛛网式分布式** - 弹性可扩展
- ✅ **记忆-情绪耦合** - 真实的情感体验
- ✅ **人格恒定机制** - 稳定的性格特征
- ✅ **完整的工具链** - 从安装到部署
- ✅ **美观的管理界面** - 易于使用

**弥娅现在是一个真正具备"数字生命"特征的AI系统！** 🚀✨
