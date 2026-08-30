import { ref } from 'vue'

const COMPILED_PORT = Number(import.meta.env.VITE_API_PORT) || 9800
const COMPILED_MANAGEMENT_PORT = Number(import.meta.env.VITE_MANAGEMENT_PORT) || 9800
const PORT_SCAN_PORTS = [8000, 8001, 8002, 9800, 9801, 9802]

export const apiPort = ref(COMPILED_PORT)
export const managementPort = ref(COMPILED_MANAGEMENT_PORT)

function checkDynamicPort() {
  if (typeof window === 'undefined') return
  const dynamic = (window as any).__MIYA_API_PORT__
  if (dynamic && typeof dynamic === 'number' && dynamic !== apiPort.value) {
    apiPort.value = dynamic
  }
  const dynamicManagement = (window as any).__MIYA_MANAGEMENT_PORT__
  if (dynamicManagement && typeof dynamicManagement === 'number' && dynamicManagement !== managementPort.value) {
    managementPort.value = dynamicManagement
  }
}

let _pollTimer: ReturnType<typeof setInterval> | null = null

export function startApiPortPolling() {
  if (_pollTimer) return
  checkDynamicPort()
  _pollTimer = setInterval(checkDynamicPort, 1500)
}

export function getApiPort(): number {
  checkDynamicPort()
  return apiPort.value
}

export function getManagementPort(): number {
  checkDynamicPort()
  return managementPort.value
}

async function tryHealth(port: number): Promise<boolean> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 1500)
  try {
    const res = await fetch(`http://localhost:${port}/health`, { signal: controller.signal })
    clearTimeout(timer)
    if (res.ok) {
      const data = await res.json().catch(() => ({}))
      return data.status === 'healthy'
    }
  }
  catch {
    clearTimeout(timer)
  }
  return false
}

export async function discoverApiPort(): Promise<number> {
  checkDynamicPort()
  if (apiPort.value !== COMPILED_PORT) return apiPort.value

  const results = await Promise.allSettled(
    PORT_SCAN_PORTS.map(port => tryHealth(port).then(ok => (ok ? port : 0)))
  )
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value > 0) {
      apiPort.value = r.value
      console.log('[MIYA] Discovered API port:', r.value)
      return r.value
    }
  }
  console.warn('[MIYA] No API port discovered, using default:', COMPILED_PORT)
  return COMPILED_PORT
}
