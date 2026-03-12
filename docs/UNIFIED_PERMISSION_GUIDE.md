# 弥娅统一权限配置系统 - 使用指南

## 概述

弥娅系统现在使用**统一权限配置文件**来管理所有平台的权限。权限只能通过编辑配置文件来修改，**不支持通过命令修改**，确保权限管理的安全性和可控性。

## 核心特性

✅ **统一管理** - 所有平台的权限在一个配置文件中管理
✅ **只读模式** - 不支持通过命令修改权限
✅ **配置驱动** - 权限完全由配置文件控制
✅ **多平台支持** - 支持 Terminal, Web, Desktop, QQ 等平台
✅ **权限组** - 支持权限组概念，便于管理
✅ **白名单机制** - 支持管理员白名单和超级管理员
✅ **平台限制** - 支持平台级别的权限限制

## 配置文件

弥娅支持两种配置文件格式（优先级从高到低）：

1. **config/permissions.json** - JSON 格式（推荐）
2. **config/permissions.yaml** - YAML 格式（需要安装 PyYAML）

## 配置文件结构

```json
{
  "version": "1.0.0",
  "last_updated": "2026-03-11",

  // 权限组定义
  "permission_groups": {
    "Admin": {
      "name": "管理员",
      "permissions": ["*.*"]
    },
    "Terminal": {
      "name": "终端用户",
      "permissions": [
        "tool.terminal.execute",
        "tool.web_search",
        "tool.get_current_time"
      ]
    }
  },

  // 平台默认权限组
  "platform_defaults": {
    "terminal": ["Terminal"],
    "web": ["Web"],
    "desktop": ["Desktop"],
    "qq": ["QQ"]
  },

  // 用户定义
  "users": [
    {
      "user_id": "terminal_default",
      "username": "默认终端用户",
      "platform": "terminal",
      "permission_groups": ["Admin"],
      "description": "终端平台的默认管理员用户"
    }
  ],

  // 特殊规则
  "special_rules": {
    "admin_whitelist": ["terminal_default"],
    "super_admin_whitelist": ["terminal_default"]
  },

  // 安全设置
  "security": {
    "enable_audit": true,
    "enable_cache": true,
    "cache_ttl": 300
  }
}
```

## 快速开始

### 1. 编辑配置文件

编辑 `config/permissions.json`：

```bash
# Windows
notepad config\permissions.json

# Linux/macOS
vim config/permissions.json
```

### 2. 添加新用户

在 `users` 数组中添加新用户：

```json
{
  "users": [
    {
      "user_id": "qq_123456",
      "username": "张三",
      "platform": "qq",
      "permission_groups": ["QQ"],
      "description": "QQ用户",
      "created_at": "2026-03-11T12:00:00"
    }
  ]
}
```

### 3. 添加权限组

在 `permission_groups` 中添加新权限组：

```json
{
  "permission_groups": {
    "MyGroup": {
      "name": "我的权限组",
      "description": "自定义权限组",
      "permissions": [
        "tool.web_search",
        "tool.get_current_time",
        "memory.read",
        "memory.write"
      ]
    }
  }
}
```

### 4. 重启系统

修改配置后，**必须重启弥娅系统**才能生效：

```bash
# Windows
# 重启 start.bat

# Linux/macOS
./start.sh
```

## 用户ID格式

用户ID格式为：`platform_id`

例如：
- `qq_123456` - QQ用户ID为123456
- `web_user001` - Web用户user001
- `desktop_admin` - Desktop管理员
- `terminal_default` - 终端默认用户

## 权限格式

权限格式为：`category.action.object`

例如：
- `tool.web_search` - 网络搜索工具
- `tool.terminal.execute` - 终端命令执行
- `memory.read` - 读取记忆
- `memory.write` - 写入记忆
- `*.*` - 所有权限

## 可用权限节点

