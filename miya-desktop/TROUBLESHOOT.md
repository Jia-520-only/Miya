# 弥娅桌面应用 - 问题修复指南

## ✅ 已修复的问题

### 1. preload.js 文件缺失

**错误信息**：
```
Unable to load preload script: D:\AI_MIYA_Facyory\MIYA\Miya\miya-desktop\dist-electron\preload.js
Error: ENOENT: no such file or directory
```

**原因**：
- Electron 主进程和 preload 脚本需要先编译才能运行
- `vite-plugin-electron` 会在 `npm run dev` 时自动编译这些文件

**解决方案**：
使用 Vite 开发服务器启动，它会自动编译 Electron 文件：

```bash
# 方法1：使用开发模式启动（推荐）
npm run dev

# 方法2：使用启动脚本
start_dev.bat
```

---

### 2. systemStore 为 null 错误

**错误信息**：
```
Uncaught (in promise) TypeError: Cannot read properties of null (reading 'emotion')
at ComputedRefImpl.fn (ChatView.vue:28:29)
```

**原因**：
- `systemStore` 在某些情况下可能未正确初始化
- 计算属性没有安全检查

**已修复**：
在 `ChatView.vue` 中添加了安全检查：

```typescript
// 计算当前情绪
const currentEmotion = computed(() => {
  try {
    return systemStore?.status?.emotion?.dominant || '平静'
  } catch {
    return '平静'
  }
})

// 计算情绪强度
const emotionIntensity = computed(() => {
  try {
    return systemStore?.status?.emotion?.intensity || 0.5
  } catch {
    return 0.5
  }
})
```

---

## 🚀 启动方式

### 开发模式（推荐）

使用 Vite 开发服务器，它会：
1. 自动编译 Electron 主进程和 preload 脚本
2. 启动 Vite 开发服务器（支持热更新）
3. 同时启动 Electron 应用

```bash
npm run dev
```

### 使用启动脚本

```bash
# Windows
start_dev.bat

# Linux/Mac
bash start_dev.sh
```

### 手动启动（不推荐）

如果需要手动启动，确保先运行 `npm run dev` 编译 Electron 文件。

---

## 📂 文件说明

| 文件 | 说明 |
|-----|------|
| `electron/main.ts` | Electron 主进程入口 |
| `electron/preload.ts` | Preload 脚本（需要在 dist-electron 编译） |
| `dist-electron/` | 编译后的 Electron 文件目录 |
| `vite.config.ts` | Vite 配置（包含 Electron 插件配置） |

---

## 🔧 开发依赖说明

项目使用 `vite-plugin-electron` 插件来编译 Electron 文件，不需要额外安装 `electron-vite`。

关键依赖：
- `vite-plugin-electron` - Electron 集成插件
- `vite-plugin-electron-renderer` - 渲染进程支持
- `electron` - Electron 运行时

---

## 📝 常见问题

### Q: 为什么不能直接用 `npm run dev:electron` 启动？

A: 因为需要先编译 `electron/preload.ts` 到 `dist-electron/preload.js`。使用 `npm run dev` 会自动完成这个步骤。

### Q: 如何重新编译 Electron 文件？

A: 运行 `npm run dev` 会自动重新编译。如果需要清理编译缓存，可以删除 `dist-electron` 目录：

```bash
# Windows
rmdir /s /q dist-electron

# Linux/Mac
rm -rf dist-electron
```

### Q: Live2D SDK 如何安装？

A: 运行安装脚本：

```bash
# Windows
install_live2d_manual.bat

# 手动安装
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

如果遇到权限问题，请以管理员身份运行。

---

## 🎯 下一步

1. **启动应用**：
   ```bash
   npm run dev
   ```

2. **安装 Live2D SDK**（可选）：
   ```bash
   install_live2d_manual.bat
   ```

3. **开始使用**：
   - 右侧会显示御姐猫猫头像（简化版 Live2D）
   - 对话时情绪会实时变化
   - 可以手动切换 8 种表情

---

## 📞 获取帮助

如果遇到其他问题：

1. 检查 `logs/` 目录下的日志文件
2. 查看 Electron 开发者工具的控制台输出
3. 参考 `README.md` 和其他文档

---

最后更新：2026-03-08
