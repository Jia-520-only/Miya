<script setup lang="ts">
import type { PlatformChangeEvent } from '@/composables/useMIYARealtime'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMIYARealtime } from '@/composables/useMIYARealtime'
import { getManagementPort } from '@/utils/api-port'
import { getPlatformColor, getPlatformLabel } from '@/utils/platform'

const { connected: wsConnected, platforms, connect: wsConnect, setOnPlatformChange } = useMIYARealtime()
const backendOnline = ref(false)
const showDetailId = ref<string | null>(null)

const onlineCount = computed(() => platforms.value.filter(p => p.status === 'online').length)
const allOnline = computed(() => platforms.value.length > 0 && onlineCount.value === platforms.value.length)
const hasIssue = computed(() => platforms.value.some(p => p.status === 'offline' || p.status === 'error'))

function statusLabel(s: string) {
  const m: Record<string, string> = {
    online: '在线', connecting: '连接中', reconnecting: '重连中',
    degraded: '降级', offline: '离线', error: '错误', disabled: '禁用',
  }
  return m[s] || s
}

function statusClass(s: string) {
  const m: Record<string, string> = {
    online: 'st-online', connecting: 'st-connecting', reconnecting: 'st-connecting',
    degraded: 'st-degraded', offline: 'st-offline', error: 'st-offline', disabled: 'st-offline',
  }
  return m[s] || 'st-offline'
}

function statusDotClass(s: string) {
  const m: Record<string, string> = {
    online: 'dot-online', connecting: 'dot-connecting', reconnecting: 'dot-connecting',
    degraded: 'dot-degraded', offline: 'dot-offline', error: 'dot-offline-pulse',
  }
  return m[s] || 'dot-offline'
}

