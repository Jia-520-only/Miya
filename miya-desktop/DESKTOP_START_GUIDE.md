# 弥娅桌面端使用指南

## 📦 快速开始

### 前提条件

- ✅ Python 3.11+ (已安装虚拟环境)
- ✅ Node.js 18+
- ✅ 已配置 `config/.env`
- ✅ 弥娅后端依赖已安装

### 启动方式

#### 方式一：使用主启动菜单 (推荐)

```bash
# Windows
start.bat

# Linux/Mac
bash start.sh
```

然后选择 `4. Start Desktop UI (Electron)`

#### 方式二：直接启动

```bash
# Windows
start_desktop.bat

# Linux/Mac
bash start_desktop.sh
```

---

## 🚀 启动流程

启动脚本会自动执行以下步骤:

1. **检查Python环境** - 验证虚拟环境存在
2. **检查配置文件** - 验证 `config/.env` 存在
3. **清理端口** - 清理被占用的8000端口
4. **检查Node.js** - 验证Node.js版本
5. **安装依赖** - 首次启动时自动安装桌面端依赖
6. **启动服务** - 启动后端API和Electron窗口

---

## 🎯 启动成功后的状态

```
========================================
弥娅桌面端启动中...
========================================

后端API服务启动中...
访问地址: http://127.0.0.1:8000

等待后端启动...

========================================
桌面端启动完成!
========================================

说明:
  - 后端API: http://127.0.0.1:8000
  - 桌面窗口: 即将弹出
  - 按Ctrl+C停止服务
```

---

## 📂 项目结构

```
Miya/
├── run/
│   └── desktop_main.py         # 桌面端主入口(Python后端)
├── miya-desktop/               # Electron桌面应用
│   ├── electron/
│   │   ├── main.ts            # Electron主进程
│   │   ├── preload.ts         # IPC通信
│   │   └── modules/           # 功能模块
│   ├── src/
│   │   ├── views/             # Vue页面组件
│   │   ├── components/        # 通用组件
│   │   └── composables/       # 组合式函数
│   └── package.json
├── start_desktop.bat           # Windows启动脚本
└── start_desktop.sh            # Linux/Mac启动脚本
```

---

## 🔧 开发模式

### 启动开发模式

```bash
# 1. 启动弥娅后端 (终端1)
python run/main.py

# 2. 启动桌面端 (终端2)
cd miya-desktop
npm run dev
```

### 构建生产版本

```bash
cd miya-desktop
npm run build:electron
```

### 打包安装包

```bash
cd miya-desktop
npm run build
```

生成的安装包在 `release/` 目录:
- Windows: `Miya-Setup-x.x.x.exe`
- macOS: `弥娅-x.x.x.dmg`
- Linux: `Miya_x.x.x_amd64.deb`

---

## 🎮 功能特性

### 核心功能

- ✅ **对话界面** - 智能聊天,打字机动画
- ✅ **编程界面** - Monaco编辑器 + 终端
- ✅ **博客管理** - 文章编辑和发布
- ✅ **系统监控** - 人格/情绪可视化
- ✅ **设置管理** - 应用配置

### 桌面端特色

- ✅ **无边框窗口** - 精美界面设计
- ✅ **系统托盘** - 最小化到托盘
- ✅ **全局快捷键** - Alt+Space/Alt+F/Alt+C
- ✅ **悬浮球模式** - 4种模式切换 (开发中)
- ✅ **Live2D形象** - 动态虚拟形象 (开发中)

---

## 🔄 通信架构

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

---

## 🎨 窗口模式

### 1. Classic 模式
- 默认完整窗口
- 包含所有功能

### 2. Ball 模式 (悬浮球)
- 小型悬浮窗口 (200x200px)
- 始终置顶
- 快速对话

### 3. Compact 模式
- 紧凑型窗口
- 适合小屏幕

### 4. Full 模式
- 全屏模式
- 专注体验

快捷键: `Alt + F` 切换模式

---

## 📱 快捷键列表

| 快捷键 | 功能 |
|--------|------|
| `Alt + Space` | 显示/隐藏主窗口 |
| `Alt + F` | 进入/退出悬浮球模式 |
| `Alt + C` | 快速聊天 |
| `F11` | 全屏切换 |
| `Ctrl + W` | 关闭窗口 |

---

## 🛠️ 故障排除

### 问题1: Electron窗口未弹出

**解决方案:**
```bash
# 检查Node.js版本
node --version  # 应该 >= 18

# 手动启动Electron
cd miya-desktop
npm run dev
```

### 问题2: 后端API无法访问

**解决方案:**
```bash
# 检查端口占用
netstat -ano | findstr :8000

# 清理端口
taskkill /F /PID <PID>

# 检查后端日志
logs/miya_desktop_desktop_main.log
```

### 问题3: 依赖安装失败

**解决方案:**
```bash
cd miya-desktop
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### 问题4: 配置文件错误

**解决方案:**
```bash
# 检查配置文件
cat config/.env

# 重新配置
cp config/.env.example config/.env
```

---

## 📊 日志文件

- `logs/miya_desktop_desktop_main.log` - 桌面端主日志
- `logs/miya_{日期}.log` - 弥娅核心日志

---

## 🎯 与其他模式对比

| 特性 | 终端模式 | Web模式 | 桌面端 |
|------|---------|---------|--------|
| **启动方式** | 命令行 | 浏览器 | 独立窗口 |
| **界面** | 文本 | 网页 | 原生窗口 |
| **托盘** | ❌ | ❌ | ✅ |
| **快捷键** | ❌ | ❌ | ✅ |
| **悬浮球** | ❌ | ❌ | ✅ (开发中) |
| **Live2D** | ❌ | ❌ | ✅ (开发中) |
| **系统访问** | ✅ | ❌ | ✅ |
| **离线使用** | ❌ | ❌ | ✅ |

---

## 💡 开发建议

1. **先测试后端** - 确保 `run/main.py` 正常运行
2. **逐步启动** - 先启动后端,再启动桌面端
3. **查看日志** - 遇到问题先看日志文件
4. **热重载** - 开发模式支持热重载,修改代码自动刷新

---

## 📞 获取帮助

- 查看日志: `logs/miya_desktop_desktop_main.log`
- 检查配置: `config/.env`
- 测试API: 访问 `http://127.0.0.1:8000/docs`

---

## ✨ 下一步

- [ ] 集成Live2D虚拟形象
- [ ] 完善悬浮球4种模式
- [ ] 开发桌面宠物
- [ ] 添加语音交互
- [ ] 配置自动更新

---

**祝您使用愉快!** 🤖💕
