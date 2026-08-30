# 桌宠大屏模式更新说明

## 更新内容

### 1. 桌宠窗口大幅放大

**窗口尺寸**：
- 之前：280 x 350 像素
- 现在：**800 x 1000 像素**

这样Live2D模型可以在更大的空间中自由放大，不会受窗口限制。

### 2. 允许内容溢出

**Live2DFull.vue 改进**：
- 独立模式下移除了 `max-width` 和 `max-height` 限制
- 画布可以自由缩放，不受窗口边界约束
- 背景完全透明，只有模型可见

### 3. 样式优化

**新增CSS类 `.is-standalone`**：
```css
.is-standalone .canvas-container canvas {
  max-width: none;
  max-height: none;
  border-radius: 0;
  border: none;
  background: transparent;
}
```

这样在独立模式下，Live2D模型可以：
- ✅ 放大到超出窗口边界
- ✅ 无边框限制
- ✅ 背景完全透明

## 使用方法

### 启动桌宠

1. 启动应用（使用 `start_all.bat`）
2. 点击"桌宠模式"按钮
3. 桌宠窗口会显示在屏幕上

### 缩放桌宠

现在桌宠的模型可以**无限放大**：

| 操作 | 效果 |
|------|------|
| 向上滚动滚轮 | 放大模型 |
| 向下滚动滚轮 | 缩小模型 |
| Shift + 拖动 | 移动窗口位置 |
| 直接拖动模型 | 移动模型位置 |

**重要**：模型现在可以放大到超出窗口边界，就像真正的桌面宠物一样！

## 技术细节

### 窗口配置

```typescript
{
  width: 800,    // 大窗口
  height: 1000,  // 高窗口
  frame: false,        // 无边框
  transparent: true,   // 透明背景
  alwaysOnTop: true,    // 始终置顶
  skipTaskbar: true,    // 不显示在任务栏
  // ...
}
```

### 画布配置

```typescript
// Live2DStandalone.vue
<Live2DFull
  :width="800"
  :height="1000"
  :isStandalone="true"
/>
```

### 样式配置

```css
/* 允许内容溢出 */
.live2d-viewer.is-standalone {
  overflow: visible;  /* 关键：允许溢出 */
  background: transparent;
}

/* 移除画布尺寸限制 */
.is-standalone .canvas-container canvas {
  max-width: none;
  max-height: none;
  border: none;
  background: transparent;
}
```

## 预期效果

### 主窗口

- Live2D在固定区域内显示
- 有边框和背景
- 缩放受窗口大小限制

### 桌宠窗口（独立模式）

- ✅ **窗口很大**：800x1000像素
- ✅ **完全无边框**：没有窗口边界
- ✅ **背景透明**：只有Live2D模型可见
- ✅ **可以自由缩放**：模型可以超出窗口边界
- ✅ **始终置顶**：显示在所有窗口之上
- ✅ **不显示在任务栏**：像真正的桌宠

## 与之前的区别

| 特性 | 之前 | 现在 |
|------|------|------|
| 窗口大小 | 280x350 | 800x1000 |
| 模型放大 | 受窗口限制 | 可以超出窗口 |
| 边框 | 有 | 无 |
| 背景 | 有颜色 | 完全透明 |
| 使用体验 | 在框框里 | 真正的桌宠 |

## 注意事项

1. **性能**：窗口越大，渲染开销越大
2. **透明度**：Windows 10/11 支持更好的透明效果
3. **缩放范围**：现在可以无限放大（但建议不要太大，否则会影响性能）
4. **控制按钮**：右上角的控制按钮始终可见

## 故障排除

### 模型还是无法放大到窗口外

**检查**：
1. 确认使用了独立模式（`:isStandalone="true"`）
2. 检查CSS中是否应用了 `.is-standalone` 类
3. 查看控制台是否有错误

### 窗口背景不透明

**检查**：
1. 窗口配置中 `transparent: true`
2. `backgroundColor: '#00000000'`
3. CSS中所有容器都设置了 `background: transparent`

### 窗口太大了

**调整**：
```typescript
// electron/modules/live2d-window.ts
const LIVE2D_WINDOW_CONFIG = {
  width: 600,   // 调小
  height: 800,  // 调小
  // ...
}
```

## 未来改进

可能的改进方向：

1. **动态窗口大小**：根据模型缩放自动调整窗口大小
2. **鼠标穿透**：让鼠标事件穿透到桌面（点击模型除外）
3. **多模型支持**：支持同时显示多个桌宠
4. **自定义位置**：保存和恢复桌宠位置

---

**享受大屏桌宠体验！** 🎀
