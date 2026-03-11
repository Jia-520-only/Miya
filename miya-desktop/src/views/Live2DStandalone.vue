<template>
  <div class="live2d-standalone" @mousemove="showControls" @mouseenter="showControls">
    <!-- 顶部透明拖动条 -->
    <div class="drag-area"></div>

    <Live2DFull
      ref="live2dComponentRef"
      :key="modelKey"
      :modelPath="modelPath"
      :emotion="currentEmotion"
      :width="600"
      :height="800"
      :isStandalone="true"
      @loaded="onModelLoaded"
      @error="onModelError"
    />

    <!-- 悬浮控制按钮 -->
    <Transition name="fade">
      <div v-show="controlsVisible" class="float-controls">
        <!-- 换装按钮 -->
        <button class="float-btn" @click="toggleClothingPanel" title="换装">
          <span class="btn-icon">👗</span>
        </button>
        <!-- 拖动切换按钮 -->
        <button class="float-btn" :class="{ active: isDraggable }" @click="toggleDraggable" title="拖动">
          <span class="btn-icon">✋</span>
        </button>
        <!-- 点击穿透按钮 -->
        <button class="float-btn" :class="{ active: ignoreMouse }" @click="toggleIgnoreMouse" title="点击穿透">
          <span class="btn-icon">👻</span>
        </button>
      </div>
    </Transition>

    <!-- 换装面板 -->
    <Transition name="slide">
      <div v-show="clothingPanelVisible && controlsVisible" class="clothing-panel">
        <div class="panel-title">换装</div>
        <div class="clothing-grid">
          <button
            v-for="model in availableModels"
            :key="model.id"
            class="clothing-item"
            :class="{ active: selectedModelId === model.id }"
            @click="selectModel(model.id)"
          >
            {{ model.name }}
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import Live2DFull from '../components/Live2DFull.vue'
import { LIVE2D_MODELS } from '../config/live2dModels'

// 可用模型列表
const availableModels = ref(Object.values(LIVE2D_MODELS))

const modelPath = ref('/live2d/ht/ht.model3.json')
const currentEmotion = ref('平静')
const live2dComponentRef = ref<InstanceType<typeof Live2DFull>>()
const modelKey = ref(0)
const selectedModelId = ref('ht')

// 控制按钮显示
const controlsVisible = ref(false)
const clothingPanelVisible = ref(false)
const isDraggable = ref(true)
const ignoreMouse = ref(false)
let hideControlsTimer: ReturnType<typeof setTimeout> | null = null

function onModelLoaded() {
  console.log('[Live2D Standalone] 模型加载成功:', modelPath.value)
}

function onModelError(error: any) {
  console.error('[Live2D Standalone] 模型加载失败:', error)
}

// 显示控制按钮
function showControls() {
  controlsVisible.value = true
  if (hideControlsTimer) {
    clearTimeout(hideControlsTimer)
  }
  hideControlsTimer = setTimeout(() => {
    controlsVisible.value = false
    clothingPanelVisible.value = false
  }, 3000)
}

// 切换换装面板
function toggleClothingPanel() {
  clothingPanelVisible.value = !clothingPanelVisible.value
  showControls()
}

// 切换拖动状态
function toggleDraggable() {
  isDraggable.value = !isDraggable.value
  showControls()
}

// 切换点击穿透
function toggleIgnoreMouse() {
  ignoreMouse.value = !ignoreMouse.value
  if (window.electronAPI) {
    window.electronAPI.setIgnoreMouseEvents(ignoreMouse.value, { forward: true })
  }
  showControls()
}

// 选择模型
function selectModel(modelId: string) {
  selectedModelId.value = modelId
  const model = availableModels.value.find(m => m.id === modelId)
  if (model) {
    modelPath.value = model.path
    modelKey.value++
  }
  // 通知主窗口切换模型
  if (window.electronAPI) {
    window.electronAPI.live2d?.sendModelChange(modelId)
  }
  clothingPanelVisible.value = false
}

// 监听来自主窗口的控制消息
function setupIPCListeners() {
  if (!window.electronAPI) return

  // 监听表情设置
  window.electronAPI.onLive2DSetExpression((index: number) => {
    console.log('[Live2D Standalone] 收到表情设置:', index)
    if (live2dComponentRef.value) {
      live2dComponentRef.value.setExpression(index)
    }
  })

  // 监听动作设置
  window.electronAPI.onLive2DSetMotion((index: number) => {
    console.log('[Live2D Standalone] 收到动作设置:', index)
    if (live2dComponentRef.value) {
      live2dComponentRef.value.playMotion(index)
    }
  })

  // 监听模型切换
  window.electronAPI.onLive2DSetModelChange((modelId: string) => {
    console.log('[Live2D Standalone] 收到模型切换:', modelId)
    selectModel(modelId)
  })
}

onMounted(() => {
  // 确保背景完全透明
  document.body.style.backgroundColor = 'transparent'
  document.documentElement.style.backgroundColor = 'transparent'
  // 清除页面标题
  document.title = ''

  // 设置 IPC 监听
  setupIPCListeners()

  // 初始显示控制按钮
  setTimeout(() => {
    showControls()
  }, 1000)
})

onBeforeUnmount(() => {
  document.body.style.backgroundColor = ''
  document.documentElement.style.backgroundColor = ''
  if (hideControlsTimer) {
    clearTimeout(hideControlsTimer)
  }
})
</script>

<style scoped>
.live2d-standalone {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: transparent;
  overflow: visible;
}

/* 顶部拖动区域 - 透明但可拖动 */
.drag-area {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 32px;
  -webkit-app-region: drag;
  cursor: move;
  z-index: 9999;
  background: transparent;
}

/* 悬浮控制按钮 */
.float-controls {
  position: fixed;
  top: 40px;
  right: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 100;
}

.float-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.float-btn:hover {
  background: rgba(45, 212, 191, 0.5);
  border-color: rgba(45, 212, 191, 0.8);
  transform: scale(1.1);
}

.float-btn.active {
  background: rgba(45, 212, 191, 0.6);
  border-color: #2dd4bf;
}

.btn-icon {
  font-size: 16px;
}

/* 换装面板 */
.clothing-panel {
  position: fixed;
  top: 80px;
  right: 8px;
  width: 140px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 10px;
  z-index: 99;
}

.panel-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 8px;
  text-align: center;
}

.clothing-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
}

.clothing-item {
  padding: 6px 10px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.2s ease;
}

.clothing-item:hover {
  background: rgba(45, 212, 191, 0.3);
}

.clothing-item.active {
  background: rgba(45, 212, 191, 0.5);
  border-color: #2dd4bf;
  color: #fff;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>

<style>
/* 全局样式，确保透明背景 */
html, body, #app, .app-container, .main-content {
  background: transparent !important;
  background-color: transparent !important;
}

.live2d-standalone,
.live2d-viewer,
.canvas-container,
.live2d-viewer canvas {
  background: transparent !important;
  background-color: transparent !important;
}
</style>
