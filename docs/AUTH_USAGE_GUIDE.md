# 弥娅鉴权系统使用指南

## 概述

弥娅系统使用一个完整的鉴权系统来管理用户权限，支持跨平台用户管理（QQ、Web、Desktop、Terminal等）。

## 文件结构

```
data/auth/
├── users.json      # 用户数据
└── groups.json     # 权限组数据
```

## 权限组

权限组是权限的集合，一个用户可以属于多个权限组。

### 默认权限组

| 权限组 | 描述 | 权限 |
|--------|------|------|
| Default | 默认权限组 | `tool.web_search`, `tool.get_current_time`, `memory.read`, `memory.write`, `knowledge.search` |
| Admin | 管理员 | `*.*` (所有权限) |
| Terminal | 终端用户 | `tool.terminal.execute`, `tool.web_search`, `tool.get_current_time`, `memory.read`, `memory.write` |

## 用户ID格式

用户ID格式为：`platform_id`

例如：
- `qq_123` - QQ用户ID为123
- `web_user456` - Web用户user456
- `desktop_abc` - Desktop用户abc
- `terminal_default` - 终端默认用户

## 权限格式

权限格式为：`category.action.object`

例如：
- `tool.web_search` - 网络搜索工具
- `tool.terminal.execute` - 终端命令执行
- `memory.read` - 读取记忆
- `*.*` - 所有权限

## 使用方法

### 方法1：使用初始化脚本（推荐）

运行初始化脚本：

```bash
python init_auth.py
```

选择：
1. 初始化鉴权系统（创建默认用户和权限组）
2. 添加新用户

### 方法2：使用工具调用（在对话中）

弥娅会自动识别需要添加用户的请求，并通过 `add_user` 工具添加用户。

**注意**：`add_user` 是一个弥娅工具，不是终端命令。不应该用 `!` 或 `>>` 前缀执行。

**错误示例**：
```
!add_user terminal_default admin *.*
```

**正确方法**：
直接对话：
```
请帮我添加一个用户，ID是 qq_123，平台是 qq，权限组是 Admin
```

### 方法3：手动编辑配置文件

#### 添加用户到 `data/auth/users.json`：

```json
{
  "users": [
    {
      "user_id": "qq_123",
      "username": "张三",
      "platform": "qq",
      "permission_groups": ["Default"],
      "permissions": [],
      "created_at": "2026-03-11T00:00:00"
    }
  ]
}
```

#### 添加权限组到 `data/auth/groups.json`：

```json
{
  "groups": {
    "MyGroup": {
      "name": "MyGroup",
      "description": "我的权限组",
      "permissions": [
        "tool.web_search",
        "tool.get_current_time"
      ]
    }
  }
}
```

## 权限检查示例

### 检查用户权限

```python
from webnet.AuthNet.permission_core import PermissionCore

permission_core = PermissionCore()

# 检查是否有权限
has_perm = permission_core.check_permission("qq_123", "tool.web_search")
print(has_perm)  # True or False

# 获取权限详情
perm_details = permission_core.check_permission("qq_123", "tool.web_search", list_mode=True)
print(perm_details)
```

## 常见问题

### Q1: 为什么 `!add_user` 命令不工作？

**A**: `add_user` 不是终端命令，而是弥娅工具。不要使用 `!` 或 `>>` 前缀。直接对话即可：
```
请添加一个用户，ID是 qq_123
```

### Q2: 如何给用户所有权限？

**A**: 将用户添加到 `Admin` 权限组：
```json
{
  "user_id": "qq_123",
  "permission_groups": ["Admin"]
}
```

### Q3: 如何禁用某个用户的权限？

**A**: 将用户从所有权限组移除，或只保留 `Default` 组：
```json
{
  "user_id": "qq_123",
  "permission_groups": []
}
```

### Q4: 权限组是否继承？

**A**: 目前不支持继承，但用户可以属于多个权限组，所有权限组的权限会合并。

## 可用权限节点

### 工具权限 (tool.*)
- `tool.web_search` - 网络搜索
- `tool.get_current_time` - 获取时间
- `tool.terminal.execute` - 终端命令执行
- `tool.ai_chat` - AI对话
- `tool.file_read` - 文件读取
- `tool.file_write` - 文件写入

### 记忆权限 (memory.*)
- `memory.read` - 读取记忆
- `memory.write` - 写入记忆
- `memory.delete` - 删除记忆

### 知识权限 (knowledge.*)
- `knowledge.search` - 知识搜索
- `knowledge.add` - 添加知识
- `knowledge.update` - 更新知识

### 管理员权限
- `*.*` - 所有权限
