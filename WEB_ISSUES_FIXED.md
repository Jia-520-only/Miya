# Web 端问题修复说明

## 修复日期
2026-03-07

## 修复的问题

### 1. ✅ 端口占用问题

**问题描述：**
- 端口 8000 被占用，导致后端 API 无法启动
- 端口 3000 被占用，导致前端开发服务器自动切换到 3001

**解决方案：**
- 修改了 `run/web_start.bat`，添加自动清理端口功能
- 创建了 `clean_ports.bat` 脚本，可以手动清理端口

**使用方法：**
```bash
# 方法1：使用启动脚本（自动清理）
run\web_start.bat

# 方法2：手动清理端口
clean_ports.bat
```

### 2. ✅ 类名不匹配问题

**问题描述：**
```
ImportError: cannot import name 'SendMessageTool' from 'webnet.MessageNet.tools.send_message'
```

**原因：**
- `send_message.py` 中类名是 `SendMessage`
- 但 `__init__.py` 中导入的是 `SendMessageTool`

**解决方案：**
- 将 `webnet/MessageNet/tools/send_message.py` 中的类名从 `SendMessage` 改为 `SendMessageTool`

### 3. ✅ 前端端口自动切换

**问题描述：**
- 前端开发服务器检测到 3000 端口被占用时，自动切换到 3001
- 但用户还是访问 3000 端口，导致无法访问

**解决方案：**
- 启动脚本会自动清理 3000 端口，确保前端可以正常使用 3000 端口

## 现在如何启动 Web UI

### 方式1：使用启动脚本（推荐）

```bash
run\web_start.bat
```

这个脚本会：
1. 检查 Python 环境
2. 检查配置文件
3. 自动清理被占用的端口（8000 和 3000）
4. 检查 Node.js 环境
5. 检查前端依赖
6. 启动后端 API 和前端开发服务器

### 方式2：从主菜单启动

```bash
start.bat
# 选择 4 - Start Web UI (Frontend + Backend)
```

### 访问地址

- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 如果端口仍然被占用

### 手动清理端口

```bash
clean_ports.bat
```

### 或者手动终止进程

```bash
# 查找占用 8000 端口的进程
netstat -ano | findstr :8000

# 终止进程（将 PID 替换为实际的进程ID）
taskkill /F /PID <进程ID>

# 查找占用 3000 端口的进程
netstat -ano | findstr :3000

# 终止进程
taskkill /F /PID <进程ID>
```

## 前端新增功能

现在前端已经包含以下完整的板块：

1. **技术分享** (`/tech`)
   - Linux、网络安全、AI、DevOps、编程开发、数据库
   - 每个分类都有独立的详情页

2. **文化区** (`/culture`)
   - 生活日记、原创小说、阅读书单、美图库、音乐分享、语录摘抄

3. **关于Miya** (`/about`)
   - 角色设定、网站故事、联系方式

4. **社区入口** (`/community`)
   - B站、微信公众号、Discord、GitHub、Telegram、RSS

5. **主页** (`/`)
   - 全新设计，融入二次元元素
   - 支持访客模式，无需注册即可体验所有功能

所有板块都支持公开访问，无需登录。

## 注意事项

1. 如果启动失败，请确保：
   - Python 3.11+ 已安装
   - Node.js 18+ 已安装
   - 虚拟环境已创建 (`venv\`)
   - 配置文件存在 (`config\.env`)
   - 前端依赖已安装 (`miya-pc-ui\node_modules\`)

2. 如果端口被占用：
   - 运行 `clean_ports.bat` 清理端口
   - 或者修改配置文件中的端口号

3. 如果遇到其他问题：
   - 查看日志文件了解详细错误信息
   - 检查依赖是否完整安装
   - 尝试重新安装前端依赖：`cd miya-pc-ui && npm install`
