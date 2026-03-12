# 弥娅终端工具使用指南

## 功能简介

弥娅终端工具是一个智能命令执行助手，支持：
- ✅ 跨平台支持（Windows PowerShell / Linux Bash / MacOS Bash）
- ✅ 自然语言输入（说"查看当前目录"即可）
- ✅ 直接命令执行（使用 `!` 或 `>>` 前缀）
- ✅ 安全审计（自动检测危险命令）
- ✅ 命令历史记录
- ✅ 命令建议系统

## 使用方法

### 1. 直接命令执行

在终端模式下，使用 `!` 或 `>>` 前缀执行命令：

```
您: !ls
弥娅: ✅ 命令执行成功
命令: ls
耗时: 0.12秒
平台: windows

【输出】
Directory: C:\Users\...
...
```

```
您: >>pwd
弥娅: ✅ 命令执行成功
命令: pwd
耗时: 0.08秒
【输出】
d:\AI_MIYA_Facyory\MIYA\Miya
```

### 2. 自然语言命令

直接用自然语言描述你想做的：

```
您: 查看当前目录
弥娅: ✅ 命令执行成功
【输出】
...
```

```
您: 查看最近10行日志
弥娅: ✅ 命令执行成功
【输出】
（显示最近10行日志）
```

```
您: 搜索Python文件
弥娅: ✅ 命令执行成功
【输出】
（搜索结果）
```

```
您: 检查Git状态
弥娅: ✅ 命令执行成功
【输出】
（Git状态）
```

### 3. QQ机器人中使用

在私聊中使用终端命令（仅限私聊）：

```
用户: !ls
弥娅: ✅ 命令执行成功
【输出】
...
```

**注意**：终端命令仅在私聊中支持，群聊中会提示"终端命令仅在私聊中支持~"

## 支持的自然语言命令

### 查看类
- `查看当前目录` → `ls`
- `查看当前路径` → `pwd`
- `查看所有文件` → `ls -la`
- `读取文件xxx` → `cat xxx`
- `查看最近N行日志xxx` → `tail -n N xxx`

### 导航类
- `进入xxx目录` → `cd xxx`
- `打开xxx文件夹` → `cd xxx`

### 搜索类
- `搜索关键词在目录中` → `grep -r "关键词" 目录`
- `查找文件名` → `find . -name "*文件名*"`
- `搜索关键词` → `grep -r "关键词" .`

### 检查类
- `检查Git状态` → `git status`
- `检查系统状态` → `ps aux`
- `检查磁盘使用` → `df -h`
- `检查内存使用` → `free -h`

## 安全机制

### 安全等级

1. **只读操作** - ✅ 安全，直接执行
   - ls, cat, grep, git log, ps, df, 等

2. **写入操作** - ⚠️ 需要确认
   - touch, mkdir, cp, mv, git add, 等

3. **危险操作** - 🚨 需要严格确认
   - rm, rmdir, del, kill, sudo, 等

### 危险命令黑名单

以下命令会被拦截：
- `rm -rf /` - 删除根目录
- `dd if=/dev/zero` - 擦除硬盘
- `mkfs` - 格式化文件系统
- Fork bomb - 系统炸弹
- Windows 格式化磁盘命令
- Windows 删除系统文件

## 配置文件

### config/terminal_config.json

```json
{
  "security_level": "safe",          // 安全等级: safe/strict/permissive
  "max_execution_time": 30,          // 最大执行时间（秒）
  "work_dir": "d:/...",            // 工作目录
  "enable_history": true,            // 启用历史记录
  "enable_ai": false,               // 启用AI分析（Phase 3）
  "ai_model": "gpt-4",            // AI模型
  "ai_api_key": "",                  // AI API密钥
  "ai_base_url": "https://...",      // AI API地址
  "max_history_entries": 1000,         // 最大历史记录数
  "enable_progress_tracking": true,    // 启用进度跟踪（Phase 2）
  "enable_command_suggestions": true   // 启用命令建议（Phase 2）
}
```

### config/terminal_whitelist.json

命令白名单配置，按安全等级分类。

## 跨平台命令映射

### Windows PowerShell

| 原始命令 | PowerShell 命令 |
|-----------|-----------------|
| ls | Get-ChildItem |
| pwd | Get-Location |
| cd | Set-Location |
| cat | Get-Content |
| ps | Get-Process |
| df | Get-PSDrive |
| netstat | Get-NetTCPConnection |

### Linux/MacOS Bash

| 原始命令 | Bash 命令 |
|-----------|-----------|
| ls | ls |
| pwd | pwd |
| cd | cd |
| cat | cat |
| ps | ps |
| df | df -h |
| netstat | netstat |

## 当前实现功能（Phase 1）

✅ 平台检测和适配器
✅ 命令执行器（同步）
✅ 简单自然语言识别
✅ 基础命令白名单
✅ 安全审计
✅ 命令历史记录
✅ 集成到 DecisionHub
✅ 集成到终端模式

## 即将实现功能（Phase 2）

🔄 进度展示
🔄 命令建议系统
🔄 输出格式化

## 即将实现功能（Phase 3）

📦 云端大模型集成
📦 本地模型支持（LLaMA 3）
📦 SSH 远程执行
📦 多服务器管理

## 示例对话

### 示例 1: 日常开发

```
您: 检查Git状态
弥娅: ✅ 命令执行成功
命令: git status
耗时: 0.35秒

【输出】
On branch main
Your branch is up to date with 'origin/main'.
...
```

### 示例 2: 日志查看

```
您: 查看最近20行日志
弥娅: ✅ 命令执行成功
命令: tail -n 100 logs/miya.log
耗时: 0.15秒

【输出】
（显示最近100行日志）
```

### 示例 3: 文件搜索

```
您: 搜索config文件
弥娅: ✅ 命令执行成功
命令: find . -name "*config*"
耗时: 0.42秒

【输出】
./config/terminal_config.json
./config/settings.py
...
```

## 故障排查

### 终端工具未启用

如果启动信息显示"终端工具: 未启用"，请检查：
1. `config/terminal_config.json` 文件是否存在
2. 文件格式是否正确（JSON）
3. 查看日志中的错误信息

### 命令执行失败

1. 检查命令语法是否正确
2. 查看错误输出中的提示信息
3. 确认平台（Windows/Linux/MacOS）
4. 检查安全等级是否过于严格

### 编码问题（Windows）

如果遇到中文乱码：
1. 确保终端支持 UTF-8
2. 使用 PowerShell 而非 cmd
3. 检查系统区域设置

## 后续规划

请参考实施计划表（在对话历史中查看详细的 Phase 1-7 规划）

---

**Enjoy using Miya's Terminal Tool! 🚀**
