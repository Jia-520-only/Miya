# Live2D 独立窗口功能

## 功能概述

现在 Live2D 可以在一个独立的桌面窗口中显示，支持以下功能：

### 核心功能
1. ✅ **独立窗口** - Live2D 在独立的 Electron 窗口中显示
2. ✅ **自由拖动** - 窗口可以在桌面上自由拖动
3. ✅ **调整大小** - 可以自由调整窗口大小
4. ✅ **始终置顶** - 可选的窗口置顶功能
5. ✅ **透明背景** - 窗口背景透明，只显示 Live2D 角色
6. ✅ **无边框设计** - 现代化的无边框窗口

### 控制面板
在主窗口的聊天界面中，通过控制面板可以：
- 打开/关闭 Live2D 窗口
- 调整窗口大小（200-800px 宽度，300-900px 高度）
- 切换窗口置顶状态
- 控制 8 种表情（开心、害羞、生气、悲伤、平静、兴奋、调皮、嘘声）
- 快速设置预设大小（小、中、大、全屏）

## 使用方法

### 1. 打开控制面板
在聊天界面左侧工具栏，点击机器人图标 🤮 即可打开 Live2D 控制面板。

### 2. 创建独立窗口
在控制面板中点击"打开窗口"按钮，会在桌面上创建一个新的 Live2D 窗口。

### 3. 调整窗口
- **拖动**: 点击并拖动窗口任意位置
- **调整大小**: 拖动窗口边缘调整大小，或在控制面板中使用滑块
- **置顶**: 点击"窗口置顶"按钮切换置顶状态

### 4. 控制表情
在控制面板的表情网格中点击任意表情按钮，Live2D 角色会立即切换表情。

## 技术架构

### 文件结构
```
miya-desktop/
├── electron/
│   ├── main.ts                      # 主进程（添加了 Live2D IPC 处理）
│   └── modules/
│       ├── live2d-window.ts         # Live2D 窗口管理模块
│       └── ...
├── src/
│   ├── components/
│   │   ├── Live2DFull.vue           # Live2D 完整版组件
│   │   └── Live2DControlPanel.vue   # Live2D 控制面板组件
│   ├── views/
│   │   ├── Live2DStandalone.vue     # Live2D 独立页面
│   │   └── ChatView.vue            # 聊天界面（集成控制面板）
│   └── router/
│       └── index.ts                 # 路由配置（添加 /live2d 路由）
└── public/
    └── libraries/                   # Live2D 本地库文件
        ├── live2dcubismcore.min.js
        ├── pixi.min.js
        └── pixi-live2d-display.min.js
```

### 核心模块

#### 1. Live2D 窗口管理 (electron/modules/live2d-window.ts)
- `createLive2DWindow()` - 创建独立窗口
- `getLive2DWindow()` - 获取窗口实例
- `closeLive2DWindow()` - 关闭窗口
- `toggleLive2DWindow()` - 切换显示/隐藏
- `setLive2DWindowSize()` - 设置窗口大小
- `setLive2DWindowPosition()` - 设置窗口位置
- `setLive2DWindowAlwaysOnTop()` - 设置置顶状态

#### 2. IPC 通信 (electron/main.ts)
主进程注册的 IPC 处理器：
- `live2d:create` - 创建窗口
- `live2d:get` - 获取窗口
- `live2d:close` - 关闭窗口
- `live2d:toggle` - 切换窗口
- `live2d:setSize` - 设置大小
- `live2d:setPosition` - 设置位置
- `live2d:setAlwaysOnTop` - 设置置顶
- `live2d:setExpression` - 设置表情（主进程 → Live2D 窗口）

#### 3. Live2D 控制面板 (src/components/Live2DControlPanel.vue)
- 窗口控制（打开、关闭、置顶）
- 大小调节（滑块控制）
- 表情控制（8种表情）
- 快捷预设（小、中、大、全屏）

#### 4. Live2D 独立页面 (src/views/Live2DStandalone.vue)
- 纯净的 Live2D 显示页面
- 监听表情控制 IPC 消息
- 支持拖动（`-webkit-app-region: drag`）

### 窗口配置
```typescript
const LIVE2D_WINDOW_CONFIG = {
  width: 400,
  height: 500,
  x: 100,
  y: 100,
  frame: false,        // 无边框
  transparent: true,   // 透明背景
  resizable: true,      // 可调整大小
  alwaysOnTop: true,    // 始终置顶
  skipTaskbar: false,   // 显示在任务栏
  webPreferences: {
    preload: join(__dirname, '../preload/index.js'),
    contextIsolation: true,
    nodeIntegration: false,
    webSecurity: false // 允许加载本地资源
  }
}
```

## 通信流程

### 表情控制流程
```
用户点击表情（主窗口）
  → Live2DControlPanel.vue
  → IPC: live2d:setExpression
  → main.ts (主进程)
  → IPC: live2d:setExpression (转发)
  → Live2DStandalone.vue (Live2D 窗口)
  → Live2DFull.vue (更新表情)
```

### 窗口控制流程
```
用户点击打开窗口（主窗口）
  → Live2DControlPanel.vue
  → IPC: live2d:create
  → live2d-window.ts
  → BrowserWindow (创建新窗口)
  → 加载 /live2d 路由
  → Live2DStandalone.vue
```

## 特性说明

### 1. 拖动功能
通过 CSS 属性 `-webkit-app-region: drag` 实现整个窗口可拖动。

### 2. 调整大小
窗口原生支持调整大小，同时提供滑块精确控制。

### 3. 置顶功能
默认置顶，可以切换关闭。适合在观看视频或工作时陪伴。

### 4. 透明背景
设置 `transparent: true` 和 `frame: false`，只显示 Live2D 角色。

## 未来优化

### 计划功能
- [ ] 窗口位置记忆（自动保存上次位置）
- [ ] 多模型支持（可以切换不同的 Live2D 模型）
- [ ] 动作控制（播放不同的动作）
- [ ] 眼神跟随（鼠标跟随功能）
- [ ] 呼吸动画（更自然的呼吸效果）
- [ ] 点击交互（点击角色触发反应）
- [ ] 右键菜单（快速访问常用功能）

### 性能优化
- [ ] 模型缓存（避免重复加载）
- [ ] 渲染优化（减少资源占用）
- [ ] 懒加载（按需加载模型）

## 故障排除

### 窗口无法打开
1. 检查控制台日志
2. 确认库文件已下载到 `public/libraries/`
3. 重启应用

### 表情不切换
1. 确认 Live2D 窗口已打开
2. 检查 IPC 通信是否正常
3. 查看控制台错误信息

### 窗口无法拖动
1. 检查窗口是否被设置为不可拖动
2. 确认 CSS 中 `-webkit-app-region: drag` 是否生效

## 快捷键（计划）
- `Ctrl + L` - 切换 Live2D 窗口显示/隐藏
- `Ctrl + 1-8` - 快速切换表情 1-8
- `Ctrl + +` - 放大窗口
- `Ctrl + -` - 缩小窗口

## 相关文档
- `LIVE2D_LOCAL_LIBRARY_FIX.md` - 本地库文件修复
- `LIVE2D_FULL_GUIDE.md` - Live2D 完整版指南
- `DESKTOP_START_GUIDE.md` - 桌面应用启动指南

## 更新日志

### v1.0.0 (2026-03-08)
- ✅ 实现独立窗口功能
- ✅ 支持拖动和调整大小
- ✅ 添加控制面板
- ✅ 支持 8 种表情控制
- ✅ 窗口置顶功能
- ✅ 透明背景支持

---

Enjoy your Live2D standalone window! 🎉
