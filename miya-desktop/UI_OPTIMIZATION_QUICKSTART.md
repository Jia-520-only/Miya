# UI 优化 - 快速开始指南

## ✅ 已完成的工作

### 1. Live2D 浮动卡片组件
**文件**: `src/components/Live2DFull.vue`

**功能**:
- ✅ 可拖动（鼠标拖拽）
- ✅ 位置自动保存（localStorage）
- ✅ 位置自动恢复
- ✅ 展开/收起操作
- ✅ 快捷指令输入
- ✅ 任务状态显示
- ✅ 快捷操作按钮
- ✅ 毛玻璃效果
- ✅ 流畅动画

### 2. 专业深色主题
**文件**: `src/styles/theme.css`

**特性**:
- ✅ 完整的 CSS 变量系统
- ✅ 专业配色方案（蓝、绿、黄、红）
- ✅ 多层次背景色
- ✅ 统一的圆角、间距、阴影
- ✅ 全局组件样式
- ✅ 响应式设计
- ✅ 自定义滚动条

### 3. 工作台布局
**文件**: `src/components/Workspace.vue`

**布局**:
- ✅ 三栏式工作台
- ✅ 左侧：会话列表（280px）
- ✅ 中间：主工作区（flex: 1）
- ✅ 右侧：工具箱（300px）
- ✅ 顶部导航栏（60px）
- ✅ 响应式适配

### 4. 任务清单
**文件**: `UI_OPTIMIZATION_TASKS.md`

**内容**:
- ✅ 10 个阶段，20 个详细任务
- ✅ 预计 133 小时完成
- ✅ 进度跟踪表格
- ✅ 里程碑定义
- ✅ 开发规范

---

## 🚀 如何使用新组件

### 1. 在主应用中引入样式

在 `src/main.ts` 或 `src/App.vue` 中：

```typescript
import './styles/theme.css'
```

### 2. 替换现有布局

将 `src/views/ChatView.vue` 替换为新的 `Workspace.vue`：

```vue
<template>
  <Workspace />
</template>

<script setup lang="ts">
import Workspace from '@/components/Workspace.vue'
</script>
```

### 3. Live2D 浮动卡片使用

```vue
<template>
  <Live2DFloat
    :model-path="currentModelPath"
    :emotion="currentEmotion"
    :width="200"
    :height="280"
    :current-task="currentTask"
    @emotion-change="handleEmotionChange"
    @toggle-desktop="toggleDesktopPet"
    @open-settings="toggleSettings"
    @quick-command="executeCommand"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Live2DFloat from '@/components/Live2DFloat.vue'

const currentModelPath = ref('/live2d/ht/ht.model3.json')
const currentEmotion = ref('平静')
const currentTask = ref('正在分析数据...')

function handleEmotionChange(emotion: string) {
  currentEmotion.value = emotion
}

function toggleDesktopPet() {
  // 切换桌宠模式
}

function toggleSettings() {
  // 打开设置
}

function executeCommand(command: string) {
  // 执行快捷指令
}
</script>
```

---

## 🎨 使用主题变量

### CSS 变量示例

```css
.my-component {
  /* 背景色 */
  background: var(--bg-primary);
  background: var(--bg-secondary);
  background: var(--bg-tertiary);

  /* 文字色 */
  color: var(--text-primary);
  color: var(--text-secondary);
  color: var(--text-tertiary);

  /* 边框色 */
  border: 1px solid var(--border-primary);
  border: 1px solid var(--border-secondary);

  /* 主色调 */
  color: var(--primary);
  background: var(--primary);

  /* 语义色 */
  color: var(--success);
  color: var(--warning);
  color: var(--error);

  /* 阴影 */
  box-shadow: var(--shadow-sm);
  box-shadow: var(--shadow-md);
  box-shadow: var(--shadow-lg);

  /* 圆角 */
  border-radius: var(--radius-md);
  border-radius: var(--radius-lg);

  /* 间距 */
  padding: var(--spacing-md);
  gap: var(--spacing-lg);

  /* 过渡 */
  transition: all var(--transition-base);
}
```

---

## 📋 下一步行动

### 立即可以做的：

1. **测试 Live2DFloat 组件**
   ```bash
   # 在开发环境中测试
   npm run dev
   ```

2. **应用主题样式**
   ```vue
   <!-- 在组件中使用 -->
   <style scoped>
   .my-class {
     background: var(--bg-tertiary);
     border: 1px solid var(--border-secondary);
     border-radius: var(--radius-lg);
   }
   </style>
   ```

3. **创建新的工作台页面**
   ```bash
   # 创建新页面
   mkdir src/views/workspace
   touch src/views/workspace/WorkspaceView.vue
   ```

### 本周可以完成的：

1. **集成 Live2DFloat 到现有页面**
2. **应用主题样式到所有组件**
3. **创建工具箱基础框架**
4. **实现快捷指令输入框**

### 本月可以完成的：

1. **完成所有 UI 优化任务**
2. **实现结果预览组件**
3. **优化性能和动画**
4. **测试和修复**

---

## 🛠️ 需要创建的组件

按优先级排序：

### 高优先级
- [ ] QuickCommand.vue - 快捷指令面板
- [ ] Toolbox.vue - 工具箱
- [ ] ResultPreview.vue - 结果预览

### 中优先级
- [ ] FileExplorer.vue - 文件浏览器
- [ ] CodeEditor.vue - 代码编辑器
- [ ] Terminal.vue - 终端

### 低优先级
- [ ] ChartViewer.vue - 图表查看器
- [ ] DocumentViewer.vue - 文档查看器
- [ ] Browser.vue - 浏览器

---

## 📊 进度跟踪

使用 `UI_OPTIMIZATION_TASKS.md` 中的任务列表来跟踪进度。

当前状态：
- ✅ Phase 1-3: 设计系统和基础组件（已完成）
- ⏳ Phase 4: 布局重构（进行中）
- ⏸️ Phase 5-10: 其他功能（待开始）

---

## 💡 技术提示

### 1. 使用 CSS 变量
```css
/* 好 */
.my-component {
  background: var(--bg-primary);
  color: var(--text-primary);
}

/* 不好（硬编码） */
.my-component {
  background: #0f1115;
  color: #f1f5f9;
}
```

### 2. 使用工具类
```vue
<!-- 好 -->
<div class="flex items-center justify-between gap-md">

<!-- 不好（重复样式） -->
<div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;">
```

### 3. 使用过渡
```css
/* 好 */
.my-element {
  transition: all var(--transition-base);
}

/* 不好（硬编码） */
.my-element {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 🐛 常见问题

### Q: Live2DFloat 拖动不流畅？
**A**: 检查是否使用了 `will-change` 属性优化性能：
```css
.live2d-float-card {
  will-change: transform;
}
```

### Q: 主题变量不生效？
**A**: 确保在 `main.ts` 中导入了主题样式：
```typescript
import './styles/theme.css'
```

### Q: 布局在不同屏幕上错位？
**A**: 检查响应式断点是否正确设置：
```css
@media (max-width: 1280px) {
  /* 平板样式 */
}

@media (max-width: 768px) {
  /* 移动端样式 */
}
```

---

## 📞 获取帮助

- 📖 查看 `UI_OPTIMIZATION_TASKS.md` 了解详细任务
- 🎨 查看 `theme.css` 了解主题系统
- 💬 查看 `MIYA_WORKBUDDY_PLAN.md` 了解整体规划

---

**最后更新**: 2026-03-09
**文档版本**: 1.0
