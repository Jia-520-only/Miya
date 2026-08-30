# 弥娅桌面端 - 快速启动指南

## 🚀 5分钟快速开始

### 步骤1: 安装依赖

```bash
cd miya-desktop

# Windows
install.bat

# Linux/macOS
chmod +x install.sh && ./install.sh
```

### 步骤2: 启动弥娅后端

打开一个新终端:

```bash
cd d:/AI_MIYA_Facyory/MIYA/Miya
python run/main.py
```

等待看到 "服务器已启动" 消息。

### 步骤3: 启动桌面端

在原终端:

```bash
# Windows
start.bat

# Linux/macOS
./start.sh
```

或者直接运行:

```bash
npm run dev
```

### 步骤4: 享受弥娅!

桌面端会自动弹出,开始与弥娅对话吧!

---

## 📦 功能一览

### 已完成功能 ✅

- 🖥️ **对话界面** - 与弥娅进行智能对话
- 💻 **编程界面** - Monaco代码编辑器 + 代码执行
- 📝 **博客管理** - 创建和管理博客文章
- 📊 **系统监控** - 实时查看人格和情绪状态
- ⚙️ **设置页面** - 配置应用偏好
- ℹ️ **关于页面** - 版本和系统信息
- 🎨 **暗色主题** - 护眼的深色界面
- 📌 **系统托盘** - 最小化到托盘
- ⌨️ **快捷键** - Alt+Space, Alt+F, Alt+C

### 开发中功能 🚧

- 🎭 Live2D虚拟形象
- 🐱 桌面宠物
- 🎤 语音交互
- 📁 文件管理器
- 🌐 多语言支持

---

## ⌨️ 快捷键

| 按键 | 功能 |
|------|------|
| `Alt + Space` | 显示/隐藏主窗口 |
| `Alt + F` | 进入/退出悬浮球模式 |
| `Alt + C` | 快速聊天(展开悬浮球) |

---

## 🔧 故障排除

### 问题1: 启动时报错

**错误**: `Module not found: Error: Can't resolve`

**解决**: 重新安装依赖
```bash
rm -rf node_modules package-lock.json
npm install
```

### 问题2: 后端连接失败

**错误**: `Network Error` 或 `连接被拒绝`

**解决**:
1. 确认弥娅后端已启动
2. 检查端口8000是否被占用
3. 修改 `src/views/*.vue` 中的API地址

### 问题3: 窗口无法启动

**错误**: Electron窗口不显示

**解决**:
1. 检查终端是否有错误日志
2. 确认 `dist/` 目录已生成
3. 尝试删除 `dist/` 重新构建

---

## 📁 项目目录

```
miya-desktop/
├── electron/          # Electron主进程
├── src/               # Vue前端
├── resources/         # 资源文件
├── install.bat        # Windows安装脚本
├── start.bat          # Windows启动脚本
└── README.md          # 详细文档
```

---

## 📖 更多文档

- [开发指南](DEVELOPMENT_GUIDE.md) - 完整的开发文档
- [API文档](../docs/) - 弥娅后端API文档
- [主README](../README.md) - 弥娅项目总览

---

## 💡 提示

1. 首次启动可能需要较长时间(编译TypeScript)
2. 开发模式会自动打开DevTools方便调试
3. 确保Node.js版本 >= 18
4. 推荐使用VS Code + Volar插件开发

---

## 🤝 贡献

欢迎提交Issue和Pull Request!

---

**享受与弥娅的对话时光!** 🤖💕
