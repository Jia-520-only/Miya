<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import API from '@/api/core'
import { useCameraVision } from '@/utils/cameraVision'

const backendOnline = ref(false)
const miyaPersona = ref('默认')
const currentTime = ref('')
const cameraMode = ref(localStorage.getItem('miya-camera-mode') || 'off')
const cameraHeartbeat = ref(Number(localStorage.getItem('miya-camera-heartbeat') || 0))
let timer: ReturnType<typeof setInterval> | null = null
const router = useRouter()
const cameraVision = useCameraVision()

const companionActive = computed(() => cameraMode.value === 'companion' && Date.now() - cameraHeartbeat.value < 35_000)

async function fetchStatus() {
  try {
    const health = await API.health()
    backendOnline.value = health.status === 'healthy'
    const persona = await API.getCurrentPersona()
    miyaPersona.value = persona?.persona?.name || persona?.persona?.id || '默认'
  } catch {
    backendOnline.value = false
  }
}

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function updateCameraState() {
  cameraMode.value = localStorage.getItem('miya-camera-mode') || 'off'
  cameraHeartbeat.value = Number(localStorage.getItem('miya-camera-heartbeat') || 0)
}

function handleCameraState(event: Event) {
  const detail = (event as CustomEvent).detail || {}
  cameraMode.value = detail.mode || 'off'
  cameraHeartbeat.value = Date.now()
}

onMounted(() => {
  fetchStatus()
  updateTime()
  updateCameraState()
  window.addEventListener('miya-camera-state', handleCameraState)
  timer = setInterval(() => {
    updateTime()
    updateCameraState()
    fetchStatus()
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('miya-camera-state', handleCameraState)
})

const showStatus = useStorage('miya-show-status', true)
</script>

<template>
  <header v-if="showStatus" class="top-bar">
    <div class="top-left">
      <span class="top-dot" :class="{ online: backendOnline }" />
      <span class="top-brand">MIYA</span>
      <span class="top-sep">·</span>
      <span class="top-persona">{{ miyaPersona }}</span>
    </div>
    <div class="top-right">
      <button v-if="companionActive" class="camera-status" title="打开弥娅视觉" @click="router.push('/screen')">
        <span class="camera-status-dot" />陪伴视觉
      </button>
      <button v-if="companionActive" class="camera-stop" title="立即关闭摄像头" aria-label="立即关闭摄像头" @click="cameraVision.stop()">
        ×
      </button>
      <span class="top-time">{{ currentTime }}</span>
    </div>
  </header>
</template>

<style scoped>
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--miya-shell-status);
  min-height: var(--miya-shell-status);
  padding: 0 var(--miya-space-4) 0 calc(var(--miya-shell-nav) + var(--miya-space-4));
  background: rgba(7, 11, 18, 0.68);
  border-bottom: 1px solid var(--miya-line-soft);
  backdrop-filter: blur(18px);
  z-index: 60;
  user-select: none;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.top-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--miya-danger);
  transition: all 0.5s ease;
}

.top-dot.online {
  background: var(--miya-success);
  box-shadow: 0 0 8px rgba(114, 214, 177, 0.35);
}

.top-brand {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.7rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--miya-chat-ai), var(--miya-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.top-sep {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: var(--miya-line-strong);
}

.top-persona {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.52rem;
  color: var(--miya-text-muted);
  letter-spacing: 0.04em;
}

.top-right {
  display: flex;
  align-items: center;
}

.top-time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--miya-text-muted);
}

.camera-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-right: 10px;
  padding: 3px 6px;
  border: 1px solid rgba(255, 112, 110, 0.28);
  border-radius: 3px;
  background: rgba(255, 112, 110, 0.08);
  color: rgba(255, 190, 185, 0.8);
  cursor: pointer;
  font: .5rem 'JetBrains Mono', monospace;
}

.camera-status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #ff706e;
  box-shadow: 0 0 7px rgba(255, 92, 92, .75);
}

.camera-stop {
  width: 18px;
  height: 18px;
  margin-right: 8px;
  border: 1px solid rgba(255, 112, 110, .32);
  border-radius: 3px;
  background: rgba(255, 112, 110, .1);
  color: rgba(255, 190, 185, .85);
  cursor: pointer;
  font-size: .8rem;
  line-height: 1;
}
</style>
