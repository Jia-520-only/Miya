# 弥娅 Web API 连接指南

## 📋 当前状态

### ✅ 已完成
1. **后端API** (`core/web_api.py`):
   - `/api/health` - 健康检查
   - `/api/blog/posts` - 博客列表
   - `/api/blog/posts/{slug}` - 博客详情
   - `/api/blog/posts` (POST) - 创建博客
   - `/api/auth/register` - 用户注册
   - `/api/auth/login` - 用户登录
   - `/api/chat` - 聊天对话
   - `/api/status` - 系统状态
   - `/api/emotion` - 情绪状态
   - `/api/security/scan` - 安全扫描
   - `/api/security/block-ip` - 封禁IP
   - `/api/github/*` - GitHub集成

2. **前端页面** (`miya-pc-ui/src/`):
   - LandingPage - 着陆页(强调Miya核心能力)
   - DashboardPage - 控制台(现在会调用真实API)
   - Blog系统、聊天界面、安全控制台等

3. **Miya核心能力**:
   - ✅ 终端控制 (`TerminalTool`, `terminal_command`工具)
   - ✅ 自主决策引擎 (`AutonomousEngine`, `autonomy_with_personality`)
   - ✅ 自动防御系统 (`SecurityGuard` in `WebNet`)
   - ✅ 记忆系统 (`MemoryNet`, `MemoryEngine`)
   - ✅ 动态人格 (`Personality`, `Emotion`)

### ⚠️ 需要修复的问题
- 前端和后端需要同时启动
- 前端需要后端API提供真实数据

## 🚀 启动方式

### 方法1: 使用 start.bat (推荐)

1. 打开终端
2. 运行 `start.bat`
3. 选择选项3 - Start Web UI (Frontend + Backend)

这会自动:
- 启动后端API服务 (http://localhost:8000)
- 启动前端开发服务器 (http://localhost:3000)

### 方法2: 手动启动

#### 启动后端:
```bash
cd d:\AI_MIYA_Facyory\MIYA\Miya
venv\Scripts\python run\web_main.py
```

#### 启动前端(新终端):
```bash
cd d:\AI_MIYA_Facyory\MIYA\Miya\miya-pc-ui
npm run dev:web
```

## 📊 API端点对照

| 前端API路径 | 后端API路径 | 功能 | 状态 |
|-----------|-----------|------|------|
| `/api/health` | `/api/health` | 健康检查 | ✅ |
| `/api/status` | `/api/status` | 系统状态 | ✅ |
| `/api/emotion` | `/api/emotion` | 情绪状态 | ✅ |
| `/api/chat` | `/api/chat` | 聊天对话 | ✅ |
| `/api/blog/posts` | `/api/blog/posts` | 博客列表 | ✅ |
| `/api/blog/posts/{slug}` | `/api/blog/posts/{slug}` | 博客详情 | ✅ |
| `/api/auth/login` | `/api/auth/login` | 用户登录 | ✅ |
| `/api/auth/register` | `/api/auth/register` | 用户注册 | ✅ |
| `/api/security/scan` | `/api/security/scan` | 安全扫描 | ✅ |
| `/api/security/block-ip` | `/api/security/block-ip` | 封禁IP | ✅ |

## 🎯 Miya的核心能力展示

### 1. 终端控制
- **工具**: `TerminalTool`, `terminal_command` (ToolNet)
- **能力**: 完全掌控命令行,支持跨平台(Windows/Linux/macOS)
- **API**: `/api/chat` - 通过对话执行终端命令

### 2. 自主决策引擎
- **模块**: `AutonomousEngine`, `autonomy_with_personality`
- **能力**: 自动发现问题、评估风险、决策修复
- **状态**: DashboardPage显示决策数和修复数

### 3. 自动防御系统
- **模块**: `SecurityGuard` (WebNet)
- **能力**: 实时安全监控、IP封禁、限流保护
- **API**: `/api/security/scan`, `/api/security/block-ip`

### 4. 记忆系统
- **模块**: `MemoryNet`, `MemoryEngine`, `GRAGMemoryManager`
- **能力**: 短期/长期/潮汐记忆,向量检索,知识图谱
- **API**: `/api/status` - 显示记忆统计

### 5. 动态人格
- **模块**: `Personality`, `Emotion`, `autonomy_with_personality`
- **能力**: 五维人格向量,情绪演化,个性化响应
- **API**: `/api/status`, `/api/emotion`

## 🔧 前端修复内容

### 1. API端点对齐 (`services/api.ts`)
- ✅ 修正了聊天API: `/api/chat/message` → `/api/chat`
- ✅ 修正了系统API: `/api/system/status` → `/api/status`
- ✅ 新增了健康检查API: `/api/health`

### 2. DashboardPage重构
- ✅ 添加了真实API调用
- ✅ 添加了加载状态和错误处理
- ✅ 每30秒自动刷新状态
- ✅ 显示后端连接状态提示

## 📝 测试步骤

1. **启动后端服务**
   ```bash
   start.bat → 选项3
   ```

2. **访问前端**
   ```
   http://localhost:3000
   ```

3. **测试API**
   - 健康检查: http://localhost:8000/api/health
   - API文档: http://localhost:8000/docs

4. **查看控制台**
   - DashboardPage应该显示真实系统状态
   - 如果看到"后端服务未启动"提示,检查8000端口是否启动

## ⚡ 常见问题

### Q: 前端显示"后端服务未启动"?
**A:** 确保运行了 `start.bat` 选项3,或者手动启动 `run\web_main.py`

### Q: 前端和后端无法连接?
**A:**
1. 检查8000端口: `netstat -ano | findstr :8000`
2. 检查CORS配置: 允许 `http://localhost:3000`
3. 检查环境变量: `VITE_API_BASE_URL=http://localhost:8000`

### Q: 前端数据是静态的?
**A:** 现在DashboardPage已经调用真实API,确保后端启动即可看到动态数据

### Q: 如何执行终端命令?
**A:** 通过聊天界面输入命令,Miya会通过 `terminal_command` 工具执行

## 🎉 总结

**框架未偏航!** Miya的所有核心能力都已经在代码中正确实现:

1. ✅ 后端API完整,涵盖了所有核心功能
2. ✅ 前端已修复,现在调用真实API
3. ✅ 终端控制、自主决策、自动防御都已集成
4. ✅ DashboardPage展示真实系统状态

只需要启动后端服务 (`start.bat` 选项3),前端就能显示Miya的真实能力!
