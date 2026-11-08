import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import API from '@/api/core'
import { normalizeMiyaPresence } from '@/utils/miyaPresence'

const presence = shallowRef(normalizeMiyaPresence(null))
const connection = ref<'connecting' | 'online' | 'offline'>('connecting')
const updatedAt = ref<Date | null>(null)
let consumers = 0
let timer: ReturnType<typeof setInterval> | undefined
let pending: AbortController | undefined

async function refreshPresence() {
  if (pending || document.hidden)
    return
  const controller = new AbortController()
  pending = controller
  const options = { signal: controller.signal, timeout: 8000 }
  try {
    const [status, persona] = await Promise.allSettled([
      API.instance.get<Record<string, any>, Record<string, any>>('/api/status', options),
      API.instance.get<Record<string, any>, Record<string, any>>('/api/persona/current', options),
    ])
    if (controller.signal.aborted)
      return
    if (status.status !== 'fulfilled' || !status.value || status.value.error || status.value.success === false)
      throw new Error('Status unavailable')
    presence.value = normalizeMiyaPresence(status.value, persona.status === 'fulfilled' ? persona.value : null)
    updatedAt.value = new Date()
    connection.value = 'online'
  }
  catch {
    if (!controller.signal.aborted)
      connection.value = 'offline'
  }
  finally {
    if (pending === controller)
      pending = undefined
  }
}

function onVisibilityChange() {
  if (!document.hidden)
    void refreshPresence()
}

export function useMiyaPresence() {
  onMounted(() => {
    if (consumers++ === 0) {
      void refreshPresence()
      timer = setInterval(() => void refreshPresence(), 15000)
      document.addEventListener('visibilitychange', onVisibilityChange)
    }
  })
  onUnmounted(() => {
    if (--consumers === 0) {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      pending?.abort()
      pending = undefined
    }
  })
  return {
    presence,
    connection,
    updatedAt,
    online: computed(() => connection.value === 'online'),
    refresh: refreshPresence,
  }
}
