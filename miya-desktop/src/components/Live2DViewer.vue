<template>
  <div class="live2d-viewer">
    <div v-if="isLoading" class="loading">
      <div class="spinner"></div>
      <p>加载模型中...</p>
    </div>
    <canvas
      ref="canvasRef"
      :width="width"
      :height="height"
      class="live2d-canvas"
    ></canvas>
    <div v-if="showControls" class="controls">
      <button
        v-for="(expression, name) in expressions"
        :key="name"
        @click="setExpression(name)"
        class="control-btn"
        :class="{ active: currentExpression === name }"
      >
        {{ name }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useLive2D } from '../composables/useLive2D'

interface Props {
  modelPath: string
  width?: number
  height?: number
  emotion?: string
  showControls?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 280,
  height: 350,
  emotion: '平静',
  showControls: false
})

const expressions: Record<string, string> = {
  '开心': '开心',
  '兴奋': '兴奋',
  '害羞': '害羞',
  '悲伤': '悲伤',
  '生气': '生气',
  '唱歌': '唱歌',
  '嘘声': '嘘声',
  '狐狸': '调皮'
}

const { canvasRef, isLoading, currentExpression, setExpression } = useLive2D({
  modelPath: props.modelPath,
  width: props.width,
  height: props.height,
  onLoaded: (model) => {
    console.log('Live2D模型加载成功:', model)
  },
  onError: (error) => {
    console.error('Live2D模型加载失败:', error)
  }
})

const normalizedEmotion = computed(() => {
  const emotionMap: Record<string, string> = {
    '喜悦': '开心',
    '愉快': '开心',
    '快乐': '开心',
    '激动': '兴奋',
    '热情': '兴奋',
    '尴尬': '害羞',
    '羞涩': '害羞',
    '难过': '悲伤',
    '痛苦': '悲伤',
    '愤怒': '生气',
    '暴躁': '生气',
    '安静': '平静',
    '专注': '平静',
    '调皮': '调皮',
    '可爱': '调皮'
  }

  return emotionMap[props.emotion] || props.emotion
})

setExpression(normalizedEmotion.value)
</script>

<style scoped>
.live2d-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.1) 0%, rgba(14, 165, 233, 0.1) 100%);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  z-index: 10;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(45, 212, 191, 0.2);
  border-top-color: #2dd4bf;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading p {
  font-size: 14px;
  color: #2dd4bf;
  margin: 0;
}

.live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.controls {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  z-index: 10;
}

.control-btn {
  padding: 6px 12px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 12px;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.control-btn:hover {
  background: rgba(45, 212, 191, 0.3);
  transform: translateY(-2px);
}

.control-btn.active {
  background: rgba(45, 212, 191, 0.5);
  box-shadow: 0 0 15px rgba(45, 212, 191, 0.3);
}
</style>
