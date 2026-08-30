import type { Message } from '@/utils/session'
import type { PlatformInfo } from '@/utils/platform'
import { ref } from 'vue'
import { MESSAGES } from '@/utils/session'
import { getPlatformLabel } from '@/utils/platform'
import { getManagementPort } from '@/utils/api-port'

const connected = ref(false)
const reconnecting = ref(false)
const platforms = ref<PlatformInfo[]>([])
const lastPlatformStatus = ref<Record<string, string>>({})
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let shouldReconnect = true

export interface PlatformChangeEvent {
  platformId: string
  platformName: string
  oldStatus: string
  newStatus: string
}

const onPlatformChange = ref<((event: PlatformChangeEvent) => void) | null>(null)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isPlatformInfo(value: unknown): value is PlatformInfo {
  return isRecord(value)
    && typeof value.platform_id === 'string'
    && typeof value.platform_name === 'string'
    && typeof value.status === 'string'
}

export function useMIYARealtime() {
  function connect() {
    if (ws && ws.readyState !== WebSocket.CLOSED)
      return

    shouldReconnect = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const socket = new WebSocket(`ws://localhost:${getManagementPort()}/api/v1/ws`)
    ws = socket

    socket.onopen = () => {
      connected.value = true
      reconnecting.value = false
      console.log('[MIYA WS] 已连接')
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch {}
    }

    socket.onclose = () => {
      if (ws !== socket)
        return
      connected.value = false
      ws = null
      if (shouldReconnect && !reconnecting.value) {
        reconnecting.value = true
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null
          reconnecting.value = false
          connect()
        }, 3000)
      }
    }

    socket.onerror = () => {
      socket.close()
    }
  }

  function handleMessage(data: any) {
    if (data.type === 'initial_state' || data.type === 'status_update') {
      handlePlatformList(data.platforms || data)
    }

    if (data.type === 'platform_event') {
      handlePlatformEvent(data)
    }

    if (data.type === 'new_message' || data.type === 'message') {
      handleNewMessage(data)
    }
  }

  function handlePlatformList(plats: unknown) {
    const list = Array.isArray(plats)
      ? plats
      : isRecord(plats) && Array.isArray(plats.platforms) ? plats.platforms : []

    const normalized = list.filter(isPlatformInfo)

    for (const p of normalized) {
      const old = lastPlatformStatus.value[p.platform_id]
      const cur = p.status
      if (old && old !== cur && onPlatformChange.value) {
        onPlatformChange.value({
          platformId: p.platform_id,
          platformName: p.platform_name || p.platform_id,
          oldStatus: old,
          newStatus: cur,
        })
      }
    }

    for (const p of normalized) {
      lastPlatformStatus.value[p.platform_id] = p.status
    }

    platforms.value = normalized
      .filter(p => p.status !== 'disabled')
      .sort((a, b) => a.platform_name.localeCompare(b.platform_name))
  }

  function handlePlatformEvent(data: any) {
    const pid = data.platform_id
    const status = data.status
    const old = lastPlatformStatus.value[pid]
    if (old && old !== status && onPlatformChange.value) {
      onPlatformChange.value({
        platformId: pid,
        platformName: data.platform_name || pid,
        oldStatus: old,
        newStatus: status,
      })
    }
    lastPlatformStatus.value[pid] = status

    if (data.health && typeof data.health === 'object') {
      const idx = platforms.value.findIndex(p => p.platform_id === pid)
      if (idx >= 0) {
        const current = platforms.value[idx]
        if (!current) return
        platforms.value[idx] = {
          ...current,
          status: status || current.status,
          latency_ms: data.health.latency_ms ?? current.latency_ms,
          last_heartbeat: data.health.last_heartbeat ?? current.last_heartbeat,
          consecutive_health_failures: data.health.consecutive_health_failures ?? current.consecutive_health_failures,
          message_count: data.health.message_count ?? current.message_count,
        }
      }
    }
  }

  function handleNewMessage(data: any) {
    const msg = data.data || data
    const content = msg.content || msg.text || msg.message || ''
    const sender = msg.sender_name || msg.sender || msg.platform || '未知'
    const platform = msg.platform || data.platform || ''
    const platformName = getPlatformLabel(platform, data.platform_name || msg.platform_name)
    const direction = msg.direction || (platform === 'desktop' ? 'in' : 'in')
    const messageId = msg.message_id || msg.msg_id || undefined
    const timestamp = msg.timestamp || msg.time || null

    if (!content.trim()) return

    // 去重：检查最近 5 条已有消息，按内容和平台近似匹配
    const trimmed = content.trim()
    const recent = MESSAGES.value.slice(-5)
    const duplicate = recent.find(
      (m) => {
        if (!m.content) return false
        const mTrimmed = m.content.trim()
        // 精确匹配
        if (mTrimmed === trimmed && m.platform === platform) return true
        // 同平台 + 内容匹配 → 防重复（本地已渲染的平台消息会被 WS 重复推送）
        if ((platform === 'desktop' || platform === 'mobile') && mTrimmed === trimmed) return true
        return false
      }
    )
    if (duplicate) return

    // 角色判定：弥娅发出的消息用 assistant，用户发出的用 user，其他用 system
    let role: string
    if (direction === 'out' || sender === '弥娅' || msg.sender_id === 'miya') {
      role = 'assistant'
    } else if (platform === 'desktop' || platform === 'mobile') {
      role = 'user'
    } else {
      role = 'system'
    }

    const newMsg: Message = {
      role: role as 'assistant' | 'system' | 'user',
      content: content,
      sender,
      platform,
      platformName: platformName !== platform ? platformName : msg.platform_name,
      messageId,
      direction,
      timestamp,
    }
    MESSAGES.value.push(newMsg)
  }

  function setOnPlatformChange(fn: (event: PlatformChangeEvent) => void) {
    onPlatformChange.value = fn
    return () => {
      if (onPlatformChange.value === fn)
        onPlatformChange.value = null
    }
  }

  function disconnect() {
    shouldReconnect = false
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = null
    reconnecting.value = false
    ws?.close()
    ws = null
  }

  return { connected, reconnecting, platforms, connect, disconnect, setOnPlatformChange, lastPlatformStatus }
}
