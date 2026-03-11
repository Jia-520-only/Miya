# PC UI 端集成指南

## ✅ 框架符合性确认

**完全符合弥娅的蛛网式模块化架构！**

### 架构对比

#### 弥娅现有架构
```
Python 后端（单进程）
├── DecisionHub (决策中枢)
├── M-Link (消息路由)
├── PCUINet (PC UI 子网) ← 已存在，826行
├── QQNet (QQ 子网)
├── ToolNet (工具子网)
├── MemoryNet (记忆子网)
└── RuntimeAPIServer (API 服务) ← 已存在
```

#### 新 PC UI 设计
```
Electron 前端
├── 聊天界面
├── Live2D 虚拟形象
├── 悬浮球
├── 桌面宠物
└── 编程界面
         ↓ HTTP/WebSocket
Python 后端（已存在）
├── RuntimeAPIServer
├── DecisionHub
└── PCUINet
```

**架构一致性：✅ 完全一致**
- 新设计只是添加了**前端表示层**
- 核心逻辑、决策、记忆均不变
- 通过标准 HTTP/WebSocket 通信

---

## 🔧 集成步骤

### 步骤 1: 已完成的准备工作

✅ **已创建**：
- `miya-pc-ui/` - Electron + React 前端项目
- `core/pc_ui_api.py` - PC UI API 路由器补充

✅ **已存在**：
- `webnet/pc_ui.py` - PCUINet 子网（826行）
- `core/runtime_api_server.py` - RuntimeAPI 服务器

### 步骤 2: 修改 `run/main.py` 集成 PC UI API

在 `Miya.__init__()` 中添加：

```python
# 在 DecisionHub 初始化之后

# 【新增】初始化 PC UI 子网
from webnet.pc_ui import PCUINet
self.pc_ui_net = PCUINet(
    mlink=self.mlink,
    memory_engine=self.memory_engine,
    emotion_manager=self.emotion
)
await self.pc_ui_net.initialize()

# 【新增】初始化 PC UI API 路由器
from core.pc_ui_api import create_pc_ui_router
from core.runtime_api_server import RuntimeAPIServer

# 如果 RuntimeAPI 服务器已存在，添加 PC UI 路由
if hasattr(self, 'runtime_api_server') and self.runtime_api_server:
    pc_ui_router = create_pc_ui_router(
        mlink=self.mlink,
        pc_ui_net=self.pc_ui_net,
        emotion_manager=self.emotion,
        personality=self.personality
    )
    
    if pc_ui_router:
        self.runtime_api_server.app.include_router(pc_ui_router)
        self.logger.info("[PC UI] API 路由器已集成")
else:
    # 或者创建新的 RuntimeAPI 服务器
    from core.runtime_api import RuntimeAPIServer
    self.runtime_api_server = RuntimeAPIServer(
        host="0.0.0.0",
        port=8000,
        enable_api=True
    )
    
    # 注入依赖
    self.runtime_api_server.set_cognitive_service(self.memory_net)
    
    # 添加 PC UI 路由
    pc_ui_router = create_pc_ui_router(
        mlink=self.mlink,
        pc_ui_net=self.pc_ui_net,
        emotion_manager=self.emotion,
        personality=self.personality
    )
    
    if pc_ui_router:
        self.runtime_api_server.app.include_router(pc_ui_router)
    
    self.logger.info("[PC UI] API 路由器已集成")
```

### 步骤 3: 在 `run()` 方法中启动 RuntimeAPI

```python
async def run(self):
    """启动弥娅系统"""
    # ... 其他初始化代码 ...
    
    # 启动 RuntimeAPI 服务器
    if hasattr(self, 'runtime_api_server') and self.runtime_api_server:
        self.logger.info("[PC UI] 启动 RuntimeAPI 服务器...")
        await self.runtime_api_server.start()
    
    # ... 其他运行代码 ...
```

### 步骤 4: 在 `shutdown()` 方法中停止 RuntimeAPI

```python
async def shutdown(self):
    """关闭弥娅系统"""
    self.logger.info("关闭弥娅系统...")
    
    # 停止 RuntimeAPI 服务器
    if hasattr(self, 'runtime_api_server') and self.runtime_api_server:
        await self.runtime_api_server.stop()
    
    # ... 其他清理代码 ...
```

---

## 📋 API 端点列表

