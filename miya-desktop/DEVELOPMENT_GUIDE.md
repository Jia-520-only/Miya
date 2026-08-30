# 弥娅桌面端开发指南

## 项目概述

弥娅桌面端是一个基于 **Vue 3 + Electron** 的独立桌面应用,参考了 NagaAgent 的成熟架构。

### 核心特性

- ✅ 无边框透明窗口
- ✅ 悬浮球模式(4种状态: classic/ball/compact/full)
- ✅ 平滑窗口动画过渡
- ✅ 系统托盘集成
- ✅ 全局快捷键
- 🚧 Live2D虚拟形象(开发中)
- 🚧 桌面宠物(开发中)

### 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4+ | 前端框架 |
| TypeScript | 5.4+ | 类型安全 |
| Vite | 5.1+ | 构建工具 |
| Electron | 29+ | 桌面应用框架 |
| Pinia | 2.1+ | 状态管理 |
| PrimeVue | 3.52+ | UI组件库 |
| Monaco Editor | 0.45+ | 代码编辑器 |
| Axios | 1.6+ | HTTP客户端 |

---

## 快速开始

### 1. 环境要求

- Node.js 18+
- Python 3.9+ (弥娅后端)
- npm 或 pnpm

### 2. 安装依赖

```bash
cd miya-desktop

# Windows
install.bat

# Linux/macOS
chmod +x install.sh
./install.sh
```

### 3. 启动开发服务器

```bash
# 先启动弥娅后端
cd ..
python run/main.py

# 新终端启动桌面端
cd miya-desktop
npm run dev
```

### 4. 构建应用

```bash
npm run build
```

构建产物在 `release/` 目录。

---

## 项目结构

```
miya-desktop/
├── electron/                  # Electron主进程
│   ├── main.ts               # 主入口文件
│   ├── preload.ts            # 预加载脚本(IPC通信)
│   └── modules/              # 功能模块
│       ├── window.ts         # 窗口管理(悬浮球逻辑)
│       ├── tray.ts           # 系统托盘
│       ├── menu.ts           # 应用菜单
│       └── hotkeys.ts        # 全局快捷键
│
├── src/                      # Vue渲染进程
│   ├── views/                # 页面组件
│   │   ├── ChatView.vue      # 对话界面
│   │   ├── CodeView.vue      # 编程界面
│   │   ├── BlogView.vue      # 博客管理
│   │   ├── MonitorView.vue   # 系统监控
│   │   ├── SettingsView.vue  # 设置
│   │   └── AboutView.vue     # 关于
│   │
│   ├── components/           # 通用组件
│   │   └── TitleBar.vue      # 自定义标题栏
│   │
│   ├── composables/          # 组合式函数
│   │   ├── useElectron.ts    # Electron封装
│   │   └── useFloatingState.ts  # 悬浮球状态管理
│   │
│   ├── router/               # 路由配置
│   │   └── index.ts
│   │
│   ├── App.vue               # 根组件
│   ├── main.ts               # Vue入口
│   └── style.css             # 全局样式
│
├── resources/                # 资源文件
│   ├── icon.png              # 应用图标
│   ├── live2d/               # Live2D模型
│   └── public/               # 公共资源
│
├── package.json              # 项目配置
├── vite.config.ts            # Vite配置
├── tsconfig.json             # TypeScript配置
└── electron-builder.yml      # 打包配置
```

---

## 核心架构

### Electron主进程

主进程负责:
- 窗口创建和管理
- 系统托盘
- 全局快捷键
- IPC通信

**关键文件**: `electron/main.ts`

### Vue渲染进程

渲染进程负责:
- UI渲染
- 用户交互
- 与后端API通信
- 状态管理

**关键文件**: `src/App.vue`

### 窗口管理

窗口管理模块实现了悬浮球的核心逻辑:

- **classic**: 经典窗口模式
- **ball**: 悬浮球模式(100x100)
- **compact**: 展开紧凑模式
- **full**: 完整展开模式

**关键文件**: `electron/modules/window.ts`

---

## API通信

### 与弥娅后端通信

桌面端通过HTTP API与弥娅后端通信:

```typescript
// 示例: 发送聊天消息
const response = await axios.post('http://localhost:8000/api/chat', {
  message: '你好',
  session_id: 'desktop_session',
  platform: 'desktop'
})

// 示例: 获取系统状态
const status = await axios.get('http://localhost:8000/api/status')
```

### IPC通信

渲染进程与主进程通过IPC通信:

```typescript
// 示例: 最小化窗口
window.electronAPI.minimize()

// 示例: 监听悬浮球状态变化
window.electronAPI.onFloatingStateChanged((state) => {
  console.log('当前状态:', state)
})
```

---

## 开发功能

### 1. 添加新页面

1. 在 `src/views/` 创建Vue组件
2. 在 `src/router/index.ts` 添加路由

```typescript
{
  path: '/new-page',
  name: 'NewPage',
  component: () => import('@views/NewPage.vue')
}
```

3. 在侧边栏添加导航链接(在 `src/App.vue`)

### 2. 添加新的IPC功能

1. 在 `electron/preload.ts` 暴露API
2. 在 `electron/main.ts` 注册处理器

```typescript
// 预加载脚本
contextBridge.exposeInMainWorld('electronAPI', {
  myNewFunction: () => ipcRenderer.invoke('my:new-function')
})

// 主进程
ipcMain.handle('my:new-function', () => {
  // 处理逻辑
  return result
})
```

### 3. 添加状态管理

使用Pinia创建store:

```typescript
// src/stores/myStore.ts
import { defineStore } from 'pinia'

export const useMyStore = defineStore('my', {
  state: () => ({
    data: null
  }),
  actions: {
    async fetchData() {
      const response = await axios.get('/api/data')
      this.data = response.data
    }
  }
})
```

---

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt + Space` | 显示/隐藏主窗口 |
| `Alt + F` | 进入/退出悬浮球模式 |
| `Alt + C` | 快速聊天(展开悬浮球) |

---

## 调试技巧

### 1. 开发模式

开发模式会自动打开DevTools:

```bash
npm run dev
```

### 2. 查看渲染进程日志

在DevTools的Console中查看。

### 3. 查看主进程日志

主进程日志输出在终端。

### 4. 调试IPC

使用 `console.log` 在preload脚本中调试。

---

## 常见问题

### Q1: 启动时报错 "找不到模块"

确保已安装依赖:
```bash
npm install
```

### Q2: 后端连接失败

确保弥娅后端已启动:
```bash
cd ..
python run/main.py
```

### Q3: 窗口样式异常

检查 `src/style.css` 是否正确加载。

### Q4: 悬浮球模式无法进入

检查窗口状态,确保不在全屏模式下。

---

## 待开发功能

- [ ] Live2D虚拟形象集成
- [ ] 桌面宠物功能
- [ ] 语音交互
- [ ] 代码执行完善
- [ ] 文件管理器
- [ ] 主题切换
- [ ] 多语言支持

---

## 参考资源

- [Vue 3文档](https://vuejs.org/)
- [Electron文档](https://www.electronjs.org/)
- [Vite文档](https://vitejs.dev/)
- [PrimeVue文档](https://primevue.org/)
- [NagaAgent项目](https://github.com/Xxiii8322766509/NagaAgent)

---

## 许可证

MIT
