<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

const emit = defineEmits<{
  close: []
  save: [blob: Blob]
}>()

const props = defineProps<{
  referenceImage?: string
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let drawing = false
const color = ref('#3b82f6')
const brushSize = ref(3)
const bgLoaded = ref(false)

const colors = ['#ffffff', '#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#a855f7', '#ec4899', '#14b8a6', '#000000']
const brushSizes = [1, 2, 3, 5, 8, 12, 20]

let lastX = 0
let lastY = 0

onMounted(() => {
  if (!canvasRef.value) return
  const canvas = canvasRef.value

  const parent = canvas.parentElement
  if (parent) {
    canvas.width = parent.clientWidth
    canvas.height = parent.clientHeight
  }

  ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.fillStyle = '#1a1f2e'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
  }

  loadBackground()
  resize()
  window.addEventListener('resize', resize)
})

onUnmounted(() => {
  window.removeEventListener('resize', resize)
})

watch(() => props.referenceImage, () => {
  bgLoaded.value = false
  loadBackground()
})

function resize() {
  if (!canvasRef.value) return
  const canvas = canvasRef.value
  const data = ctx?.getImageData(0, 0, canvas.width, canvas.height)
  const parent = canvas.parentElement
  if (!parent) return
  canvas.width = parent.clientWidth
  canvas.height = parent.clientHeight
  ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
  }
  if (data) {
    ctx?.putImageData(data, 0, 0)
  }
  bgLoaded.value = false
  loadBackground()
}

function loadBackground() {
  if (!props.referenceImage || !canvasRef.value || !ctx) return
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    if (!ctx || !canvasRef.value) return
    ctx.globalAlpha = 0.3
    const scale = Math.min(
      canvasRef.value.width / img.width,
      canvasRef.value.height / img.height,
    )
    const x = (canvasRef.value.width - img.width * scale) / 2
    const y = (canvasRef.value.height - img.height * scale) / 2
    ctx.drawImage(img, x, y, img.width * scale, img.height * scale)
    ctx.globalAlpha = 1
    bgLoaded.value = true
  }
  img.src = props.referenceImage
}

function getPos(e: MouseEvent): { x: number, y: number } {
  if (!canvasRef.value) return { x: 0, y: 0 }
  const rect = canvasRef.value.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function onMouseDown(e: MouseEvent) {
  drawing = true
  const pos = getPos(e)
  lastX = pos.x
  lastY = pos.y
}

function onMouseMove(e: MouseEvent) {
  if (!drawing || !ctx) return
  const pos = getPos(e)
  ctx.strokeStyle = color.value
  ctx.lineWidth = brushSize.value
  ctx.beginPath()
  ctx.moveTo(lastX, lastY)
  ctx.lineTo(pos.x, pos.y)
  ctx.stroke()
  lastX = pos.x
  lastY = pos.y
}

function onMouseUp() {
  drawing = false
}

function clearCanvas() {
  if (!ctx || !canvasRef.value) return
  ctx.fillStyle = '#1a1f2e'
  ctx.fillRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  bgLoaded.value = false
  loadBackground()
}

function saveImage() {
  if (!canvasRef.value) return
  canvasRef.value.toBlob((blob) => {
    if (blob) emit('save', blob)
  }, 'image/png')
}

function downloadImage() {
  if (!canvasRef.value) return
  const link = document.createElement('a')
  link.download = `miya-doodle-${Date.now()}.png`
  link.href = canvasRef.value.toDataURL()
  link.click()
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Toolbar -->
    <div class="flex items-center gap-2 p-2 border-b border-gray-800 bg-gray-900/50 shrink-0">
      <div class="flex gap-0.5">
        <button
          v-for="c in colors"
          :key="c"
          class="w-5 h-5 rounded-full border transition-transform hover:scale-110"
          :style="{ backgroundColor: c, borderColor: c === '#ffffff' ? '#4b5563' : 'transparent' }"
          :class="{ 'ring-2 ring-white scale-110': color === c }"
          @click="color = c"
        />
      </div>
      <div class="w-px h-5 bg-gray-700" />
      <div class="flex gap-0.5">
        <button
          v-for="s in brushSizes"
          :key="s"
          class="w-5 h-5 rounded flex items-center justify-center text-xs transition-all"
          :class="brushSize === s ? 'bg-gray-600 text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="brushSize = s"
        >
          <div
            class="rounded-full bg-current"
            :style="{ width: `${Math.min(s * 2, 14)}px`, height: `${Math.min(s * 2, 14)}px` }"
          />
        </button>
      </div>
      <div class="w-px h-5 bg-gray-700" />
      <button class="art-btn-sm text-gray-400 hover:text-white" title="清空" @click="clearCanvas">
        清空
      </button>
      <button class="art-btn-sm text-blue-400 hover:text-blue-300" title="保存" @click="saveImage">
        保存
      </button>
      <button class="art-btn-sm text-green-400 hover:text-green-300" title="下载" @click="downloadImage">
        导出
      </button>
      <div class="flex-1" />
      <button class="art-btn-sm text-gray-400 hover:text-red-400" @click="emit('close')">
        关闭
      </button>
    </div>

    <!-- Canvas -->
    <div class="flex-1 relative bg-[#1a1f2e] overflow-hidden">
      <canvas
        ref="canvasRef"
        class="absolute inset-0 cursor-crosshair"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
      />
      <div
        v-if="!bgLoaded && referenceImage"
        class="absolute inset-0 flex items-center justify-center text-xs text-gray-500"
      >
        加载参考图...
      </div>
    </div>
  </div>
</template>
