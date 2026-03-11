# 弥娅桌面端 - Vue 3 + Electron

基于 Vue 3 + Electron 的弥娅桌面端应用,完全符合弥娅框架启动方式,参考 NagaAgent 架构。

## 功能特性

### 核心功能
- ✅ 聊天界面 - 智能对话,打字机动画
- ✅ 编程界面 - Monaco编辑器 + 终端集成
- ✅ 博客管理 - 文章编辑和发布
- ✅ 系统监控 - 人格/情绪可视化
- ✅ 设置管理 - 应用配置

### 桌面端特色
- ✅ 无边框透明窗口
- ✅ 悬浮球模式(4种状态切换)
- ✅ 窗口动画过渡
- ✅ 系统托盘集成
- ✅ 全局快捷键 (Alt+Space/Alt+F/Alt+C)
- 🚧 Live2D虚拟形象(开发中)
- 🚧 桌面宠物(开发中)

## 技术栈

- **框架**: Vue 3.4 + TypeScript
- **桌面端**: Electron 29
- **构建工具**: Vite 5
- **状态管理**: Pinia
- **UI组件**: PrimeVue
- **代码编辑器**: Monaco Editor

## 快速开始

### 前提条件
- ✅ Python 3.11+ (已安装虚拟环境)
- ✅ Node.js 18+
- ✅ 已配置 `config/.env`

### 启动方式

#### 方式一: 使用主启动菜单 (推荐)
```bash
# Windows
start.bat
# 选择: 4. Start Desktop UI (Electron)

# Linux/Mac
bash start.sh
# 选择: 4. Start Desktop UI (Electron)
```

#### 方式二: 直接启动
```bash
# Windows
start_desktop.bat

# Linux/Mac
bash start_desktop.sh
```

#### 方式三: 开发模式
```bash
# 终端1: 启动后端
python run/main.py

# 终端2: 启动桌面端
cd miya-desktop
npm run dev
```

## 安装依赖

### 基础依赖

如果首次运行,启动脚本会自动安装依赖。也可以手动安装:

```bash
cd miya-desktop
npm install
```

### Live2D SDK

要使用Live2D虚拟形象功能,需要额外安装:

#### 方法一: 使用安装脚本(推荐)

```bash
# 在 miya-desktop 目录下
install_live2d_manual.bat
```

#### 方法二: 手动安装

```bash
cd miya-desktop
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

**注意**: 遇到权限错误时,请以管理员身份运行。

详见 [LIVE2D_INSTALL_GUIDE.md](./LIVE2D_INSTALL_GUIDE.md)

## 构建

```bash
npm run build
```

## 打包

```bash
npm run build:electron
```

生成的安装包在 `release/` 目录.

## 项目结构

```
Miya/
├── run/
│   └── desktop_main.py         # 桌面端主入口 (Python后端)
│
├── miya-desktop/               # Electron桌面应用
│   ├── electron/
│   │   ├── main.ts            # Electron主入口
│   │   ├── preload.ts         # IPC通信
│   │   └── modules/           # 功能模块
│   │       ├── window.ts      # 窗口管理 (参考NagaAgent)
│   │       ├── tray.ts        # 系统托盘
│   │       ├── menu.ts        # 应用菜单
│   │       └── hotkeys.ts     # 全局快捷键
│   │
│   ├── src/
│   │   ├── views/            # Vue页面组件 (9个)
│   │   │   ├── ChatView.vue  # 聊天界面
│   │   │   ├── CodeView.vue  # 编程界面
│   │   │   ├── BlogView.vue  # 博客管理
│   │   │   └── ...
│   │   ├── components/       # 通用组件
│   │   ├── composables/      # 组合式函数
│   │   └── App.vue           # 根组件
│   │
│   └── package.json
│
├── start_desktop.bat          # Windows启动脚本
├── start_desktop.sh           # Linux/Mac启动脚本
└── test_desktop_start.py     # 测试脚本
```

## 文档

- 📖 [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) - 开发指南
- 📖 [DESKTOP_START_GUIDE.md](DESKTOP_START_GUIDE.md) - 使用指南
- 📖 [QUICKSTART.md](QUICKSTART.md) - 快速启动
- 📖 [FINAL_REPORT.md](FINAL_REPORT.md) - 最终报告

## 测试

运行测试脚本检查环境:

```bash
python test_desktop_start.py
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt + Space` | 显示/隐藏主窗口 |
| `Alt + F` | 进入/退出悬浮球模式 |
| `Alt + C` | 快速聊天 |
| `F11` | 全屏切换 |
| `Ctrl + W` | 关闭窗口 |

## 架构说明

### 启动流程

```
start_desktop.bat
  ↓
