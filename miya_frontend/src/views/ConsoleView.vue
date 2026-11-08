<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { getManagementPort } from '@/utils/api-port'

interface LogEntry {
  seq: number
  ts: string
  level: string
  name: string
  text: string
  source?: 'backend' | 'frontend'
}

type LogSource = 'backend' | 'frontend'
type SourceFilter = LogSource | 'all'

const MAX_LINES = 3000
const managementPort = computed(getManagementPort)

const lines = ref<LogEntry[]>([])
const totalReceived = ref(0)
const sseStatus = ref<'connecting' | 'open' | 'reconnecting'>('connecting')
const levelFilter = ref<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL')
const sourceFilter = ref<SourceFilter>('backend')
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

const sources: Array<{ id: SourceFilter, label: string, icon: string, description: string }> = [
  { id: 'backend', label: '后端日志', icon: 'BE', description: '核心运行、AI 处理与平台服务' },
  { id: 'frontend', label: '前端日志', icon: 'FE', description: '桌面接口请求与连接状态' },
  { id: 'all', label: '全部日志', icon: 'ALL', description: '按时间查看前后端的完整记录' },
]

function logSource(entry: LogEntry): LogSource {
  return entry.source ?? (entry.name === 'Miya.DesktopFrontend' ? 'frontend' : 'backend')
}

const selectedSource = computed(() => sources.find(source => source.id === sourceFilter.value)!)
const sourceCounts = computed(() => {
  const counts = { backend: 0, frontend: 0, all: lines.value.length }
  for (const entry of lines.value) counts[logSource(entry)]++
  return counts
})
const sourceLines = computed(() => sourceFilter.value === 'all'
  ? lines.value
  : lines.value.filter(entry => logSource(entry) === sourceFilter.value))

const sseLabel = computed(() => {
  if (sseStatus.value === 'open') return 'SSE'
  if (sseStatus.value === 'connecting') return 'SSE 连接中'
  return 'SSE-OFF'
})

