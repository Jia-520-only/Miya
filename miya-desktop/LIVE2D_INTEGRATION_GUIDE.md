# Live2D 集成指南

## 📋 概述

本文档说明如何在弥娅桌面应用中集成和使用 Live2D 虚拟形象。

## 🎯 当前状态

### 已实现
- ✅ Live2D 状态管理 (`useLive2D.ts`)
- ✅ Live2D 显示组件 (`Live2DViewer.vue`)
- ✅ 情绪驱动的表情切换
- ✅ 打字时的口型动画
- ✅ 右侧 Live2D 显示区域

### 待完成
- ⏳ Live2D SDK 集成
- ⏳ 模型文件加载
- ⏳ 实际渲染实现
- ⏳ 音频响应
- ⏳ 模型切换功能

## 📁 项目结构

```
miya-desktop/
├── src/
│   ├── components/
│   │   ├── Live2DViewer.vue       # Live2D 显示组件
│   │   └── MiyaAvatar.vue         # 头像组件(兼容旧版)
│   ├── composables/
│   │   └── useLive2D.ts          # Live2D 状态管理
│   └── views/
│       └── ChatView.vue           # 集成 Live2D 的聊天视图
└── live2d/                       # Live2D 资源目录(待创建)
    ├── models/                    # 模型文件
    │   ├── Miya_Casual/
    │   ├── Miya_Happy/
    │   └── Miya_Thoughtful/
    ├── motions/                   # 动作文件
    └── expressions/              # 表情参数
```

## 🎨 界面布局

### 新布局结构
```
┌─────────────────────────────────────────────────────────┐
│  [左侧功能栏]  [主聊天区域]        [Live2D区域]   │
│  ┌────────┐  ┌────────────┐        ┌──────────┐   │
│  │ 会话   │  │            │        │          │   │
│  │ 主题   │  │  消息列表  │        │  Live2D  │   │
│  │ 人格   │  │            │        │  显示器   │   │
│  │ Live2D │  │            │        │          │   │
│  └────────┘  └────────────┘        └──────────┘   │
│              ┌────────────┐                           │
│              │ 输入框    │                           │
│              └────────────┘                           │
└─────────────────────────────────────────────────────────┘
```

### 特点
- **左侧功能栏**: 60px 宽度,垂直排列所有功能按钮
- **主聊天区域**: 占据主要空间,消息列表自适应
- **Live2D 区域**: 280px 宽度,固定在右侧

## 📦 Live2D SDK 集成

### 1. 安装依赖

```bash
cd miya-desktop
npm install @pixiv/three-vrm
# 或使用 Live2D Cubism SDK
npm install pixi-live2d-display
```

### 2. 创建资源目录

```bash
mkdir -p live2d/models
```

### 3. 添加模型文件

将你的 Live2D 模型文件放入 `live2d/models/` 目录:

```
live2d/models/
└── Miya_Model/
    ├── Miya_Model.moc3
    ├── Miya_Model.model3.json
    ├── Miya_Model.physics3.json
    ├── Miya_Model.2048/
    │   ├── texture_00.png
    │   └── texture_01.png
    └── exp/
        ├── exp_01.json
        └── exp_02.json
```

### 4. 更新 Live2DViewer.vue

替换 `drawPlaceholder()` 函数,实现实际的 Live2D 渲染:

```typescript
import { Live2DModel } from 'pixi-live2d-display'

// 在组件中
let live2d: Live2DModel | null = null

async function loadLive2DModel() {
  const app = new PIXI.Application({
    width: canvasRef.value.width,
    height: canvasRef.value.height,
    view: canvasRef.value
  })

  live2d = await PIXI.live2d.Live2DModel.from(
    '/live2d/models/Miya_Model/Miya_Model.model3.json'
  )

  live2d.scale.set(0.8)
  live2d.anchor.set(0.5, 0.5)
  live2d.position.set(
    app.view.width / 2,
    app.view.height / 2
  )

  app.stage.addChild(live2d)
}
```

