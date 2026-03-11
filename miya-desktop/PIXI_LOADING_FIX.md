# PIXI.js 加载问题修复

## 🔍 问题描述

**错误信息**：
```
TypeError: PIXI.Application is not a constructor
```

**原因**：PIXI.js 文件可能没有正确加载或初始化。

## ✅ 已实施的修复

### 1. 添加加载验证脚本

在 `index.html` 中添加了验证脚本，检测 PIXI 是否正确加载：

```html
<script>
  console.log('[Library Check] PIXI loaded:', typeof PIXI !== 'undefined')
  console.log('[Library Check] PIXI.Application:', typeof PIXI?.Application)

  if (typeof PIXI === 'undefined') {
    console.error('[Library Check] PIXI.js 未能正确加载！')
    alert('PIXI.js 加载失败，请刷新页面重试')
  } else if (typeof PIXI.Application !== 'function') {
    console.error('[Library Check] PIXI.Application 不是构造函数')
    alert('PIXI.Application 加载失败，请刷新页面重试')
  } else {
    console.log('[Library Check] 所有库文件加载成功！')
  }
</script>
```

### 2. 创建 PIXI 检查工具

创建了 `src/utils/pixi-check.ts` 工具，提供详细的 PIXI 状态检查：

```typescript
export function checkPIXI(): any {
  const win = window as any

  console.log('[PIXI Check] Checking PIXI availability...')
  console.log('[PIXI Check] window.PIXI:', !!win.PIXI)
  console.log('[PIXI Check] window.PIXI.Application:', !!win.PIXI?.Application)

  if (!win.PIXI) {
    console.error('[PIXI Check] PIXI not found in window')
    return null
  }

  if (typeof win.PIXI.Application !== 'function') {
    console.error('[PIXI Check] PIXI.Application is not a function/constructor')
    return null
  }

  return win.PIXI
}
```

### 3. 更新 Live2DFull.vue

使用 PIXI 检查工具，并提供更好的错误处理：

```typescript
const PIXI = computed(() => {
  const pixi = checkPIXI()
  return pixi
})

async function initLive2D() {
  try {
    const pixi = checkPIXI()
    if (!pixi) {
      throw new Error('PIXI 未正确加载，请刷新页面重试')
    }

    // 使用 pixi 而不是 window.PIXI
    app = new (pixi.Application as any)({
      view: canvasRef.value!,
      width: props.width,
      height: props.height,
      // ...
    })

  } catch (err: any) {
    console.error('[Live2D] 初始化错误:', err)
    console.error('[Live2D] 错误堆栈:', err.stack)
  }
}
```

## 🧪 测试步骤

### 1. 检查控制台日志

打开浏览器控制台（F12），查看以下日志：

**成功的情况**：
```
[Library Check] PIXI loaded: true
[Library Check] PIXI.Application: function
[Library Check] 所有库文件加载成功！
```

**失败的情况**：
```
[Library Check] PIXI loaded: false
[Library Check] PIXI.js 未能正确加载！
```

### 2. 使用测试页面

访问 `http://localhost:5173/test-pixi.html` 查看 PIXI 加载状态：

```
✓ PIXI 全局对象: PIXI 已加载
✓ PIXI.Application: Application 是函数
✓ 创建 PIXI 应用: Application 创建成功
```

### 3. 检查文件完整性

确认以下文件存在且大小正确：

```bash
cd miya-desktop/public/libraries

# 检查文件大小
ls -lh pixi.min.js                    # 应该是 ~460 KB
ls -lh pixi-live2d-display.min.js    # 应该是 ~126 KB
ls -lh live2dcubismcore.min.js       # 应该是 ~207 KB
```

## 🔧 故障排除

### 问题 1: "PIXI 加载失败"

**可能原因**：
1. 文件未下载成功
2. 文件损坏
3. 浏览器缓存问题

**解决方法**：
1. 清除浏览器缓存（Ctrl + Shift + Delete）
2. 重新下载库文件：
   ```bash
   powershell -ExecutionPolicy Bypass -File download_libraries.ps1
   ```
3. 刷新页面（Ctrl + F5 强制刷新）

### 问题 2: "PIXI.Application 不是构造函数"

**可能原因**：
1. PIXI.js 版本不兼容
2. 脚本加载顺序错误
3. PIXI 对象未正确导出

**解决方法**：
1. 检查 `index.html` 中的脚本加载顺序
2. 确保 PIXI.js 在 pixi-live2d-display 之前加载
3. 查看 `test-pixi.html` 测试结果

### 问题 3: 文件大小不对

**正确大小**：
- `pixi.min.js`: ~460 KB
- `pixi-live2d-display.min.js`: ~126 KB
- `live2dcubismcore.min.js`: ~207 KB

**解决方法**：
```bash
# 删除现有文件
rm public/libraries/*.js

# 重新下载
powershell -ExecutionPolicy Bypass -File download_libraries.ps1
```

## 📋 检查清单

使用以下清单确认问题：

- [ ] `public/libraries/pixi.min.js` 存在
- [ ] `public/libraries/pixi-live2d-display.min.js` 存在
- [ ] `public/libraries/live2dcubismcore.min.js` 存在
- [ ] `pixi.min.js` 大小约为 460 KB
- [ ] `pixi-live2d-display.min.js` 大小约为 126 KB
- [ ] `live2dcubismcore.min.js` 大小约为 207 KB
- [ ] 控制台显示 "PIXI loaded: true"
- [ ] 控制台显示 "PIXI.Application: function"
- [ ] 访问 `test-pixi.html` 显示所有测试通过

## 🚀 快速修复流程

```bash
# 1. 停止开发服务器
# Ctrl + C

# 2. 清除 Vite 缓存
rm -rf node_modules/.vite

# 3. 重新下载库文件
powershell -ExecutionPolicy Bypass -File download_libraries.ps1

# 4. 重启开发服务器
npm run dev

# 5. 强制刷新浏览器（Ctrl + F5）

# 6. 检查控制台日志
# F12 打开控制台，查看 PIXI 加载状态
```

## 📞 需要进一步帮助？

如果以上方法都无法解决问题，请：

1. **提供完整错误日志**
   - 打开控制台（F12）
   - 复制所有错误信息
   - 包括堆栈跟踪

2. **提供系统信息**
   - 操作系统版本
   - 浏览器版本
   - Node.js 版本

3. **检查文件**
   - 确认 `public/libraries/` 下的文件存在
   - 确认文件大小正确

4. **尝试测试页面**
   - 访问 `http://localhost:5173/test-pixi.html`
   - 截图显示测试结果

## 🎯 预期结果

修复后，你应该看到：

1. **控制台日志**：
   ```
   [Library Check] PIXI loaded: true
   [Library Check] PIXI.Application: function
   [Library Check] 所有库文件加载成功！
   [Live2D] PIXI 应用创建成功
   [Live2D] 模型加载成功
   ```

2. **Live2D 显示**：
   - Live2D 角色正确显示
   - 可以切换表情
   - 可以在独立窗口中拖动

3. **测试页面**：
   - 所有测试项都显示为绿色（通过）
   - 可以看到 PIXI 测试画布

---

**修复完成后，Live2D 独立窗口功能将正常工作！** 🎉
