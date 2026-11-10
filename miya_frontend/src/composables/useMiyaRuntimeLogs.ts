import type { RuntimeLog } from '@/utils/miyaRuntimeLogs'
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { getManagementPort, managementPort } from '@/utils/api-port'
import { reduceRuntimePayload } from '@/utils/miyaRuntimeLogs'

export function useMiyaRuntimeLogs() {
  const entries = shallowRef<RuntimeLog[]>([])
  const connection = ref<'connecting' | 'online' | 'offline'>('connecting')
  const now = ref(Date.now())
  const hidden = ref(document.hidden)
  let cursor = 0
  let source: EventSource | undefined
  let retry: ReturnType<typeof setTimeout> | undefined
  let clock: ReturnType<typeof setInterval> | undefined
  let stopPortWatch: (() => void) | undefined
  let disposed = false
  let failures = 0
  const recent = computed(() => entries.value.filter(entry => !entry.historical && now.value - entry.receivedAt < 60000))

  function disconnect() {
    clearTimeout(retry)
    source?.close()
    source = undefined
  }
  function connect() {
    disconnect()
    if (disposed || hidden.value)
      return
    connection.value = cursor ? 'offline' : 'connecting'
    const stream = new EventSource(`http://localhost:${getManagementPort()}/api/v1/logs/stream${cursor ? `?since=${cursor}` : ''}`)
    source = stream
    stream.onopen = () => {
      if (source !== stream)
        return
      connection.value = 'online'
      failures = 0
    }
    stream.onmessage = (event) => {
      if (source !== stream)
        return
      try {
        const payload = JSON.parse(event.data)
        const result = reduceRuntimePayload(entries.value, cursor, payload, Date.now())
        if (!result)
          return
        entries.value = result.entries
        cursor = result.cursor
        now.value = Date.now()
      }
      catch { /* A malformed log must not break the stream. */ }
    }
    // SSE comments do not fire onmessage. A quiet stream is still connected.
    stream.onerror = () => {
      if (source !== stream)
        return
      disconnect()
      connection.value = 'offline'
      retry = setTimeout(connect, Math.min(15000, 1500 * 2 ** Math.min(failures++, 4)))
    }
  }
  function onVisibility() {
    hidden.value = document.hidden
    if (hidden.value) {
      disconnect()
      connection.value = 'offline'
    }
    else {
      now.value = Date.now()
      connect()
    }
  }
  onMounted(() => {
    connect()
    clock = setInterval(() => {
      now.value = Date.now()
    }, 1000)
    document.addEventListener('visibilitychange', onVisibility)
    stopPortWatch = watch(managementPort, () => {
      cursor = 0
      entries.value = []
      connect()
    })
  })
  onUnmounted(() => {
    disposed = true
    disconnect()
    clearInterval(clock)
    stopPortWatch?.()
    document.removeEventListener('visibilitychange', onVisibility)
  })
  return { entries, recent, connection, now, hidden }
}