## 🎭 情绪映射

### 当前情绪到表情的映射

| 情绪 | 表情 | 说明 |
|------|------|------|
| 开心/高兴/快乐 | happy | 眼睛弯弯,嘴角上扬 |
| 平静/放松 | normal | 自然表情 |
| 疑惑/思考 | thoughtful | 眉头微皱 |
| 惊讶 | surprised | 眼睛睁大,嘴巴张开 |
| 生气 | angry | 眉毛紧皱,嘴角向下 |
| 难过 | sad | 眼睛下垂,嘴角向下 |
| 关心 | caring | 温柔的表情 |

### 修改映射

在 `useLive2D.ts` 中修改 `emotionMap`:

```typescript
const emotionMap: Record<string, string> = {
  '开心': 'happy',
  '平静': 'normal',
  // 添加更多映射...
}
```

## 🔄 与现有系统的集成

### 1. 与情绪系统集成

Live2D 自动响应 `systemStore.status.emotion`:

```typescript
const currentEmotion = computed(() => {
  return systemStore.status.emotion?.dominant || '平静'
})
```

### 2. 与打字状态集成

弥娅回复时自动触发口型动画:

```typescript
const isTyping = computed(() => chatStore.isTyping)
```

### 3. 与人格系统集成

人格数据可用于选择不同的 Live2D 模型:

```typescript
const currentModel = computed(() => {
  const personality = systemStore.status.personality
  // 根据人格向量选择模型
  return personality.warmth > 0.7 ? 'miya-happy' : 'miya-casual'
})
```

## 🎯 未来计划

### Phase 1: 基础集成 (当前)
- [x] 创建组件框架
- [x] 实现状态管理
- [ ] 集成 Live2D SDK
- [ ] 加载模型文件

### Phase 2: 交互增强
- [ ] 点击 Live2D 触发动作
- [ ] 拖拽 Live2D 移动位置
- [ ] 缩放 Live2D
- [ ] 切换模型按钮

### Phase 3: 音频集成
- [ ] 语音播放时的口型同步
- [ ] 音量驱动嘴部动作
- [ ] 语音识别驱动表情

### Phase 4: 高级功能
- [ ] 自定义动作录制
- [ ] 模型自定义(换装)
- [ ] 多模型同时显示
- [ ] AR 模式

## 📝 配置选项

### 在 settings store 中添加 Live2D 配置

```typescript
interface Live2DSettings {
  enabled: boolean
  modelId: string
  size: 'sm' | 'md' | 'lg' | 'full'
  autoEmotion: boolean
  mouthSync: boolean
  volume: number
}

const live2DSettings: Live2DSettings = {
  enabled: true,
  modelId: 'miya-casual',
  size: 'lg',
  autoEmotion: true,
  mouthSync: true,
  volume: 0.7
}
```

## 🔧 故障排除

### 问题 1: Live2D 不显示
**解决方案:**
1. 检查模型文件路径
2. 查看控制台错误
3. 确认 Canvas 大小正确

### 问题 2: 表情不切换
**解决方案:**
1. 检查 `systemStore.status.emotion` 是否更新
2. 确认情绪映射正确
3. 查看 `setEmotion` 是否被调用

### 问题 3: 口型不动
**解决方案:**
1. 检查 `chatStore.isTyping` 状态
2. 确认 `startTalking()` 被调用
3. 验证音频设备权限

## 📚 参考资源

- [Live2D Cubism SDK](https://www.live2d.com/)
- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)
- [Pixi.js 文档](https://pixijs.io/)
- [Vue 3 组件开发](https://vuejs.org/guide/components/registration.html)

## 💡 提示

1. **性能优化**: Live2D 模型较重,建议使用 Web Worker
2. **内存管理**: 及时释放不需要的模型资源
3. **错误处理**: 添加完善的错误捕获和降级方案
4. **用户体验**: 提供加载状态和占位符

---

**更新日期**: 2026-03-08
**版本**: 0.1.0
**作者**: Auto AI Assistant