### 新增的 PC UI API 端点

| 方法 | 端点 | 功能 | 请求 | 响应 |
|------|--------|------|------|------|
| POST | `/api/chat` | 发送聊天消息 | `ChatRequest` | `ChatResponse` |
| GET | `/api/status` | 获取系统状态 | - | `SystemStatus` |
| GET | `/api/emotion` | 获取情绪状态 | - | `EmotionState` |
| GET | `/api/sessions` | 获取会话列表 | - | `sessions` |
| POST | `/api/sessions` | 创建新会话 | `session_data` | `session_id` |
| GET | `/api/agents` | 获取 Agent 列表 | - | `agents` |

### 现有的 RuntimeAPI 端点

| 方法 | 端点 | 功能 |
|------|--------|------|
| GET | `/api/probe` | 健康检查 |
| GET | `/health` | 健康检查 |
| GET | `/api/status` | 系统状态（简化版）|
| GET | `/api/endpoints` | 获取交互端列表 |
| POST | `/api/endpoints/{id}/start` | 启动交互端 |
| POST | `/api/endpoints/{id}/stop` | 停止交互端 |
| GET | `/api/cognitive/events` | 查询认知事件 |
| GET | `/api/cognitive/profiles` | 查询用户侧写 |
| GET | `/api/agents` | 获取 Agent 信息 |
| GET | `/api/agents/stats` | 获取 Agent 统计 |
| GET | `/api/queue/stats` | 获取队列统计 |

---

## 🧪 测试步骤

### 1. 启动 Python 后端

```bash
cd d:/AI_MIYA_Facyory/MIYA/Miya
python run/main.py
```

确认看到：
```
[INFO] [PC UI] API 路由器已集成
[INFO] [PC UI] 启动 RuntimeAPI 服务器...
[INFO] Uvicorn running on http://0.0.0.0:8000
```

### 2. 测试 API 端点

```bash
# 健康检查
curl http://localhost:8000/api/probe

# 获取系统状态
curl http://localhost:8000/api/status

# 获取情绪状态
curl http://localhost:8000/api/emotion

# 发送聊天消息
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "session_id": "test"}'
```

### 3. 启动 Electron 前端

```bash
cd d:/AI_MIYA_Facyory/MIYA/Miya/miya-pc-ui
npm install
npm run dev
```

### 4. 测试聊天功能

1. Electron 窗口打开
2. 输入消息："你好"
3. 按 Enter 发送
4. 查看 AI 回复和情绪显示

---

## 🎯 开发优先级

### P0: 基础功能（当前）

- [x] 项目搭建
- [x] 基础聊天界面
- [x] PC UI API 集成（需要手动集成）
- [ ] 情绪可视化
- [ ] 消息持久化

### P0: 情绪可视化（2-3天）

- [ ] 情绪雷达图
- [ ] 情绪历史曲线
- [ ] 情绪动画

### P1: Live2D 集成（5-7天）

- [ ] Live2D SDK 集成
- [ ] 模型加载
- [ ] 情绪驱动
- [ ] 嘴型同步

### P1: 悬浮球（3-5天）

- [ ] 悬浮窗口
- [ ] 拖拽功能
- [ ] 快捷操作

### P2: 桌面宠物（7-10天）

- [ ] 透明窗口
- [ ] 交互功能
- [ ] 闲置动画

### P2: 编程界面（5-7天）

- [ ] Monaco Editor
- [ ] 代码执行
- [ ] 文件管理

---

## ⚠️ 注意事项

1. **后端依赖**：确保 Python 后端已启动，默认监听 `http://localhost:8000`
2. **FastAPI 依赖**：需要安装 `fastapi` 和 `uvicorn`
   ```bash
   pip install fastapi uvicorn
   ```
3. **PCUINet 依赖**：确保 `webnet/pc_ui.py` 正常初始化
4. **M-Link 依赖**：确保 `mlink` 模块正常工作
5. **跨域问题**：FastAPI 默认允许 CORS，如有问题需要配置

---

## 📚 参考文档

- [弥娅架构分析](ARCHITECTURE_ANALYSIS.md)
- [PC UI 开发指南](miya-pc-ui/DEVELOPMENT_GUIDE.md)
- [PC UI 快速开始](miya-pc-ui/QUICKSTART.md)
- [Runtime API 文档](core/runtime_api_server.py)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT
