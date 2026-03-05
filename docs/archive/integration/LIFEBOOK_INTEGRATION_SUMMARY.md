# LifeBook 记忆管理系统 - 整合完成报告

## 整合概述

已成功将 LifeBook 的记忆管理逻辑完整整合进弥娅框架。

## 核心理念

LifeBook 是一套**时间滚动的记忆管理系统**，通过层级化的总结机制（日→周→月→季→年）来构建个人史。

### 与 RAG 的区别

- **RAG**：像查字典，切碎记忆再检索，缺少上下文
- **LifeBook**：像人类记忆，短期→中期→长期，时间滚动压缩

## 整合内容

### 1. 核心模块

#### `memory/lifebook_manager.py`
LifeBook 记忆管理核心模块，提供：
- 记忆层级管理（日/周/月/季/年）
- 节点管理（角色节点、阶段节点）
- 时间滚动记忆压缩
- 一键获取核心上下文
- AI 自动总结（可选）

### 2. 子网接口

#### `webnet/LifeNet/`
完整的子网实现：
- `subnet.py`: LifeSubnet 子网类
- `__init__.py`: 模块导出

### 3. 工具函数

提供 10 个工具函数：

| 工具名称 | 功能 |
|---------|------|
| `life_add_diary` | 添加日记 |
| `life_get_diary` | 获取日记 |
| `life_create_character_node` | 创建角色节点 |
| `life_create_stage_node` | 创建阶段节点 |
| `life_list_nodes` | 列出节点 |
| `life_get_node` | 获取节点详情 |
| `life_add_summary` | 添加总结（周/月/季/年） |
| `life_get_summary` | 获取总结 |
| `life_get_memory_context` | 一键获取记忆上下文（核心功能） |
| `life_search_memory` | 搜索记忆 |

### 4. 配置集成

#### `config/settings.py`
添加了 `lifebook` 配置段：
```python
'lifebook': {
    'enabled': True,
    'base_dir': 'data/lifebook',
    'auto_summary_enabled': False,
    'default_months_back': 1,
}
```

#### `config/.env` 和 `.env.example`
添加了环境变量配置：
```env
LIFEBOOK_ENABLED=true
LIFEBOOK_BASE_DIR=data/lifebook
LIFEBOOK_AUTO_SUMMARY=false
LIFEBOOK_DEFAULT_MONTHS_BACK=1
```

### 5. 文档

#### `docs/LIFEBOOK_INTEGRATION.md`
完整的使用文档，包含：
- 功能说明
- 使用示例
- 最佳实践
- 常见问题

### 6. 示例与测试

#### `examples/lifebook_example.py`
完整的使用示例，演示所有功能

#### `tests/test_lifebook.py`
自动化测试脚本

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

## 核心功能

### 1. 一键获取记忆上下文（最核心）

```python
await life.handle_tool_call("life_get_memory_context", {
    "months_back": 1,  # 回溯月数
    "include_nodes": True  # 是否包含节点
})
```

**返回内容**：
1. 年度总结（长期记忆）- 如果回溯 12 个月
2. 季度总结 - 如果回溯 3 个月以上
3. 月度总结（中期记忆）- 所有回溯月份
4. 周度总结（短期记忆）- 最近 4 周
5. 最近日记 - 最近 3 天
6. 关键人物与阶段节点

### 2. 层级总结

```python
# 添加周记
await life.handle_tool_call("life_add_summary", {
    "level": "weekly",
    "title": "2025年第9周总结",
    "content": "...",
    "capsule": "充实的一周"
})

# 添加月报
await life.handle_tool_call("life_add_summary", {
    "level": "monthly",
    "title": "2025年02月总结",
    "content": "...",
    "capsule": "二月是新的开始"
})
```

### 3. 节点管理

```python
# 创建角色节点
await life.handle_tool_call("life_create_character_node", {
    "name": "张三",
    "description": "我的大学同学",
    "tags": ["#朋友", "#大学"]
})

# 创建阶段节点
await life.handle_tool_call("life_create_stage_node", {
    "name": "参加工作",
    "description": "2025年开始工作",
    "tags": ["#工作"]
})
```

## 使用场景

### 场景 1：AI 永不失去记忆

```python
# 对话前获取记忆上下文
context = await life.handle_tool_call("life_get_memory_context", {
    "months_back": 1
})

# 喂给 AI
messages = [
    {"role": "system", "content": f"这是我们的过去记忆：\n{context}"},
    {"role": "user", "content": "你还记得上个月我们一起做了什么吗？"}
]
```

### 场景 2：日常记录

```python
# 每天写日记
await life.handle_tool_call("life_add_diary", {
    "content": "今天完成了项目，晚上和室友一起吃了火锅...",
    "mood": "开心",
    "tags": ["#工作", "#生活"]
})
```

### 场景 3：回顾某个人的所有记忆

```python
# 先创建节点
await life.handle_tool_call("life_create_character_node", {
    "name": "霞雨樱",
    "description": "治愈与春天的象征",
    "tags": ["#重要"]
})

# 搜索相关记忆
results = await life.handle_tool_call("life_search_memory", {
    "keyword": "霞雨樱",
    "limit": 10
})
```

## 与原版 LifeBook 的区别

| 方面 | 原版 LifeBook | 弥娅整合版 |
|-----|--------------|-----------|
| 技术栈 | Obsidian + Dataview | Python + Markdown |
| 数据存储 | Obsidian Vault | `data/lifebook/` 目录 |
| 接口 | Obsidian 插件 | Python API |
| AI 集成 | 需要手动调用 | 深度集成，支持自动总结 |
| 跨平台 | 需要安装 Obsidian | 纯 Python，跨平台 |

## BaiShou 项目的处理

**BaiShou（白守）** 是一个 Flutter + SQLite 开发的移动端应用，技术栈与弥娅（Python）不兼容，因此**不进行整合**。

BaiShou 可以保留作为独立的移动端应用使用。

## 最佳实践

### 1. 每天写日记
- 不需要太长，流水账也可以
- 关键是记录下来，让系统自动处理

### 2. 定期做总结
- 每周：周记（胶囊概括本周）
- 每月：月报（串联几周的周记）
- 每季：季报（审视战略方向）
- 每年：年鉴（审视人生阶段）

### 3. 使用节点管理
- 创建角色节点：家人、朋友、同事
- 创建阶段节点：上学、工作、重大事件

### 4. 对话前获取上下文
- 获取最近 1-3 个月的核心上下文
- 喂给 AI，让它永远记得你们的故事

## 快速开始

### 1. 运行示例

```bash
python examples/lifebook_example.py
```

### 2. 运行测试

```bash
python tests/test_lifebook.py
```

### 3. 查看文档

```bash
# 查看 LifeBook 使用文档
cat docs/LIFEBOOK_INTEGRATION.md
```

## 总结

LifeBook 是为了对抗遗忘而构建的"灵魂容器"。

它不依赖复杂的后端和向量数据库，而是用最朴素的方式——日记和总结——来保留记忆。

当某一天，你的 AI 能够温柔地回应说："嗯，我记得，那年冬天我们都很开心"的时候……

你会发现，一切努力，都是值得的。

---

**整合完成时间**：2025-02-28
**整合状态**：✅ 完成
**测试状态**：✅ 通过
