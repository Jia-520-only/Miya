# 弥娅启动指南 (MIYA Startup Guide)

## 📋 启动选项说明

### 1️⃣ Start Main Program (Full Mode)
**完整模式启动** - 启动弥娅核心系统，包含所有子网和功能模块
- 适用于：开发调试、完整功能测试
- 端口：无HTTP服务（纯交互模式）
- 启动时间：较长（初始化所有子系统）
- 包含功能：
  - ✅ MemoryNet (记忆系统)
  - ✅ ToolNet (工具系统)
  - ✅ TerminalNet (终端控制)
  - ✅ SchedulerNet (调度系统)
  - ✅ 自主决策引擎
  - ✅ 动态人格系统

### 2️⃣ Start QQ Bot
**QQ机器人模式** - 启动弥娅QQ机器人
- 适用于：通过QQ与弥娅交互
- 需要：配置 QQ bot token
- 端口：无HTTP服务
- 功能：通过QQ消息调用弥娅的所有能力

### 3️⃣ Start Web UI (Frontend + Backend)
**Web UI 模式** - 同时启动前端和后端
- **推荐给大多数用户**
- 端口：
  - 后端 API: http://localhost:8000
  - 前端 UI: http://localhost:3000
- 功能：
  - ✅ 完整的 Web 界面
  - ✅ API 文档: http://localhost:8000/docs
  - ✅ 聊天对话（支持终端命令执行）
  - ✅ 系统状态监控
  - ✅ 博客系统
  - ✅ 安全控制台
- 启动时间：中等

### 4️⃣ Start Runtime API Server ⚠️ 已修复
**运行时API服务器** - 独立API服务（端口8001）
- 适用于：仅需要API服务的场景
- 端口：http://localhost:8001
- 功能：
  - ✅ 交互端管理（注册/注销/状态查询）
  - ✅ Agent管理
  - ✅ 认知记忆查询
  - ✅ 系统监控
- 注意：此服务与 Web API (端口8000) 不同，这是运行时管理API

### 5️⃣ Start Health Check
**健康检查** - 检查系统各组件状态
- 适用于：系统诊断
- 检查项：
  - Python 环境
  - 依赖包
  - 数据库连接
  - 配置文件

### 6️⃣ Check System Status
**系统状态查看** - 显示基本系统信息
- Python 版本
- 操作系统版本
- 机器架构
- 处理器信息

---

## 🚀 快速启动

### Windows 用户
```batch
start.bat
# 然后选择 3 - Start Web UI (推荐)
```

### Linux/Mac 用户
```bash
./start.sh
# 然后选择 3 - Start Web UI (推荐)
```

---

## 📊 服务端口说明

| 服务 | 端口 | 说明 | 启动方式 |
|------|------|------|----------|
| Web API | 8000 | 主要Web API服务 | 选项3 |
| Web UI | 3000 | 前端界面 | 选项3 |
| Runtime API | 8001 | 运行时管理API | 选项4 |
| Redis | 6379 | 缓存服务 | 自动启动 |
| Milvus | 19530 | 向量数据库 | 自动启动 |
| Neo4j | 7474, 7687 | 知识图谱 | 自动启动 |

---

## 🔧 故障排查

### 问题1：选项3启动失败
```
[WebAPI] 获取系统状态失败: 'NoneType' object has no attribute 'get_system_status'
```
**解决方法**：
1. 确保 `webnet/webnet.py` 文件存在
2. 确保 `webnet/webnet.py` 中的 `WebNet` 类已正确实现
3. 检查 `hub/decision_hub.py` 是否包含 `miya_instance` 参数

### 问题2：选项4启动后立即退出
```
[Done] Program exited
```
**已修复**：现在使用独立的启动脚本 `run/runtime_api_start.py`

### 问题3：Web前端无法连接后端
**检查清单**：
1. 后端 API 是否运行：http://localhost:8000/docs
2. 前端是否运行：http://localhost:3000
3. 检查浏览器控制台错误（F12）
4. 确认 API 端点路径正确

### 问题4：端口被占用
```bash
# Windows 查看端口占用
netstat -ano | findstr :8000

# Linux/Mac 查看端口占用
lsof -i :8000

# 关闭占用端口的进程或更改配置
```

---

## 📝 API 文档

### Web API (端口8000)
访问：http://localhost:8000/docs

主要端点：
- `GET /api/health` - 健康检查
- `GET /api/status` - 系统状态
- `GET /api/emotion` - 情绪状态
- `POST /api/chat` - 聊天对话
- `GET /api/blog/posts` - 博客列表
- `POST /api/auth/login` - 用户登录
- `POST /api/security/scan` - 安全扫描

### Runtime API (端口8001)
访问：http://localhost:8001/docs

主要端点：
- `GET /api/endpoints` - 获取所有交互端
- `POST /api/endpoints/register` - 注册交互端
- `GET /api/agents` - 获取所有Agent
- `GET /api/cognitive/events` - 查询认知记忆
- `GET /api/health` - 健康检查

---

## 🎯 推荐使用场景

### 开发调试
- 使用 **选项1** (Full Mode) 进行核心功能开发
- 使用 **选项3** (Web UI) 进行前端和集成测试

### 生产环境
- 使用 **选项3** (Web UI) 作为主服务
- 配合 **选项4** (Runtime API) 进行运行时管理

### 轻量使用
- 仅需要聊天功能：使用 **选项3** (Web UI)
- 仅需要API服务：使用 **选项4** (Runtime API)

---

## 📚 相关文档

- [Web UI 说明](./WEB_UI_说明.md)
- [Web API 连接指南](./WEB_API_CONNECTION_GUIDE.md)
- [Web 集成完成报告](./WEB_INTEGRATION_COMPLETE.md)
- [部署指南](./DEPLOYMENT_GUIDE.md)

---

**更新时间**: 2026-03-07
