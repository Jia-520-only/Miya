# 弥娅 PC UI 端快速开始

## 🚀 5 分钟快速体验

### 第一步：安装依赖

```bash
cd miya-pc-ui
npm install
```

或者直接运行安装脚本：
```bash
install.bat
```

### 第二步：启动 Python 后端

确保弥娅的 Python 后端正在运行：

```bash
cd ..
python run/main.py
```

确认看到类似输出：
```
[INFO] Runtime API 启动在 http://0.0.0.0:8000
[INFO] 弥娅系统已就绪
```

### 第三步：启动 PC UI

在新的终端窗口中运行：

```bash
cd miya-pc-ui
npm run dev
```

或者直接运行：
```bash
start-dev.bat
```

### 第四步：开始对话

1. Electron 窗口会自动打开
2. 在输入框中输入消息
3. 按 Enter 发送（Shift+Enter 换行）
4. 查看 AI 回复和情绪显示

## 📸 功能预览

### 当前功能

- ✅ 聊天界面
- ✅ 消息历史
- ✅ 情绪实时显示
- ✅ 情绪强度可视化

### 即将上线

- 🔄 Live2D 虚拟形象
- 🔄 悬浮球
- 🔄 桌面宠物
- 🔄 编程界面

## 🎯 使用技巧

### 快捷键

- `Enter` - 发送消息
- `Shift + Enter` - 换行

### 情绪说明

弥娅有 5 种基础情绪：
- 😊 **快乐** (joy) - 金色
- 😢 **悲伤** (sadness) - 蓝色
- 😠 **愤怒** (anger) - 橙红色
- 😨 **恐惧** (fear) - 紫色
- 😲 **惊讶** (surprise) - 粉色

### 侧边栏功能

- **会话历史** - 查看历史对话
- **记忆查看** - 查看弥娅的记忆
- **设置** - 配置系统参数

## ⚠️ 常见问题

### Q: 无法连接后端？

**A:** 检查以下几点：
1. Python 后端是否已启动
2. 后端是否在 `http://localhost:8000`
3. 防火墙是否允许连接

### Q: 消息发送失败？

**A:** 检查网络连接和后端状态

### Q: 情绪显示不更新？

**A:** 确认后端返回了情绪数据

### Q: 窗口显示空白？

**A:** 检查 Vite 开发服务器是否在 `http://localhost:3000`

## 📱 系统要求

- Windows 10+
- Node.js 18+
- Python 3.9+
- 4GB+ RAM
- 500MB 硬盘空间

## 🔧 开发模式

开发模式下会自动开启：
- 热重载（代码修改自动刷新）
- Chrome DevTools（调试工具）
- 日志输出

## 📞 获取帮助

- 查看 [README.md](README.md) 了解详细信息
- 查看 [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) 了解开发细节
- 提交 Issue 反馈问题

## 🎉 开始体验

现在你已经可以开始使用弥娅 PC UI 了！

点击聊天框，输入 "你好"，开始和弥娅的对话吧！
