import type { Session } from 'electron'

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])
// Include the ports scanned by src/utils/api-port.ts, before runtime_ports.json exists.
const DEFAULT_PORTS = [8000, 8001, 8002, 9800, 9801, 9802]

export function installDesktopRequestLogs(
  appSession: Session,
  readPorts: () => Record<string, number> | null,
): void {
  let ports = new Set(DEFAULT_PORTS)
  let refreshAt = 0
  const pending = new Map<number, { url: URL, method: string, started: number }>()
  const responseStarted = new Set<number>()

  function backendUrl(raw: string): URL | null {
    let url: URL
    try { url = new URL(raw) }
    catch { return null }
    if (!LOOPBACK_HOSTS.has(url.hostname)) return null
    if (!url.port) return null
    if (Date.now() >= refreshAt) {
      const runtime = readPorts()
      ports = new Set([
        ...DEFAULT_PORTS,
        Number(process.env.VITE_API_PORT),
        Number(process.env.VITE_MANAGEMENT_PORT),
        runtime?.web_api ?? 0,
        runtime?.management_api ?? 0,
      ].filter(port => Number.isInteger(port) && port > 0 && port <= 65535))
      refreshAt = Date.now() + 2000
    }
    return ports.has(Number(url.port)) ? url : null
  }

  function printResponse(id: number, status: number) {
    const request = pending.get(id)
    if (!request) return
    const elapsed = Math.round(performance.now() - request.started)
    const time = new Date().toLocaleTimeString('en-GB', { hour12: false })
    // Query strings can contain user text/tokens; the path is enough to locate a request.
    const line = `[Frontend] ${time} ${request.method} :${request.url.port}${request.url.pathname} -> ${status} (${elapsed} ms)`
    if (status >= 400) console.warn(line)
    else console.log(line)
    pending.delete(id)
  }

  const filter = { urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }
  appSession.webRequest.onBeforeSendHeaders(filter, (details, callback) => {
    const url = backendUrl(details.url)
    if (url) {
      for (const header of Object.keys(details.requestHeaders)) {
        if (header.toLowerCase() === 'x-miya-client') delete details.requestHeaders[header]
      }
      details.requestHeaders['X-Miya-Client'] = 'desktop'
      pending.set(details.id, { url, method: details.method, started: performance.now() })
    }
    callback({ requestHeaders: details.requestHeaders })
  })
  // Log when headers arrive, so SSE, audio and camera streams appear immediately.
  appSession.webRequest.onResponseStarted(filter, (details) => {
    if (pending.has(details.id)) responseStarted.add(details.id)
    printResponse(details.id, details.statusCode)
  })
  appSession.webRequest.onBeforeRedirect(filter, (details) => {
    printResponse(details.id, details.statusCode)
    responseStarted.delete(details.id)
  })
  appSession.webRequest.onCompleted(filter, (details) => {
    printResponse(details.id, details.statusCode)
    responseStarted.delete(details.id)
  })
  appSession.webRequest.onErrorOccurred(filter, (details) => {
    const request = pending.get(details.id)
    const url = request?.url ?? backendUrl(details.url)
    const hadResponse = responseStarted.delete(details.id)
    pending.delete(details.id)
    if (!url) return
    // Chromium reports closing an EventSource / navigating away as a failed request.
    if (details.error === 'net::ERR_ABORTED' || (hadResponse && details.error === 'net::ERR_FAILED')) return
    console.warn(`[Frontend] ${details.method} :${url.port}${url.pathname} -> ${details.error}`)
  })
  console.log('[Frontend] Desktop API request logging enabled')
}
