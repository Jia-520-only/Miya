<template>
  <div class="live2d-viewer-auto">
    <!-- 加载中 -->
    <div v-if="isLoading" class="loading">
      <div class="spinner"></div>
      <p>加载Live2D模型中...</p>
    </div>

    <!-- 错误提示 -->
    <div v-else-if="error" class="error">
      <div class="error-icon">⚠️</div>
      <h3>Live2D 加载失败</h3>
      <p>{{ error }}</p>
      <button @click="retry" class="retry-btn">重试</button>
      <div class="fallback-hint">
        <p>将使用简化版 Live2D</p>
      </div>
    </div>

    <!-- Live2D 容器 -->
    <div v-else-if="modelLoaded" class="live2d-container">
      <canvas ref="canvasRef" :width="width" :height="height"></canvas>
    </div>

    <!-- 简化版显示 -->
    <div v-else class="live2d-placeholder">
      <div class="placeholder-content">
        <div class="avatar-icon">🐱</div>
        <h3>御姐猫猫头</h3>
        <p class="emotion-display">当前情绪: {{ currentEmotionDisplay }}</p>

        <div class="expression-list">
          <button
            v-for="(expr, name) in expressions"
            :key="name"
            @click="setExpression(name)"
            class="expr-btn"
            :class="{ active: currentExpression === name }"
          >
            {{ expr.emoji }} {{ name }}
          </button>
        </div>

        <div class="info-box">
          <p class="info-title">Live2D模型信息</p>
          <p>• 模型: 御姐猫猫头</p>
          <p>• 表情数量: 8个</p>
          <p>• 状态: 🟢 已加载（简化版）</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

interface Props {
  modelPath: string
  emotion: string
  width?: number
  height?: number
  showControls?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 260,
  height: 340,
  emotion: '平静',
  showControls: false
})

const canvasRef = ref<HTMLCanvasElement>()
const isLoading = ref(true)
const modelLoaded = ref(false)
const error = ref<string>()
const currentExpression = ref('平静')

const expressions: Record<string, { emoji: string; color: string }> = {
  '开心': { emoji: '😊', color: '#2dd4bf' },
  '兴奋': { emoji: '💕', color: '#f472b6' },
  '害羞': { emoji: '😳', color: '#fb923c' },
  '悲伤': { emoji: '😢', color: '#60a5fa' },
  '生气': { emoji: '😠', color: '#f87171' },
  '唱歌': { emoji: '🎤', color: '#a78bfa' },
  '调皮': { emoji: '🦊', color: '#fb923c' },
  '嘘声': { emoji: '🤫', color: '#34d399' }
}

const currentEmotionDisplay = ref(props.emotion)

onMounted(async () => {
  await loadLive2D()
})

watch(() => props.emotion, (newEmotion) => {
  currentEmotionDisplay.value = newEmotion
  currentExpression.value = normalizeEmotion(newEmotion)
})

async function loadLive2D() {
  isLoading.value = true
  error.value = undefined

  try {
    // 尝试动态导入 Live2D SDK
    const PIXI = await import('pixi.js')
    const { Live2DModel } = await import('pixi-live2d-display')

    console.log('Live2D SDK 导入成功', { PIXI, Live2DModel })

    // 创建 PIXI 应用
    const app = new PIXI.Application({
      view: canvasRef.value,
      width: props.width,
      height: props.height,
      backgroundAlpha: 0,
      antialias: true
    })

    // 加载模型
    const model = await Live2DModel.from(props.modelPath)
    model.scale.set(0.8, 0.8)
    model.x = props.width / 2
    model.y = props.height
    app.stage.addChild(model)

    modelLoaded.value = true
    console.log('Live2D 模型加载成功')
  } catch (e) {
    console.log('Live2D SDK 加载失败，使用简化版:', e)
    error.value = (e as Error).message
    modelLoaded.value = false
  } finally {
    isLoading.value = false
  }
}

function retry() {
  loadLive2D()
}

function normalizeEmotion(emotion: string): string {
  const map: Record<string, string> = {
    '快乐': '开心',
    '愉快': '开心',
    '喜悦': '开心',
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
    '可爱': '调皮'
  }
  return map[emotion] || emotion
}

function setExpression(emotion: string) {
  currentExpression.value = emotion
}
</script>

<style scoped>
.live2d-viewer-auto {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.1) 0%, rgba(14, 165, 233, 0.1) 100%);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px;
}

.spinner {
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

.loading p {
  font-size: 14px;
  color: #2dd4bf;
  margin: 0;
}

.error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px;
  text-align: center;
}

.error-icon {
  font-size: 48px;
}

.error h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #f87171;
}

.error p {
  margin: 0;
  font-size: 14px;
  color: #94a3b8;
}

.retry-btn {
  padding: 8px 24px;
  background: rgba(45, 212, 191, 0.2);
  border: 1px solid #2dd4bf;
  border-radius: 8px;
  color: #2dd4bf;
  cursor: pointer;
  transition: all 0.3s ease;
}

.retry-btn:hover {
  background: rgba(45, 212, 191, 0.3);
  transform: translateY(-2px);
}

.fallback-hint {
  margin-top: 8px;
  padding: 8px 16px;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 8px;
}

.fallback-hint p {
  margin: 0;
  font-size: 12px;
  color: #fbbf24;
}

.live2d-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live2d-container canvas {
  width: 100%;
  height: 100%;
}

.live2d-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.avatar-icon {
  font-size: 80px;
  animation: bounce 2s ease-in-out infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.placeholder-content h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #f0fdfa;
}

.emotion-display {
  margin: 0;
  font-size: 14px;
  color: #5eead4;
  background: rgba(45, 212, 191, 0.1);
  padding: 8px 16px;
  border-radius: 20px;
}

.expression-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 240px;
}

.expr-btn {
  padding: 8px 12px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 16px;
  color: #f0fdfa;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.expr-btn:hover {
  background: rgba(45, 212, 191, 0.2);
  transform: translateY(-2px);
  border-color: #2dd4bf;
}

.expr-btn.active {
  background: rgba(45, 212, 191, 0.3);
  border-color: #2dd4bf;
  box-shadow: 0 0 15px rgba(45, 212, 191, 0.3);
}

.info-box {
  background: rgba(0, 0, 0, 0.3);
  padding: 16px;
  border-radius: 12px;
  text-align: left;
  width: 100%;
  max-width: 280px;
}

.info-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: #2dd4bf;
}

.info-box p {
  margin: 4px 0;
  font-size: 12px;
  color: #94a3b8;
}
</style>
