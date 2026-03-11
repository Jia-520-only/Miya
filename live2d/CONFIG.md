# Live2D 配置文件

## 📋 配置总览

### 配置文件列表

| 文件名 | 用途 | 必需 |
|--------|------|------|
| CONFIG.md | 配置说明文档 | ✅ |
| README.md | 使用说明 | ✅ |
| MODELS.md | 模型详细说明 | ✅ |
| EXPRESSIONS.md | 表情映射配置 | ✅ |
| .gitignore | Git忽略配置 | ✅ |

## 🔧 环境配置

### 桌面端配置

#### 路径设置

```typescript
// miya-desktop/src/composables/useLive2D.ts
const defaultModelPath = '/live2d/ht/ht.model3.json'
```

#### 渲染设置

```typescript
const app = new Application({
  view: canvas,
  width: 300,
  height: 400,
  backgroundAlpha: 0,
  resolution: window.devicePixelRatio || 1,
  autoDensity: true
})
```

#### 模型缩放

```typescript
model.scale.set(0.8)  // 调整模型大小
model.x = app.screen.width / 2
model.y = app.screen.height / 2 + 50
model.anchor.set(0.5, 0.5)
```

### 后端配置

#### 情绪检测配置

```python
# core/emotion_analyzer.py
emotion_threshold = 0.5  # 情绪强度阈值
emotion_timeout = 3000    # 情绪持续时间（毫秒）
```

#### 状态更新配置

```python
# core/system_status.py
status_update_interval = 1000  # 状态更新间隔（毫秒）
```

## 🎨 外观配置

### UI主题配置

#### 颜色方案

```css
/* Cyan-Blue Theme */
--primary-color: #2dd4bf;
--secondary-color: #0ea5e9;
--accent-color: #06b6d4;
--bg-primary: rgba(4, 47, 46, 0.8);
--bg-secondary: rgba(6, 78, 59, 0.6);
```

#### 玻璃态效果

```css
.glass-effect {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
```

### Live2D显示配置

#### 显示尺寸

```vue
<!-- miya-desktop/src/views/ChatView.vue -->
<Live2DViewer
  :width="260"   <!-- 宽度 -->
  :height="340"  <!-- 高度 -->
/>
```

#### 显示位置

```css
/* ChatView.css */
.live2d-area {
  width: 280px;
  flex-shrink: 0;
  padding: 16px;
}
```

## ⚙️ 性能配置

### 渲染性能

#### 帧率控制

```typescript
// 限制为30fps
const targetFPS = 30
const frameInterval = 1000 / targetFPS
```

#### 物理引擎

```json
// ht.physics3.json
{
  "PhysicsSettings": {
    "Live2DPhysicsFPS": 3,      // 物理帧率
    "PhysicsStrength": 65,       // 物理强度
    "WindStrength": 0           // 风力强度
  }
}
```

#### 内存优化

```typescript
// 清理未使用的资源
function cleanupModel(model: Live2DModel) {
  model.destroy()
  // Pixi.js会自动清理纹理
}
```

### 加载优化

#### 预加载

```typescript
// 在应用启动时预加载模型
async function preloadModels() {
  const models = ['/live2d/ht/ht.model3.json']
  for (const path of models) {
    await Live2DModel.from(path)
  }
}
```

#### 懒加载

```typescript
// 只在需要时加载模型
const shouldLoadModel = ref(false)

watch(shouldLoadModel, (load) => {
  if (load && !model.value) {
    loadModel()
  }
})
```

## 🎭 表情配置

### 情绪映射配置

```typescript
// miya-desktop/src/composables/useLive2D.ts
const emotionToExpressionMap: Record<string, string> = {
  '开心': 'expression3',
  '兴奋': 'expression4',
  '害羞': 'expression5',
  // ... 更多映射
}
```

### 表情过渡配置

```typescript
// 过渡时长（毫秒）
const transitionDuration = 500

// 缓动函数
const easingFunction = 'easeInOutQuad'
```

### 表情强度配置

```typescript
// 根据情绪强度调整
const expressionIntensity = computed(() => {
  return systemStore.status.emotion?.intensity || 0.5
})

watch(expressionIntensity, (intensity) => {
  // 调整参数值
  model.setParameterValueById('ParamCheek', intensity * 0.8)
})
```

## 🔊 语音同步配置

### 嘴型同步

```typescript
// 根据语音波形调整嘴型
function lipSync(waveform: number[]) {
  const mouthOpen = Math.max(...waveform) * 2
  model.setParameterValueById('ParamMouthOpenY', mouthOpen)
}
```

### 语音识别

```typescript
// 语音活动检测
function detectSpeechActivity(audioData: Float32Array): boolean {
  const energy = audioData.reduce((sum, val) => sum + val * val, 0)
  return energy > threshold
}
```

## 🎯 交互配置

### 鼠标追踪

```typescript
// 眼睛跟随鼠标
function onMouseMove(e: MouseEvent) {
  const rect = canvas.getBoundingClientRect()
  const x = (e.clientX - rect.left) / rect.width
  const y = (e.clientY - rect.top) / rect.height

  lookAt(x * 2 - 1, y * 2 - 1)
}
```