### 工具权限 (tool.*)
- `tool.web_search` - 网络搜索
- `tool.get_current_time` - 获取时间
- `tool.terminal.execute` - 终端命令执行
- `tool.ai_chat` - AI对话
- `tool.file_read` - 文件读取
- `tool.file_write` - 文件写入
- `tool.data_analyzer` - 数据分析
- `tool.chart_generator` - 图表生成

### 记忆权限 (memory.*)
- `memory.read` - 读取记忆
- `memory.write` - 写入记忆
- `memory.delete` - 删除记忆

### 知识权限 (knowledge.*)
- `knowledge.search` - 知识搜索
- `knowledge.add` - 添加知识
- `knowledge.update` - 更新知识
- `knowledge.delete` - 删除知识

### Agent权限 (agent.*)
- `agent.chat` - 对话
- `agent.task.execute` - 任务执行

### 系统权限 (system.*)
- `system.config.read` - 读取配置
- `system.config.write` - 写入配置
- `system.shutdown` - 关闭系统

## 权限组

### 预定义权限组

| 权限组 | 描述 | 权限 |
|--------|------|------|
| Default | 默认权限组 | tool.get_current_time, memory.read, knowledge.search, agent.chat |
| Admin | 管理员 | *.* (所有权限) |
| Terminal | 终端用户 | tool.terminal.execute, tool.web_search, tool.get_current_time, memory.read/write, knowledge.search |
| Web | Web用户 | tool.web_search, tool.get_current_time, memory.read/write, knowledge.search |
| Desktop | Desktop用户 | tool.web_search, tool.get_current_time, memory.read/write, knowledge.search, system.config.read |
| QQ | QQ用户 | tool.web_search, tool.get_current_time, memory.read, knowledge.search |
| Developer | 开发者 | tool.*, memory.*, knowledge.*, agent.*, system.*, config.* |

## 平台限制

可以为每个平台设置权限组限制：

```json
{
  "platform_restrictions": {
    "qq": {
      "allowed_groups": ["Default", "QQ", "Web", "Admin"],
      "forbidden_groups": ["Terminal", "Developer"]
    }
  }
}
```

## 特殊规则

### 管理员白名单

白名单中的用户将自动拥有管理员权限：

```json
{
  "special_rules": {
    "admin_whitelist": ["terminal_default", "qq_admin_id"]
  }
}
```

### 超级管理员白名单

超级管理员可以绕过某些安全检查：

```json
{
  "special_rules": {
    "super_admin_whitelist": ["terminal_default"]
  }
}
```

## 禁用权限

可以全局禁用某些权限，即使权限组中有这些权限也不生效：

```json
{
  "disabled_permissions": [
    "system.config.write",
    "system.shutdown",
    "system.format"
  ]
}
```

## 安全设置

```json
{
  "security": {
    "enable_audit": true,      // 启用审计日志
    "enable_cache": true,      // 启用权限缓存
    "cache_ttl": 300,         // 缓存过期时间（秒）
    "log_denied": true,        // 记录拒绝的权限检查
    "log_allowed": false,      // 记录允许的权限检查
    "whitelist_mode": false,   // 白名单模式
    "user_whitelist": []       // 用户白名单
  }
}
```

## 常见场景

### 场景1：添加一个QQ用户

编辑 `config/permissions.json`：

```json
{
  "users": [
    {
      "user_id": "qq_123456",
      "username": "新用户",
      "platform": "qq",
      "permission_groups": ["QQ"],
      "description": "新添加的QQ用户",
      "created_at": "2026-03-11T12:00:00"
    }
  ]
}
```

### 场景2：给用户添加管理员权限

将用户添加到 `Admin` 权限组：

```json
{
  "user_id": "qq_123456",
  "permission_groups": ["QQ", "Admin"]
}
```

### 场景3：创建自定义权限组

```json
{
  "permission_groups": {
    "Moderator": {
      "name": "版主",
      "description": "版主权限组",
      "permissions": [
        "tool.web_search",
        "tool.get_current_time",
        "memory.read",
        "memory.write",
        "knowledge.search",
        "knowledge.add"
      ]
    }
  }
}
```

