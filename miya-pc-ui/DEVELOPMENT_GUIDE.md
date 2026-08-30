# 弥娅 PC UI 端开发指南

## 📋 项目概览

弥娅 PC UI 端是基于 Electron + React 的桌面应用，提供聊天、情绪可视化、Live2D 虚拟形象、悬浮球、桌面宠物等功能。

## 🎯 技术选型

### 为什么选择 Electron + React？

**Electron 优势：**
- ✅ 跨平台支持（Windows、macOS、Linux）
- ✅ 丰富的桌面功能（系统托盘、文件系统、原生通知）
- ✅ 可以使用 Web 技术
- ✅ 生态系统成熟

**React 优势：**
- ✅ 组件化开发
- ✅ 状态管理（Zustand）
- ✅ 丰富的 UI 库
- ✅ TypeScript 支持良好

**其他选项对比：**
- **PyQt5**: 纯 Python，但 UI 美观度差，学习成本高
- **纯 Web**: 无法访问桌面功能（悬浮球、桌宠）
- **Tauri**: 更轻量，但生态不如 Electron

## 🏗️ 架构设计

### 整体架构

```
┌─────────────────────────────────────────────┐
│         Electron 主进程                       │
│  - 窗口管理                                   │
│  - 系统托盘                                   │
│  - 文件系统访问                               │
│  - IPC 通信                                   │
└───────────────┬─────────────────────────────┘
                ↓ IPC
┌─────────────────────────────────────────────┐
│         React 渲染进程                       │
│  ├── 聊天界面                                │
│  ├── Live2D 视图                             │
│  ├── 悬浮球                                  │
│  └── 桌面宠物                                │
└───────────────┬─────────────────────────────┘
                ↓ WebSocket/HTTP
┌─────────────────────────────────────────────┐
│         Python 后端                          │
│  ├── RuntimeAPI                             │
│  ├── DecisionHub                            │
│  ├── TTS 引擎                                │
│  └── 状态推送                                │
└─────────────────────────────────────────────┘
```

### 数据流

```
用户输入
  ↓
React 组件
  ↓
API 调用 (axios)
  ↓
Python 后端 (WebSocket/HTTP)
  ↓
DecisionHub 处理
  ↓
AI 推理 + 情绪生成
  ↓
响应返回
  ↓
React 更新 UI + Live2D 动画
```

## 📁 项目结构详解

```
miya-pc-ui/
│
├── main/                    # Electron 主进程
│   ├── index.ts            # 入口，创建窗口
│   ├── window.ts           # 窗口管理（后续添加）
│   ├── floating-ball.ts    # 悬浮球窗口（后续添加）
│   ├── desktop-pet.ts      # 桌宠窗口（后续添加）
│   └── preload.ts          # 预加载脚本，暴露 API
│
├── src/                     # React 渲染进程
│   ├── main.tsx            # React 入口
│   ├── App.tsx             # 主应用，路由配置
│   ├── index.css           # 全局样式
│   │
│   ├── Chat/               # 聊天模块
│   │   └── ChatWindow.tsx # 聊天主界面
│   │
│   ├── Live2D/             # Live2D 模块（后续添加）
│   │   ├── Live2DViewer.tsx      # Live2D 查看器
│   │   ├── emotionMapping.ts       # 情绪映射
│   │   └── mouthSync.ts           # 嘴型同步
│   │
│   ├── FloatingBall/       # 悬浮球模块（后续添加）
│   │   ├── FloatingBall.tsx       # 悬浮球组件
│   │   └── QuickActions.tsx       # 快捷操作菜单
│   │
│   ├── DesktopPet/         # 桌宠模块（后续添加）
│   │   ├── DesktopPet.tsx         # 桌宠组件
│   │   └── Interactions.tsx       # 交互逻辑
│   │
│   ├── CodeEditor/         # 编程模块（后续添加）
│   │   ├── CodeEditor.tsx         # 编程界面
│   │   └── MonacoEditor.tsx       # Monaco 编辑器
│   │
│   └── shared/             # 共享组件（后续添加）
│       ├── Sidebar.tsx             # 侧边栏
│       ├── Settings.tsx            # 设置面板
│       └── MemoryView.tsx          # 记忆查看
│
├── shared/                   # 共享代码（渲染进程和主进程）
│   ├── types.ts            # TypeScript 类型定义
│   ├── api.ts              # API 调用封装
│   └── constants.ts        # 常量定义
│
├── index.html               # HTML 入口
├── package.json            # 项目配置
├── tsconfig.json           # TypeScript 配置
├── vite.config.ts          # Vite 配置
└── README.md               # 项目说明
```

## 🔌 API 接口设计

### 1. 聊天接口

**端点**: `POST /api/chat`

**请求**:
```json
{
  "message": "用户输入的消息",
  "session_id": "session_123",
  "platform": "pc_ui"
}
```

**响应**:
```json
{
  "response": "AI 的回复",
  "emotion": {
    "dominant": "joy",
    "intensity": 0.8,
    "all": {
      "joy": 0.8,
      "sadness": 0.05,
      "anger": 0.05,
      "fear": 0.05,
      "surprise": 0.05
    }
  },
  "timestamp": "2026-03-06T12:00:00Z",
  "tts_url": "http://localhost:8000/tts/audio123.mp3"
}
```

