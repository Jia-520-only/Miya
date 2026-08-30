<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import API from '@/api/art'
import type { ArtProviderInfo, ArtImageEntry, ArtGenerateResult } from '@/types/art'
import PromptPanel from '@/components/artboard/PromptPanel.vue'
import GallerySidebar from '@/components/artboard/GallerySidebar.vue'
import DoodleCanvas from '@/components/artboard/DoodleCanvas.vue'

const isInArtboardWindow = ref(false)
const showDoodle = ref(false)
const router = useRouter()
const previewImage = ref<ArtImageEntry | null>(null)
const selectedImage = ref<ArtImageEntry | null>(null)
const zoom = ref(1)

const generating = ref(false)
const generateResult = ref<ArtGenerateResult | null>(null)
const error = ref('')

const gallery = ref<ArtImageEntry[]>([])
const showGallery = ref(true)

onMounted(async () => {
  try {
    isInArtboardWindow.value = !!(window as any).__IS_ARTBOARD_WINDOW__
  } catch {}
  await loadGallery()
})

async function loadGallery() {
  try {
    const res = await API.getGallery({ limit: 100 })
    gallery.value = res.images || []
  } catch {}
}

async function handleGenerate(params: {
  prompt: string
  provider: string
  negativePrompt: string
  width: number
  height: number
  steps: number
  cfgScale: number
  seed: number | null
  numImages: number
  style: string
}) {
  generating.value = true
  error.value = ''
  generateResult.value = null

  try {
    const res = await API.generate(params)
    generateResult.value = res

    if (res.success && res.images.length > 0) {
      gallery.value.unshift(...res.images)
      selectImage(res.images[0]!)
    } else {
      error.value = res.error || '生成失败'
    }
  } catch (e: any) {
    error.value = e?.message || '请求失败'
  } finally {
    generating.value = false
  }
}

function selectImage(img: ArtImageEntry) {
  selectedImage.value = img
  zoom.value = 1
}

function deleteImage(img: ArtImageEntry) {
  API.deleteImage(img.id)
  gallery.value = gallery.value.filter(i => i.id !== img.id)
  if (selectedImage.value?.id === img.id) {
    selectedImage.value = null
  }
}

function clearGallery() {
  API.clearGallery()
  gallery.value = []
  selectedImage.value = null
}

function getImageSrc(img: ArtImageEntry): string {
  return API.getImageUrl(img.filename)
}

async function fitCanvas() {
  zoom.value = 1
  await new Promise(r => setTimeout(r, 50))
  const canvas = document.getElementById('art-canvas')?.parentElement
  if (!canvas || !selectedImage.value) return
  const cw = canvas.clientWidth - 40
  const ch = canvas.clientHeight - 40
  const iw = selectedImage.value.width || 1024
  const ih = selectedImage.value.height || 1024
  zoom.value = Math.min(cw / iw, ch / ih, 2)
}

function handleWheel(e: WheelEvent) {
  e.preventDefault()
  zoom.value = Math.max(0.1, Math.min(5, zoom.value - e.deltaY * 0.001))
}
</script>

<template>
  <div class="art-layout">
    <!-- Left Panel: Prompt Input -->
    <div class="art-left">
      <div class="art-left-head">
        <button class="art-back-btn" title="返回" @click="router.push('/')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        </button>
        <span class="art-left-dot" />
        <span class="art-left-title">弥娅画板</span>
        <div class="art-left-actions">
          <button class="art-icon-btn" :class="{ active: showDoodle }" title="涂鸦模式" @click="showDoodle = !showDoodle">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" /></svg>
          </button>
          <button class="art-icon-btn" :class="{ active: !showGallery }" title="切换画廊" @click="showGallery = !showGallery">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></svg>
          </button>
        </div>
      </div>

      <div class="art-left-body">
        <PromptPanel :generating="generating" @generate="handleGenerate" />
      </div>

      <div class="art-left-foot">
        <span>{{ gallery.length }} 张作品</span>
        <button v-if="gallery.length > 0" class="art-clear-btn" title="清空画廊" @click="clearGallery">清空</button>
      </div>
    </div>

    <!-- Center: Canvas / Doodle -->
    <div class="art-center">
      <!-- Toolbar -->
      <div v-if="selectedImage && !showDoodle" class="art-toolbar">
        <button class="art-zoom-btn" @click="zoom = Math.max(0.1, zoom - 0.2)">−</button>
        <span class="art-zoom-label">{{ Math.round(zoom * 100) }}%</span>
        <button class="art-zoom-btn" @click="zoom = Math.min(5, zoom + 0.2)">+</button>
        <button class="art-zoom-btn" @click="fitCanvas">适应</button>
        <button class="art-zoom-btn" @click="zoom = 1">1:1</button>
      </div>

      <div v-if="showDoodle" class="art-canvas-wrap">
        <DoodleCanvas
          :reference-image="selectedImage ? getImageSrc(selectedImage) : ''"
          @close="showDoodle = false"
        />
      </div>

      <div v-else-if="selectedImage" class="art-canvas-wrap" @wheel="handleWheel">
        <div id="art-canvas" class="art-image-stage">
          <img
            :src="getImageSrc(selectedImage)"
            :style="{
              transform: `scale(${zoom})`,
              maxWidth: `${100 / zoom}%`,
              maxHeight: `${100 / zoom}%`,
            }"
            class="art-image"
            draggable="false"
          >
        </div>
        <div class="art-image-info">
          {{ selectedImage.prompt?.slice(0, 100) || '' }}
          <span class="art-image-meta"> · {{ selectedImage.width }}x{{ selectedImage.height }}</span>
          <span v-if="selectedImage.provider" class="art-image-meta"> · {{ selectedImage.provider }}</span>
        </div>
      </div>

      <div v-else-if="generating" class="art-empty">
        <div class="art-spinner" />
        <span>弥娅正在创作中...</span>
      </div>

      <div v-else-if="error" class="art-empty">
        <span class="art-error-text">{{ error }}</span>
        <button class="art-zoom-btn" @click="error = ''">关闭</button>
      </div>

      <div v-else class="art-empty">
        <svg class="art-empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <span>在左侧输入 prompt，让弥娅为你创作</span>
      </div>
    </div>

    <!-- Right Panel: Gallery -->
    <div v-if="showGallery" class="art-right">
      <GallerySidebar
        :images="gallery"
        :selected-id="selectedImage?.id"
        @select="selectImage"
        @delete="deleteImage"
      />
    </div>
  </div>
