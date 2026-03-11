<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { checkPIXI } from '../utils/pixi-check'

interface Props {
  modelPath: string
  emotion: string
  width?: number
  height?: number
  isStandalone?: boolean  // 是否在独立窗口中
}

const emit = defineEmits<{
  (e: 'emotion-change', emotion: string): void
  (e: 'loaded'): void
  (e: 'error', error: any): void
}>()

const props = withDefaults(defineProps<Props>(), {
  width: 300,
  height: 400,
  emotion: '平静',
  isStandalone: false
})

const PIXI = checkPIXI()

// Refs
const canvasRef = ref<HTMLCanvasElement>()
const canvasContainerRef = ref<HTMLDivElement>()

// State
const isLoading = ref(true)
const loadingDetail = ref('初始化中...')
const isLoaded = ref(false)
const isPaused = ref(false)
const error = ref<string>('')
const modelName = ref('御姐猫猫')
const currentEmotion = ref(props.emotion)
const currentExpressionIndex = ref(0)

// Live2D 相关
let live2dModel: any = null
let app: any = null

// 拖动状态
let isDragging = false
let lastMousePos = { x: 0, y: 0 }

// 表情列表
const expressions = [
  { name: '开心', value: 'expression1.exp3.json' },
  { name: '害羞', value: 'expression2.exp3.json' },
  { name: '生气', value: 'expression3.exp3.json' },
  { name: '悲伤', value: 'expression4.exp3.json' },
  { name: '平静', value: 'expression5.exp3.json' },
  { name: '兴奋', value: 'expression6.exp3.json' },
  { name: '调皮', value: 'expression7.exp3.json' },
  { name: '嘘声', value: 'expression8.exp3.json' }
]

// 初始化Live2D
async function initLive2D() {
  try {
    isLoading.value = true
    loadingDetail.value = '等待库加载...'
    error.value = ''

    console.log('[Live2D] 开始初始化...')

    // 检查 PIXI
    if (!PIXI) {
      throw new Error('PIXI 未正确加载，请刷新页面重试')
    }

    // 等待 PIXI.live2d 加载完成
    const win = window as any
    const maxWait = 10000
    const startTime = Date.now()

    while (!win.PIXI?.live2d?.Live2DModel && Date.now() - startTime < maxWait) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    if (!win.PIXI?.live2d?.Live2DModel) {
      throw new Error('PIXI.live2d.Live2DModel 未找到，请检查网络连接')
    }

    loadingDetail.value = '创建画布...'

    // 动态创建新的 canvas 元素
    if (canvasContainerRef.value) {
      // 清空容器
      canvasContainerRef.value.innerHTML = ''

      // 创建新 canvas
      const canvas = document.createElement('canvas')
      canvas.width = props.width
      canvas.height = props.height
      canvas.style.width = `${props.width}px`
      canvas.style.height = `${props.height}px`
      canvasContainerRef.value.appendChild(canvas)
      canvasRef.value = canvas
    }

    loadingDetail.value = '创建PIXI应用...'

    console.log('[Live2D] PIXI Application:', typeof PIXI.Application)
    console.log('[Live2D] PIXI 版本:', PIXI.VERSION)

    // 创建PIXI应用
    const appOptions = {
      width: props.width,
      height: props.height,
      transparent: true,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
      forceCanvas: false,
      view: canvasRef.value!,
      // 避免 shader 编译错误
      preserveDrawingBuffer: false,
      powerPreference: 'high-performance'
    }

    app = new PIXI.Application(appOptions)

    // 额外的错误处理
    app.renderer.on('error', (error: any) => {
      console.error('[Live2D] WebGL 渲染器错误:', error)
    })

    console.log('[Live2D] PIXI 应用创建成功')

    loadingDetail.value = '加载Live2D模型...'

    const Live2DModelClass = win.PIXI.live2d.Live2DModel
    const modelUrl = new URL(props.modelPath, window.location.origin).href
    console.log('[Live2D] 模型URL:', modelUrl)

    live2dModel = await Live2DModelClass.from(modelUrl)

    console.log('[Live2D] 模型加载成功')

    // 设置模型位置和缩放
    live2dModel.x = props.width / 2
    live2dModel.y = props.height / 2
    live2dModel.anchor.set(0.5)

    const scale = Math.min(
      (props.width - 10) / live2dModel.width,
      (props.height - 10) / live2dModel.height
    )
    live2dModel.scale.set(scale * 1.8)

    // 添加到舞台
    app.stage.addChild(live2dModel)

    // 设置可交互
    live2dModel.interactive = true
    live2dModel.cursor = 'move'

    // 添加拖动事件
    live2dModel.on('pointerdown', onDragStart)
    live2dModel.on('pointerup', onDragEnd)
    live2dModel.on('pointerupoutside', onDragEnd)
    live2dModel.on('pointermove', onDragMove)

    // 桌宠模式：鼠标穿透控制
    if (props.isStandalone) {
      live2dModel.on('pointerdown', () => {
        window.electronAPI?.setIgnoreMouseEvents(false)
      })
      live2dModel.on('pointerup', () => {
        window.electronAPI?.setIgnoreMouseEvents(true, { forward: true })
      })
      live2dModel.on('pointerupoutside', () => {
        window.electronAPI?.setIgnoreMouseEvents(true, { forward: true })
      })
    }

    // 添加滚轮缩放事件
    const container = canvasRef.value?.parentElement
    if (container) {
      container.addEventListener('wheel', onWheel, { passive: false })
    }

    if (props.isStandalone) {
      window.addEventListener('wheel', onWheel as any, { passive: false })
    }

    loadingDetail.value = '设置初始表情...'
    setExpressionByEmotion(props.emotion)

    isLoaded.value = true
    isLoading.value = false

    console.log('[Live2D] 模型加载成功:', modelName.value)
    emit('loaded')

  } catch (err: any) {
    console.error('[Live2D] 初始化错误:', err)
    error.value = err.message || 'Live2D加载失败'
    isLoading.value = false
    emit('error', err)
  }
}

