# 弥娅终端代理连接配置指南

## 快速开始

终端代理会自动尝试连接弥娅主系统，无需手动配置。

默认尝试的端口顺序：`8000, 8080, 8001, 8888`

## 连接问题排查

如果终端代理显示"无法连接到弥娅主系统"，请按以下步骤排查：

### 1. 确认弥娅主系统已启动

终端代理需要弥娅主程序运行才能工作。启动方式：

```bash
# Windows
start.bat
# 选择 1 - Start Main Program (Full Mode)

# Linux/macOS
./start.sh
# 选择 1 - Start Main Program (Full Mode)
```

启动成功后，你会看到：
```
2026-03-12 23:18:23,877 - Miya - INFO - Web API 服务器已在后台启动 (http://127.0.0.1:8000)
```

### 2. 确认端口监听状态

弥娅主系统默认监听的端口：

| 端口 | 服务 | 说明 |
|------|------|------|
| 8000 | Web API | 主API服务器（聊天、终端、工具等） |
| 8080 | Runtime API | 运行时管理API（需单独启动选项5） |
| 7687 | Neo4j | 图数据库 |
| 6379 | Redis | 缓存数据库 |
| 19530 | Milvus | 向量数据库 |

**终端代理只需要连接8000端口**

### 3. 检查端口占用

#### Windows
```powershell
# 检查8000端口
netstat -ano | findstr :8000

# 检查8080端口
netstat -ano | findstr :8080
```

#### Linux/macOS
```bash
# 检查8000端口
lsof -i :8000

# 或使用
netstat -tuln | grep 8000
```

### 4. 防火墙设置

确保防火墙允许本地连接（localhost/127.0.0.1）。

#### Windows防火墙
```powershell
# 允许Python通过防火墙
New-NetFirewallRule -DisplayName "Miya Web API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

#### Linux (ufw)
```bash
# 允许本地连接
sudo ufw allow from 127.0.0.1 to any port 8000
```

## 自定义端口配置

### 修改弥娅主系统端口

如果需要修改Web API的监听端口：

1. **编辑配置文件**

找到弥娅的配置文件（通常是 `config/` 目录）：

- `config/config.json` 或
- `config/server_config.json` 或
- `.env` 文件

2. **修改端口设置**

```json
{
  "web_api": {
    "host": "127.0.0.1",
    "port": 9000  // 修改为你想要的端口
  }
}
```

或使用 `.env` 文件：
```
WEB_API_HOST=127.0.0.1
WEB_API_PORT=9000
```

3. **重启弥娅主系统**

```bash
# 在主终端中输入 'exit' 退出
# 然后重新启动
start.bat
```

### 修改终端代理连接端口

如果修改了弥娅主系统的端口，需要告诉终端代理使用哪个端口：

#### 方法1：修改 `local_terminal_manager.py`

编辑 `core/local_terminal_manager.py` 中的 `_open_visible_window` 方法：

```python
# Windows PowerShell
cmd = f'cd "{work_dir}"; "{venv_python}" "{agent_script}" --session-id {session_id} --port 9000'
```

#### 方法2：直接运行终端代理

手动在终端中运行终端代理并指定端口：

```bash
# Windows PowerShell
python core/terminal_agent.py --session-id your-session-id --port 9000

# Linux/macOS
python3 core/terminal_agent.py --session-id your-session-id --port 9000
```

## 网络连接配置

### 允许远程连接（可选）

如果需要从其他机器访问弥娅主系统：

#### 1. 修改监听地址

将 `127.0.0.1` 改为 `0.0.0.0`：

```json
{
  "web_api": {
    "host": "0.0.0.0",  // 监听所有网络接口
    "port": 8000
  }
}
```

#### 2. 配置防火墙

**Windows防火墙**
```powershell
New-NetFirewallRule -DisplayName "Miya Web API Remote" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Linux (ufw)**
```bash
sudo ufw allow 8000/tcp
```

