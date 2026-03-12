# 弥娅（Miya）配置指南

> 版本: 1.0.0  
> 最后更新: 2026-03-10

本文档详细说明弥娅系统的所有配置项，包括环境变量、模型配置、权限配置等。

---

## 目录

1. [配置文件概览](#1-配置文件概览)
2. [环境变量配置 (.env)](#2-环境变量配置-env)
3. [多模型配置 (multi_model_config.json)](#3-多模型配置-multi_model_configjson)
4. [权限配置](#4-权限配置)
5. [终端工具配置](#5-终端工具配置)
6. [人格和情绪配置](#6-人格和情绪配置)
7. [数据库配置](#7-数据库配置)
8. [日志配置](#8-日志配置)
9. [API配置](#9-api配置)
10. [常见配置问题](#10-常见配置问题)

---

## 1. 配置文件概览

弥娅系统使用多种配置文件，位于 `config/` 目录：

```
config/
├── .env                          # 主配置文件（环境变量）
├── multi_model_config.json       # 多模型配置
├── terminal_config.json         # 终端工具配置
├── settings.py                   # Python配置类
└── auth/                         # 权限配置目录
    ├── users.json                # 用户配置
    └── groups.json               # 用户组配置
```

### 配置文件优先级

1. 环境变量（最高优先级）
2. `.env` 文件
3. `settings.py` 默认值

---

## 2. 环境变量配置 (.env)

### 2.1 应用基础配置

```bash
# 应用信息
APP_NAME=Miya
APP_VERSION=1.0.0

# 调试模式
DEBUG=false
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### 2.2 AI模型配置

**重要**：这是AI模型的核心配置！

#### DeepSeek 配置（主要推荐）

```bash
# DeepSeek API 配置
DEEPSEEK_API_KEY=sk-15346aa170c442c69d726d8e95cabca3
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

#### 硅基流动配置（快速、低成本）

```bash
# 硅基流动 API 配置
SILICONFLOW_API_KEY=sk-lbybyiqrbaxasvwmspsoxulfkrprzibertsjanyaurcxbird
SILICONFLOW_API_BASE=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen2.5-7B-Instruct
```

#### OpenAI 配置（可选）

```bash
# OpenAI API 配置
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

#### AI通用参数

```bash
# AI 参数配置
AI_TEMPERATURE=0.7        # 温度：0.0-2.0，越高越随机
AI_MAX_TOKENS=2000        # 最大生成token数
AI_TIMEOUT=60             # API超时时间（秒）
AI_MAX_RETRIES=3          # 最大重试次数
```

### 2.3 数据库配置

#### Redis 配置

```bash
# Redis 配置（潮汐记忆）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=10
REDIS_SOCKET_TIMEOUT=5
```

#### Milvus 配置

```bash
# Milvus 配置（向量记忆）
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory
MILVUS_DIMENSION=1536
MILVUS_INDEX_TYPE=IVF_FLAT
```

#### Neo4j 配置

```bash
# Neo4j 配置（知识图谱）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

### 2.4 人格和情绪配置

```bash
# 人格向量初始值（0.0-1.0）
PERSONALITY_WARMTH=0.8      # 温暖度
PERSONALITY_LOGIC=0.7       # 逻辑性
PERSONALITY_CREATIVITY=0.6  # 创造力
PERSONALITY_EMPATHY=0.75    # 同理心
PERSONALITY_RESILIENCE=0.7  # 韧性

# 情绪系统配置
EMOTION_DECAY_RATE=0.1              # 情绪衰减率
EMOTION_COLORING_THRESHOLD=0.7      # 情绪染色阈值
EMOTION_MAX_INTENSITY=1.0           # 最大情绪强度
```

### 2.5 信任系统配置

```bash
# 信任系统配置
TRUST_DECAY_RATE=0.05         # 信任衰减率
TRUST_INITIAL_SCORE=0.5        # 初始信任分数
TRUST_HIGH_THRESHOLD=0.7      # 高信任阈值
TRUST_LOW_THRESHOLD=0.3       # 低信任阈值
```

### 2.6 记忆系统配置

```bash
# 记忆系统配置
MEMORY_TIDE_TTL=3600                  # 潮汐记忆TTL（秒）
MEMORY_DREAM_THRESHOLD=100           # 梦境压缩阈值
MEMORY_MAX_MEMORIES_PER_USER=1000     # 每用户最大记忆数
MEMORY_AUTO_EXTRACT=true              # 自动提取记忆
```

### 2.7 感知系统配置

```bash
# 感知系统配置
PERCEPTION_ACTIVATION_RATE=0.3         # 激活率
PERCEPTION_INTENSITY_THRESHOLD=0.5     # 感知强度阈值
PERCEPTION_UPDATE_INTERVAL=1.0         # 更新间隔（秒）
```

### 2.8 演化系统配置

```bash
# 演化系统配置
SANDBOX_ENABLED=true          # 沙箱模式
AB_TEST_ENABLED=true          # A/B测试
EVOLUTION_RATE=0.1            # 演化率
MAX_EVOLUTION_STEPS=100        # 最大演化步数
```

### 2.9 QQ机器人配置

```bash
# QQ机器人配置
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_ONEBOT_TOKEN=
QQ_BOT_QQ=1234567890
QQ_SUPERADMIN_QQ=9876543210

# 群组白名单/黑名单
QQ_GROUP_WHITELIST=123456,789012
QQ_GROUP_BLACKLIST=345678

# 用户白名单/黑名单
QQ_USER_WHITELIST=123456,789012
QQ_USER_BLACKLIST=345678
```

### 2.10 LifeBook 配置

```bash
# LifeBook 记忆管理配置
LIFEBOOK_ENABLED=true
LIFEBOOK_BASE_DIR=data/lifebook
LIFEBOOK_AUTO_SUMMARY=false
LIFEBOOK_DEFAULT_MONTHS_BACK=1
```

### 2.11 Web API 配置

```bash
# Web API 配置
WEB_HOST=0.0.0.0
WEB_PORT=8000
WEB_CORS_ORIGINS=*
WEB_SECRET_KEY=your-secret-key-here
WEB_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 2.12 检测系统配置

```bash
# 检测系统配置
DETECTION_TIME_THRESHOLD=3600        # 时间循环阈值（秒）
DETECTION_SPACE_THRESHOLD=1.0        # 空间距离阈值
DETECTION_ENABLED=true               # 启用检测
```

---

## 3. 多模型配置 (multi_model_config.json)

**重要**：这是多模型智能调度的核心配置文件！

### 3.1 配置文件结构

```json
{
  "models": {
    "chinese": {
      "name": "deepseek-chat",
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-15346aa170c442c69d726d8e95cabca3",
      "capabilities": [...],
      "cost_per_1k_tokens": {...},
      "latency": "fast",
      "quality": "excellent"
    },
    "fast": {...},
    "chat": {...},
    "reasoning": {...},
    "code": {...}
  },
  "routing_strategy": {
    "simple_chat": {...},
    "complex_reasoning": {...},
    "code_generation": {...}
  },
  "budget_control": {...},
  "performance_settings": {...}
}
```

### 3.2 模型定义

#### chinese 模型（中文优化）

```json
{
  "name": "deepseek-chat",
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com/v1",
  "api_key": "sk-15346aa170c442c69d726d8e95cabca3",
  "capabilities": [
    "simple_chat",
    "chinese_understanding",
    "task_planning",
    "tool_calling"
  ],
  "cost_per_1k_tokens": {
    "input": 0.00014,
    "output": 0.00028
  },
  "latency": "fast",
  "quality": "excellent"
}
```

**说明：**
- `name`: 模型名称
- `provider`: 提供商（deepseek, openai, anthropic, zhipu）
- `base_url`: API基础URL
- `api_key`: API密钥
- `capabilities`: 模型能力列表
- `cost_per_1k_tokens`: 每1000 token成本
- `latency`: 延迟等级（fast, medium, slow）
- `quality`: 质量等级（excellent, good, fair）

#### fast 模型（快速响应）

```json
{
  "name": "Qwen/Qwen2.5-7B-Instruct",
  "provider": "openai",
  "base_url": "https://api.siliconflow.cn/v1",
  "api_key": "sk-lbybyiqrbaxasvwmspsoxulfkrprzibertsjanyaurcxbird",
  "capabilities": [
    "simple_chat",
    "summarization",
    "task_classification"
  ],
  "cost_per_1k_tokens": {
    "input": 0.0001,
    "output": 0.0002
  },
  "latency": "fast",
  "quality": "excellent"
}
```

#### chat 模型（工具调用优化）

```json
{
  "name": "deepseek-chat",
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com/v1",
  "api_key": "sk-15346aa170c442c69d726d8e95cabca3",
  "capabilities": [
    "tool_calling",
    "multimodal",
    "code_analysis"
  ],
  "cost_per_1k_tokens": {
    "input": 0.00014,
    "output": 0.00028
  },
  "latency": "fast",
  "quality": "excellent"
}
```

#### reasoning 模型（复杂推理）

```json
{
  "name": "deepseek-chat",
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com/v1",
  "api_key": "sk-15346aa170c442c69d726d8e95cabca3",
  "capabilities": [
    "complex_reasoning",
    "code_analysis",
    "creative_writing"
  ],
  "cost_per_1k_tokens": {
    "input": 0.00014,
    "output": 0.00028
  },
  "latency": "fast",
  "quality": "excellent"
}
```

#### code 模型（代码生成）

```json
{
  "name": "deepseek-chat",
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com/v1",
  "api_key": "sk-15346aa170c442c69d726d8e95cabca3",
  "capabilities": [
    "code_generation",
    "code_analysis"
  ],
  "cost_per_1k_tokens": {
    "input": 0.00014,
    "output": 0.00028
  },
  "latency": "fast",
  "quality": "excellent"
}
```

### 3.3 路由策略

路由策略定义了不同任务类型应该使用哪个模型。

#### simple_chat 策略

```json
{
  "simple_chat": {
    "primary": "fast",
    "fallback": "chinese",
    "cost_priority": 1.0,
    "speed_priority": 0.9,
    "quality_priority": 0.7
  }
}
```

**说明：**
- `primary`: 首选模型
- `fallback`: 回退模型
- `secondary`: 次选模型
- `cost_priority`: 成本优先级（0.0-1.0）
- `speed_priority`: 速度优先级（0.0-1.0）
- `quality_priority`: 质量优先级（0.0-1.0）

#### complex_reasoning 策略

```json
{
  "complex_reasoning": {
    "primary": "reasoning_pro",
    "fallback": "reasoning",
    "cost_priority": 0.5,
    "speed_priority": 0.4,
    "quality_priority": 1.0
  }
}
```

#### code_analysis 策略

```json
{
  "code_analysis": {
    "primary": "reasoning",
    "secondary": "code",
    "cost_priority": 0.6,
    "speed_priority": 0.7,
    "quality_priority": 0.9
  }
}
```

#### code_generation 策略

```json
{
  "code_generation": {
    "primary": "code",
    "fallback": "reasoning",
    "cost_priority": 0.2,
    "speed_priority": 0.8,
    "quality_priority": 0.85
  }
}
```

#### tool_calling 策略

```json
{
  "tool_calling": {
    "primary": "chat",
    "fallback": "reasoning",
    "cost_priority": 0.8,
    "speed_priority": 0.6,
    "quality_priority": 0.95
  }
}
```

#### creative_writing 策略

```json
{
  "creative_writing": {
    "primary": "reasoning_pro",
    "secondary": "reasoning",
    "cost_priority": 0.5,
    "speed_priority": 0.4,
    "quality_priority": 1.0
  }
}
```

#### chinese_understanding 策略

```json
{
  "chinese_understanding": {
    "primary": "chinese",
    "fallback": "fast",
    "cost_priority": 0.1,
    "speed_priority": 0.9,
    "quality_priority": 0.85
  }
}
```

#### summarization 策略

```json
{
  "summarization": {
    "primary": "fast",
    "fallback": "chat",
    "cost_priority": 0.2,
    "speed_priority": 0.8,
    "quality_priority": 0.9
  }
}
```

#### multimodal 策略

```json
{
  "multimodal": {
    "primary": "chat",
    "fallback": "reasoning_pro",
    "cost_priority": 1.0,
    "speed_priority": 0.5,
    "quality_priority": 1.0
  }
}
```

#### task_planning 策略

```json
{
  "task_planning": {
    "primary": "chinese",
    "secondary": "chat",
    "cost_priority": 0.3,
    "speed_priority": 0.7,
    "quality_priority": 0.9
  }
}
```

### 3.4 预算控制

```json
{
  "budget_control": {
    "daily_budget_usd": 10.0,
    "monthly_budget_usd": 300.0,
    "alert_threshold": 0.8,
    "stop_threshold": 0.95
  }
}
```

**说明：**
- `daily_budget_usd`: 每日预算（美元）
- `monthly_budget_usd`: 每月预算（美元）
- `alert_threshold`: 预算警告阈值（0.0-1.0）
- `stop_threshold`: 预算停止阈值（0.0-1.0）

### 3.5 性能设置

```json
{
  "performance_settings": {
    "enable_caching": true,
    "cache_ttl_seconds": 3600,
    "enable_parallel_execution": true,
    "max_parallel_models": 3,
    "consensus_threshold": 0.7
  }
}
```

**说明：**
- `enable_caching`: 启用缓存
- `cache_ttl_seconds`: 缓存TTL（秒）
- `enable_parallel_execution`: 启用并行执行
- `max_parallel_models`: 最大并行模型数
- `consensus_threshold`: 共识阈值（0.0-1.0）

---

## 4. 权限配置

### 4.1 用户配置 (users.json)

```json
{
  "users": [
    {
      "user_id": "qq_123456",
      "username": "test_user",
      "platform": "qq",
      "permission_groups": ["Default", "VIP"],
      "permissions": ["tool.web_search"],
      "created_at": "2024-01-01T00:00:00"
    },
    {
      "user_id": "terminal_root",
      "username": "root",
      "platform": "terminal",
      "permission_groups": ["Admin"],
      "permissions": ["*"],
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

**说明：**
- `user_id`: 唯一用户ID（格式：`{platform}_{platform_user_id}`）
- `username`: 用户名
- `platform`: 平台（qq, web, terminal, desktop）
- `permission_groups`: 用户组列表
- `permissions`: 直接权限列表
- `created_at`: 创建时间

### 4.2 用户组配置 (groups.json)

```json
{
  "groups": {
    "Default": {
      "description": "默认用户组",
      "permissions": [
        "tool.web_search",
        "agent.chat"
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
      "permissions": [
        "*"
      ]
    }
  }
}
```

**说明：**
- `Default`: 默认用户组
- `VIP`: VIP用户组
- `Admin`: 管理员组（拥有所有权限）

### 4.3 权限节点

**权限节点格式：**

```
{模块}.{操作}.{子操作}
```

**常用权限节点：**

```
# 工具权限
tool.web_search              # Web搜索工具
tool.terminal_command        # 终端命令工具
tool.file_read               # 文件读取
tool.file_write              # 文件写入
tool.*                       # 所有工具

# Agent权限
agent.chat                   # 聊天Agent
agent.code                   # 代码Agent
agent.*                      # 所有Agent

# Web API权限
web.api.access               # Web API访问
web.blog.read                # 博客读取
web.blog.write               # 博客写入

# 系统权限
system_admin                # 系统管理员
*                            # 所有权限（超级管理员）
```

**权限检查优先级：**

1. 超级管理员（`*`）- 最高优先级
2. 精确拒绝（例如：`-tool.web_search`）
3. 精确允许（例如：`tool.web_search`）
4. 父级权限（例如：`tool.*` 匹配 `tool.web_search`）
5. 默认拒绝

---

## 5. 终端工具配置

### 5.1 terminal_config.json

```json
{
  "security_level": "safe",
  "max_execution_time": 30,
  "enable_history": true,
  "history_size": 100,
  "whitelist": [
    "ls", "dir", "pwd", "cd",
    "cat", "head", "tail",
    "cp", "mv", "rm",
    "mkdir", "rmdir",
    "python", "python3", "node", "npm",
    "git", "docker", "docker-compose"
  ],
  "blacklist": [
    "rm -rf /",
    "del /F /Q",
    "format",
    "shutdown",
    "reboot"
  ],
  "allowed_paths": [
    "/",
    "/home",
    "/tmp",
    "C:\\",
    "C:\\Users"
  ]
}
```

**说明：**
- `security_level`: 安全等级（safe, moderate, risky）
- `max_execution_time`: 最大执行时间（秒）
- `enable_history`: 启用历史记录
- `history_size`: 历史记录大小
- `whitelist`: 白名单命令
- `blacklist`: 黑名单命令
- `allowed_paths`: 允许访问的路径

### 5.2 跨平台命令映射

系统会自动将Unix命令转换为Windows命令：

| Unix命令 | Windows命令 |
|---------|-----------|
| `ls` | `Get-ChildItem` |
| `pwd` | `Get-Location` |
| `cat` | `Get-Content` |
| `rm` | `Remove-Item` |
| `cp` | `Copy-Item` |
| `mv` | `Move-Item` |

---

## 6. 人格和情绪配置

### 6.1 人格配置 (prompts/miya_personality.json)

```json
{
  "personality_vector": {
    "warmth": 0.8,
    "logic": 0.7,
    "creativity": 0.6,
    "empathy": 0.75,
    "resilience": 0.7
  },
  "traits": [
    {
      "name": "高冷温柔",
      "description": "外表高冷，内心温柔",
      "triggers": ["陌生人", "正式场合"]
    },
    {
      "name": "活泼可爱",
      "description": "活泼开朗，可爱友善",
      "triggers": ["朋友", "轻松场合"]
    }
  ],
  "system_prompt": "你是弥娅，一个数据生命体...",
  "system_prompt_full": "你是弥娅，一个数据生命体..."
}
```

### 6.2 情绪配置

情绪系统通过 `.env` 配置：

```bash
# 情绪衰减率
EMOTION_DECAY_RATE=0.1

# 情绪染色阈值
EMOTION_COLORING_THRESHOLD=0.7

# 最大情绪强度
EMOTION_MAX_INTENSITY=1.0
```

---

## 7. 数据库配置

### 7.1 Redis配置

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=10
```

**Docker启动Redis：**

```bash
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:latest
```

### 7.2 Milvus配置

```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=miya_memory
MILVUS_DIMENSION=1536
```

**Docker启动Milvus：**

```bash
docker-compose -f docker-compose.milvus.yml up -d
```

### 7.3 Neo4j配置

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

**Docker启动Neo4j：**

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

---

## 8. 日志配置

### 8.1 日志级别

```bash
LOG_LEVEL=INFO
```

**日志级别：**
- `DEBUG`: 详细调试信息
- `INFO`: 一般信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

### 8.2 日志目录

```bash
LOG_DIR=logs
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=10
```

---

## 9. API配置

### 9.1 Web API配置

```bash
WEB_HOST=0.0.0.0
WEB_PORT=8000
WEB_CORS_ORIGINS=*
WEB_SECRET_KEY=your-secret-key-here
WEB_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 9.2 QQ机器人配置

```bash
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_ONEBOT_TOKEN=
QQ_BOT_QQ=1234567890
QQ_SUPERADMIN_QQ=9876543210
```

---

## 10. 常见配置问题

### Q1: 模型配置文件在哪里？

**A**: 模型配置文件是 `config/multi_model_config.json`。这个文件定义了所有模型、路由策略、预算控制等。

### Q2: 如何添加新的AI模型？

**A**: 在 `multi_model_config.json` 的 `models` 节点中添加：

```json
{
  "models": {
    "my_model": {
      "name": "gpt-4",
      "provider": "openai",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your-api-key",
      "capabilities": ["simple_chat", "reasoning"],
      "cost_per_1k_tokens": {
        "input": 0.03,
        "output": 0.06
      },
      "latency": "medium",
      "quality": "excellent"
    }
  }
}
```

### Q3: 如何修改模型路由策略？

**A**: 在 `multi_model_config.json` 的 `routing_strategy` 节点中修改：

```json
{
  "routing_strategy": {
    "simple_chat": {
      "primary": "my_model",
      "fallback": "fast",
      "cost_priority": 0.5,
      "speed_priority": 0.8,
      "quality_priority": 0.9
    }
  }
}
```

### Q4: 如何给用户添加权限？

**A**: 在 `data/auth/users.json` 中添加用户，在 `data/auth/groups.json` 中配置用户组权限。

### Q5: 如何启用终端工具？

**A**: 确保 `config/terminal_config.json` 存在，并且用户有 `tool.terminal_command` 权限。

### Q6: 数据库配置失败怎么办？

**A**: 数据库是可选的。如果连接失败，系统会自动降级到模拟模式，核心功能不受影响。

### Q7: 如何重置配置？

**A**: 删除 `config/.env` 文件，系统会使用默认配置。

### Q8: 如何查看当前配置？

**A**: 启动系统后，输入 `status` 或 `状态` 查看系统状态和配置信息。

---

## 总结

弥娅系统的配置非常灵活，支持：

1. **多模型智能调度** - 通过 `multi_model_config.json` 配置
2. **细粒度权限控制** - 通过 `users.json` 和 `groups.json` 配置
3. **跨平台命令适配** - 自动适配不同操作系统的命令
4. **动态人格演化** - 通过人格向量配置
5. **多种数据库支持** - Redis、Milvus、Neo4j

如需进一步了解，请参考：
- [系统分析文档](MIYA_SYSTEM_ANALYSIS.md)
- [README](README.md)
- [多模型快速开始](MULTI_MODEL_QUICK_START.md)