// 拖动开始
function onDragStart(event: any) {
  isDragging = true
  lastMousePos = event.data.getLocalPosition(live2dModel.parent)
}

// 拖动结束
function onDragEnd() {
  isDragging = false
}

// 拖动中
function onDragMove(event: any) {
  if (!isDragging) return

  const newPos = event.data.getLocalPosition(live2dModel.parent)
  const dx = newPos.x - lastMousePos.x
  const dy = newPos.y - lastMousePos.y

  live2dModel.x += dx
  live2dModel.y += dy

  lastMousePos = newPos
}

// 滚轮缩放
function onWheel(event: WheelEvent) {
  event.preventDefault()
  event.stopPropagation()

  if (!live2dModel) return

  if (props.isStandalone) {
    window.electronAPI?.setIgnoreMouseEvents(false)
  }

  const delta = event.deltaY > 0 ? 0.9 : 1.1
  const newScale = live2dModel.scale.x * delta

  const minScale = 0.01
  const maxScale = 3.0

  if (newScale >= minScale && newScale <= maxScale) {
    live2dModel.scale.set(newScale)
  }
}

// 设置表情
function setExpression(index: number) {
  if (!live2dModel) return

  currentExpressionIndex.value = index
  const expr = expressions[index]
  console.log('[Live2D] 尝试设置表情:', index, expr?.name)

  if (!expr) {
    console.warn('[Live2D] 表情不存在:', index)
    return
  }

  try {
    // 尝试通过 live2dModel.expressions 获取表情列表
    const expressionsList = live2dModel.expressions
    console.log('[Live2D] 模型表情列表:', expressionsList)

    if (expressionsList && expressionsList.length > 0) {
      // 使用索引直接设置表情
      const expressionIndex = index % expressionsList.length
      const expression = expressionsList[expressionIndex]

      if (expression) {
        live2dModel.expression = expression
        console.log('[Live2D] ✅ 设置表情成功:', expression.name || expressionIndex, expr.name)
        currentEmotion.value = expr.name
        emit('emotion-change', expr.name)
        return
      }
    }

    // 尝试通过 internalModel 设置
    const internalModel = live2dModel.internalModel

    if (internalModel?.motionManager?.expressionManager) {
      // 检查模型是否有表情
      const hasExpressions = internalModel.internalModel?.settings?.expressions &&
        Object.keys(internalModel.internalModel.settings.expressions).length > 0

      if (!hasExpressions) {
        console.log('[Live2D] 模型没有表情定义，跳过设置表情')
        currentEmotion.value = expr.name
        emit('emotion-change', expr.name)
        return
      }

      const expressionName = `expression${index + 1}`
      internalModel.motionManager.expressionManager.setExpression(expressionName)
      console.log('[Live2D] ✅ 设置表情成功:', expressionName, expr.name)
      currentEmotion.value = expr.name
      emit('emotion-change', expr.name)
    } else {
      console.log('[Live2D] 模型不支持表情功能，使用默认状态')
      currentEmotion.value = expr.name
      emit('emotion-change', expr.name)
    }
  } catch (err) {
    console.log('[Live2D] 设置表情失败（模型可能没有表情）:', err)
    currentEmotion.value = expr.name
    emit('emotion-change', expr.name)
  }
}

