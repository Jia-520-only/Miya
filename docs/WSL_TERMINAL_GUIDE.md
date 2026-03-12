# 弥娅WSL终端使用指南

## 快速开始

### 1. 启动弥娅主系统

```bash
# Windows
start.bat
# 选择 1 - Start Main Program (Full Mode)

# 确认看到：
# Web API 服务器已在后台启动 (http://127.0.0.1:8000)
```

### 2. 测试API连接

```bash
# 运行测试脚本
python test_terminal_agent.py
# 选择 1 测试终端代理连接
```

### 3. 打开WSL终端

在弥娅主终端中输入：

```bash
# 方式1：让弥娅自动选择发行版
佳: 打开一个WSL

# 方式2：指定发行版
佳: 打开Ubuntu WSL
佳: 打开Debian WSL
佳: 打开kali WSL
佳: 打开Arch Linux WSL

# 方式3：先查看所有发行版
佳: 列出所有WSL发行版
# 然后选择一个
佳: 打开Ubuntu WSL
```

## WSL管理命令

### 查看WSL状态

```bash
# 检查WSL是否安装
佳: 检查WSL

# 列出所有WSL发行版
佳: 列出所有WSL发行版
佳: 查看WSL发行版

# 查看默认WSL发行版
佳: 查看默认WSL发行版
```

### 打开WSL终端

```bash
# 打开默认WSL
佳: 打开一个WSL

# 打开指定发行版
佳: 打开Ubuntu WSL
佳: 启动Debian WSL
佳: 创建Arch Linux WSL终端
```

### 检查和配置WSL环境

```bash
# 检查WSL的Python环境
佳: 检查Ubuntu的Python环境
佳: 检查WSL Python环境

# 自动安装Python环境
佳: 为Ubuntu安装Python环境
佳: 安装Debian的Python环境
```

## 支持的WSL发行版

弥娅可以管理和打开以下WSL发行版：

| 发行版 | 命令示例 | 说明 |
|--------|----------|------|
| Ubuntu | `打开Ubuntu WSL` | 最常用的Linux发行版 |
| Debian | `打开Debian WSL` | 稳定可靠的发行版 |
| Kali Linux | `打开kali WSL` | 渗透测试发行版 |
| Arch Linux | `打开Arch Linux WSL` | 滚动更新发行版 |
| Ubuntu-24.04 | `打开Ubuntu-24.04 WSL` | Ubuntu特定版本 |

**注意**: 发行版名称必须与`wsl --list --verbose`显示的名称一致。

## 终端代理功能

WSL窗口中的终端代理提供：

### ✅ 已连接功能
- 发送消息到弥娅主系统
- 接收弥娅的响应
- 执行弥娅的命令
- 显示执行结果

### 🔍 连接状态指示

```
✅ 已连接到弥娅主系统 (端口: 8000)
```
- 表示终端代理成功连接到弥娅主系统
- 可以正常使用所有功能

```
⚠️ 无法连接到弥娅主系统
```
- 表示连接失败
- 交互功能受限
- 可以手动输入命令，但无法与弥娅交互

### 💬 交互方式

```bash
# 在WSL窗口中输入消息
[bc196cfd] 你好

# 弥娅的响应
【弥娅】你好！我是弥娅，有什么可以帮助你的吗？

# 退出终端代理
[bc196cfd] exit
# 或
[bc196cfd] 退出
```

## 故障排查

### 问题1：终端代理无法连接

**症状**:
```
⚠️ 无法连接到弥娅主系统
   尝试的端口: 8000, 8080, 8001, 8888
```

**解决方案**:
1. 确认弥娅主程序已启动
2. 检查启动日志中的端口号
3. 运行测试脚本: `python test_terminal_agent.py`
4. 查看 `docs/TERMINAL_AGENT_SETUP.md` 详细指南

### 问题2：WSL窗口不可见

**症状**: 弥娅说"WSL终端已打开"，但看不到窗口

**解决方案**:
1. 检查任务栏是否有新窗口
2. 尝试按 `Alt+Tab` 切换窗口
3. 检查Windows Terminal是否已安装
4. 查看系统托盘是否有终端图标

### 问题3：WSL中Python未安装

**症状**:
```
bash: python3: command not found
[已退出进程，代码为 127]
```

