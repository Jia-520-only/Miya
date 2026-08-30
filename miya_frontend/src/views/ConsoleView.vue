<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { getManagementPort } from '@/utils/api-port'

interface LogEntry {
  seq: number
  ts: string
  level: string
  name: string
  text: string
}

const MAX_LINES = 3000
const managementPort = computed(getManagementPort)

const lines = ref<LogEntry[]>([])
const totalReceived = ref(0)
const sseStatus = ref<'connecting' | 'open' | 'reconnecting'>('connecting')
const levelFilter = ref<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL')
const keyword = ref('')
const autoScroll = ref(true)
const terminalEl = ref<HTMLElement | null>(null)

let lastSeq = 0
let es: EventSource | null = null
let disposed = false
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

const levelFilters: Array<{ id: 'ALL' | 'INFO' | 'WARNING' | 'ERROR', label: string }> = [
  { id: 'ALL', label: '全部' },
  { id: 'INFO', label: 'INFO' },
  { id: 'WARNING', label: '警告' },
  { id: 'ERROR', label: '错误' },
]

const sseLabel = computed(() => {
  if (sseStatus.value === 'open') return 'SSE'
  if (sseStatus.value === 'connecting') return 'SSE 连接中'
  return 'SSE-OFF'
})

const filteredLines = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return lines.value.filter((l) => {
    if (levelFilter.value === 'WARNING' && !l.level.startsWith('WARNING'))
      return false
    if (levelFilter.value === 'ERROR' && !['ERROR', 'CRITICAL'].includes(l.level))
      return false
    if (kw && !l.text.toLowerCase().includes(kw) && !l.name.toLowerCase().includes(kw))
      return false
    return true
  })
})

function levelClass(level: string) {
  if (level === 'WARNING') return 'lv-warn'
  if (level === 'ERROR' || level === 'CRITICAL') return 'lv-error'
  if (level === 'DEBUG') return 'lv-debug'
  if (level === 'INFO') return 'lv-info'
  return 'lv-plain'
}

function formatTime(ts: string) {
  // ISO 时间取 HH:MM:SS 部分
  const m = ts.match(/T(\d{2}:\d{2}:\d{2})/)
  return m ? m[1] : ts
}

function pushEntries(entries: LogEntry[]) {
  if (!entries.length) return
  totalReceived.value += entries.length
  for (const e of entries) {
    if (e.seq > lastSeq) lastSeq = e.seq
  }
  lines.value.push(...entries)
  if (lines.value.length > MAX_LINES)
    lines.value.splice(0, lines.value.length - MAX_LINES)
}

function handlePayload(payload: any) {
  if (payload.type === 'init' || payload.type === 'reset') {
    if (payload.type === 'reset') lines.value = []
    pushEntries(payload.entries || [])
  }
  else if (payload.type === 'logs') {
    pushEntries(payload.entries || [])
  }
}

function connect() {
  if (disposed) return
  es?.close()
  const url = `http://localhost:${getManagementPort()}/api/v1/logs/stream`
    + (lastSeq > 0 ? `?since=${lastSeq}` : '')
  sseStatus.value = lastSeq > 0 ? 'reconnecting' : 'connecting'
  es = new EventSource(url)
  es.onopen = () => {
    sseStatus.value = 'open'
  }
  es.onmessage = (ev) => {
    try {
      handlePayload(JSON.parse(ev.data))
    }
    catch {}
  }
  es.onerror = () => {
    es?.close()
    es = null
    if (disposed) return
    sseStatus.value = 'reconnecting'
    reconnectTimer = setTimeout(connect, 2000)
  }
}

function onScroll() {
  const el = terminalEl.value
  if (!el) return
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function scrollToBottom() {
  const el = terminalEl.value
  if (el) el.scrollTop = el.scrollHeight
}

function clearLines() {
  lines.value = []
}

function exportLogs() {
  const text = filteredLines.value
    .map(l => `${formatTime(l.ts)} ${l.text}`)
    .join('\n')
  const blob = new Blob([text || ''], { type: 'text/plain;charset=utf-8' })
  const a = document.createElement('a')
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  a.href = URL.createObjectURL(blob)
  a.download = `miya-console-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`
  a.click()
  URL.revokeObjectURL(a.href)
}

watch(() => lines.value.length, () => {
  if (autoScroll.value) nextTick(scrollToBottom)
})

onMounted(connect)

onUnmounted(() => {
  disposed = true
  if (reconnectTimer) clearTimeout(reconnectTimer)
  es?.close()
  es = null
})
</script>

<template>
  <div class="console-view">
    <!-- 顶栏 -->
    <div class="cv-header">
      <div class="cv-header-left">
        <span class="cv-title">▤ 后台终端</span>
        <span class="cv-sub">
          <span class="cv-sse-dot" :class="sseStatus" />
          {{ sseLabel }}
        </span>
      </div>
      <div class="cv-header-right">
        <div class="cv-level-filter">
          <button
            v-for="f in levelFilters"
            :key="f.id"
            class="cv-filter-btn"
            :class="[`f-${f.id.toLowerCase()}`, { active: levelFilter === f.id }]"
            @click="levelFilter = f.id"
          >
            {{ f.label }}
          </button>
        </div>
        <input
          v-model="keyword"
          class="cv-search"
          type="text"
          placeholder="过滤关键词..."
          spellcheck="false"
        >
        <button class="cv-btn" :class="{ active: autoScroll }" @click="autoScroll = !autoScroll">
          {{ autoScroll ? '⏸ 暂停滚动' : '▶ 自动滚动' }}
        </button>
        <button class="cv-btn" @click="clearLines">
          清屏
        </button>
        <button class="cv-btn" @click="exportLogs">
          导出
        </button>
      </div>
    </div>

    <!-- 终端主体 -->
    <div ref="terminalEl" class="cv-terminal" @scroll="onScroll">
      <div v-if="filteredLines.length === 0" class="cv-empty">
        <span class="cv-empty-icon">▤</span>
        <span class="cv-empty-text">{{ sseStatus === 'open' ? '等待日志输出...' : '等待守护进程日志流...' }}</span>
      </div>
      <div v-for="l in filteredLines" :key="l.seq" class="cv-line" :class="levelClass(l.level)">
        <span class="cv-time">{{ formatTime(l.ts) }}</span>
        <span class="cv-text">{{ l.text }}</span>
      </div>
    </div>

    <!-- 底部状态条 -->
    <div class="cv-statusbar">
      <span>已接收 {{ totalReceived }} 条</span>
      <span>显示 {{ filteredLines.length }} 条</span>
      <span v-if="!autoScroll" class="cv-paused">⏸ 已暂停自动滚动</span>
      <span class="cv-grow" />
      <span>daemon console · :{{ managementPort }}</span>
    </div>
  </div>
</template>

<style scoped>
.console-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px;
  height: 100%;
}