// 根据情绪设置表情
function setExpressionByEmotion(emotion: string) {
  const emotionMap: Record<string, number> = {
    '开心': 0, '快乐': 0, '喜悦': 0,
    '害羞': 1, '尴尬': 1, '羞涩': 1,
    '生气': 2, '愤怒': 2, '暴躁': 2,
    '悲伤': 3, '难过': 3, '痛苦': 3,
    '平静': 4, '安静': 4, '专注': 4,
    '兴奋': 5, '激动': 5, '热情': 5,
    '调皮': 6, '可爱': 6,
    '嘘声': 7
  }

  const index = emotionMap[emotion] ?? 4
  setExpression(index)
}

// 播放动作
function playMotion(index: number = 0) {
  if (!live2dModel) {
    console.log('[Live2D] 模型未加载，无法播放动作')
    return
  }

  console.log('[Live2D] 尝试播放动作，索引:', index)

  try {
    // 尝试通过 live2dModel.motions 获取动作列表
    const motionsList = live2dModel.motions
    console.log('[Live2D] 模型动作列表:', motionsList)

    if (motionsList && motionsList.length > 0) {
      const motionIndex = index % motionsList.length
      const motion = motionsList[motionIndex]
      console.log('[Live2D] ✅ 播放动作（通过motions）:', motionIndex)
      // 触发动作需要通过模型的方法
    }

    // 尝试通过 internalModel 设置
    const internalModel = live2dModel.internalModel

    if (internalModel?.motionManager) {
      // 尝试播放指定索引的动作
      const groups = internalModel.motionManager.motionGroups
      console.log('[Live2D] 动作组 (motionGroups):', groups)

      if (groups && Object.keys(groups).length > 0) {
        const groupNames = Object.keys(groups)
        console.log('[Live2D] 可用动作组:', groupNames)
        const groupName = groupNames[index % groupNames.length]
        const motionList = groups[groupName]

        if (motionList && motionList.length > 0) {
          const motionIndex = index % motionList.length
          internalModel.motionManager.startMotion(groupName, motionIndex)
          console.log('[Live2D] ✅ 播放动作:', groupName, motionIndex)
          return
        } else {
          console.warn('[Live2D] 动作组为空:', groupName)
        }
      }

      // 尝试使用CoreMotion
      if (internalModel.coreModel) {
        console.log('[Live2D] 尝试通过CoreModel播放动作')
        // Cubism 4 SDK 可以通过 coreModel 播放动作
      }

      // 尝试播放随机动作（通常是idle或空闲动作）
      console.log('[Live2D] 尝试播放随机空闲动作')
      if (internalModel.motionManager.startRandomMotion) {
        internalModel.motionManager.startRandomMotion('idle')
      } else if (internalModel.motionManager.startMotion) {
        // 尝试播放名为 Idle 或 Motion 的动作组
        internalModel.motionManager.startMotion('Idle', 0)
      }
      console.log('[Live2D] ✅ 已触发随机空闲动作')
    } else {
      console.warn('[Live2D] motionManager 不可用，模型可能不支持动作')
    }
  } catch (err) {
    console.error('[Live2D] 播放动作失败:', err)
  }
}

// 暂停 Live2D 渲染（用于隐藏时）
function pause() {
  if (app && !isPaused.value) {
    try {
      app.stop()
      isPaused.value = true
      console.log('[Live2D] 渲染已暂停')
    } catch (err) {
      console.error('[Live2D] 暂停渲染失败:', err)
    }
  }
}