检查Python环境
  ↓
检查配置文件
  ↓
检查Node.js
  ↓
安装依赖 (首次)
  ↓
启动后端API (run/desktop_main.py)
  ↓
启动Electron (npm run dev)
  ↓
弹出桌面窗口
```

### 通信架构

```
用户操作
  ↓
Electron窗口 (Vue 3)
  ↓
IPC通信 (preload.ts)
  ↓
弥娅后端API (http://127.0.0.1:8000)
  ↓
DecisionHub (决策中枢)
  ↓
弥娅核心系统
```

## 完成度

| 模块 | 完成度 | 说明 |
|------|--------|------|
| 基础架构 | 100% | Vue 3 + Electron + TypeScript |
| 核心功能 | 100% | 聊天/编程/博客/监控 |
| Electron模块 | 100% | 窗口/托盘/菜单/快捷键 |
| 桌面端特色 | 50% | 悬浮球基础完成,Live2D待开发 |
| 打包配置 | 0% | electron-builder待配置 |

**总体完成度: 约 75%**

## 与其他模式对比

| 特性 | 终端模式 | Web模式 | 桌面端 |
|------|---------|---------|--------|
| **启动方式** | 命令行 | 浏览器 | 独立窗口 |
| **界面** | 文本 | 网页 | 原生窗口 |
| **托盘** | ❌ | ❌ | ✅ |
| **快捷键** | ❌ | ❌ | ✅ |
| **悬浮球** | ❌ | ❌ | ✅ (基础) |
| **Live2D** | ❌ | ❌ | 🚧 待开发 |

## 故障排除

详见 [DESKTOP_START_GUIDE.md](DESKTOP_START_GUIDE.md)

## 下一步

- [ ] 集成Live2D虚拟形象
- [ ] 完善悬浮球4种模式
- [ ] 配置electron-builder打包
- [ ] 开发桌面宠物

## 许可

基于弥娅框架,与主项目保持一致。

---

**祝您使用愉快!** 🤖💕
│       ├── window.ts     # 窗口管理
│       ├── tray.ts       # 系统托盘
│       ├── menu.ts       # 菜单
│       └── hotkeys.ts    # 快捷键
├── src/                  # Vue渲染进程
│   ├── views/            # 页面组件
│   ├── components/       # 通用组件
│   ├── composables/      # 组合式函数
│   ├── router/           # 路由配置
│   └── main.ts           # 入口文件
├── resources/            # 资源文件
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 快捷键

- `Alt + Space`: 显示/隐藏主窗口
- `Alt + F`: 进入/退出悬浮球模式
- `Alt + C`: 快速聊天

## API 接口

桌面端通过以下 API 与弥娅后端通信:

- `POST /api/chat` - 对话接口
- `GET /api/status` - 系统状态
- `GET /api/blog` - 博客列表
- `POST /api/blog` - 创建博客
- `POST /api/tools/terminal` - 终端命令

## 注意事项

1. 确保弥娅后端已启动(默认端口 8000)
2. Live2D 模型文件需要放在 `resources/live2d/` 目录
3. 图标文件放在 `resources/icon.png`

## 许可证

MIT