**解决方案**:
```bash
# 让弥娅自动安装
佳: 为WSL安装Python环境

# 或手动安装（在WSL窗口中）
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

### 问题4：AI不打开WSL

**症状**: AI返回"没有安装WSL发行版"，但实际已安装

**解决方案**:
1. 先让AI列出发行版: `佳: 列出所有WSL发行版`
2. 使用AI显示的准确发行版名称
3. 例如：`佳: 打开kali-linux WSL`（注意用小写和连字符）

## 多终端管理

### 同时打开多个WSL终端

```bash
# 打开第一个WSL
佳: 打开Ubuntu WSL
# 会话ID: abc12345

# 打开第二个WSL
佳: 打开Debian WSL
# 会话ID: def67890

# 打开第三个WSL
佳: 打开kali WSL
# 会话ID: ghi13579
```

每个WSL窗口都是独立的，可以同时在不同发行版中工作。

### 查看所有终端

```bash
佳: 列出所有终端
```

弥娅会显示所有打开的终端及其状态。

### 切换活动终端

弥娅会自动管理终端焦点，通常最后打开的终端是活动的。

## 高级用法

### 在WSL中执行命令

弥娅可以通过终端代理在WSL中执行命令：

```bash
# 让弥娅在WSL中执行命令
佳: 在Ubuntu中运行 ls -la
佳: 在Debian中更新软件包
佳: 在Kali中扫描网络
```

弥娅会通过WSL管理工具执行命令并返回结果。

### 环境配置

弥娅会自动检测和配置WSL环境：

```bash
# 自动检测
佳: 检查WSL环境

# 自动安装缺失组件
佳: 配置WSL环境
```

弥娅会：
1. 检查Python环境
2. 检查pip和aiohttp
3. 自动安装缺失的组件

## 示例工作流

### 示例1：首次设置WSL

```bash
# 1. 检查WSL状态
佳: 检查WSL
# ✅ WSL已安装

# 2. 查看可用的发行版
佳: 列出所有WSL发行版
# Ubuntu-24.04, Debian, kali-linux

# 3. 打开一个发行版
佳: 打开Ubuntu WSL
# ✅ 已打开Ubuntu WSL终端

# 4. 在WSL中配置环境
佳: 为Ubuntu安装Python环境
# ✅ Python环境已安装

# 5. 测试终端代理
# 在WSL窗口中输入: 你好
# 【弥娅】你好！
```

### 示例2：多发行版协作

```bash
# 1. 打开Ubuntu进行开发
佳: 打开Ubuntu WSL

# 2. 打开Debian进行测试
佳: 打开Debian WSL

# 3. 打开Kali进行安全测试
佳: 打开kali WSL

# 4. 让弥娅在不同发行版中执行任务
佳: 在Ubuntu中运行测试
佳: 在Debian中部署应用
佳: 在Kali中检查安全
```

## 配置文件

### 终端代理配置

位置: `core/terminal_agent.py`

可配置项:
- 默认主机: `localhost`
- 默认端口: `8000`（自动检测）
- 连接超时: 60秒

### WSL管理配置

位置: `webnet/TerminalNet/tools/wsl_manager.py`

自动检测:
- WSL安装状态
- WSL发行版列表
- Python环境
- 系统配置

## 性能优化

### 快速连接

终端代理使用连接复用和智能端口检测：
1. 优先使用8000端口（Web API）
2. 自动回退到其他端口
3. 连接失败快速重试

### 资源管理

- 每个终端代理使用独立的会话
- 自动清理空闲连接
- 支持并发多个终端

## 安全建议

1. **仅本地使用**: 终端代理默认连接localhost
2. **环境隔离**: 每个WSL发行版独立运行
3. **权限管理**: 终端代理遵循弥娅权限系统
4. **日志记录**: 所有操作都有日志记录

## 获取帮助

如果遇到问题：

1. 查看 `docs/TERMINAL_AGENT_SETUP.md` - 详细配置指南
2. 运行 `python test_terminal_agent.py` - 测试连接
3. 检查弥娅主程序日志 - 查看启动信息
4. 查看终端代理输出 - 诊断连接问题

## 下一步

- 配置WSL的Python开发环境
- 设置项目目录
- 配置代码同步
- 设置远程访问（可选）