#### 3. 配置终端代理连接

从远程机器连接时，指定弥娅主系统的IP地址：

```bash
python core/terminal_agent.py --session-id your-session-id --host 192.168.1.100 --port 8000
```

## 端口冲突处理

如果8000端口被占用，可以使用其他端口：

### 快速解决方案

1. **找到占用8000端口的进程**

   ```bash
   # Windows
   netstat -ano | findstr :8000
   # 记下PID，然后
   taskkill /PID <PID> /F

   # Linux/macOS
   lsof -ti:8000 | xargs kill -9
   ```

2. **使用其他端口**

   终端代理会自动尝试 `8080, 8001, 8888` 端口，你可以：

   - 启动弥娅时选择 "Start Runtime API Server"（选项5），它使用8080端口
   - 或修改配置使用其他端口

### 修改弥娅主系统使用其他端口

编辑配置文件，将端口改为8081或其他：

```json
{
  "web_api": {
    "host": "127.0.0.1",
    "port": 8081
  }
}
```

## 调试模式

### 启用详细日志

如果仍有连接问题，可以启用详细日志：

1. **编辑弥娅主系统日志配置**

   找到 `config/logging_config.json` 或创建一个：

   ```json
   {
     "version": 1,
     "handlers": {
       "console": {
         "class": "logging.StreamHandler",
         "level": "DEBUG",
         "formatter": "default"
       }
     },
     "loggers": {
       "Miya": {
         "level": "DEBUG",
         "handlers": ["console"]
       }
     }
   }
   ```

2. **查看终端代理的详细错误**

   终端代理会显示每个端口的连接尝试结果，包括具体错误信息。

### 使用curl测试连接

在终端代理窗口中手动测试API连接：

```bash
# Windows PowerShell
curl http://localhost:8000/status

# Linux/macOS
curl http://localhost:8000/status
```

如果返回JSON数据，说明API正常。

## 常见问题

### Q: 终端代理显示"端口连接失败"，但弥娅主系统已启动？

**A**: 可能的原因：
1. 端口配置不一致
2. 防火墙阻止
3. IP地址不匹配（127.0.0.1 vs localhost）

**解决方法**:
- 检查弥娅主系统日志，确认实际监听地址和端口
- 使用curl或浏览器访问 http://localhost:8000/status 测试
- 检查防火墙设置

### Q: 多个终端代理同时运行？

**A**: 可以！每个终端代理有独立的会话ID，互不干扰。

### Q: 可以在Docker容器中运行吗？

**A**: 可以，但需要配置端口映射：

```bash
docker run -p 8000:8000 -p 8080:8080 miya
```

然后在容器内的终端代理使用 `localhost:8000` 连接。

### Q: 如何设置终端代理的超时时间？

**A**: 编辑 `core/terminal_agent.py`:

```python
async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)):  # 120秒超时
```

## 性能优化

### 连接池配置

对于大量并发连接，可以配置连接池：

编辑 `core/terminal_agent.py`:

```python
import aiohttp

connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
async with aiohttp.ClientSession(connector=connector) as session:
    # ...
```

### 心跳检测

添加心跳检测以保持连接活跃：

```python
async def heartbeat(self):
    """心跳检测"""
    while self.running:
        try:
            await self.send_message("ping")
        except:
            await self.connect_to_miya()
        await asyncio.sleep(30)  # 每30秒发送一次心跳
```

## 安全建议

1. **不要暴露到公网** - 除非必要，否则只监听127.0.0.1
2. **使用HTTPS** - 生产环境使用SSL/TLS加密
3. **添加认证** - 配置API密钥或token认证
4. **定期更新** - 保持弥娅系统最新版本

## 联系支持

如果仍有问题，请提供：
1. 弥娅主系统启动日志
2. 终端代理输出
3. 端口监听状态（`netstat`或`lsof`输出）
4. 操作系统和Python版本
