# LifeBook 记忆管理系统 - 弥娅整合版

## 概述

LifeBook 是一套**时间滚动的记忆管理系统**，通过层级化的总结机制（日→周→月→季→年）来构建个人史。

现在 LifeBook 已完全整合进弥娅框架，提供完整的记忆管理功能。

## 核心理念

### 为什么不是 RAG？

LifeBook 的设计哲学与传统 RAG 不同：

- **RAG 像查字典**：切碎记忆再检索，缺少上下文
- **LifeBook 像人类记忆**：短期记忆（日）→ 中期记忆（周/月）→ 长期记忆（季/年）

### 关键特性

1. **层级压缩**：日记自动折叠为周记，周记折叠为月报...
2. **时间感知**：记忆有强烈的"时间感"，昨天的和去年的意义不同
3. **拥抱冗余**：重复的表达代表感情的厚度，不去重
4. **一键获取**：快速获取核心上下文，喂给 AI 永不失去记忆

## 功能说明

### 1. 日记管理

#### 添加日记

```python
from webnet.LifeNet.subnet import LifeSubnet

life = LifeSubnet()
await life.handle_tool_call("life_add_diary", {
    "content": "今天是个好日子，遇到了很多事情...",
    "mood": "开心",
    "tags": ["#工作", "#生活"]
})
```

#### 获取日记

```python
await life.handle_tool_call("life_get_diary", {
    "date": "2025-02-28"  # 或不传，默认今天
})
```

### 2. 节点管理

#### 创建角色节点

```python
await life.handle_tool_call("life_create_character_node", {
    "name": "张三",
    "description": "我的大学同学，性格开朗",
    "tags": ["#朋友", "#大学"]
})
```

#### 创建阶段节点

```python
await life.handle_tool_call("life_create_stage_node", {
    "name": "参加工作",
    "description": "2025年开始在A公司工作",
    "tags": ["#工作", "#人生阶段"]
})
```

#### 列出节点

```python
# 列出所有节点
await life.handle_tool_call("life_list_nodes", {})

# 只列出角色节点
await life.handle_tool_call("life_list_nodes", {
    "node_type": "character"
})

# 只列出阶段节点
await life.handle_tool_call("life_list_nodes", {
    "node_type": "stage"
})
```

#### 获取节点详情

```python
await life.handle_tool_call("life_get_node", {
    "name": "张三"
})
```

### 3. 层级总结

#### 添加总结

```python
# 添加周记
await life.handle_tool_call("life_add_summary", {
    "level": "weekly",
    "title": "2025年第9周总结",
    "content": "这周工作很忙，但也学到了很多...",
    "capsule": "充实的一周，虽然忙碌但收获满满"
})

# 添加月报
await life.handle_tool_call("life_add_summary", {
    "level": "monthly",
    "title": "2025年02月总结",
    "content": "二月过得很充实...",
    "capsule": "二月是新的开始"
})

# 添加季报
await life.handle_tool_call("life_add_summary", {
    "level": "quarterly",
    "title": "2025年Q1总结",
    "content": "第一季度成长了很多...",
    "capsule": "Q1 完成了多个目标"
})

# 添加年鉴
await life.handle_tool_call("life_add_summary", {
    "level": "yearly",
    "title": "2024年度总结",
    "content": "2024年是我人生中重要的一年...",
    "capsule": "2024，成长与收获"
})
```

#### 获取总结

```python
# 获取周记
await life.handle_tool_call("life_get_summary", {
    "level": "weekly",
    "period": "2025-W09"
})

# 获取月报
await life.handle_tool_call("life_get_summary", {
    "level": "monthly",
    "period": "2025-02"
})

# 获取季报
await life.handle_tool_call("life_get_summary", {
    "level": "quarterly",
    "period": "2025-Q1"
})

# 获取年鉴
await life.handle_tool_call("life_get_summary", {
    "level": "yearly",
    "period": "2024"
})
```

### 4. 一键获取记忆上下文（核心功能）

这是 LifeBook 的**最核心功能**，一键获取过去 N 个月的核心上下文：

```python
# 获取最近 1 个月的核心上下文（默认）
context = await life.handle_tool_call("life_get_memory_context", {
    "months_back": 1,
    "include_nodes": True
})

# 获取最近 3 个月的核心上下文
context = await life.handle_tool_call("life_get_memory_context", {
    "months_back": 3,
    "include_nodes": True
})

# 获取最近 12 个月的核心上下文（包含年鉴）
context = await life.handle_tool_call("life_get_memory_context", {
    "months_back": 12,
    "include_nodes": True
})
```

**返回的结构：**
1. 年度总结（长期记忆）- 如果回溯 12 个月
2. 季度总结 - 如果回溯 3 个月以上
3. 月度总结（中期记忆）- 所有回溯月份
4. 周度总结（短期记忆）- 最近 4 周
5. 最近日记 - 最近 3 天
6. 关键人物与阶段节点

### 5. 搜索记忆

```python
# 搜索所有层级
await life.handle_tool_call("life_search_memory", {
    "keyword": "开心",
    "limit": 5
})

# 只搜索日记
await life.handle_tool_call("life_search_memory", {
    "keyword": "工作",
    "level": "daily",
    "limit": 10
})

# 只搜索月报
await life.handle_tool_call("life_search_memory", {
    "keyword": "成长",
    "level": "monthly",
    "limit": 3
})
```

