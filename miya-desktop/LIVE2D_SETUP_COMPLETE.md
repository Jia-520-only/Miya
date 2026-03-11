# Live2D 集成完成指南

## ✅ 集成状态

你的Live2D模型已经成功集成到Miya桌面应用中！

### 📦 已完成的工作

1. **SDK 安装**
   - 添加了 `pixi.js@^7.3.2`
   - 添加了 `pixi-live2d-display@^0.4.0`

2. **模型文件部署**
   - 模型文件已复制到 `public/live2d/ht/` 目录
   - 包含所有必需文件：moc3、纹理、物理、表情等

3. **组件开发**
   - `src/composables/useLive2D.ts` - Live2D管理逻辑
   - `src/components/Live2DViewer.vue` - Live2D展示组件

4. **UI集成**
   - ChatView右侧280px区域显示Live2D角色
   - 根据systemStore中的情绪自动切换表情

## 🎭 表情映射系统

你的Live2D模型8个表情已映射到系统情绪：

| 系统情绪 | Live2D表情 | 描述 |
|---------|-----------|------|
| 开心/愉快/快乐 | expression3 | 白色爱心眼 |
| 兴奋/激动/热情 | expression4 | 粉色爱心眼 |
| 尴尬/羞涩 | expression5 | 害羞脸红 |
| 悲伤/难过/痛苦 | expression2 | 流泪 |
| 生气/愤怒/暴躁 | expression1 | 黑脸 |
| 唱歌 | expression7 | 拿麦克风 |
| 嘘声 | expression6 | 嘘声手势 |
| 调皮/可爱 | expression8 | 狐狸耳朵 |

## 🚀 使用说明

### 1. 安装依赖

在 `miya-desktop` 目录下运行：

```bash
# 运行安装脚本
install_live2d.bat

# 或手动安装
npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0
```

### 2. 启动应用

使用 `start.bat` 启动应用，Live2D会自动加载并显示在右侧边栏。

### 3. 测试功能

- **自动表情切换**: 与弥娅对话时，她的表情会根据情绪状态自动变化
- **呼吸动画**: 模型会自动播放呼吸动画
- **流畅渲染**: 基于Pixi.js的高性能渲染

## 🎨 自定义配置

### 调整Live2D显示大小

编辑 `src/views/ChatView.vue`:

```vue
<Live2DViewer
  model-path="/live2d/ht/ht.model3.json"
  :emotion="currentEmotion"
  :width="260"      <!-- 修改这里调整宽度 -->
  :height="340"     <!-- 修改这里调整高度 -->
  :show-controls="false"  <!-- 设为true显示表情测试按钮 -->
/>
```

### 添加更多表情映射

编辑 `src/composables/useLive2D.ts`:

```typescript
const emotionToExpressionMap: Record<string, string> = {
  '开心': 'expression3',
  '兴奋': 'expression4',
  '害羞': 'expression5',
  // 添加你的映射...
}
```

## 📂 文件结构

```
miya-desktop/
├── public/
│   └── live2d/
│       └── ht/                 # 你的Live2D模型
│           ├── ht.model3.json  # 主配置
│           ├── ht.moc3        # 模型文件
│           ├── ht.physics3.json
│           ├── ht.8192/
│           │   └── texture_00.png
│           └── expression*.exp3.json  # 8个表情
├── src/
│   ├── components/
│   │   └── Live2DViewer.vue   # Live2D展示组件
│   ├── composables/
│   │   └── useLive2D.ts       # Live2D管理逻辑
│   └── views/
│       └── ChatView.vue       # 已集成Live2D
└── install_live2d.bat         # 安装脚本
```

## 🔧 高级功能

### 手动控制Live2D

在组件中引用Live2D实例：

```vue
<script setup>
import { useLive2D } from '@/composables/useLive2D'

const { setExpression, setMouthOpen, setEyeOpen, lookAt } = useLive2D({
  modelPath: '/live2d/ht/ht.model3.json'
})

// 设置表情
setExpression('开心')

// 张嘴动画 (0-1)
setMouthOpen(0.5)

// 睁眼动画 (0-1)
setEyeOpen(1.0)

// 眼睛跟随鼠标
lookAt(0.5, 0.5)
</script>
```

### 添加鼠标追踪

扩展 `Live2DViewer.vue` 添加鼠标追踪：

```vue
<script setup>
const { lookAt } = useLive2D(config)

const handleMouseMove = (e: MouseEvent) => {
  const rect = e.currentTarget.getBoundingClientRect()
  const x = (e.clientX - rect.left) / rect.width
  const y = (e.clientY - rect.top) / rect.height
  lookAt(x, y)
}
</script>

<template>
  <div @mousemove="handleMouseMove">
    <!-- Live2D canvas -->
  </div>
</template>
```

## 🐛 故障排查

### 模型无法加载

1. 检查控制台错误信息
2. 确认 `public/live2d/ht/` 目录存在
3. 验证模型文件完整性
4. 检查浏览器控制台是否有CORS错误

### 表情不切换

1. 确认 `systemStore.status.emotion` 有值
2. 检查情绪映射是否正确
3. 查看控制台是否有表情加载错误

### 性能问题

1. 降低渲染分辨率：在 `useLive2D.ts` 中设置 `resolution: 1`
2. 减少模型复杂度
3. 关闭不必要的动画

## 📚 参考资源

- [Pixi.js 官方文档](https://pixijs.io/)
- [Live2D Cubism SDK](https://www.live2d.com/)
- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)

## 🎉 完成！

现在你的Miya桌面应用已经拥有了可爱的Live2D虚拟形象！

开始与弥娅对话，观察她的表情变化吧！