const filteredLines = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return sourceLines.value.filter((l) => {
    if (levelFilter.value === 'INFO' && l.level !== 'INFO')
      return false
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
    lines.value = []
    lastSeq = 0
    pushEntries(payload.entries || [])
    lastSeq = payload.latest_seq ?? lastSeq
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
  lines.value = sourceFilter.value === 'all'
    ? []
    : lines.value.filter(entry => logSource(entry) !== sourceFilter.value)
}

function exportLogs() {
  const text = filteredLines.value
    .map(l => `${formatTime(l.ts)} [${logSource(l)}] [${l.level}] ${l.text}`)
    .join('\n')
  const blob = new Blob([text || ''], { type: 'text/plain;charset=utf-8' })
  const a = document.createElement('a')
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  a.href = URL.createObjectURL(blob)
  a.download = `miya-console-${sourceFilter.value}-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`
  a.click()
  URL.revokeObjectURL(a.href)
}

watch(() => [lines.value[lines.value.length - 1]?.seq, sourceFilter.value, levelFilter.value, keyword.value], () => {
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
        <button class="cv-btn" title="清空当前分类，保留其他分类的日志" @click="clearLines">
          清屏
        </button>
        <button class="cv-btn" @click="exportLogs">
          导出
        </button>
      </div>
    </div>

    <div class="cv-sourcebar">
      <div class="cv-sources" role="group" aria-label="日志来源">
        <button
          v-for="source in sources"
          :key="source.id"
          class="cv-source-btn"
          :class="[source.id, { active: sourceFilter === source.id }]"
          :aria-pressed="sourceFilter === source.id"
          @click="sourceFilter = source.id"
        >
          <span class="cv-source-icon" aria-hidden="true">{{ source.icon }}</span>
          <span>{{ source.label }}</span>
          <span class="cv-source-count">{{ sourceCounts[source.id] }}</span>
        </button>
      </div>
      <span class="cv-source-description">{{ selectedSource.description }}</span>
    </div>

    <!-- 终端主体 -->
    <div ref="terminalEl" class="cv-terminal" @scroll="onScroll">
      <div v-if="filteredLines.length === 0" class="cv-empty">
        <span class="cv-empty-icon">▤</span>
        <span class="cv-empty-text">{{ sourceLines.length ? '没有符合当前筛选条件的日志' : sseStatus === 'open' ? `等待${selectedSource.label}输出…` : '正在连接日志服务…' }}</span>
      </div>
      <div v-for="l in filteredLines" :key="l.seq" class="cv-line" :class="levelClass(l.level)">
        <span class="cv-time">{{ formatTime(l.ts) }}</span>
        <span class="cv-source-tag" :class="logSource(l)">{{ logSource(l) === 'frontend' ? '前端' : '后端' }}</span>
        <span class="cv-level">{{ l.level }}</span>
        <span class="cv-text">{{ l.text }}</span>
      </div>
    </div>

    <!-- 底部状态条 -->
    <div class="cv-statusbar">
      <span>{{ selectedSource.label }} · 显示 {{ filteredLines.length }} / {{ sourceLines.length }} 条</span>
      <span>累计接收 {{ totalReceived }} 条</span>
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
  min-width: 0;
  min-height: 0;
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

.cv-sourcebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.cv-sources {
  display: flex;
  gap: 5px;
  padding: 4px;
  border: 1px solid color-mix(in srgb, var(--miya-border) 14%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--miya-bg-elevated, #101925) 80%, transparent);
}

.cv-source-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--miya-text-muted, #7f919a);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, border-color 0.2s;
}

.cv-source-btn:hover { color: var(--miya-text-strong, #f2f6f7); }
.cv-source-btn:focus-visible { outline: 2px solid var(--miya-accent); outline-offset: 2px; }
.cv-source-btn.active { color: #5eead4; background: rgba(113, 157, 230, 0.11); border-color: rgba(94, 234, 212, 0.18); }
.cv-source-btn.frontend.active { color: #93c5fd; background: rgba(59, 130, 246, 0.12); border-color: rgba(147, 197, 253, 0.2); }

.cv-source-icon {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  opacity: 0.7;
}

.cv-source-count {
  min-width: 20px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.1);
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.cv-source-description {
  color: var(--miya-text-muted, #7f919a);
  font-size: 11px;
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
  font-size: 11px;
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

.cv-filter-btn.active.f-all { background: rgba(113, 157, 230, 0.12); color: #5eead4; }
.cv-filter-btn.active.f-info { background: rgba(59, 130, 246, 0.12); color: #60a5fa; }
.cv-filter-btn.active.f-warning { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }
.cv-filter-btn.active.f-error { background: rgba(239, 68, 68, 0.12); color: #f87171; }

.cv-search {
  width: 160px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
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
  font-size: 11px;
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
  font-size: 12px;
  line-height: 1.8;
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
  font-variant-numeric: tabular-nums;
}

.cv-source-tag {
  align-self: flex-start;
  flex-shrink: 0;
  margin-top: 2px;
  padding: 0 5px;
  border-radius: 4px;
  color: #5eead4;
  background: rgba(94, 234, 212, 0.08);
  font-size: 10px;
  line-height: 18px;
}

.cv-source-tag.frontend { color: #93c5fd; background: rgba(147, 197, 253, 0.1); }

.cv-level {
  flex: 0 0 48px;
  color: #64748b;
  font-size: 10px;
}

.cv-line.lv-warn .cv-level { color: #fbbf24; }
.cv-line.lv-error .cv-level { color: #f87171; }

.cv-text {
  min-width: 0;
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
  font-size: 11px;
  flex-wrap: wrap;
  color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}

.cv-paused {
  color: #fbbf24;
}

.cv-grow {
  flex: 1;
}

@media (max-width: 700px) {
  .console-view { padding: 16px; }
  .cv-header-right { width: 100%; }
  .cv-search { flex: 1; min-width: 110px; width: auto; }
  .cv-sources { width: 100%; }
  .cv-source-btn { flex: 1; justify-content: center; gap: 5px; padding: 8px 6px; }
  .cv-source-icon { display: none; }
  .cv-source-description { display: none; }
  .cv-line { gap: 6px; }
  .cv-level { display: none; }
  .cv-terminal { padding: 10px; font-size: 11px; }
}
</style>
