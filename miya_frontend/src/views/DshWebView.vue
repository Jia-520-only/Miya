<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const statusText = ref('● 就绪')
const dshUrl = ref('')
const loadFailed = ref(false)

async function initWeb() {
  loadFailed.value = false

  const running = await window.electronAPI?.dshWeb.isRunning()
  if (running) {
    const url = await window.electronAPI?.dshWeb.getUrl()
    if (url) {
      dshUrl.value = url
      statusText.value = '● 运行中'
      return
    }
  }

  try {
    statusText.value = '● 启动中...'
    const { url } = await window.electronAPI!.dshWeb.ensure()
    dshUrl.value = url
    statusText.value = '● 运行中'
  }
  catch (err) {
    loadFailed.value = true
    statusText.value = `● 启动失败: ${err}`
  }
}

function goHome() {
  router.push('/')
}

function restartWeb() {
  loadFailed.value = false
  dshUrl.value = ''
  window.electronAPI?.dshWeb.stop()
  setTimeout(() => initWeb(), 400)
}

function openBrowser() {
  window.electronAPI?.dshWeb.openBrowser()
}

function onWebviewFail() {
  loadFailed.value = true
  statusText.value = '● 页面加载失败'
}

onMounted(() => {
  initWeb()
})
</script>

<template>
  <div class="web-view">
    <div class="web-header">
      <div class="web-header-left">
        <button class="web-back-btn" title="返回主页 (进程保持运行)" @click="goHome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        </button>
        <span class="web-header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="15" height="15"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a15 15 0 010 18M12 3a15 15 0 000 18" /></svg>
        </span>
        <span class="web-header-title">DSH · 弥娅网页工作台</span>
        <span class="web-header-ver">deepseek-harness</span>
        <span class="web-status" :class="{ running: statusText.includes('运行'), error: statusText.includes('失败') || loadFailed }">
          <span class="web-status-dot" />{{ statusText }}
        </span>
      </div>
      <div class="web-header-right">
        <button class="web-hdr-btn" title="在浏览器中打开" @click="openBrowser">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" /><path d="M15 3h6v6M10 14L21 3" /></svg>
        </button>
        <button class="web-hdr-btn" title="重启工作台" @click="restartWeb">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><path d="M1 4v6h6M23 20v-6h-6" /><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" /></svg>
        </button>
      </div>
    </div>
    <div class="web-container">
      <webview
        v-if="dshUrl"
        :src="dshUrl"
        class="dsh-webview"
        allowpopups
        @did-fail-load="onWebviewFail"
      />
      <div v-else class="web-placeholder">
        {{ loadFailed ? 'DSH Web 启动失败，请检查 deepseek-harness 是否已构建 (pnpm install && pnpm run build)' : '正在启动弥娅网页工作台…' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.web-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem 1.2rem;
  gap: 0.6rem;
  perspective: 600px;
  -webkit-perspective: 600px;
  overflow: hidden;
}

/* ── Header ── */
.web-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.8rem;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 8px rgba(0, 40, 50, 0.3),
    -2px -2px 6px rgba(0, 180, 200, 0.04);
  flex-shrink: 0;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.web-header:hover {
  border-color: rgba(0, 255, 245, 0.2);
  box-shadow:
    3px 3px 12px rgba(0, 40, 50, 0.4),
    -2px -2px 8px rgba(0, 180, 200, 0.06);
}

.web-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.web-back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(0, 173, 181, 0.1);
  background: rgba(0, 173, 181, 0.04);
  color: rgba(0, 173, 181, 0.5);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.web-back-btn:hover {
  background: rgba(0, 173, 181, 0.1);
  border-color: rgba(0, 255, 245, 0.3);
  color: rgba(0, 255, 245, 0.8);
  transform: skewX(-4deg);
}

.web-header-icon {
  color: var(--miya-primary, #00ADB5);
  display: flex;
}

.web-header-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.8rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.05em;
}

.web-header-ver {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: rgba(0, 173, 181, 0.3);
}

.web-status {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.58rem;
  color: rgba(200, 200, 200, 0.4);
}

.web-status-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(0, 173, 181, 0.15);
  flex-shrink: 0;
}

.web-status.running .web-status-dot {
  background: rgba(34, 211, 238, 0.6);
  box-shadow: 0 0 6px rgba(34, 211, 238, 0.4);
  animation: web-dot-breath 2s ease-in-out infinite;
}

.web-status.error .web-status-dot {
  background: rgba(248, 113, 113, 0.6);
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.4);
}

@keyframes web-dot-breath {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.web-header-right {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.web-hdr-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(0, 173, 181, 0.1);
  background: transparent;
  color: rgba(200, 200, 200, 0.4);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.web-hdr-btn:hover {
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 255, 245, 0.25);
  color: rgba(255, 255, 255, 0.85);
  transform: skewX(-4deg);
}

/* ── Web Container ── */
.web-container {
  flex: 1;
  min-height: 0;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(0, 173, 181, 0.06);
  border-radius: 6px;
  box-shadow:
    3px 3px 10px rgba(0, 40, 50, 0.35),
    -1px -1px 4px rgba(0, 180, 200, 0.04);
  overflow: hidden;
  transition: border-color 0.3s ease;
  backdrop-filter: blur(8px);
}
.web-container:focus-within {
  border-color: rgba(0, 255, 245, 0.15);
}

.dsh-webview {
  width: 100%;
  height: 100%;
  border: none;
  display: flex;
}

.web-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: rgba(200, 200, 200, 0.4);
}
</style>
