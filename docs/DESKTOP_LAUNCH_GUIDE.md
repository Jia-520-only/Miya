# 弥娅桌面端 - 完整启动指南

## 🚀 快速启动

### 最简单的方式（推荐）

```bash
# 在项目根目录执行
start_desktop_smart.bat
```

这个脚本会：
1. ✅ 自动清理端口占用
2. ✅ 启动弥娅后端（端口 8000）
3. ✅ 集成桌面端前端

---

## 📋 详细启动步骤

### 方式一：完整启动（包含前端和 Electron）

#### 步骤 1：启动后端
```bash
# 在项目根目录
python run/desktop_main.py
```

等待看到类似这样的输出：
```
✓ 弥娅后端已启动
✓ API 服务运行在 http://localhost:8000
```

#### 步骤 2：启动桌面端
打开新的终端窗口：

```bash
# 进入桌面端目录
cd miya-desktop

# 启动前端和 Electron
npm run dev:all
```

或者分别启动：

```bash
# 终端 2：启动前端
cd miya-desktop
npm run dev

# 终端 3：启动 Electron
cd miya-desktop
npm run dev:electron
```

---

### 方式二：开发模式启动（自动打开开发者工具）

```bash
# 在 miya-desktop 目录
start_dev.bat
```

这会：
1. 启动前端开发服务器（端口 5173）
2. 启动 Electron（自动打开开发者工具）
3. 按 F12 可以随时打开/关闭开发者工具

---

### 方式三：使用 npm 脚本

```bash
# 在 miya-desktop 目录
npm run dev:all
```

---

## 🔍 验证启动成功

### 检查后端
打开浏览器访问：
```
http://localhost:8000/docs
```
应该看到 API 文档页面。

### 检查前端
打开浏览器访问：
```
http://localhost:5173
```
应该看到弥娅的登录/聊天界面。

### 检查 Electron
- 应该看到弥娅桌面应用窗口
- 按 F12 可以打开开发者工具
- 可以看到导航标签（对话、代码、终端、文件、监控）

---

## 🎯 测试导航功能

启动成功后，测试导航标签：

1. **点击"对话"** → 应该显示聊天界面
2. **点击"代码"** → 应该显示代码编辑器
3. **点击"终端"** → 应该显示终端界面
4. **点击"文件"** → 应该显示文件浏览器
5. **点击"监控"** → 应该显示系统监控

如果点击无反应：
1. 按 F12 打开开发者工具
2. 查看 Console 标签是否有错误
3. 参考 `DEVELOPER_TOOLS_GUIDE.md` 进行调试

---

## 🛠️ 故障排除

### 问题 1：端口被占用

**错误信息**：
```
Error: listen EADDRINUSE: address already in use :::8000
```

**解决方案**：
```bash
# Windows - 清理端口 8000
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %a

# Windows - 清理端口 5173
for /f "tokens=5" %a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %a
```

或使用提供的脚本：
```bash
clean_ports.bat
```

### 问题 2：npm 依赖未安装

**错误信息**：
```
Error: Cannot find module '...'
```

**解决方案**：
```bash
cd miya-desktop
npm install
```

### 问题 3：Python 依赖未安装

**错误信息**：
```
ModuleNotFoundError: No module named '...'
```

**解决方案**：
```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 或使用安装脚本
install.bat
```

### 问题 4：Electron 窗口白屏

**解决方案**：
1. 按 F12 打开开发者工具
2. 查看 Console 标签的错误信息
3. 检查前端服务器是否正常运行
4. 尝试刷新页面（Ctrl+R）

### 问题 5：F12 无法打开开发者工具

**解决方案**：
1. 确保使用开发模式启动
2. 通过菜单打开：帮助 → 开发者工具
3. 参考 `DEVELOPER_TOOLS_GUIDE.md`

---

## 📝 启动脚本说明

### start_desktop_smart.bat
- **位置**：项目根目录
- **功能**：一键启动后端 + 前端
- **推荐**：日常使用

### miya-desktop/start_dev.bat
- **位置**：miya-desktop 目录
- **功能**：开发模式启动（自动打开开发者工具）
- **推荐**：开发调试

### miya-desktop/start.bat
- **位置**：miya-desktop 目录
- **功能**：标准启动
- **说明**：确保后端已运行

---

## 🎨 界面预览

### 对话页面
- 聊天界面
- AI 对话
- 会话管理

### 代码页面
- Monaco 编辑器
- 文件树
- 终端集成

### 终端页面
- 命令执行
- 输出显示
- 快捷命令

### 文件页面
- 文件浏览
- 文件操作
- 路径导航

### 监控页面
- CPU 使用率
- 内存使用率
- 磁盘使用率

---

## 💡 使用技巧

### 1. 快捷键

| 快捷键 | 功能 |
|--------|------|
| F12 | 打开/关闭开发者工具 |
| Alt+F4 | 关闭窗口 |
| Ctrl+R | 刷新页面 |

### 2. 导航标签
- 顶部有 5 个导航标签
- 点击即可切换页面
- 当前页面标签会高亮显示

### 3. 开发者工具
- 按 F12 打开
- 查看 Console 错误
- 检查 Elements 样式
- 监控 Network 请求

### 4. 多窗口
- 支持最小化到托盘
- 支持悬浮球模式
- 支持窗口缩放

---

## 🔧 高级配置

### 修改端口

**后端端口（默认 8000）**：
编辑 `config/.env` 文件：
```
PORT=8000
```

**前端端口（默认 5173）**：
编辑 `miya-desktop/vite.config.ts`：
```typescript
export default defineConfig({
  server: {
    port: 5173
  }
})
```

### 启用/禁用开发者工具

在 `electron/modules/window.ts` 中修改：
```typescript
// 自动打开
if (process.env.NODE_ENV === 'development') {
  mainWindow.webContents.openDevTools()
}

// 或添加命令行参数
if (process.argv.includes('--dev')) {
  mainWindow.webContents.openDevTools()
}
```

---

## 📚 相关文档

- **开发者工具指南**：`DEVELOPER_TOOLS_GUIDE.md`
- **代码编辑器指南**：`MIYA_CODE_EDITOR_GUIDE.md`
- **快速启动**：`CODE_EDITOR_QUICK_START.md`
- **导航修复**：`NAVIGATION_FIX_SUMMARY.md`

---

## 🆘 获取帮助

如果遇到问题：

1. **查看错误日志**
   - 开发者工具 Console 标签
   - 终端窗口输出

2. **检查文档**
   - 相关的故障排除指南
   - GitHub Issues

3. **联系支持**
   - GitHub：https://github.com/Jia-520-only/Miya/issues

---

**祝您使用愉快！** 🎉