function formatUptime(seconds: number): string {
  if (seconds <= 0) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function formatLatency(ms: number): string {
  if (ms <= 0) return '--'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

async function platformAction(platformId: string, action: 'start' | 'stop' | 'restart') {
  try {
    await fetch(`http://localhost:${getManagementPort()}/api/v1/platforms/${platformId}/${action}`, {
      method: 'POST',
    })
  } catch {}
}

async function checkBackend() {
  try {
    const r = await fetch(`http://localhost:${getManagementPort()}/api/v1/health`)
    const d = await r.json()
    backendOnline.value = d.status === 'ok'
  } catch { backendOnline.value = false }
}

let timer: ReturnType<typeof setInterval> | null = null
let unsubscribePlatformChange: (() => void) | null = null

onMounted(() => {
  checkBackend()
  wsConnect()
  timer = setInterval(checkBackend, 30000)
  unsubscribePlatformChange = setOnPlatformChange((event: PlatformChangeEvent) => {
    if (event.newStatus === 'offline' || event.newStatus === 'error') {
      showDesktopNotification(event.platformName, event.newStatus)
    }
  })
})

function showDesktopNotification(name: string, status: string) {
  if (!('Notification' in window)) return
  if (Notification.permission === 'granted') {
    new Notification(`弥娅 · ${name}`, {
      body: `平台状态变更: ${statusLabel(status)}`,
      icon: '/my.png',
    })
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission()
  }
}

function formatLastMessage(ts: string | null) {
  if (!ts) return '--'
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h前`
  return `${Math.floor(diff / 86400000)}d前`
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
  unsubscribePlatformChange?.()
  unsubscribePlatformChange = null
})
</script>

<template>
  <div class="platform-view">
    <!-- 顶部总结 -->
    <div class="pv-header">
      <div class="pv-header-left">
        <span class="pv-title">◇ 平台状态</span>
        <span class="pv-sub">
          <span class="pv-sys-dot" :class="{ 'dot-online': backendOnline }" />
          {{ backendOnline ? 'SYS.ONLINE' : 'SYS.OFFLINE' }}
        </span>
      </div>
      <div class="pv-header-right">
        <div class="pv-summary-card" :class="{ ok: allOnline, warn: hasIssue }">
          <span class="pv-sum-num">{{ onlineCount }}/{{ platforms.length }}</span>
          <span class="pv-sum-label">平台在线</span>
        </div>
        <div class="pv-ws-indicator" :class="{ connected: wsConnected }">
          <span class="pv-ws-dot" />
          <span class="pv-ws-label">{{ wsConnected ? 'WS' : 'WS-OFF' }}</span>
        </div>
      </div>
    </div>

    <!-- 平台卡片网格 -->
    <div class="pv-grid">
      <div
        v-for="p in platforms"
        :key="p.platform_id"
        class="pv-card"
        :class="[statusClass(p.status), { expanded: showDetailId === p.platform_id }]"
        :style="{ '--pc': getPlatformColor(p.platform_id) }"
      >
        <!-- 卡片头部 -->
        <div class="pvc-head" @click="showDetailId = showDetailId === p.platform_id ? null : p.platform_id">
          <div class="pvc-head-left">
            <span class="pvc-dot" :class="statusDotClass(p.status)" />
            <span class="pvc-name">{{ getPlatformLabel(p.platform_id, p.platform_name) }}</span>
            <span class="pvc-id">#{{ p.platform_id }}</span>
          </div>
          <div class="pvc-head-right">
            <span class="pvc-status" :class="statusClass(p.status)">{{ statusLabel(p.status) }}</span>
            <span class="pvc-latency" v-if="p.status === 'online' && p.latency_ms > 0">
              {{ formatLatency(p.latency_ms) }}
            </span>
            <span class="pvc-arrow">{{ showDetailId === p.platform_id ? '▲' : '▼' }}</span>
          </div>
        </div>

        <!-- 在线指示条 -->
        <div class="pvc-bar">
          <div
            class="pvc-bar-fill"
            :class="statusClass(p.status)"
            :style="{ width: p.status === 'online' ? '100%' : p.status === 'degraded' ? '60%' : p.status === 'connecting' ? '30%' : '0%' }"
          />
        </div>

        <!-- 展开详情 -->
        <Transition name="detail">
          <div v-if="showDetailId === p.platform_id" class="pvc-detail">
            <div class="pvc-metrics">
              <div class="pvc-metric">
                <span class="pvc-m-label">消息</span>
                <span class="pvc-m-val">{{ p.message_count || 0 }}</span>
                <span class="pvc-m-sub">{{ p.message_in_count || 0 }}入 / {{ p.message_out_count || 0 }}出</span>
              </div>
              <div class="pvc-metric">
                <span class="pvc-m-label">在线</span>
                <span class="pvc-m-val">{{ formatUptime(p.uptime_seconds) }}</span>
              </div>
              <div class="pvc-metric">
                <span class="pvc-m-label">延迟</span>
                <span class="pvc-m-val" :class="{ warn: p.latency_ms > 500 }">
                  {{ formatLatency(p.latency_ms) }}
                </span>
              </div>
              <div class="pvc-metric">
                <span class="pvc-m-label">心跳</span>
                <span class="pvc-m-val">
                  {{ p.consecutive_health_failures > 0 ? '!' + p.consecutive_health_failures : 'OK' }}
                </span>
              </div>
            </div>

            <div class="pvc-timestamps" v-if="p.last_online || p.last_offline || p.last_message_received">
              <div class="pvc-ts" v-if="p.last_message_received">
                <span class="pvc-ts-label">最近消息</span>
                <span class="pvc-ts-val">{{ formatLastMessage(p.last_message_received) }}</span>
              </div>
              <div class="pvc-ts" v-if="p.last_online">
                <span class="pvc-ts-label">上线</span>
                <span class="pvc-ts-val">{{ new Date(p.last_online).toLocaleString('zh-CN') }}</span>
              </div>
              <div class="pvc-ts" v-if="p.last_offline">
                <span class="pvc-ts-label">离线</span>
                <span class="pvc-ts-val">{{ new Date(p.last_offline).toLocaleString('zh-CN') }}</span>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="pvc-actions">
              <button
                v-if="p.status !== 'online'"
                class="pvc-btn pvc-btn-start"
                @click="platformAction(p.platform_id, 'start')"
              >
                ▶ 启动
              </button>
              <button
                v-if="p.status === 'online' || p.status === 'degraded'"
                class="pvc-btn pvc-btn-stop"
                @click="platformAction(p.platform_id, 'stop')"
              >
                ■ 停止
              </button>
              <button
                class="pvc-btn pvc-btn-restart"
                @click="platformAction(p.platform_id, 'restart')"
              >
                ↻ 重启
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="platforms.length === 0" class="pv-empty">
      <span class="pv-empty-icon">◇</span>
      <span class="pv-empty-text">等待平台数据...</span>
    </div>
  </div>
</template>

<style scoped>
.platform-view {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.pv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.pv-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pv-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.1rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--miya-chat-ai), var(--miya-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.pv-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: color-mix(in srgb, var(--miya-border) 50%, transparent);
}

.pv-sys-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 100, 100, 0.5);
  transition: all 0.5s;
}

.pv-sys-dot.dot-online {
  background: color-mix(in srgb, var(--miya-chat-ai) 60%, transparent);
  box-shadow: 0 0 6px color-mix(in srgb, var(--miya-chat-ai) 40%, transparent);
}

.pv-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pv-summary-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 14px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--miya-chat-ai) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-chat-ai) 15%, transparent);
  transition: all 0.3s;
}

.pv-summary-card.warn {
  background: rgba(255, 120, 80, 0.08);
  border-color: rgba(255, 120, 80, 0.2);
}

.pv-sum-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  font-weight: 700;
  color: var(--miya-chat-ai);
}

.pv-summary-card.warn .pv-sum-num {
  color: #f59e0b;
}

.pv-sum-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: color-mix(in srgb, var(--miya-border) 45%, transparent);
}

.pv-ws-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(255, 100, 100, 0.08);
  border: 1px solid rgba(255, 100, 100, 0.15);
}

.pv-ws-indicator.connected {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.2);
}

.pv-ws-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 100, 100, 0.5);
}

.pv-ws-indicator.connected .pv-ws-dot {
  background: #22c55e;
  box-shadow: 0 0 4px rgba(34, 197, 94, 0.4);
}

.pv-ws-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: color-mix(in srgb, var(--miya-border) 50%, transparent);
}

/* 网格 */
.pv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

/* 卡片 */
.pv-card {
  background: linear-gradient(135deg, rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.35));
  border: 1px solid color-mix(in srgb, var(--pc, #6B7280) 12%, transparent);
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.pv-card:hover {
  border-color: color-mix(in srgb, var(--pc, #6B7280) 25%, transparent);
  transform: translateY(-1px);
}

.pv-card.st-online {
  border-left: 2px solid color-mix(in srgb, var(--pc, #22c55e) 60%, transparent);
}

.pv-card.st-degraded {
  border-left: 2px solid color-mix(in srgb, var(--pc, #f59e0b) 60%, transparent);
}

.pv-card.st-connecting {
  border-left: 2px solid color-mix(in srgb, var(--pc, #3b82f6) 60%, transparent);
}

.pv-card.st-offline {
  border-left: 2px solid transparent;
  opacity: 0.65;
}

/* 卡片头 */
.pvc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}

.pvc-head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pvc-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #6B7280;
  flex-shrink: 0;
  transition: all 0.3s;
}

.dot-online {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.dot-degraded {
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.4);
  animation: pulse-warn 2s infinite;
}

.dot-connecting {
  background: #3b82f6;
  box-shadow: 0 0 6px rgba(59, 130, 246, 0.4);
  animation: pulse-warn 1s infinite;
}

.dot-offline {
  background: #ef4444;
}

.dot-offline-pulse {
  background: #ef4444;
  animation: pulse-error 1.5s infinite;
}

@keyframes pulse-warn {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@keyframes pulse-error {
  0%, 100% { opacity: 1; box-shadow: 0 0 2px rgba(239, 68, 68, 0.3); }
  50% { opacity: 0.5; box-shadow: 0 0 8px rgba(239, 68, 68, 0.6); }
}

.pvc-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 600;
  color: #e4ecf0;
  letter-spacing: 0.03em;
}

.pvc-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}

.pvc-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pvc-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  padding: 2px 8px;
  border-radius: 3px;
  letter-spacing: 0.04em;
}

.st-online .pvc-status { background: rgba(34, 197, 94, 0.1); color: #4ade80; }
.st-degraded .pvc-status { background: rgba(245, 158, 11, 0.1); color: #fbbf24; }
.st-connecting .pvc-status { background: rgba(59, 130, 246, 0.1); color: #60a5fa; }
.st-offline .pvc-status { background: rgba(239, 68, 68, 0.1); color: #f87171; }

.pvc-latency {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: color-mix(in srgb, var(--miya-border) 50%, transparent);
}

.pvc-arrow {
  font-size: 0.5rem;
  color: color-mix(in srgb, var(--miya-border) 35%, transparent);
}

/* 在线指示条 */
.pvc-bar {
  height: 2px;
  background: color-mix(in srgb, var(--pc, #6B7280) 8%, transparent);
  margin: 0 14px;
  border-radius: 1px;
}

.pvc-bar-fill {
  height: 100%;
  border-radius: 1px;
  transition: width 0.5s ease;
}

.pvc-bar-fill.st-online { background: color-mix(in srgb, var(--pc, #22c55e) 60%, #22c55e); }
.pvc-bar-fill.st-degraded { background: color-mix(in srgb, var(--pc, #f59e0b) 60%, #f59e0b); }
.pvc-bar-fill.st-connecting { background: color-mix(in srgb, var(--pc, #3b82f6) 60%, #3b82f6); animation: bar-pulse 1s infinite; }
.pvc-bar-fill.st-offline { background: transparent; }

@keyframes bar-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 详情 */
.pvc-detail {
  padding: 0 14px 12px;
}

.detail-enter-active { transition: all 0.25s ease-out; }
.detail-leave-active { transition: all 0.15s ease-in; }
.detail-enter-from, .detail-leave-to { opacity: 0; transform: translateY(-6px); }

.pvc-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 12px;
}

.pvc-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.pvc-m-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}

.pvc-m-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 700;
  color: color-mix(in srgb, var(--pc, #e4ecf0) 85%, #e4ecf0);
}

.pvc-m-val.warn { color: #f59e0b; }

.pvc-m-sub {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.45rem;
  color: color-mix(in srgb, var(--miya-border) 35%, transparent);
}

.pvc-timestamps {
  margin-top: 10px;
  display: flex;
  gap: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
}

.pvc-ts {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.pvc-ts-label {
  color: color-mix(in srgb, var(--miya-border) 35%, transparent);
}

.pvc-ts-val {
  color: color-mix(in srgb, var(--miya-border) 55%, transparent);
}

.pvc-actions {
  display: flex;
  gap: 6px;
  margin-top: 12px;
}

.pvc-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  padding: 5px 12px;
  border-radius: 4px;
  border: 1px solid;
  cursor: pointer;
  background: transparent;
  transition: all 0.2s;
}

.pvc-btn-start {
  color: #4ade80;
  border-color: color-mix(in srgb, #4ade80 30%, transparent);
}

.pvc-btn-start:hover { background: rgba(34, 197, 94, 0.08); }

.pvc-btn-stop {
  color: #f87171;
  border-color: color-mix(in srgb, #f87171 30%, transparent);
}

.pvc-btn-stop:hover { background: rgba(239, 68, 68, 0.08); }

.pvc-btn-restart {
  color: color-mix(in srgb, var(--miya-border) 55%, transparent);
  border-color: color-mix(in srgb, var(--miya-border) 18%, transparent);
}

.pvc-btn-restart:hover { background: rgba(255, 255, 255, 0.04); }

/* 空状态 */
.pv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 0;
  opacity: 0.4;
}

.pv-empty-icon {
  font-size: 2rem;
  color: var(--miya-chat-ai);
}

.pv-empty-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: color-mix(in srgb, var(--miya-border) 40%, transparent);
}
</style>