</template>

<style scoped>
.art-layout {
  height: 100%; display: flex; gap: 0.8rem; padding: 0.8rem 1rem;
  overflow: hidden;
  perspective: 800px;
  -webkit-perspective: 800px;
}

/* ── Left Panel ── */
.art-left {
  width: 260px; flex-shrink: 0; display: flex; flex-direction: column;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 10px rgba(0, 40, 50, 0.35),
    -1px -1px 4px rgba(0, 180, 200, 0.04);
  border-radius: 4px;
  transform: rotateY(5deg);
  transition: transform 0.5s ease;
  overflow: hidden;
}
.art-left:hover { transform: rotateY(3deg); }

.art-left-head {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgba(0, 173, 181, 0.06);
  flex-shrink: 0;
}

.art-back-btn {
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 4px;
  border: 1px solid rgba(0, 173, 181, 0.1);
  background: rgba(0, 173, 181, 0.04);
  color: rgba(0, 173, 181, 0.5); cursor: pointer;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.art-back-btn:hover {
  background: rgba(0, 173, 181, 0.1); border-color: rgba(0, 255, 245, 0.3); color: rgba(0, 255, 245, 0.8);
}

.art-left-dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: rgba(0, 255, 245, 0.6);
  box-shadow: 0 0 6px rgba(0, 255, 245, 0.4);
  animation: art-dot-breath 2s ease-in-out infinite;
}
@keyframes art-dot-breath { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }

.art-left-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.75rem; font-weight: 700; color: #ffffff;
  letter-spacing: 0.04em; flex: 1;
}
.art-left-actions { display: flex; gap: 0.2rem; }

.art-icon-btn {
  display: flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 4px;
  border: 1px solid rgba(0, 173, 181, 0.08);
  background: transparent; color: rgba(200, 200, 200, 0.35);
  cursor: pointer; transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.art-icon-btn:hover, .art-icon-btn.active {
  background: rgba(0, 173, 181, 0.1); border-color: rgba(0, 255, 245, 0.25); color: rgba(0, 255, 245, 0.7);
}
.art-icon-btn:hover { transform: skewX(-4deg); }

.art-left-body {
  flex: 1; overflow-y: auto;
}
.art-left-body::-webkit-scrollbar { width: 3px; }
.art-left-body::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.1); border-radius: 2px; }

.art-left-foot {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.4rem 0.6rem; border-top: 1px solid rgba(0, 173, 181, 0.06);
  font-size: 0.55rem; color: rgba(200, 200, 200, 0.3); flex-shrink: 0;
}

.art-clear-btn {
  background: none; border: none; color: rgba(248, 113, 113, 0.4);
  font-size: 0.55rem; cursor: pointer; transition: color 0.2s;
}
.art-clear-btn:hover { color: rgba(248, 113, 113, 0.8); }

/* ── Center ── */
.art-center {
  flex: 1; min-width: 0; display: flex; flex-direction: column;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 10px rgba(0, 40, 50, 0.35),
    -1px -1px 4px rgba(0, 180, 200, 0.04);
  border-radius: 4px; overflow: hidden;
  backdrop-filter: blur(8px);
}

.art-toolbar {
  display: flex; align-items: center; gap: 0.3rem;
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid rgba(0, 173, 181, 0.06);
  background: rgba(0, 0, 0, 0.3); flex-shrink: 0;
}

