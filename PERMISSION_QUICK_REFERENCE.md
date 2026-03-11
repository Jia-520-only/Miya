# 弥娅权限配置 - 快速参考

## 核心原则

> **权限只能通过配置文件修改，不支持通过命令修改！**

## 配置文件

```
config/permissions.json  (推荐)
config/permissions.yaml (需要 PyYAML)
```

## 快速开始

### 1. 首次初始化

```bash
# Windows
first_run.bat

# Linux/macOS
./first_run.sh
```

### 2. 添加新用户

编辑 `config/permissions.json`：

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

### 3. 重启系统

```bash
# 重启弥娅系统使配置生效
```

## 用户ID格式

```
platform_id

例如：
- qq_123456
- web_user001
- desktop_admin
- terminal_default
```

## 权限格式

```
category.action.object

例如：
- tool.web_search
- tool.terminal.execute
- memory.read
- memory.write
- knowledge.search
- *.* (所有权限)
```

## 预定义权限组

| 权限组 | 描述 | 适用平台 |
|--------|------|----------|
| Default | 默认权限组 | 所有 |
| Admin | 管理员（所有权限） | 所有 |
| Terminal | 终端用户 | Terminal |
| Web | Web用户 | Web |
| Desktop | Desktop用户 | Desktop |
| QQ | QQ用户 | QQ |
| Developer | 开发者 | 所有 |

## 常用权限

| 权限 | 描述 |
|------|------|
| tool.web_search | 网络搜索 |
| tool.terminal.execute | 终端命令执行 |
| tool.get_current_time | 获取时间 |
| memory.read | 读取记忆 |
| memory.write | 写入记忆 |
| knowledge.search | 知识搜索 |
| agent.chat | 对话 |
| *.* | 所有权限 |

## 常见场景

### 给用户管理员权限

```json
{
  "user_id": "qq_123456",
  "permission_groups": ["QQ", "Admin"]
}
```

### 创建自定义权限组

```json
{
  "permission_groups": {
    "Moderator": {
      "name": "版主",
      "permissions": [
        "tool.web_search",
        "memory.read",
        "memory.write"
      ]
    }
  }
}
```

### 禁用危险权限

```json
{
  "disabled_permissions": [
    "system.shutdown",
    "system.format"
  ]
}
```

## 禁用的工具

以下工具已禁用：

- ❌ `add_user` - 添加用户
- ❌ `grant_permission` - 授予权限
- ❌ `revoke_permission` - 撤销权限
- ❌ `remove_user` - 删除用户

**原因**: 权限只能通过配置文件修改

## 重要提示

1. ⚠️ 修改配置后必须重启系统
2. ⚠️ 用户ID格式必须是 `platform_id`
3. ⚠️ 权限格式必须是 `category.action.object`
4. ⚠️ 权限只能通过配置文件修改

## 相关文档

- **UNIFIED_PERMISSION_GUIDE.md** - 完整配置指南
- **UNIFIED_PERMISSION_SUMMARY.md** - 实现总结

---

**更新**: 2026-03-11
**版本**: 1.0.0