.cv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.cv-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cv-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.1rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--miya-chat-ai), var(--miya-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.cv-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: color-mix(in srgb, var(--miya-border) 50%, transparent);
}

.cv-sse-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 100, 100, 0.5);
  transition: all 0.5s;
}

.cv-sse-dot.open {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.cv-sse-dot.connecting,
.cv-sse-dot.reconnecting {
  background: #3b82f6;
  animation: cv-pulse 1.2s infinite;
}

@keyframes cv-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.cv-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cv-level-filter {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid color-mix(in srgb, var(--miya-border) 10%, transparent);
}

.cv-filter-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  padding: 3px 10px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  background: transparent;
  color: color-mix(in srgb, var(--miya-border) 50%, transparent);
  transition: all 0.2s;
}

.cv-filter-btn:hover {
  color: var(--miya-text);
}

.cv-filter-btn.active.f-all { background: rgba(0, 173, 181, 0.12); color: #5eead4; }
.cv-filter-btn.active.f-info { background: rgba(59, 130, 246, 0.12); color: #60a5fa; }
.cv-filter-btn.active.f-warning { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }
.cv-filter-btn.active.f-error { background: rgba(239, 68, 68, 0.12); color: #f87171; }

.cv-search {
  width: 160px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.58rem;
  padding: 5px 10px;
  border-radius: 5px;
  border: 1px solid color-mix(in srgb, var(--miya-border) 15%, transparent);
  background: rgba(0, 0, 0, 0.3);
  color: var(--miya-text);
  outline: none;
  transition: border-color 0.2s;
}

.cv-search:focus {
  border-color: color-mix(in srgb, var(--miya-chat-ai) 40%, transparent);
}

.cv-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  padding: 5px 12px;
  border-radius: 4px;
  border: 1px solid color-mix(in srgb, var(--miya-border) 18%, transparent);
  cursor: pointer;
  background: transparent;
  color: color-mix(in srgb, var(--miya-border) 55%, transparent);
  transition: all 0.2s;
}

.cv-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--miya-text);
}

.cv-btn.active {
  color: #5eead4;
  border-color: color-mix(in srgb, #5eead4 30%, transparent);
}

/* 终端主体 */
.cv-terminal {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--miya-comp-terminal-bg, #0a0a14);
  border: 1px solid color-mix(in srgb, var(--miya-border) 10%, transparent);
  font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
  font-size: 0.62rem;
  line-height: 1.6;
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.3);
}

.cv-terminal::-webkit-scrollbar {
  width: 8px;
}

.cv-terminal::-webkit-scrollbar-track {
  background: transparent;
}

.cv-terminal::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
}

.cv-terminal::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.15);
}

.cv-line {
  display: flex;
  gap: 10px;
  white-space: pre-wrap;
  word-break: break-all;
  content-visibility: auto;
  contain-intrinsic-size: auto 18px;
}

.cv-time {
  flex-shrink: 0;
  color: rgba(148, 163, 184, 0.35);
}

.cv-text {
  color: #d4d4e8;
}

.cv-line.lv-info .cv-text { color: #9db4c8; }
.cv-line.lv-warn .cv-text { color: #fbbf24; }
.cv-line.lv-error .cv-text { color: #f87171; }
.cv-line.lv-error { background: rgba(239, 68, 68, 0.04); }
.cv-line.lv-debug .cv-text { color: #64748b; }

/* 空状态 */
.cv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 80px 0;
  opacity: 0.35;
}

.cv-empty-icon {
  font-size: 1.8rem;
  color: var(--miya-chat-ai);
}

.cv-empty-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}

/* 底部状态条 */
.cv-statusbar {
  display: flex;
  align-items: center;
  gap: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}

.cv-paused {
  color: #fbbf24;
}

.cv-grow {
  flex: 1;
}
</style>