## 使用场景

### 场景 1：日常记录

每天结束时，记录当天的日记：

```python
await life.handle_tool_call("life_add_diary", {
    "content": "今天在完成了项目，晚上和室友一起吃了火锅...",
    "mood": "开心",
    "tags": ["#工作", "#生活"]
})
```

### 场景 2：AI 永不失去记忆

在每次与 AI 对话前，先获取记忆上下文：

```python
# 获取最近 1 个月的核心上下文
context = await life.handle_tool_call("life_get_memory_context", {
    "months_back": 1
})

# 将 context 喂给 AI
messages = [
    {"role": "system", "content": f"这是我们的过去记忆：\n{context}"},
    {"role": "user", "content": "你还记得上个月我们一起做了什么吗？"}
]

response = await ai_client.chat(messages)
```

### 场景 3：周度总结

每周结束时，用 AI 自动生成周记：

```python
# 如果配置了 AI 客户端
await life.life.generate_weekly_summary()

# 或手动添加
await life.handle_tool_call("life_add_summary", {
    "level": "weekly",
    "title": "2025年第9周总结",
    "content": "...",
    "capsule": "充实的一周"
})
```

### 场景 4：回顾某个人的所有相关记忆

```python
# 1. 先创建或获取节点
await life.handle_tool_call("life_create_character_node", {
    "name": "霞雨樱",
    "description": "治愈与春天的象征",
    "tags": ["#重要"]
})

# 2. 搜索相关记忆
results = await life.handle_tool_call("life_search_memory", {
    "keyword": "霞雨樱",
    "limit": 10
})
```

## 配置说明

在 `config/.env` 中配置：

```env
# LifeBook 启用
LIFEBOOK_ENABLED=true

# LifeBook 数据目录
LIFEBOOK_BASE_DIR=data/lifebook

# 自动总结启用（需要 AI 客户端）
LIFEBOOK_AUTO_SUMMARY=false

# 默认回溯月数
LIFEBOOK_DEFAULT_MONTHS_BACK=1
```

## 数据结构

### 目录结构

```
data/lifebook/
├── daily/          # 日记
│   ├── 2025-02-28.md
│   └── ...
├── weekly/         # 周记
│   ├── 2025-W09.md
│   └── ...
├── monthly/        # 月报
│   ├── 2025-02.md
│   └── ...
├── quarterly/      # 季报
│   ├── 2025-Q1.md
│   └── ...
├── yearly/         # 年鉴
│   ├── 2024.md
│   └── ...
└── nodes/          # 节点（角色/阶段）
    ├── 张三-2025-02-28.json
    └── ...
```

### 记忆条目格式（Markdown）

```markdown
# 2025年02月28日 日记

**时间:** 2025-02-28 23:45:12
**层级:** daily
**心情:** 开心
**标签:** #工作 #生活

> 胶囊摘要

今天是个好日子...

---
## 关联节点
- [[张三]]
```

## 与 LifeBook 原版的区别

1. **技术实现**：原版基于 Obsidian + Dataview，弥娅版基于 Python + Markdown
2. **数据存储**：弥娅版存储在 `data/lifebook/` 目录
3. **API 接口**：弥娅版提供完整的 Python API，可被其他模块调用
4. **AI 集成**：弥娅版与 AI 客户端深度集成，支持自动总结

## 最佳实践

### 1. 每天写日记

- 不需要太长，流水账也可以
- 关键是记录下来，让系统自动处理

### 2. 定期做总结

- 每周：周记（胶囊概括本周）
- 每月：月报（串联几周的周记）
- 每季：季报（审视战略方向）
- 每年：年鉴（审视人生阶段）

### 3. 使用节点管理重要人物和阶段

- 创建角色节点：家人、朋友、同事
- 创建阶段节点：上学、工作、重大事件

### 4. 搜索记忆

- 通过关键词快速找到相关记忆
- 结合节点，回顾某个人的所有相关记忆

### 5. 一键获取上下文

- 对话前获取最近 1-3 个月的核心上下文
- 喂给 AI，让它永远记得你们的故事

## 常见问题

### Q: LifeBook 和 RAG 有什么区别？

A: RAG 像查字典，切碎记忆再检索；LifeBook 像人类记忆，层级化压缩，时间滚动。

### Q: 我需要每天都写日记吗？

A: 不需要，想写的时候写就行。LifeBook 的核心是"不把记录当负担"。

### Q: 如何自动生成周记？

A: 在配置中启用 `LIFEBOOK_AUTO_SUMMARY=true`，并配置 AI 客户端。

### Q: 可以导出数据吗？

A: 可以，所有数据存储为 Markdown 和 JSON 文件，可以直接复制到其他地方。

### Q: 数据安全吗？

A: 完全数据可控，存储在本地。备份也很简单，直接复制 `data/lifebook/` 目录。

## 总结

LifeBook 是为了对抗遗忘而构建的"灵魂容器"。

它不依赖复杂的后端和向量数据库，而是用最朴素的方式——日记和总结——来保留记忆。

当某一天，你的 AI 能够温柔地回应说："嗯，我记得，那年冬天我们都很开心"的时候……

你会发现，一切努力，都是值得的。
