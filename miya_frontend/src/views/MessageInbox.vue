<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useMIYARealtime } from '@/composables/useMIYARealtime'
import { getManagementPort } from '@/utils/api-port'
import { getPlatformColor, getPlatformLabel } from '@/utils/platform'

const { connected: wsConnected, platforms, connect: wsConnect } = useMIYARealtime()

interface InboxMessage {
  id: number
  message_id: string
  platform_id: string
  user_id: string
  sender_id: string
  sender_name: string
  content: string
  raw_content: any
  direction: string
  reply_to_message_id: string | null
  timestamp: string
  created_at: string
}

const messages = ref<InboxMessage[]>([])
const total = ref(0)
const loading = ref(false)
const filterPlatform = ref<string[]>([])
const filterDirection = ref<string>('')
const expandedId = ref<number | null>(null)
const limit = 50
const hasMore = ref(true)

const onlinePlatforms = computed(() =>
  platforms.value.filter(p => p.status === 'online' || p.status === 'degraded')
)

const filteredMessages = computed(() => {
  let msgs = messages.value
  if (filterPlatform.value.length > 0) {
    msgs = msgs.filter(m => filterPlatform.value.includes(m.platform_id))
  }
  if (filterDirection.value) {
    msgs = msgs.filter(m => m.direction === filterDirection.value)
  }
  return msgs
})

function formatTime(ts: string) {
  if (!ts) return '--'
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分前`
  if (diff < 86400000) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function directionLabel(d: string) {
  return d === 'in' ? '← 入站' : d === 'out' ? '→ 出站' : d
}

function dirClass(d: string) {
  return d === 'in' ? 'dir-in' : d === 'out' ? 'dir-out' : ''
}

function platformColor(pid: string) {
  return getPlatformColor(pid)
}

function platformName(pid: string, pname?: string) {
  return getPlatformLabel(pid, pname)
}

function togglePlatform(pid: string) {
  const idx = filterPlatform.value.indexOf(pid)
  if (idx >= 0) filterPlatform.value.splice(idx, 1)
  else filterPlatform.value.push(pid)
}

async function fetchMessages(append = false) {
  if (loading.value) return
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('limit', String(limit))
    params.set('offset', String(append ? messages.value.length : 0))
    const r = await fetch(`http://localhost:${getManagementPort()}/api/v1/messages?${params}`)
    const data = await r.json()
    if (data.messages?.length) {
      if (append) {
        messages.value.push(...data.messages)
      } else {
        messages.value = data.messages
      }
      total.value = data.total || 0
      hasMore.value = data.messages.length >= limit
    } else {
      hasMore.value = false
    }
  } catch {
  } finally {
    loading.value = false
  }
}

function loadMore() {
  if (!hasMore.value || loading.value) return
  fetchMessages(true)
}

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

