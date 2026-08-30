# 弥娅 PC UI 端

基于 Electron + React 的弥娅 PC 客户端。

## 功能特性

- ✅ 聊天界面（P0）
- 🔄 情绪可视化（P0 - 进行中）
- 🔄 Live2D 集成（P1 - 计划中）
- 🔄 悬浮球（P1 - 计划中）
- 🔄 桌面宠物（P2 - 计划中）
- 🔄 编程界面（P2 - 计划中）

## 技术栈

- **框架**: Electron 28 + React 18
- **语言**: TypeScript
- **构建工具**: Vite
- **状态管理**: Zustand
- **图表**: Recharts
- **Live2D**: pixi-live2d-display
- **代码编辑器**: Monaco Editor

## 快速开始

### 前置要求

- Node.js 18+
- Python 3.9+ (后端)
- 弥娅后端已启动 (默认端口 8000)

### 安装依赖

```bash
cd miya-pc-ui
npm install
```

### 开发模式

```bash
npm run dev
```

这将启动：
- Vite 开发服务器 (http://localhost:3000)
- Electron 主进程

### 构建

```bash
npm run build
```

构建产物在 `dist/` 目录。

### 打包

```bash
npm run build:electron
```

或者使用 electron-builder 手动打包。

## 项目结构

```
miya-pc-ui/
├── main/              # Electron 主进程
│   ├── index.ts      # 主入口
│   └── preload.ts    # 预加载脚本
├── src/              # React 渲染进程
│   ├── Chat/        # 聊天界面
│   ├── Live2D/      # Live2D 组件
│   ├── FloatingBall/# 悬浮球
│   ├── DesktopPet/  # 桌宠
│   └── CodeEditor/  # 编程界面
├── shared/           # 共享代码
│   ├── types.ts     # TypeScript 类型
│   ├── api.ts       # API 调用
│   └── constants.ts # 常量定义
└── package.json
```

## API 接口

### 聊天接口

```typescript
POST /api/chat
{
  "message": "用户输入",
  "session_id": "session_123",
  "platform": "pc_ui"
}
```

### 状态接口

```typescript
GET /api/status
```

返回系统状态、人格、情绪等信息。

## 开发计划

### P0: 基础聊天界面 (3-5天)
- [x] 项目搭建
- [x] 基础聊天界面
- [ ] 情绪可视化
- [ ] 消息历史持久化

### P0: 情绪可视化 (2-3天)
- [ ] 情绪雷达图
- [ ] 情绪历史曲线
- [ ] 情绪强度动画

### P1: Live2D 集成 (5-7天)
- [ ] Live2D SDK 集成
- [ ] 模型加载
- [ ] 情绪驱动
- [ ] 嘴型同步

### P1: 悬浮球 (3-5天)
- [ ] 悬浮窗口
- [ ] 拖拽功能
- [ ] 快捷操作

### P2: 桌面宠物 (7-10天)
- [ ] 透明窗口
- [ ] 交互功能
- [ ] 闲置动画

### P2: 编程界面 (5-7天)
- [ ] Monaco Editor 集成
- [ ] 代码执行
- [ ] 文件管理

## 注意事项

1. **后端依赖**: 确保 Python 后端已启动，默认监听 `http://localhost:8000`
2. **Live2D 模型**: 需要准备 Live2D 模型文件
3. **跨域问题**: 开发时注意 CORS 配置

## 许可证

MIT