### 点击交互

```typescript
// 点击模型触发动作
function onModelClick() {
  // 随机切换表情
  const expressions = Object.keys(emotionToExpressionMap)
  const randomExpr = expressions[Math.floor(Math.random() * expressions.length)]
  setExpression(randomExpr)
}
```

### 拖拽交互

```typescript
// 允许拖拽模型
function onDragStart(e: InteractionEvent) {
  isDragging = true
  dragOffset = { x: e.data.global.x - model.x, y: e.data.global.y - model.y }
}

function onDragMove(e: InteractionEvent) {
  if (isDragging) {
    model.x = e.data.global.x - dragOffset.x
    model.y = e.data.global.y - dragOffset.y
  }
}

function onDragEnd() {
  isDragging = false
}
```

## 📱 响应式配置

### 屏幕适配

```typescript
// 根据屏幕尺寸调整
const isMobile = ref(window.innerWidth < 768)

watch(isMobile, (mobile) => {
  if (mobile) {
    // 移动端隐藏Live2D或缩小
    model.scale.set(0.5)
  } else {
    model.scale.set(0.8)
  }
})
```

### 窗口大小调整

```typescript
window.addEventListener('resize', () => {
  app.renderer.resize(container.clientWidth, container.clientHeight)
  model.x = app.screen.width / 2
  model.y = app.screen.height / 2
})
```

## 🌐 网络配置

### CORS配置

```typescript
// 如果模型从CDN加载
app.loader.add('live2d', modelUrl, {
  crossOrigin: 'anonymous'
})
```

### 加载超时

```typescript
// 设置加载超时
const loadTimeout = 10000  // 10秒

const timeoutPromise = new Promise((_, reject) => {
  setTimeout(() => reject(new Error('Load timeout')), loadTimeout)
})

await Promise.race([
  Live2DModel.from(modelPath),
  timeoutPromise
])
```

## 🐛 调试配置

### 日志输出

```typescript
// 开发模式启用详细日志
const isDev = import.meta.env.DEV

if (isDev) {
  console.log('Live2D model loaded:', model)
  console.log('Current expression:', currentExpression.value)
}
```

### 性能监控

```typescript
// FPS监控
let frameCount = 0
let lastTime = performance.now()

function updateFPS() {
  const now = performance.now()
  const delta = now - lastTime

  if (delta >= 1000) {
    const fps = frameCount / (delta / 1000)
    console.log(`Live2D FPS: ${fps.toFixed(2)}`)

    frameCount = 0
    lastTime = now
  }

  frameCount++
}

app.ticker.add(updateFPS)
```

### 错误处理

```typescript
// 全局错误捕获
window.addEventListener('error', (e) => {
  if (e.message.includes('Live2D')) {
    console.error('Live2D error:', e)
    // 显示友好错误信息
    showErrorToast('Live2D模型加载失败')
  }
})
```

## 🎛️ 高级配置

### 多模型支持

```typescript
const models: Record<string, Live2DModel> = {}

async function loadModel(modelId: string, path: string) {
  const model = await Live2DModel.from(path)
  models[modelId] = model
  return model
}

async function switchModel(modelId: string) {
  if (models[modelId]) {
    app.stage.removeChildren()
    app.stage.addChild(models[modelId])
  }
}
```

### 自定义着色器

```typescript
// 为模型添加特效
const shader = new Shader(defaultVertexShader, customFragmentShader)
model.filters = [new Filter(new PIXI.Graphics(), shader)]
```

### 后处理效果

```typescript
// 添加模糊效果
const blurFilter = new PIXI.BlurFilter()
blurFilter.blur = 5
model.filters = [blurFilter]
```

## 📊 监控配置

### 使用统计

```typescript
// 记录模型使用情况
const usageStats = {
  totalExpressionChanges: 0,
  expressionDistribution: {},
  averageFPS: 0
}

function recordExpressionChange(expression: string) {
  usageStats.totalExpressionChanges++
  usageStats.expressionDistribution[expression] =
    (usageStats.expressionDistribution[expression] || 0) + 1
}
```

### 性能指标

```typescript
// 收集性能指标
const performanceMetrics = {
  loadTime: 0,
  renderTime: 0,
  memoryUsage: 0,
  fps: 0
}
```

## 🔄 更新配置

### 模型更新策略

```typescript
// 检查模型版本
const modelVersion = '1.0.0'
const latestVersion = await checkLatestVersion()

if (latestVersion > modelVersion) {
  // 提示用户更新
  showUpdateNotification()
}
```

### 缓存策略

```typescript
// 使用缓存
const cachedModel = localStorage.getItem('live2d_model')
if (cachedModel) {
  // 使用缓存的模型
  loadModelFromCache(cachedModel)
} else {
  // 下载并缓存新模型
  await downloadAndCacheModel()
}
```

---

**配置完成！** 根据需要调整各项参数以获得最佳体验。
