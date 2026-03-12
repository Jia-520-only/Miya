# 弥娅云服务器部署优化指南

## 📋 系统信息
- 服务器配置：2核4G 轻量型云服务器
- 操作系统：Windows 10.0.26200
- Python: 3.11.9
- Node.js: 24.12.0

## 🔧 已修复的问题

### 1. 对话历史持久化 ✅
**问题**：刷新页面后聊天记录丢失
**修复**：
- 在 `ChatWindow.tsx` 中添加 localStorage 支持
- 添加 console.log 用于调试
- 移除了保存条件限制

**测试方法**：
1. 发送几条消息
2. 刷新页面（F5）
3. 查看聊天记录是否保留

**注意事项**：
- localStorage 存储在浏览器本地
- 清除浏览器数据会丢失历史
- 限制大小通常为 5-10MB

### 2. 终端命令执行修复 ✅
**问题**：PowerShell 命令执行失败
**错误信息**：
```
Get-NetTCPConnection : A parameter cannot be found that matches parameter name 'ano'.
```
**修复**：
- `netstat` 命令直接使用 `netstat.exe` 而不是 PowerShell `Get-NetTCPConnection`
- 避免参数转换错误

## ⚡ 云服务器优化建议

### 1. 轻量级启动配置
对于 2核4G 服务器，建议：

#### 后端优化
```python
# config/.env
# 减少并发连接
MAX_WORKERS=2
MAX_CONNECTIONS=50

# 使用更快的模型
DEFAULT_MODEL=qwen2.5-7b-instruct

# 禁用不必要的功能
ENABLE_VECTOR_CACHE=false
ENABLE_KNOWLEDGE_GRAPH=false
```

#### 前端优化
```javascript
// 减少轮询频率
const REFRESH_INTERVAL = 60000; // 60秒

// 限制历史记录数量
const MAX_MESSAGES = 50;

// 使用 CDN 资源
// vite.config.js
export default {
  server: {
    host: '0.0.0.0',
    port: 3000
  },
  build: {
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
        },
      },
    },
  },
}
```

### 2. 内存优化

#### Python 后端
```python
# 减少 AI 上下文长度
MAX_CONTEXT_TOKENS = 2000  # 默认 4096

# 限制记忆历史
MEMORY_HISTORY_LIMIT = 50  # 默认 100

# 缓存优化
REDIS_MAX_CONNECTIONS = 10
```

#### Node.js 前端
```bash
# 增加 Node.js 内存限制
NODE_OPTIONS=--max-old-space-size=2048 npm run dev
```

### 3. 启动脚本优化

创建轻量级启动脚本 `start_lightweight.bat`：

```batch
@echo off
chcp 65001 >nul
echo ========================================
echo   MIYA - Cloud Light Mode
echo ========================================

REM 只启动 Web API 和前端
echo [Starting] Web API (Lightweight)...

venv\Scripts\python.exe run/web_main.py

echo [Done]
pause
```

修改 `run/web_main.py`，添加轻量级模式：

```python
if __name__ == "__main__":
    import sys

    # 轻量级模式
    if '--lightweight' in sys.argv:
        print("启动轻量级模式...")
        # 禁用某些功能
        enable_milvus = False
        enable_neo4j = False
    else:
        enable_milvus = True
        enable_neo4j = True

    # ...
```

### 4. Docker 部署（推荐）

使用 Docker 可以更好地控制资源：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs

# 复制代码
COPY . .

# 限制资源
ENV MAX_WORKERS=2
ENV MAX_CONNECTIONS=50

# 启动
CMD ["python", "run/web_main.py"]
```

### 5. 性能监控

添加监控脚本：

```python
import psutil
import time

def monitor_resources():
    """监控资源使用"""
    while True:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        print(f"CPU: {cpu}%")
        print(f"Memory: {memory.percent}%")

        if memory.percent > 90:
            print("警告：内存使用过高！")

        time.sleep(60)

if __name__ == "__main__":
    monitor_resources()
```

## 🐛 故障排查

### 问题1：聊天记录仍然丢失

**检查步骤**：
1. 打开浏览器开发者工具（F12）
2. 切换到 Console 标签
3. 查看是否有日志输出

**预期日志**：
```
已加载聊天记录: 5 条消息
保存聊天记录: 6 条消息
```

**如果没有日志**：
- 检查浏览器是否阻止了 localStorage
- 检查是否在隐私/无痕模式
- 尝试使用 Chrome/Edge 浏览器

### 问题2：终端命令执行失败

**检查步骤**：
1. 查看后端日志中的错误信息
2. 尝试直接在后端测试命令

**测试命令**：
```python
# 在 Python REPL 中
from tools.terminal import TerminalTool
tool = TerminalTool()
result = tool.execute("ls")
print(result)
```

### 问题3：服务器响应慢

**优化方案**：
1. 使用更快的模型（Qwen 7B）
2. 减少 AI 上下文长度
3. 减少历史消息数量
4. 禁用不必要的功能

## 📊 资源使用监控

### 查看资源使用
```bash
# Windows
powershell -Command "Get-Process | Select-Object Name, CPU, WorkingSet"

# Linux
top -b -n 1 | head -20
```

### 内存优化建议
- AI 模型：~500MB
- Redis：~100MB
- Milvus：~500MB（如果启用）
- Neo4j：~300MB（如果启用）
- Python 运行时：~200MB
- Node.js：~100MB

**总计：约 1.5-2GB**

## 🚀 部署检查清单

### 部署前
- [ ] 测试所有功能在本地正常
- [ ] 备份配置文件
- [ ] 检查 API 密钥
- [ ] 准备域名和 SSL 证书

### 部署中
- [ ] 上传代码到服务器
- [ ] 安装依赖
- [ ] 配置环境变量
- [ ] 启动服务
- [ ] 测试 API 连接

### 部署后
- [ ] 监控资源使用
- [ ] 检查日志文件
- [ ] 测试所有功能
- [ ] 设置自动重启脚本

## 📝 维护建议

### 日常维护
1. 每日检查日志文件大小
2. 每周清理旧日志
3. 每月更新依赖包
4. 定期备份数据库

### 日志清理
```bash
# 清理 7 天前的日志
powershell -Command "Get-ChildItem logs | Where-Object LastWriteTime -LT (Get-Date).AddDays(-7) | Remove-Item"
```

### 自动重启
使用 systemd（Linux）或任务计划程序（Windows）：

```batch
# Windows 任务计划
schtasks /create /tn "Miya-Restart" /tr "C:\path\to\restart.bat" /sc daily /st 03:00
```

## 🎉 完成

所有修复和优化建议已完成！现在弥娅可以在轻量级云服务器上稳定运行。

**更新时间**: 2026-03-07
