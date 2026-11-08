import assert from 'node:assert/strict'
import test from 'node:test'
import { installDesktopRequestLogs } from '../electron/modules/desktop-request-logs.ts'

function harness(run, runtimePorts = null) {
  const handlers = {}
  const output = []
  const webRequest = Object.fromEntries([
    'onBeforeSendHeaders', 'onResponseStarted', 'onBeforeRedirect', 'onCompleted', 'onErrorOccurred',
  ].map(name => [name, (_filter, listener) => { handlers[name] = listener }]))
  const originalLog = console.log
  const originalWarn = console.warn
  console.log = line => output.push(line)
  console.warn = line => output.push(line)
  try {
    installDesktopRequestLogs({ webRequest }, () => runtimePorts)
    assert.ok(output.every(line => /^[\x00-\x7F]*$/.test(line)))
    output.length = 0
    run(handlers, output)
  }
  finally {
    console.log = originalLog
    console.warn = originalWarn
  }
}

function request(handlers, url, id = 1) {
  const details = { id, url, method: 'GET', requestHeaders: {} }
  let response
  handlers.onBeforeSendHeaders(details, result => { response = result })
  return { ...details, requestHeaders: response.requestHeaders }
}

test('tags loopback API requests and prints once as soon as stream headers arrive', () => {
  harness((handlers, output) => {
    const details = request(handlers, 'http://localhost:8000/api/vision/stream')
    assert.equal(details.requestHeaders['X-Miya-Client'], 'desktop')
    handlers.onResponseStarted({ ...details, statusCode: 200 })
    assert.equal(output.length, 1)
    assert.ok(output.every(line => /^[\x00-\x7F]*$/.test(line)))
    assert.match(output[0], /GET :8000\/api\/vision\/stream -> 200/)
    handlers.onCompleted({ ...details, statusCode: 200 })
    assert.equal(output.length, 1)
  })
})

test('does not tag external sites, Vite assets, or the DSH host', () => {
  harness((handlers, output) => {
    for (const url of [
      'http://example.com:8000/api/status', 'http://localhost:5173/src/App.vue',
      'http://localhost:3199/api/status',
      'http://localhost/api/status', 'https://localhost/api/status',
    ]) {
      const details = request(handlers, url)
      assert.deepEqual(details.requestHeaders, {})
      handlers.onResponseStarted({ ...details, statusCode: 200 })
    }
    assert.deepEqual(output, [])
  })
})

test('supports runtime ports and IPv6 WebSocket handshakes', () => {
  harness((handlers, output) => {
    const details = request(handlers, 'ws://[::1]:19800/api/v1/ws')
    assert.equal(details.requestHeaders['X-Miya-Client'], 'desktop')
    handlers.onResponseStarted({ ...details, statusCode: 101 })
    assert.match(output[0], /:19800\/api\/v1\/ws -> 101/)
  }, { management_api: 19800 })
})

test('prints failed connections even when headers were never sent, without URL queries', () => {
  harness((handlers, output) => {
    handlers.onErrorOccurred({
      id: 77, method: 'GET', url: 'http://127.0.0.1:8000/api/chat?token=secret',
      error: 'net::ERR_CONNECTION_REFUSED',
    })
    assert.match(output[0], /ERR_CONNECTION_REFUSED/)
    assert.ok(!output[0].includes('secret'))
  })
})

test('logs redirect and final response without leaking query values', () => {
  harness((handlers, output) => {
    const first = request(handlers, 'http://localhost:8000/api/items?token=secret')
    handlers.onBeforeRedirect({ ...first, statusCode: 307 })
    const redirected = request(handlers, 'http://localhost:8000/api/items/?token=secret')
    handlers.onResponseStarted({ ...redirected, statusCode: 200 })
    handlers.onCompleted({ ...redirected, statusCode: 200 })
    assert.equal(output.length, 2)
    assert.match(output[0], /-> 307/)
    assert.match(output[1], /-> 200/)
    assert.ok(output.every(line => !line.includes('secret')))
  })
})

test('closing an established SSE stream does not produce a false connection error', () => {
  harness((handlers, output) => {
    const details = request(handlers, 'http://localhost:8000/api/vision/stream')
    handlers.onResponseStarted({ ...details, statusCode: 200 })
    handlers.onErrorOccurred({ ...details, error: 'net::ERR_FAILED' })
    assert.equal(output.length, 1)
    assert.match(output[0], /-> 200/)
  })
})
