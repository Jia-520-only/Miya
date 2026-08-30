<script setup lang="ts">
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { onMounted, onUnmounted, ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'

type TermMode = 'tui' | 'web'

const router = useRouter()
const mode = ref<TermMode>('tui')
const terminalEl = ref<HTMLDivElement>()
const statusText = ref('● 就绪')
const exitCode = ref<number | null>(null)
const dshUrl = ref('')
const loadFailed = ref(false)

let term: Terminal | null = null
let fitAddon: FitAddon | null = null
let unsubscribeData: (() => void) | null = null
let unsubscribeExit: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null

function buildXtermTheme() {
  const root = getComputedStyle(document.documentElement)
  const c = (v: string, d: string) => root.getPropertyValue(v).trim() || d
  return {
    background: c('--miya-comp-terminal-bg', '#0a0a14'),
    foreground: c('--miya-comp-terminal-fg', '#d4d4e8'),
    cursor: c('--miya-comp-terminal-cursor', '#00ADB5'),
    cursorAccent: '#0a0a14',
    selectionBackground: c('--miya-comp-terminal-selection', '#00ADB544'),
    black: c('--miya-comp-terminal-black', '#1a1a2e'),
    red: c('--miya-comp-terminal-red', '#f87171'),
    green: c('--miya-comp-terminal-green', '#34d399'),
    yellow: c('--miya-comp-terminal-yellow', '#fbbf24'),
    blue: c('--miya-comp-terminal-blue', '#818cf8'),
    magenta: c('--miya-comp-terminal-magenta', '#c084fc'),
    cyan: c('--miya-comp-terminal-cyan', '#22d3ee'),
    white: c('--miya-comp-terminal-white', '#e2e8f0'),
    brightBlack: c('--miya-comp-terminal-bright-black', '#334155'),
    brightRed: c('--miya-comp-terminal-bright-red', '#fca5a5'),
    brightGreen: c('--miya-comp-terminal-bright-green', '#6ee7b7'),
    brightYellow: c('--miya-comp-terminal-bright-yellow', '#fde68a'),
    brightBlue: c('--miya-comp-terminal-bright-blue', '#a5b4fc'),
    brightMagenta: c('--miya-comp-terminal-bright-magenta', '#d8b4fe'),
    brightCyan: c('--miya-comp-terminal-bright-cyan', '#67e8f9'),
    brightWhite: c('--miya-comp-terminal-bright-white', '#f8fafc'),
  }
}

function startResizeObserver() {
  if (!terminalEl.value || !term) return
  resizeTimer = null
  resizeObserver = new ResizeObserver(() => {
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      try {
        fitAddon?.fit()
        if (term) {
          window.electronAPI?.terminal.resize(term.cols, term.rows)
        }
      }
      catch (_) { /* ignore */ }
    }, 100)
  })
  resizeObserver.observe(terminalEl.value)
}

function createXterm(): boolean {
  if (!terminalEl.value) return false
  if (term) return true

  term = new Terminal({
    theme: buildXtermTheme(),
    fontSize: 14,
    fontFamily: "'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    cursorBlink: true,
    cursorStyle: 'bar',
    allowProposedApi: true,
    disableStdin: false,
    rows: 40,
    cols: 120,
  })

  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(terminalEl.value)

  startResizeObserver()

  term.onData((data: string) => {
    window.electronAPI?.terminal.write(data)
  })

  return true
}

function attachToRunning() {
  unsubscribeData = window.electronAPI?.terminal.onData((data: string) => {
    term?.write(data)
  }) ?? null

  unsubscribeExit = window.electronAPI?.terminal.onExit((code: number) => {
    exitCode.value = code
    loadFailed.value = code !== 0
    statusText.value = code === 0 ? '● 已退出' : `● 退出 (code ${code})`
    if (mode.value === 'tui' && term) {
      term.write(`\r\n\x1b[33m── 终端会话结束 (exit code: ${code}) ──\x1b[0m\r\n`)
    }
  }) ?? null
}

