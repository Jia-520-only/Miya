<template>
  <div class="simple-live2d-container">
    <canvas ref="canvasRef" :width="width" :height="height"></canvas>
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

interface Props {
  modelPath: string
  emotion: string
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 260,
  height: 340,
  emotion: '平静'
})

const canvasRef = ref<HTMLCanvasElement>()
const ctx = ref<CanvasRenderingContext2D | null>(null)
const error = ref<string>('')
const image = ref<HTMLImageElement | null>(null)
let animationFrame: number = 0

// 表情对应的图片路径映射
const emotionImageMap: Record<string, string> = {
  '开心': '/live2d/ht/ht.8192/texture_00.png',
  '快乐': '/live2d/ht/ht.8192/texture_00.png',
  '喜悦': '/live2d/ht/ht.8192/texture_00.png',
  '害羞': '/live2d/ht/ht.8192/texture_00.png',
  '尴尬': '/live2d/ht/ht.8192/texture_00.png',
  '羞涩': '/live2d/ht/ht.8192/texture_00.png',
  '生气': '/live2d/ht/ht.8192/texture_00.png',
  '愤怒': '/live2d/ht/ht.8192/texture_00.png',
  '暴躁': '/live2d/ht/ht.8192/texture_00.png',
  '悲伤': '/live2d/ht/ht.8192/texture_00.png',
  '难过': '/live2d/ht/ht.8192/texture_00.png',
  '痛苦': '/live2d/ht/ht.8192/texture_00.png',
  '平静': '/live2d/ht/ht.8192/texture_00.png',
  '安静': '/live2d/ht/ht.8192/texture_00.png',
  '专注': '/live2d/ht/ht.8192/texture_00.png',
  '兴奋': '/live2d/ht/ht.8192/texture_00.png',
  '激动': '/live2d/ht/ht.8192/texture_00.png',
  '热情': '/live2d/ht/ht.8192/texture_00.png',
  '调皮': '/live2d/ht/ht.8192/texture_00.png',
  '可爱': '/live2d/ht/ht.8192/texture_00.png',
  '嘘声': '/live2d/ht/ht.8192/texture_00.png'
}

// 动画变量
let time = 0
const breathAmplitude = 0.03
const breathFrequency = 2
const eyeBlinkInterval = 3000
let lastBlinkTime = 0
const eyeOpenness = ref(1)

// 加载图片
function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`Failed to load image: ${src}`))
    img.src = src
  })
}

// 眨眼动画
function updateEyeBlink(timestamp: number) {
  if (timestamp - lastBlinkTime > eyeBlinkInterval) {
    // 触发眨眼
    eyeOpenness.value = 0
    lastBlinkTime = timestamp
  }

  // 眼睛逐渐张开
  if (eyeOpenness.value < 1) {
    eyeOpenness.value += 0.1
    if (eyeOpenness.value > 1) eyeOpenness.value = 1
  }
}

// 绘制函数
function draw(timestamp: number) {
  if (!ctx.value || !image.value) return

  const context = ctx.value
  const width = props.width
  const height = props.height

  // 清空画布
  context.clearRect(0, 0, width, height)

  // 更新动画时间
  time = timestamp / 1000

  // 更新眨眼
  updateEyeBlink(timestamp)

  // 呼吸动画
  const breathY = Math.sin(time * breathFrequency) * breathAmplitude * height

  // 缩放动画
  const breathScale = 1 + Math.sin(time * breathFrequency) * breathAmplitude

  context.save()

  // 移动到中心
  context.translate(width / 2, height / 2)

  // 应用呼吸动画
  context.translate(0, breathY)
  context.scale(breathScale, breathScale)

  // 应用眨眼（通过透明度模拟）
  if (eyeOpenness.value < 1) {
    context.globalAlpha = eyeOpenness.value
  }

  // 绘制图片
  if (image.value) {
    const img = image.value
    // 保持图片比例，居中绘制
    const scale = Math.min((width - 20) / img.width, (height - 20) / img.height)
    const drawWidth = img.width * scale
    const drawHeight = img.height * scale

    context.drawImage(
      img,
      -drawWidth / 2,
      -drawHeight / 2,
      drawWidth,
      drawHeight
    )
  }

  context.restore()

  // 继续动画循环
  animationFrame = requestAnimationFrame(draw)
}

// 初始化
async function init() {
  try {
    if (!canvasRef.value) {
      throw new Error('Canvas element not found')
    }

    // 获取 2D 上下文
    ctx.value = canvasRef.value.getContext('2d')
    if (!ctx.value) {
      throw new Error('Failed to get 2D context')
    }

    // 加载图片
    const imgPath = emotionImageMap[props.emotion] || emotionImageMap['平静']
    image.value = await loadImage(imgPath)

    // 开始动画循环
    animationFrame = requestAnimationFrame(draw)

    console.log('[SimpleLive2D] 初始化成功')
  } catch (err: any) {
    console.error('[SimpleLive2D] 初始化失败:', err)
    error.value = err.message || 'Live2D 加载失败'
  }
}

// 监听情绪变化，重新加载图片
watch(() => props.emotion, async (newEmotion) => {
  if (image.value) {
    try {
      const imgPath = emotionImageMap[newEmotion] || emotionImageMap['平静']
      image.value = await loadImage(imgPath)
      console.log('[SimpleLive2D] 表情更新:', newEmotion)
    } catch (err) {
      console.error('[SimpleLive2D] 图片加载失败:', err)
    }
  }
})

// 清理
function cleanup() {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame)
  }
  ctx.value = null
  image.value = null
}

onMounted(() => {
  init()
})

onBeforeUnmount(() => {
  cleanup()
})
</script>

<style scoped>
.simple-live2d-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(4, 47, 46, 0.3);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  overflow: hidden;
}

.simple-live2d-container canvas {
  display: block;
  max-width: 100%;
  max-height: 100%;
}

.error-message {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #f87171;
  font-size: 14px;
  text-align: center;
  padding: 12px 20px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 8px;
}
</style>