### 场景4：禁用危险权限

```json
{
  "disabled_permissions": [
    "system.shutdown",
    "system.format",
    "system.delete"
  ]
}
```

## 验证配置

### 方法1：查看配置信息

在弥娅对话中输入：
```
status
```

### 方法2：检查用户权限

使用 Python 脚本：

```python
from webnet.AuthNet.unified_permission_manager import UnifiedPermissionManager

# 初始化管理器
manager = UnifiedPermissionManager()

# 检查权限
has_perm = manager.check_permission("qq_123456", "tool.web_search", context={"platform": "qq"})
print(f"是否有权限: {has_perm}")

# 获取用户权限列表
perms = manager.get_user_permissions_list("qq_123456", context={"platform": "qq"})
print(f"用户权限: {perms}")
```

## 迁移指南

如果您之前使用的是旧的权限配置（`data/auth/users.json` 和 `data/auth/groups.json`），可以按照以下步骤迁移：

1. 备份旧配置：
```bash
cp data/auth/users.json data/auth/users.json.backup
cp data/auth/groups.json data/auth/groups.json.backup
```

2. 将旧配置转换为新的统一格式：
- 将 `groups.json` 中的权限组合并到 `permission_groups`
- 将 `users.json` 中的用户合并到 `users`

3. 重启系统，使用新的配置文件

## 常见问题

### Q1: 为什么不能通过命令添加用户？

**A**: 为了安全和可控性，权限只能通过配置文件修改。这样可以：
- 所有权限变更都有记录（通过配置文件的版本控制）
- 防止意外的权限修改
- 便于审计和审查

### Q2: 修改配置后多久生效？

**A**: 需要重启弥娅系统才能生效。

### Q3: 如何禁用某个用户的权限？

**A**: 将用户从所有权限组移除，或只保留 `Default` 组：

```json
{
  "user_id": "qq_123456",
  "permission_groups": []
}
```

### Q4: 如何给所有用户添加一个新权限？

**A**: 在相关权限组中添加权限，所有属于该权限组的用户都会获得该权限。

### Q5: 支持权限继承吗？

**A**: 不支持继承，但用户可以属于多个权限组，所有权限组的权限会合并。

### Q6: 忘记管理员密码怎么办？

**A**: 编辑配置文件，将用户添加到 `admin_whitelist` 或 `super_admin_whitelist`：

```json
{
  "special_rules": {
    "admin_whitelist": ["your_user_id"]
  }
}
```

## 故障排除

### 问题1：配置文件语法错误

**症状**: 系统启动失败或权限检查失败

**解决**: 检查 JSON/YAML 语法是否正确，使用在线 JSON 验证工具验证。

### 问题2：权限不生效

**症状**: 修改配置后权限没有变化

**解决**: 确保已重启弥娅系统。

### 问题3：用户没有权限

**症状**: 用户明明在配置文件中，但提示无权限

**解决**:
1. 检查用户ID格式是否正确（platform_id）
2. 检查权限组是否存在
3. 检查平台限制是否阻止了该权限组

## 技术细节

### 配置优先级

1. 用户直接权限（如果支持）
2. 用户所属的权限组权限
3. 平台默认权限组（如果用户不存在）
4. 特殊规则（白名单）
5. 禁用权限列表（全局禁止）

### 权限匹配规则

1. 完全匹配：`tool.web_search` 匹配 `tool.web_search`
2. 通配符匹配：`tool.*` 匹配 `tool.web_search`
3. 超级管理员：`*.*` 匹配所有权限

### 缓存机制

权限检查结果会被缓存，默认 TTL 为 300 秒（5分钟）。修改配置后需要重启系统以清除缓存。

## 相关文档

- **AUTH_USAGE_GUIDE.md** - 旧版权限系统指南（仅供参考）
- **BUGFIX_SUMMARY.md** - 系统修复摘要
- **CONFIGURATION_GUIDE.md** - 系统配置指南

---

更新时间: 2026-03-11
版本: 1.0.0