function detachFromRunning() {
  unsubscribeData?.()
  unsubscribeExit?.()
  unsubscribeData = null
  unsubscribeExit = null
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeObserver?.disconnect()
  resizeObserver = null
}

function destroyXterm() {
  detachFromRunning()
  term?.dispose()
  term = null
  fitAddon = null
}

async function startTui() {
  statusText.value = '● 启动中...'
  attachToRunning()
  try {
    const result = await window.electronAPI!.terminal.start({ mode: 'tui' })
    dshUrl.value = result.url
    statusText.value = '● 运行中'
    if (createXterm()) {
      nextTick(() => {
        try { fitAddon?.fit() } catch (_) { /* ignore */ }
      })
    }
  }
  catch (err) {
    loadFailed.value = true
    statusText.value = `● 启动失败: ${err}`
    if (term) term.write(`\r\n\x1b[31m启动失败: ${err}\x1b[0m\r\n`)
  }
}

async function initTerminal() {
  loadFailed.value = false

  if (mode.value === 'tui') {
    // TUI 是否存活以 pty 为准（host 可能被 Web 板块先行启动）
    const tuiRunning = await window.electronAPI?.terminal.isTuiRunning()
    if (tuiRunning) {
      if (createXterm()) {
        attachToRunning()
        statusText.value = '● 运行中'
        nextTick(() => {
          try {
            fitAddon?.fit()
            if (term) window.electronAPI?.terminal.resize(term.cols, term.rows)
          } catch (_) { /* ignore */ }
        })
        const buffer = await window.electronAPI?.terminal.getBuffer()
        if (buffer) term?.write(buffer)
      }
    }
    else {
      await startTui()
    }
  }
  else {
    // web 模式：复用 host（不打断 TUI）
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
}

async function switchMode(target: TermMode) {
  if (target === mode.value) return
  mode.value = target

  if (target === 'web') {
    destroyXterm()
    await initTerminal()
  }
  else {
    dshUrl.value = ''
    exitCode.value = null
    loadFailed.value = false
    await initTerminal()
  }
}

function goHome() {
  detachFromRunning()
  term?.dispose()
  term = null
  fitAddon = null
  router.push('/')
}

function restartTerminal() {
  exitCode.value = null
  loadFailed.value = false
  dshUrl.value = ''
  if (mode.value === 'tui') {
    window.electronAPI?.terminal.stop()
  }
  else {
    window.electronAPI?.dshWeb.stop()
  }
  destroyXterm()
  nextTick(() => initTerminal())
}

function onWebviewFail() {
  loadFailed.value = true
  statusText.value = '● 页面加载失败'
}

onMounted(() => {
  nextTick(() => initTerminal())
})

onUnmounted(() => {
  destroyXterm()
})
</script>

<template>
  <div class="terminal-view">
    <div class="term-header">
      <div class="term-header-left">
        <button class="term-back-btn" title="返回主页 (进程保持运行)" @click="goHome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        </button>
        <span class="term-header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="15" height="15"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M12 8v8M8 12h8" /></svg>
        </span>
        <span class="term-header-title">DSH · 弥娅终端</span>
        <span class="term-header-ver">dsh-tui</span>
        <span class="term-status" :class="{ running: statusText.includes('运行'), error: statusText.includes('失败') || loadFailed, exited: statusText.includes('退出') }">
          <span class="term-status-dot" />{{ statusText }}
        </span>
      </div>
      <div class="term-header-right">
        <button class="term-mode-btn" :class="{ active: mode === 'tui' }" title="终端模式 (dsh-tui)" @click="switchMode('tui')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><path d="M4 17l6-5-6-5M12 19h8" /></svg>
          TUI
        </button>
        <button class="term-mode-btn" :class="{ active: mode === 'web' }" title="网页模式 (DSH Web UI)" @click="switchMode('web')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a15 15 0 010 18M12 3a15 15 0 000 18" /></svg>
          Web
        </button>
        <button class="term-hdr-btn" title="重启终端" @click="restartTerminal">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="13" height="13"><path d="M1 4v6h6M23 20v-6h-6" /><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" /></svg>
        </button>
      </div>
    </div>

    <div v-show="mode === 'tui'" ref="terminalEl" class="terminal-container" />
    <div v-show="mode === 'web'" class="terminal-container">
      <webview
        v-if="dshUrl"
        :src="dshUrl"
        class="dsh-webview"
        allowpopups
        @did-fail-load="onWebviewFail"
      />
      <div v-else class="terminal-placeholder">
        {{ loadFailed ? 'DSH Web 启动失败，请检查 deepseek-harness 是否已构建 (pnpm install && pnpm run build)' : '正在启动弥娅之手…' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.terminal-view {
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
.term-header {
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
.term-header:hover {
  border-color: rgba(0, 255, 245, 0.2);
  box-shadow:
    3px 3px 12px rgba(0, 40, 50, 0.4),
    -2px -2px 8px rgba(0, 180, 200, 0.06);
}

.term-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.term-back-btn {
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
.term-back-btn:hover {
  background: rgba(0, 173, 181, 0.1);
  border-color: rgba(0, 255, 245, 0.3);
  color: rgba(0, 255, 245, 0.8);
  transform: skewX(-4deg);
}

.term-header-icon {
  color: var(--miya-primary, #00ADB5);
  display: flex;
}

.term-header-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.8rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.05em;
}

.term-header-ver {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: rgba(0, 173, 181, 0.3);
}

.term-status {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.58rem;
  color: rgba(200, 200, 200, 0.4);
}

.term-status-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(0, 173, 181, 0.15);
  flex-shrink: 0;
}

.term-status.running .term-status-dot {
  background: rgba(34, 211, 238, 0.6);
  box-shadow: 0 0 6px rgba(34, 211, 238, 0.4);
  animation: term-dot-breath 2s ease-in-out infinite;
}

.term-status.error .term-status-dot {
  background: rgba(248, 113, 113, 0.6);
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.4);
}

.term-status.exited .term-status-dot {
  background: rgba(251, 191, 36, 0.6);
  box-shadow: 0 0 6px rgba(251, 191, 36, 0.4);
}

@keyframes term-dot-breath {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.term-header-right {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.term-mode-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  height: 28px;
  padding: 0 0.6rem;
  border-radius: 6px;
  border: 1px solid rgba(0, 173, 181, 0.1);
  background: transparent;
  color: rgba(200, 200, 200, 0.4);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.term-mode-btn:hover {
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 255, 245, 0.25);
  color: rgba(255, 255, 255, 0.85);
}
.term-mode-btn.active {
  background: rgba(0, 173, 181, 0.12);
  border-color: rgba(0, 255, 245, 0.35);
  color: rgba(0, 255, 245, 0.9);
}

.term-hdr-btn {
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
.term-hdr-btn:hover {
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 255, 245, 0.25);
  color: rgba(255, 255, 255, 0.85);
  transform: skewX(-4deg);
}

/* ── Terminal Container ── */
.terminal-container {
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
.terminal-container:focus-within {
  border-color: rgba(0, 255, 245, 0.15);
}

.dsh-webview {
  width: 100%;
  height: 100%;
  border: none;
  display: flex;
}

.terminal-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: rgba(200, 200, 200, 0.4);
}

:deep(.xterm) {
  width: 100%;
  height: 100%;
  padding: 6px 8px;
}

:deep(.xterm-screen) {
  width: 100% !important;
  height: 100% !important;
}

:deep(.xterm-viewport) {
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 173, 181, 0.12) transparent;
}

:deep(.xterm-viewport::-webkit-scrollbar) {
  width: 4px;
}

:deep(.xterm-viewport::-webkit-scrollbar-track) {
  background: transparent;
}

:deep(.xterm-viewport::-webkit-scrollbar-thumb) {
  background: rgba(0, 173, 181, 0.12);
  border-radius: 2px;
}

:deep(.xterm-viewport::-webkit-scrollbar-thumb:hover) {
  background: rgba(0, 173, 181, 0.25);
}
</style>