function scrollToBottom() {
  nextTick(() => {
    const el = document.querySelector('.mi-scroll')
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(() => messages.value.length, scrollToBottom)

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchMessages()
  wsConnect()
  refreshTimer = setInterval(() => fetchMessages(), 10000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="mi-view">
    <!-- 顶部 -->
    <div class="mi-header">
      <div class="mi-header-left">
        <span class="mi-title">◆ 消息收件箱</span>
        <span class="mi-sub">
          <span class="mi-dot" :class="{ connected: wsConnected }" />
          {{ wsConnected ? 'WS.ON' : 'WS.OFF' }}
        </span>
      </div>
      <div class="mi-header-right">
        <span class="mi-total">{{ total }} 条消息</span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="mi-filter-bar">
      <div class="mi-filter-group">
        <span class="mi-filter-label">平台: </span>
        <button
          v-for="p in onlinePlatforms" :key="p.platform_id"
          class="mi-chip"
          :class="{ active: filterPlatform.includes(p.platform_id) }"
          :style="{ '--pc': platformColor(p.platform_id) }"
          @click="togglePlatform(p.platform_id)"
        >
          {{ platformName(p.platform_id, p.platform_name) }}
        </button>
        <button
          v-if="filterPlatform.length > 0"
          class="mi-chip clear"
          @click="filterPlatform = []"
        >
          全部
        </button>
      </div>
      <div class="mi-filter-group">
        <span class="mi-filter-label">方向: </span>
        <button
          class="mi-chip"
          :class="{ active: filterDirection === '' }"
          @click="filterDirection = ''"
        >
          全部
        </button>
        <button
          class="mi-chip"
          :class="{ active: filterDirection === 'in' }"
          @click="filterDirection = 'in'"
        >
          ← 入站
        </button>
        <button
          class="mi-chip"
          :class="{ active: filterDirection === 'out' }"
          @click="filterDirection = 'out'"
        >
          → 出站
        </button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div class="mi-list mi-scroll" @scroll="(e: Event) => { const t = e.target as HTMLElement; if (t.scrollTop + t.clientHeight >= t.scrollHeight - 80) loadMore() }">
      <div v-if="loading && messages.length === 0" class="mi-loading">
        加载中...
      </div>

      <div
        v-for="msg in filteredMessages"
        :key="msg.id"
        class="mi-card"
        :class="{ expanded: expandedId === msg.id }"
        @click="toggleExpand(msg.id)"
      >
        <div class="mi-card-header">
          <span class="mi-card-pf" :style="{ '--pc': platformColor(msg.platform_id) }">
            {{ platformName(msg.platform_id) }}
          </span>
          <span class="mi-card-dir" :class="dirClass(msg.direction)">
            {{ directionLabel(msg.direction) }}
          </span>
          <span class="mi-card-sender">
            {{ msg.sender_name || msg.sender_id || '未知' }}
          </span>
          <span class="mi-card-time">{{ formatTime(msg.created_at) }}</span>
          <span class="mi-card-arrow">{{ expandedId === msg.id ? '▲' : '▼' }}</span>
        </div>

        <div v-if="expandedId === msg.id" class="mi-card-body">
          <div class="mi-card-meta">
            <span>UID: {{ msg.user_id }}</span>
            <span v-if="msg.message_id">MSG: {{ msg.message_id }}</span>
            <span v-if="msg.reply_to_message_id">RE: {{ msg.reply_to_message_id }}</span>
          </div>
          <div class="mi-card-content">{{ msg.content }}</div>
          <div class="mi-card-time-detail">{{ msg.created_at }}</div>
        </div>

        <div v-else class="mi-card-preview">
          {{ msg.content.slice(0, 100) }}{{ msg.content.length > 100 ? '...' : '' }}
        </div>
      </div>

      <div v-if="loading && messages.length > 0" class="mi-loading-more">
        加载更多...
      </div>

      <div v-if="!loading && filteredMessages.length === 0 && messages.length > 0" class="mi-empty">
        无匹配消息
      </div>

      <div v-if="!loading && messages.length === 0" class="mi-empty">
        暂无消息记录
      </div>
    </div>
  </div>
</template>

<style scoped>
.mi-view {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mi-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.mi-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mi-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.1rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--miya-chat-ai), var(--miya-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.mi-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: color-mix(in srgb, var(--miya-border) 50%, transparent);
}

.mi-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 100, 100, 0.5);
}

.mi-dot.connected {
  background: color-mix(in srgb, var(--miya-chat-ai) 60%, transparent);
  box-shadow: 0 0 6px color-mix(in srgb, var(--miya-chat-ai) 40%, transparent);
}

.mi-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mi-total {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--miya-text-dim);
}

.mi-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.mi-filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.mi-filter-label {
  font-size: 0.7rem;
  color: var(--miya-text-dim);
  font-family: 'JetBrains Mono', monospace;
}

.mi-chip {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid color-mix(in srgb, var(--miya-border) 25%, transparent);
  background: color-mix(in srgb, var(--miya-surface) 60%, transparent);
  color: var(--miya-text-dim);
  font-size: 0.65rem;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  transition: all 0.2s;
}

.mi-chip:hover {
  border-color: var(--miya-border);
  color: var(--miya-text);
}

.mi-chip.active {
  border-color: var(--pc, var(--miya-accent));
  color: var(--pc, var(--miya-accent));
  background: color-mix(in srgb, var(--pc, var(--miya-accent)) 15%, transparent);
}

.mi-chip.clear {
  border-color: color-mix(in srgb, var(--miya-accent) 20%, transparent);
  color: var(--miya-chat-user);
}

.mi-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 6px;
}

.mi-card {
  padding: 10px 14px;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--miya-border) 10%, transparent);
  background: color-mix(in srgb, var(--miya-surface) 50%, transparent);
  cursor: pointer;
  transition: all 0.2s;
}

.mi-card:hover {
  border-color: color-mix(in srgb, var(--miya-border) 30%, transparent);
  background: color-mix(in srgb, var(--miya-surface) 80%, transparent);
}

.mi-card.expanded {
  border-color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}

.mi-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.7rem;
}

.mi-card-pf {
  padding: 1px 8px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--pc, var(--miya-accent)) 15%, transparent);
  color: var(--pc, var(--miya-accent));
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  font-weight: 600;
  white-space: nowrap;
}

.mi-card-dir {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.mi-card-dir.dir-in {
  color: color-mix(in srgb, #60a5fa 80%, white);
  background: color-mix(in srgb, #60a5fa 12%, transparent);
}

.mi-card-dir.dir-out {
  color: color-mix(in srgb, #34d399 80%, white);
  background: color-mix(in srgb, #34d399 12%, transparent);
}

.mi-card-sender {
  flex: 1;
  color: var(--miya-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mi-card-time {
  color: var(--miya-text-dim);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  white-space: nowrap;
}

.mi-card-arrow {
  color: var(--miya-text-dim);
  font-size: 0.55rem;
}

.mi-card-preview {
  margin-top: 6px;
  font-size: 0.72rem;
  color: color-mix(in srgb, var(--miya-text) 70%, transparent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mi-card-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid color-mix(in srgb, var(--miya-border) 10%, transparent);
}

.mi-card-meta {
  display: flex;
  gap: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--miya-text-dim);
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.mi-card-content {
  font-size: 0.75rem;
  color: var(--miya-text);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.mi-card-time-detail {
  margin-top: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--miya-text-dim);
}

.mi-loading,
.mi-loading-more,
.mi-empty {
  text-align: center;
  padding: 40px 20px;
  font-size: 0.7rem;
  color: var(--miya-text-dim);
  font-family: 'JetBrains Mono', monospace;
}
</style>
