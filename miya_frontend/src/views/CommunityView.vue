<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// 佳与弥娅的社区网站
const COMMUNITY_URL = 'https://jiaandmiya.com'

// Electron 桌面版：用 webview 内嵌展示网站（不受 X-Frame-Options 限制）
// Web 版（浏览器）：展示落地页 + 打开按钮
const isElectron = typeof window !== 'undefined' && 'electronAPI' in window

const webviewRef = ref<HTMLElement | null>(null)
const statusText = ref('● 连接中...')
const loadFailed = ref(false)

function goHome() {
  router.push('/')
}

function openInBrowser() {
  // Electron 中由主进程 setWindowOpenHandler 接管 → 系统浏览器
  // Web 版直接新标签页打开
  window.open(COMMUNITY_URL, '_blank')
}

function reloadPage() {
  const wv = webviewRef.value as any
  if (wv && typeof wv.reload === 'function') {
    statusText.value = '● 刷新中...'
    wv.reload()
  }
}

function onDidFinishLoad() {
  loadFailed.value = false
  statusText.value = '● 已连接'
}

function onDidFailLoad(e: any) {
  // -3 = ERR_ABORTED（页面被刷新打断），忽略
  if (e?.errorCode === -3)
    return
  loadFailed.value = true
  statusText.value = '● 页面加载失败'
}

function onNewWindow(e: any) {
  // 站内新窗口请求统一交给系统浏览器打开
  e.preventDefault()
  if (e?.url) {
    window.open(e.url, '_blank')
  }
}
</script>

<template>
  <div class="community-view">
    <div class="cv-header">
      <div class="cv-header-left">
        <button class="cv-back-btn" title="返回主页" @click="goHome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        </button>
        <span class="cv-header-icon">✧</span>
        <span class="cv-header-title">弥娅社区</span>
        <span class="cv-header-sub">jiaandmiya.com</span>
        <span v-if="isElectron" class="cv-status" :class="{ running: statusText.includes('已连接'), error: loadFailed }">
          <span class="cv-status-dot" />{{ statusText }}
        </span>
      </div>
      <div class="cv-header-right">
        <button v-if="isElectron" class="cv-hdr-btn" title="刷新页面" @click="reloadPage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><path d="M1 4v6h6M23 20v-6h-6" /><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" /></svg>
        </button>
        <button class="cv-hdr-btn" title="在浏览器中打开" @click="openInBrowser">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" /><path d="M15 3h6v6M10 14L21 3" /></svg>
        </button>
      </div>
    </div>

    <div class="cv-container">
      <webview
        v-if="isElectron"
        ref="webviewRef"
        :src="COMMUNITY_URL"
        class="cv-webview"
        allowpopups
        @did-finish-load="onDidFinishLoad"
        @did-fail-load="onDidFailLoad"
        @new-window="onNewWindow"
      />

      <!-- Web 版落地页（浏览器中无法跨域内嵌，提供打开入口） -->
      <div v-else class="cv-fallback">
        <div class="cv-fallback-card">
          <span class="cv-fallback-icon">✧</span>
          <h1 class="cv-fallback-title">弥娅社区</h1>
          <p class="cv-fallback-sub">佳与弥娅的社区 · 分享技术 · 记录生活</p>
          <p class="cv-fallback-desc">jiaandmiya.com</p>
          <button class="cv-fallback-btn" @click="openInBrowser">
            打开弥娅社区
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" /><path d="M15 3h6v6M10 14L21 3" /></svg>
          </button>
          <p class="cv-fallback-hint">桌面版弥娅可直接在应用内浏览社区</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.community-view {
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
.cv-header {
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
.cv-header:hover {
  border-color: rgba(0, 255, 245, 0.2);
  box-shadow:
    3px 3px 12px rgba(0, 40, 50, 0.4),
    -2px -2px 8px rgba(0, 180, 200, 0.06);
}

.cv-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.cv-back-btn {
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
.cv-back-btn:hover {
  background: rgba(0, 173, 181, 0.1);
  border-color: rgba(0, 255, 245, 0.3);
  color: rgba(0, 255, 245, 0.8);
  transform: skewX(-4deg);
}

.cv-header-icon {
  color: var(--miya-primary, #00ADB5);
  font-size: 0.9rem;
  display: flex;
}

.cv-header-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.8rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.05em;
}

.cv-header-sub {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: rgba(0, 173, 181, 0.3);
}

.cv-status {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.58rem;
  color: rgba(200, 200, 200, 0.4);
}

.cv-status-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(0, 173, 181, 0.15);
  flex-shrink: 0;
}

.cv-status.running .cv-status-dot {
  background: rgba(34, 211, 238, 0.6);
  box-shadow: 0 0 6px rgba(34, 211, 238, 0.4);
  animation: cv-dot-breath 2s ease-in-out infinite;
}

.cv-status.error .cv-status-dot {
  background: rgba(248, 113, 113, 0.6);
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.4);
}

@keyframes cv-dot-breath {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.cv-header-right {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.cv-hdr-btn {
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
.cv-hdr-btn:hover {
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 255, 245, 0.25);
  color: rgba(255, 255, 255, 0.85);
  transform: skewX(-4deg);
}

/* ── Container ── */
.cv-container {
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
.cv-container:focus-within {
  border-color: rgba(0, 255, 245, 0.15);
}

.cv-webview {
  width: 100%;
  height: 100%;
  border: none;
  display: flex;
}

/* ── Web 版落地页 ── */
.cv-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: rgba(0, 0, 0, 0.25);
}

.cv-fallback-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 2.5rem 3rem;
  border: 1px solid rgba(0, 173, 181, 0.1);
  border-radius: 10px;
  background: rgba(20, 14, 6, 0.6);
  box-shadow: 0 0 40px rgba(212, 175, 55, 0.05);
}

.cv-fallback-icon {
  font-size: 2rem;
  color: var(--miya-accent, #00FFF5);
}

.cv-fallback-title {
  margin: 0;
  font-family: 'Noto Serif SC', serif;
  font-size: 1.3rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.08em;
}

.cv-fallback-sub {
  margin: 0;
  font-size: 0.7rem;
  color: var(--miya-text-dim);
}

.cv-fallback-desc {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  color: rgba(0, 173, 181, 0.4);
}

.cv-fallback-btn {
  margin-top: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 1.6rem;
  border-radius: 6px;
  border: 1px solid rgba(0, 173, 181, 0.25);
  background: rgba(0, 173, 181, 0.12);
  color: rgba(0, 255, 245, 0.85);
  font-size: 0.78rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.cv-fallback-btn:hover {
  background: rgba(129, 191, 241, 0.14);
  border-color: rgba(0, 255, 245, 0.4);
  transform: skewX(-3deg);
  box-shadow: 0 0 14px rgba(0, 173, 181, 0.12);
}

.cv-fallback-hint {
  margin: 0;
  font-size: 0.58rem;
  color: rgba(200, 200, 200, 0.3);
}
</style>
