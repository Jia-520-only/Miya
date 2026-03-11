<template>
  <div class="live2d-control-panel">
    <div class="panel-header">
      <span class="panel-title">Live2D 控制面板</span>
      <button @click="toggleWindow" class="icon-btn">
        {{ windowOpen ? '📌' : '📭' }}
      </button>
    </div>

    <!-- 窗口控制 -->
    <div class="control-section">
      <h4>窗口控制</h4>
      <div class="button-group">
        <button @click="createWindow" :disabled="windowOpen" class="control-btn primary">
          打开窗口
        </button>
        <button @click="closeWindow" :disabled="!windowOpen" class="control-btn danger">
          关闭窗口
        </button>
        <button @click="toggleAlwaysOnTop" :disabled="!windowOpen" class="control-btn">
          {{ alwaysOnTop ? '取消置顶' : '窗口置顶' }}
        </button>
      </div>
    </div>

    <!-- 大小控制 -->
    <div class="control-section">
      <h4>窗口大小</h4>
      <div class="size-controls">
        <label>
          宽度: {{ windowSize.width }}px
          <input
            type="range"
            v-model.number="windowSize.width"
            :min="200"
            :max="800"
            @input="updateSize"
            :disabled="!windowOpen"
          />
        </label>
        <label>
          高度: {{ windowSize.height }}px
          <input
            type="range"
            v-model.number="windowSize.height"
            :min="300"
            :max="900"
            @input="updateSize"
            :disabled="!windowOpen"
          />
        </label>
      </div>
    </div>

    <!-- 表情控制 -->
    <div class="control-section">
      <h4>表情控制</h4>
      <div class="expression-grid">
        <button
          v-for="(expr, index) in expressions"
          :key="index"
          @click="setExpression(index)"
          :disabled="!windowOpen"
          class="expr-btn"
          :class="{ active: currentExpressionIndex === index }"
        >
          <span class="expr-icon">{{ expr.icon }}</span>
          <span class="expr-name">{{ expr.name }}</span>
        </button>
      </div>
    </div>

    <!-- 快捷方式 -->
    <div class="control-section">
      <h4>快捷方式</h4>
      <div class="presets">
        <button @click="setPreset('small')" :disabled="!windowOpen" class="preset-btn">
          📱 小窗口
        </button>
        <button @click="setPreset('medium')" :disabled="!windowOpen" class="preset-btn">
          💻 中窗口
        </button>
        <button @click="setPreset('large')" :disabled="!windowOpen" class="preset-btn">
          🖥️ 大窗口
        </button>
        <button @click="setPreset('fullscreen')" :disabled="!windowOpen" class="preset-btn">
          📺 全屏模式
        </button>
      </div>
    </div>

    <!-- 状态信息 -->
    <div class="status-section">
      <p>状态: {{ status }}</p>
      <p v-if="windowOpen">窗口: {{ windowSize.width }}x{{ windowSize.height }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// 状态
const windowOpen = ref(false)
const alwaysOnTop = ref(true)
const currentExpressionIndex = ref(4) // 默认平静

const windowSize = ref({
  width: 400,
  height: 500
})

const status = ref('未启动')

// 表情列表
const expressions = [
  { icon: '😊', name: '开心' },
  { icon: '😳', name: '害羞' },
  { icon: '😠', name: '生气' },
  { icon: '😢', name: '悲伤' },
  { icon: '😐', name: '平静' },
  { icon: '🤩', name: '兴奋' },
  { icon: '😜', name: '调皮' },
  { icon: '🤫', name: '嘘声' }
]

// 创建 Live2D 窗口
async function createWindow() {
  try {
    status.value = '正在创建窗口...'
    await window.electron?.ipcRenderer.invoke('live2d:create')
    windowOpen.value = true
    status.value = '窗口已打开'
  } catch (error) {
    console.error('创建窗口失败:', error)
    status.value = '创建失败'
  }
}

// 关闭 Live2D 窗口
async function closeWindow() {
  try {
    await window.electron?.ipcRenderer.invoke('live2d:close')
    windowOpen.value = false
    status.value = '窗口已关闭'
  } catch (error) {
    console.error('关闭窗口失败:', error)
  }
}

// 切换窗口显示
async function toggleWindow() {
  if (windowOpen.value) {
    await window.electron?.ipcRenderer.invoke('live2d:toggle')
  } else {
    await createWindow()
  }
}

// 切换置顶
async function toggleAlwaysOnTop() {
  alwaysOnTop.value = !alwaysOnTop.value
  try {
    await window.electron?.ipcRenderer.invoke('live2d:setAlwaysOnTop', alwaysOnTop.value)
  } catch (error) {
    console.error('设置置顶失败:', error)
  }
}

// 更新窗口大小
async function updateSize() {
  try {
    await window.electron?.ipcRenderer.invoke('live2d:setSize', windowSize.value.width, windowSize.value.height)
  } catch (error) {
    console.error('设置窗口大小失败:', error)
  }
}

// 设置表情
async function setExpression(index: number) {
  currentExpressionIndex.value = index
  try {
    // 直接发送到主进程，再转发给 Live2D 窗口
    window.electron?.ipcRenderer.send('live2d:setExpression', index)
    status.value = `已设置: ${expressions[index].name}`
  } catch (error) {
    console.error('设置表情失败:', error)
  }
}

// 预设大小
function setPreset(preset: string) {
  const presets = {
    small: { width: 300, height: 400 },
    medium: { width: 400, height: 500 },
    large: { width: 600, height: 700 },
    fullscreen: { width: 800, height: 900 }
  }

  const size = presets[preset as keyof typeof presets]
  if (size) {
    windowSize.value = size
    updateSize()
  }
}

onMounted(() => {
  console.log('[Live2D Control Panel] 组件挂载')
  status.value = '准备就绪'
})

onBeforeUnmount(() => {
  console.log('[Live2D Control Panel] 组件卸载')
})
</script>

<style scoped>
.live2d-control-panel {
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  padding: 20px;
  color: #f0fdfa;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #2dd4bf;
}

.icon-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.icon-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.control-section {
  margin-bottom: 24px;
}

.control-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.button-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.control-btn {
  padding: 8px 16px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  color: #f0fdfa;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.control-btn:hover:not(:disabled) {
  background: rgba(45, 212, 191, 0.2);
  border-color: #2dd4bf;
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.control-btn.primary {
  background: #2dd4bf;
  color: #000;
  border-color: #2dd4bf;
}

.control-btn.primary:hover:not(:disabled) {
  background: #14b8a6;
}

.control-btn.danger {
  border-color: #f87171;
  color: #f87171;
}

.control-btn.danger:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.2);
}

.size-controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.size-controls label {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #94a3b8;
}

.size-controls input[type="range"] {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.1);
  appearance: none;
  cursor: pointer;
}

.size-controls input[type="range"]::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #2dd4bf;
  cursor: pointer;
}

.size-controls input[type="range"]:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.expression-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.expr-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f0fdfa;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.expr-btn:hover:not(:disabled) {
  background: rgba(45, 212, 191, 0.2);
  border-color: #2dd4bf;
  transform: translateY(-2px);
}

.expr-btn.active {
  background: #2dd4bf;
  border-color: #2dd4bf;
  color: #000;
  box-shadow: 0 0 12px rgba(45, 212, 191, 0.4);
}

.expr-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.expr-icon {
  font-size: 24px;
}

.expr-name {
  font-weight: 500;
}

.presets {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.preset-btn {
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f0fdfa;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.preset-btn:hover:not(:disabled) {
  background: rgba(45, 212, 191, 0.2);
  border-color: #2dd4bf;
  transform: translateY(-2px);
}

.preset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-section {
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.status-section p {
  margin: 4px 0;
  display: flex;
  justify-content: space-between;
}
</style>