.art-zoom-btn {
  padding: 3px 10px; border-radius: 4px; font-size: 0.6rem; cursor: pointer;
  background: transparent; color: rgba(200, 200, 200, 0.4);
  border: 1px solid rgba(0, 173, 181, 0.08);
  font-family: 'JetBrains Mono', monospace;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.art-zoom-btn:hover {
  background: rgba(129, 191, 241, 0.12); color: rgba(255, 255, 255, 0.85);
  border-color: rgba(0, 255, 245, 0.2); transform: skewX(-4deg);
}

.art-zoom-label {
  font-family: 'JetBrains Mono', monospace; font-size: 0.58rem;
  color: rgba(0, 173, 181, 0.4); min-width: 40px; text-align: center;
}

.art-canvas-wrap {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 0; overflow: auto; padding: 0.6rem;
}

.art-image-stage {
  flex: 1; display: flex; align-items: center; justify-content: center;
  min-height: 0; width: 100%;
}

.art-image {
  border-radius: 4px;
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.5);
  transition: transform 0.15s ease; object-fit: contain;
}

.art-image-info {
  font-size: 0.58rem; color: rgba(200, 200, 200, 0.4);
  margin-top: 0.4rem; text-align: center; flex-shrink: 0; padding: 0 1rem;
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.art-image-meta { color: rgba(0, 173, 181, 0.25); }

/* ── Empty / Loading ── */
.art-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 0.8rem; color: rgba(200, 200, 200, 0.2);
}

.art-empty-icon { width: 3rem; height: 3rem; opacity: 0.15; }

.art-error-text { color: rgba(248, 113, 113, 0.6); font-size: 0.75rem; }

.art-spinner {
  width: 36px; height: 36px; border: 2px solid rgba(0, 173, 181, 0.15);
  border-top-color: rgba(0, 173, 181, 0.8); border-radius: 50%;
  animation: art-spin 0.8s linear infinite;
}
@keyframes art-spin { to { transform: rotate(360deg); } }

/* ── Right Panel ── */
.art-right {
  width: 220px; flex-shrink: 0;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 10px rgba(0, 40, 50, 0.35),
    -1px -1px 4px rgba(0, 180, 200, 0.04);
  border-radius: 4px;
  transform: rotateY(-5deg);
  transition: transform 0.5s ease;
  overflow: hidden;
}
.art-right:hover { transform: rotateY(-3deg); }

/* Override PromptPanel inner styles */
:deep(.art-input) {
  background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(0, 173, 181, 0.08);
  border-radius: 4px; color: rgba(228, 236, 240, 0.88); font-size: 0.72rem;
  outline: none; transition: border-color 0.2s;
}
:deep(.art-input:focus) { border-color: rgba(0, 255, 245, 0.25); }
:deep(.art-input::placeholder) { color: rgba(0, 173, 181, 0.3); }

:deep(.art-select) {
  background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(0, 173, 181, 0.08);
  border-radius: 4px; color: rgba(228, 236, 240, 0.88); font-size: 0.72rem; outline: none; cursor: pointer;
}

:deep(label) {
  color: rgba(228, 236, 240, 0.65) !important; font-size: 0.62rem !important; font-weight: 500;
}

:deep(.bg-gray-800) { background: rgba(0, 0, 0, 0.45) !important; }
:deep(.bg-gray-700) { background: rgba(0, 173, 181, 0.12) !important; }
:deep(.bg-blue-600) { background: rgba(0, 173, 181, 0.2) !important; }
:deep(.text-gray-400) { color: rgba(228, 236, 240, 0.6) !important; }
:deep(.text-white) { color: rgba(0, 255, 245, 0.85) !important; }
:deep(.text-gray-500) { color: rgba(228, 236, 240, 0.65) !important; }
:deep(.text-gray-300) { color: rgba(0, 255, 245, 0.7) !important; }
:deep(.text-gray-600) { color: rgba(228, 236, 240, 0.3) !important; }
:deep(.border-gray-800) { border-color: rgba(0, 173, 181, 0.06) !important; }
:deep(.border-blue-500) { border-color: rgba(0, 255, 245, 0.3) !important; }
:deep(.border-gray-600) { border-color: rgba(0, 173, 181, 0.12) !important; }
:deep(.accent-blue-500) { accent-color: #00ADB5; }
:deep(.bg-blue-600.text-white) { background: rgba(0, 173, 181, 0.2) !important; color: rgba(0, 255, 245, 0.8) !important; }
:deep(.hover\:bg-blue-500:hover) { background: rgba(0, 173, 181, 0.25) !important; }
:deep(.bg-gray-700.text-gray-400) { cursor: wait !important; }
:deep(.border-b.border-gray-800) { border-color: rgba(0, 173, 181, 0.06) !important; }
:deep(.from-black\/80) { --tw-gradient-from: rgba(0, 0, 0, 0.7); }
:deep(.bg-red-600\/80) { background: rgba(248, 113, 113, 0.6) !important; }
:deep(.border-transparent) { border-color: transparent !important; }
:deep(.p-3.space-y-3) { padding: 0.5rem 0.6rem !important; }
:deep(.h-24) { height: 5rem !important; }
</style>
