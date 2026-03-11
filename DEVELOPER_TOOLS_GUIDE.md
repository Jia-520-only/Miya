# 弥娅桌面端 - 开发者工具使用指南

## 📋 问题说明

之前 F12 无法打开开发者工具的问题已修复。

## 🔧 修复内容

### 1. 添加 F12 快捷键支持
在 `electron/modules/window.ts` 中添加了 F12 快捷键监听，现在可以：
- **按 F12** - 打开/关闭开发者工具

### 2. 添加菜单选项
在 `electron/modules/menu.ts` 中添加了"开发者工具"菜单项：
- 通过菜单栏：帮助 → 开发者工具

### 3. 优化启动脚本
- 修改了 `start.bat`，设置 `NODE_ENV=development`
- 创建了 `start_dev.bat`，专门用于开发模式启动

## 🚀 启动方式

### 方式一：完整启动（推荐）

```bash
# 1. 启动后端
python run/desktop_main.py

# 2. 启动桌面端（新终端）
cd miya-desktop
npm run dev:all
```

或使用启动脚本：

```bash
# 根目录
start_desktop_smart.bat
```

### 方式二：开发模式启动

```bash
# 在 miya-desktop 目录
start_dev.bat
```

这会：
1. 自动清理端口占用
2. 启动前端开发服务器（端口 5173）
3. 启动 Electron（自动打开开发者工具）

### 方式三：手动启动

```bash
# 终端 1：启动前端
cd miya-desktop
npm run dev

# 终端 2：启动 Electron
cd miya-desktop
npm run dev:electron
```

## 🎯 打开开发者工具的方法

### 方法 1：键盘快捷键
- **按 F12** - 打开/关闭开发者工具

### 方法 2：菜单栏
- 点击菜单栏 → 帮助 → 开发者工具

### 方法 3：自动打开
在开发模式下，开发者工具会自动打开。

## 🔍 调试导航问题

如果导航标签点击无反应，使用开发者工具检查：

### 1. 打开开发者工具
按 F12

### 2. 检查 Console 标签
查看是否有 JavaScript 错误：
```javascript
// 常见错误
NavigationTabs is not defined
Cannot read property 'push' of undefined
```

### 3. 检查 Elements 标签
1. 点击元素选择器（左上角箭头）
2. 点击导航标签
3. 检查元素样式：
   - `pointer-events: auto`
   - `z-index: 100`
   - 没有其他元素覆盖

### 4. 检查 Network 标签
点击导航标签时，查看是否有路由跳转：
- URL 应该从 `#/chat` 变为 `#/code` 等
- 如果没有变化，说明路由未触发

### 5. 检查 Vue DevTools（可选）
如果安装了 Vue DevTools 扩展，可以：
- 查看 Vue 组件树
- 检查路由状态
- 查看 Vuex/Pinia store

## 🐛 常见问题

### 问题 1：F12 仍然无法打开开发者工具
**解决方案**：
1. 确保使用开发模式启动（`start_dev.bat`）
2. 检查是否有其他程序占用了 F12 键
3. 尝试通过菜单打开：帮助 → 开发者工具

### 问题 2：开发者工具自动关闭
**解决方案**：
- 重新按 F12 打开
- 或通过菜单重新打开

### 问题 3：看不到导航标签
**解决方案**：
1. 在开发者工具的 Elements 标签中搜索 `navigation-tabs`
2. 检查 `display` 属性是否为 `none`
3. 检查 `visibility` 属性是否为 `hidden`

### 问题 4：导航标签显示但无法点击
**解决方案**：
1. 在 Elements 标签中检查导航标签的 `pointer-events` 属性
2. 检查是否有其他元素的 `z-index` 更高
3. 检查是否有透明元素覆盖在上面

## 📊 使用开发者工具的技巧

### 1. Console 命令

```javascript
// 检查当前路由
$router.currentRoute.value.path

// 手动跳转
$router.push('/code')

// 检查 NavigationTabs 组件
document.querySelector('.navigation-tabs')

// 查看所有事件监听器
getEventListeners(document.querySelector('.tab-item'))
```

### 2. 元素检查
```javascript
// 在 Console 中执行
// 检查导航标签是否可点击
const tab = document.querySelector('.tab-item')
console.log('pointer-events:', getComputedStyle(tab).pointerEvents)
console.log('z-index:', getComputedStyle(tab).zIndex)
```

### 3. 网络请求
在 Network 标签中：
- 筛选 `XHR/Fetch` 查看所有 API 请求
- 检查失败的请求（红色）
- 查看请求响应时间

### 4. Performance
- 记录页面性能
- 检查渲染瓶颈
- 优化动画流畅度

## 🔧 调试配置

### Electron 开发者工具配置
在 `electron/modules/window.ts` 中：

```typescript
// 自动打开开发者工具
if (process.env.NODE_ENV === 'development' || process.argv.includes('--dev')) {
  mainWindow.webContents.openDevTools()
}

// F12 快捷键
mainWindow.webContents.on('before-input-event', (event, input) => {
  if (input.key === 'F12' && input.type === 'keyDown') {
    if (mainWindow.webContents.isDevToolsOpened()) {
      mainWindow.webContents.closeDevTools()
    } else {
      mainWindow.webContents.openDevTools()
    }
  }
})
```

## 📝 快捷键参考

| 快捷键 | 功能 |
|--------|------|
| F12 | 打开/关闭开发者工具 |
| Ctrl+Shift+I | 打开开发者工具（替代方案） |
| Ctrl+Shift+J | 打开 Console 面板 |
| Ctrl+Shift+C | 打开元素选择器 |
| Ctrl+R | 刷新页面 |
| Ctrl+Shift+R | 强制刷新（清除缓存） |

## 🎯 调试流程示例

### 调试导航标签点击问题

1. **打开开发者工具**（按 F12）

2. **检查 Console**
   - 查看是否有错误信息
   - 记录任何警告

3. **检查路由状态**
   ```javascript
   // 在 Console 中输入
   $router.currentRoute.value
   // 应该看到 { path: '/chat', ... }
   ```

4. **检查导航元素**
   ```javascript
   // 检查导航标签是否存在
   document.querySelectorAll('.tab-item')
   // 应该返回 5 个元素
   ```

5. **测试点击事件**
   ```javascript
   // 手动触发点击
   const tabs = document.querySelectorAll('.tab-item')
   tabs[1].click() // 点击第二个标签（代码）
   ```

6. **检查路由变化**
   ```javascript
   // 路由应该改变
   $router.currentRoute.value.path
   // 应该是 '/code'
   ```

7. **如果问题仍然存在**
   - 检查元素样式（Elements 标签）
   - 查看事件监听器
   - 检查是否有 JavaScript 错误

## 💡 最佳实践

1. **开发时始终打开开发者工具**
   - 及时发现错误
   - 监控网络请求
   - 调试 UI 问题

2. **使用 Console 日志**
   ```javascript
   console.log('导航到:', path)
   console.error('路由错误:', error)
   ```

3. **使用 Vue DevTools**
   - 安装 Vue DevTools 扩展
   - 查看 Vue 组件状态
   - 调试 Pinia store

4. **定期检查 Performance**
   - 识别性能瓶颈
   - 优化渲染性能
   - 改善用户体验

---

**现在您可以正常使用 F12 打开开发者工具来调试问题了！** 🎉