### 2. 状态接口

**端点**: `GET /api/status`

**响应**:
```json
{
  "identity": {
    "name": "弥娅",
    "version": "1.0.0"
  },
  "personality": {
    "warmth": 0.8,
    "logic": 0.7,
    "creativity": 0.6,
    "empathy": 0.75,
    "resilience": 0.7
  },
  "emotion": {
    "dominant": "joy",
    "intensity": 0.8,
    "all": {
      "joy": 0.8,
      "sadness": 0.05,
      "anger": 0.05,
      "fear": 0.05,
      "surprise": 0.05
    }
  },
  "memory_stats": {
    "short_term": 20,
    "long_term": 1234,
    "vector_count": 5678
  }
}
```

### 3. Live2D 情绪推送（WebSocket）

**端点**: `WS /ws/live2d`

**消息**:
```json
{
  "emotion": "joy",
  "intensity": 0.8,
  "expression": {
    "mouth": "smile",
    "eyes": "happy",
    "brow": "normal"
  },
  "timestamp": "2026-03-06T12:00:00Z"
}
```

### 4. 代码执行接口（后续）

**端点**: `POST /api/execute`

**请求**:
```json
{
  "code": "print('Hello, Miya!')",
  "language": "python",
  "session_id": "session_123"
}
```

**响应**:
```json
{
  "output": "Hello, Miya!\n",
  "error": null,
  "execution_time": 0.123
}
```

## 🎨 情绪映射设计

### Live2D 表情映射

```typescript
const EMOTION_TO_LIVE2D = {
  joy: {
    motion: 'idle_smile',
    expression: 'smile',
    intensityMap: {
      low: 'idle_smile_1',
      medium: 'idle_smile_2',
      high: 'idle_smile_3'
    }
  },
  sadness: {
    motion: 'sad',
    expression: 'sad',
    intensityMap: {
      low: 'sad_1',
      medium: 'sad_2',
      high: 'sad_3'
    }
  },
  anger: {
    motion: 'angry',
    expression: 'angry',
    intensityMap: {
      low: 'angry_1',
      medium: 'angry_2',
      high: 'angry_3'
    }
  },
  fear: {
    motion: 'surprise',
    expression: 'surprise',
    intensityMap: {
      low: 'surprise_1',
      medium: 'surprise_2',
      high: 'surprise_3'
    }
  },
  surprise: {
    motion: 'surprise',
    expression: 'surprise',
    intensityMap: {
      low: 'surprise_1',
      medium: 'surprise_2',
      high: 'surprise_3'
    }
  }
}
```

### 情绪颜色方案

```typescript
const EMOTION_COLORS = {
  joy: '#FFD700',      // 金色
  sadness: '#4169E1',  // 皇家蓝
  anger: '#FF4500',    // 橙红色
  fear: '#9932CC',     // 深紫色
  surprise: '#FF69B4'  // 热粉色
}
```

## 🚀 开发流程

### 1. 环境搭建

```bash
# 安装依赖
cd miya-pc-ui
npm install

# 启动开发服务器
npm run dev
```

### 2. 开发模式

开发模式下会自动：
- 启动 Vite 开发服务器 (http://localhost:3000)
- 启动 Electron 主进程
- 开启热重载

### 3. 构建

```bash
# 构建前端和主进程
npm run build

# 构建产物在 dist/ 目录
```

### 4. 调试

- **前端调试**: 使用 Chrome DevTools（自动打开）
- **主进程调试**: 使用 VS Code 调试配置

## 📝 开发优先级

### P0: 基础功能（当前）

- [x] 项目搭建
- [x] 基础聊天界面
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

## 🎯 下一步行动

1. **安装依赖并启动**
   ```bash
   cd miya-pc-ui
   npm install
   npm run dev
   ```

2. **确保 Python 后端运行**
   ```bash
   cd ..
   python run/main.py
   ```

3. **测试聊天功能**
   - 打开 Electron 窗口
   - 发送消息
   - 查看情绪显示

4. **完善情绪可视化**
   - 添加情绪雷达图
   - 添加情绪历史曲线

5. **准备 Live2D 模型**
   - 获取或制作 Live2D 模型
   - 配置表情和动画

## ⚠️ 注意事项

1. **后端依赖**: 确保 Python 后端已启动，默认监听 `http://localhost:8000`
2. **Live2D 模型**: 需要准备 Live2D 模型文件（.moc3, .model3.json）
3. **跨域问题**: 开发时注意 CORS 配置
4. **性能优化**: Live2D 渲染可能占用较多资源，注意优化
5. **窗口管理**: 多窗口场景下注意内存管理

## 📚 参考资源

- [Electron 文档](https://www.electronjs.org/docs)
- [React 文档](https://react.dev)
- [Vite 文档](https://vitejs.dev)
- [Live2D Cubism SDK](https://www.live2d.com/en/sdk/cubism-sdk)
- [Monaco Editor](https://microsoft.github.io/monaco-editor)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT
