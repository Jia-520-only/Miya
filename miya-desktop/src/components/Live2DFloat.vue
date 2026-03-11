<template>
  <Teleport to="body">
    <Transition name="float">
      <div
        v-if="visible"
        class="live2d-float-card"
        :style="cardStyle"
        @mousedown="startDrag"
        ref="cardRef"
      >
        <!-- 拖动把手 -->
        <div class="drag-handle" @mousedown="startDrag">
          <i class="pi pi-grip-lines"></i>
        </div>

        <!-- Live2D 区域 -->
        <div class="live2d-content">
          <Live2DFull
            :modelPath="modelPath"
            :emotion="emotion"
            :width="width"
            :height="height"
            @emotion-change="handleEmotionChange"
          />
        </div>

        <!-- 快捷操作栏 - 简化为仅桌宠按钮 -->
        <div class="quick-actions">
          <button @click="$emit('toggle-desktop')" class="action-btn" title="桌宠模式">
            <i class="pi pi-paw"></i>
          </button>
        </div>

        <!-- 当前任务状态（可选） -->
        <div v-if="currentTask" class="task-status">
          <i class="pi pi-spin pi-spinner"></i>
          <span>{{ currentTask }}</span>
        </div>

        <!-- 快捷指令输入 -->
        <div v-if="showQuickCommand" class="quick-command">
          <input
            v-model="quickCommandInput"
            placeholder="输入指令..."
            @keyup.enter="executeQuickCommand"
            @blur="hideQuickCommand"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Live2DFull from './Live2DFull.vue'

const props = defineProps<{
  modelPath: string
  emotion: string
  width?: number
  height?: number
  currentTask?: string
}>()

const emit = defineEmits<{
  (e: 'emotion-change', emotion: string): void
  (e: 'toggle-desktop'): void
  (e: 'open-settings'): void
  (e: 'quick-command', command: string): void
}>()

// 状态
const visible = ref(true)
const expanded = ref(false)
const showQuickCommand = ref(false)
const quickCommandInput = ref('')

// 拖动相关
const cardRef = ref<HTMLElement>()
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const position = ref({ x: 20, y: 20 })

// 计算属性
const cardStyle = computed(() => ({
  position: 'fixed',
  left: `${position.value.x}px`,
  top: `${position.value.y}px`,
  width: props.width ? `${props.width}px` : '200px',
  height: props.height ? `${props.height}px` : '280px',
  zIndex: 1000
}))

// 拖动功能
function startDrag(event: MouseEvent) {
  isDragging.value = true
  dragOffset.value = {
    x: event.clientX - position.value.x,
    y: event.clientY - position.value.y
  }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(event: MouseEvent) {
  if (!isDragging.value) return

  const newX = event.clientX - dragOffset.value.x
  const newY = event.clientY - dragOffset.value.y

  // 限制在窗口内
  const maxX = window.innerWidth - (props.width || 200)
  const maxY = window.innerHeight - (props.height || 280)

  position.value = {
    x: Math.max(0, Math.min(newX, maxX)),
    y: Math.max(0, Math.min(newY, maxY))
  }
}

function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 展开/收起
function toggleExpand() {
  expanded.value = !expanded.value
}

// 快捷指令
function toggleQuickCommand() {
  showQuickCommand.value = !showQuickCommand.value
  if (showQuickCommand.value) {
    setTimeout(() => {
      const input = document.querySelector('.quick-command input') as HTMLInputElement
      input?.focus()
    }, 100)
  }
}

function hideQuickCommand() {
  setTimeout(() => {
    showQuickCommand.value = false
  }, 200)
}

function executeQuickCommand() {
  if (quickCommandInput.value.trim()) {
    emit('quick-command', quickCommandInput.value)
    quickCommandInput.value = ''
    hideQuickCommand()
  }
}

function handleEmotionChange(emotion: string) {
  emit('emotion-change', emotion)
}

// 键盘快捷键
function handleKeydown(event: KeyboardEvent) {
  if (event.altKey && event.key === 'l') {
    toggleQuickCommand()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  
  // 从本地存储恢复位置
  const savedPosition = localStorage.getItem('live2d-float-position')
  if (savedPosition) {
    try {
      position.value = JSON.parse(savedPosition)
    } catch (e) {
      console.warn('Failed to restore Live2D position:', e)
    }
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  
  // 保存位置
  localStorage.setItem('live2d-float-position', JSON.stringify(position.value))
})
</script>

<style scoped>
.live2d-float-card {
  position: fixed;
  background: rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
  overflow: hidden;
  cursor: move;
  transition: all 0.3s ease;
}

.live2d-float-card:hover {
  background: rgba(0, 0, 0, 0.25);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* 拖动把手 - 更透明 */
.drag-handle {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 24px;
  background: rgba(255, 255, 255, 0.03);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: move;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  transition: background 0.2s ease;
}

.drag-handle:hover {
  background: rgba(255, 255, 255, 0.06);
}

.drag-handle i {
  color: rgba(255, 255, 255, 0.2);
  font-size: 10px;
}

/* Live2D 内容区域 */
.live2d-content {
  position: relative;
  padding-top: 24px;
  height: calc(100% - 24px);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 快捷操作栏 - 简化为仅显示按钮 */
.quick-actions {
  position: absolute;
  top: 30px;
  right: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
}

.action-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.7);
  transform: scale(1.1);
}

/* 任务状态 */
.task-status {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(16, 185, 129, 0.6);
  color: #ecfdf5;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 10px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
  backdrop-filter: blur(4px);
  white-space: nowrap;
}

.task-status i {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 动画 */
.float-enter-active,
.float-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.float-enter-from {
  opacity: 0;
  transform: scale(0.8);
}

.float-leave-to {
  opacity: 0;
  transform: scale(0.8);
}
</style>
