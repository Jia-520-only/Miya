import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import API from '@/api/core'
import { apiPort } from '@/utils/api-port'
import { normalizeMiyaPresence } from '@/utils/miyaPresence'

const presence = shallowRef(normalizeMiyaPresence(null))
const connection = ref<'connecting' | 'online' | 'offline'>('connecting')
const updatedAt = ref<Date | null>(null)
const clock = ref(Date.now())
const streaming = ref(false)
let consumers = 0
let timer: ReturnType<typeof setInterval> | undefined
let pending: AbortController | undefined
let stream: EventSource | undefined
let stopPortWatch: (() => void) | undefined
let lastReceivedAt = 0
let lastPollAt = 0

const online = computed(() => connection.value === 'online' && updatedAt.value !== null
  && clock.value - updatedAt.value.getTime() < 45000 && clock.value - lastReceivedAt < 45000)

function acceptSnapshot(value: any) {
  if (value?.success !== true)
    throw new Error('Observatory unavailable')
  const next = normalizeMiyaPresence(value)
  const sampledAt = next.sampledAt ? Date.parse(next.sampledAt) : Number.NaN
  if (!Number.isFinite(sampledAt) || Math.abs(Date.now() - sampledAt) > 45000)
    throw new Error('Stale observatory snapshot')
  if (updatedAt.value && sampledAt < updatedAt.value.getTime())
    return
  presence.value = next
  updatedAt.value = new Date(sampledAt)
  clock.value = lastReceivedAt = Date.now()
  connection.value = 'online'
}

async function refreshPresence() {
  if (pending || document.hidden || consumers === 0)
    return
  const controller = new AbortController()
  pending = controller
  lastPollAt = Date.now()
  try {
    const value = await API.instance.get('/api/observatory/snapshot', { signal: controller.signal, timeout: 8000 })
    if (!controller.signal.aborted)
      acceptSnapshot(value)
  }
  catch {
    if (!controller.signal.aborted && (!lastReceivedAt || Date.now() - lastReceivedAt > 15000))
      connection.value = 'offline'
  }
  finally {
    if (pending === controller)
      pending = undefined
  }
}

function connectStream() {
  stream?.close()
  streaming.value = false
  if (document.hidden || !consumers || typeof EventSource === 'undefined')
    return
  const source = new EventSource(`${API.endpoint}/api/observatory/events`)
  stream = source
  source.addEventListener('presence', (event) => {
    if (stream !== source)
      return
    try {
      acceptSnapshot(JSON.parse((event as MessageEvent).data))
      streaming.value = true
    }
    catch {
      streaming.value = false
    }
  })
  source.onerror = () => {
    if (stream === source)
      streaming.value = false
  }
}

function onVisibilityChange() {
  if (document.hidden) {
    stream?.close()
    stream = undefined
    streaming.value = false
    pending?.abort()
    pending = undefined
  }
  else {
    clock.value = Date.now()
    void refreshPresence()
    connectStream()
  }
}

export function useMiyaPresence() {
  onMounted(() => {
    if (consumers++ === 0) {
      clock.value = Date.now()
      void refreshPresence()
      connectStream()
      timer = setInterval(() => {
        clock.value = Date.now()
        if (!document.hidden && (!streaming.value || clock.value - lastReceivedAt > 12000) && clock.value - lastPollAt >= 15000)
          void refreshPresence()
      }, 3000)
      document.addEventListener('visibilitychange', onVisibilityChange)
      stopPortWatch = watch(apiPort, () => {
        pending?.abort()
        pending = undefined
        presence.value = normalizeMiyaPresence(null)
        updatedAt.value = null
        lastReceivedAt = 0
        connection.value = 'connecting'
        void refreshPresence()
        connectStream()
      })
    }
  })
  onUnmounted(() => {
    if (--consumers === 0) {
      clearInterval(timer)
      stopPortWatch?.()
      document.removeEventListener('visibilitychange', onVisibilityChange)
      stream?.close()
      stream = undefined
      streaming.value = false
      pending?.abort()
      pending = undefined
    }
  })
  return {
    presence,
    connection,
    updatedAt,
    online,
    streaming,
    refresh: refreshPresence,
  }
}