// 恢复 Live2D 渲染（用于显示时）
function resume() {
  if (app && isPaused.value) {
    try {
      app.start()
      isPaused.value = false
      console.log('[Live2D] 渲染已恢复')
    } catch (err) {
      console.error('[Live2D] 恢复渲染失败:', err)
    }
  }
}

// 清理
function cleanup() {
  console.log('[Live2D] 开始清理资源...')

  // 清理模型
  if (live2dModel) {
    try {
      // 停止所有动作
      if (live2dModel.internalModel?.motionManager) {
        live2dModel.internalModel.motionManager.stopAllMotions()
      }
      // 销毁模型
      if (typeof live2dModel.destroy === 'function') {
        live2dModel.destroy()
      }
      console.log('[Live2D] 模型清理完成')
    } catch (err) {
      console.error('[Live2D] 清理模型时出错:', err)
    }
    live2dModel = null
  }

  // 清理 PIXI 应用
  if (app) {
    try {
      // 移除事件监听
      if (canvasRef.value?.parentElement) {
        const container = canvasRef.value.parentElement
        container.removeEventListener('wheel', onWheel)
      }
      if (props.isStandalone) {
        window.removeEventListener('wheel', onWheel)
      }

      // 销毁 PIXI 应用
      if (app.view) {
        app.destroy(true, {
          children: true,
          texture: true,
          baseTexture: true
        })
      }

      console.log('[Live2D] PIXI 应用清理完成')
    } catch (err) {
      console.error('[Live2D] 清理 app 时出错:', err)
    }
    app = null
  }

  console.log('[Live2D] 所有资源清理完成')
}

onMounted(() => {
  console.log('[Live2D] 组件挂载，模型路径:', props.modelPath)
  initLive2D()
})

onBeforeUnmount(() => {
  cleanup()
})

watch(() => props.emotion, (newEmotion) => {
  setExpressionByEmotion(newEmotion)
})

// 监听模型路径变化，重新初始化
watch(() => props.modelPath, (newPath, oldPath) => {
  if (newPath !== oldPath) {
    console.log('[Live2D] 模型路径变化，重新初始化:', oldPath, '->', newPath)
    cleanup()

    // 短暂延迟后重新初始化
    setTimeout(() => {
      console.log('[Live2D] 延迟结束，开始重新初始化')
      initLive2D()
    }, 100)
  }
})

defineExpose({
  setExpression,
  playMotion,
  pause,
  resume
})
</script>

<template>
  <div class="live2d-viewer" :class="{ 'is-standalone': isStandalone }">
    <div ref="canvasContainerRef" class="canvas-container">
      <!-- Canvas 将通过 JS 动态创建 -->
    </div>

    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>正在加载Live2D模型...</p>
      <p class="loading-detail">{{ loadingDetail }}</p>
    </div>

    <div v-if="error && !isLoading" class="error-overlay">
      <p>⚠️ {{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.live2d-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(4, 47, 46, 0.3);
  border-radius: 12px;
  overflow: hidden;
}

.live2d-viewer.is-standalone {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  overflow: visible;
  width: 100vw;
  height: 100vh;
}

.is-standalone .canvas-container,
.is-standalone .canvas-container canvas {
  background: transparent !important;
  border: none !important;
}

.canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.canvas-container canvas {
  max-width: 100%;
  max-height: 100%;
  border-radius: 8px;
}

.is-standalone .canvas-container canvas {
  max-width: none;
  max-height: none;
}

.is-standalone .loading-overlay,
.is-standalone .error-overlay,
.is-standalone .tips-overlay {
  display: none !important;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 10;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(45, 212, 191, 0.2);
  border-top-color: #2dd4bf;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-overlay p {
  color: #2dd4bf;
  font-size: 14px;
  margin: 0;
}

.loading-detail {
  color: #94a3b8;
  font-size: 12px;
  margin-top: -8px !important;
}

.error-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 10;
  padding: 20px;
  text-align: center;
}

.error-overlay p {
  color: #f87171;
  font-size: 14px;
  margin: 0;
  word-break: break-word;
}

.tips-overlay {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  z-index: 5;
  text-align: right;
  pointer-events: none;
  opacity: 0.8;
}

.tips-overlay p {
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  margin: 2px 0;
  line-height: 1.5;
}

.tips-overlay p:first-child {
  color: #2dd4bf;
  font-size: 12px;
  font-weight: 500;
}
</style>