/* eslint-disable test/no-import-node-test -- This project uses Node's built-in test runner. */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { normalizeMiyaPresence } from '../src/utils/miyaPresence.ts'

test('REST camelCase and SSE native keys produce identical readings', () => {
  const native = {
    persona: { id: 'gentle', name: '弥娅' },
    emotion: { name: 'joy', intensity: 72, emotions: [{ name: 'joy', intensity: 72 }] },
    lifecycle: { phase: 'IDLE', message_count: 2, observed_at: '2026-11-09T12:00:00+00:00' },
    memory: { total: 2048, layers: { short_term: 12, long_term: 99, pinned: 0 } },
    platforms: { enabled_count: 3, online_count: 2 },
    sampled_at: '2026-11-09T12:00:00+00:00',
    note: { id: 'note-1', title: '今天的微光', body: '佳，愿这一点安静的光陪你慢慢走。', created_at: '2026-11-09T12:00:00+00:00', persona_name: '弥娅' },
  }
  const camel = {
    ...native,
    lifecycle: { phase: 'IDLE', messageCount: 2, observedAt: native.lifecycle.observed_at },
    memory: { total: 2048, layers: { shortTerm: 12, longTerm: 99, pinned: 0 } },
    platforms: { enabledCount: 3, onlineCount: 2 },
    sampledAt: native.sampled_at,
    note: { ...native.note, createdAt: native.note.created_at, personaName: '弥娅' },
  }
  assert.deepEqual(normalizeMiyaPresence(native), normalizeMiyaPresence(camel))
  const result = normalizeMiyaPresence(native)
  assert.equal(result.emotionIntensity, 72)
  assert.equal(result.memoryLayers.longTerm, 99)
  assert.equal(result.memoryLayers.pinned, 0)
  assert.equal(result.onlinePlatforms, 2)
  assert.equal(result.phase, 'IDLE')
  assert.equal(result.note.id, 'note-1')
})

test('preserves actual zeroes and does not replace missing data with defaults', () => {
  const result = normalizeMiyaPresence({
    emotion: { intensity: 0 },
    memory: { total: 0, layers: { pinned: 0 } },
    platforms: { enabledCount: 0, onlineCount: 0 },
  })
  assert.equal(result.emotionIntensity, 0)
  assert.equal(result.memoryCount, 0)
  assert.equal(result.platformCount, 0)
  assert.equal(result.onlinePlatforms, 0)
  assert.equal(result.memoryLayers.pinned, 0)
  assert.equal(result.memoryLayers.semantic, null)
  assert.equal(normalizeMiyaPresence({ platforms: { totalCount: 12 } }).platformCount, null)
})

test('invalid and legacy fallback readings remain unknown', () => {
  assert.deepEqual(normalizeMiyaPresence({
    emotion: { intensity: Number.NaN },
    memory: { total: -5 },
    platforms: { enabledCount: '3' },
    lifecycle: { phase: 'invented', observedAt: 'invalid' },
    sampledAt: 'invalid',
  }), normalizeMiyaPresence(null))
  const legacy = normalizeMiyaPresence({ emotion: { emotion_name: '平静', intensity: 50 }, memory_stats: { total: 0 } })
  assert.equal(legacy.emotion, null)
  assert.equal(legacy.memoryCount, null)
  assert.equal(legacy.phase, null)
  assert.equal(normalizeMiyaPresence({ emotion: { intensity: 130 } }).emotionIntensity, null)
  assert.equal(normalizeMiyaPresence({ note: { title: 'Incomplete' } }).note, null)
})

function loadScene() {
  const listeners = {}
  const parent = { postMessage() {} }
  const window = {
    addEventListener(type, listener) {
      listeners[type] = listener
    },
    dispatchEvent() {},
  }
  const context = vm.createContext({
    window,
    parent,
    URL,
    URLSearchParams,
    Event,
    location: { search: '?miya=1', protocol: 'http:', origin: 'http://localhost', href: 'http://localhost/haloflux/lab.html?miya=1' },
    matchMedia: () => ({ matches: false }),
    Image: class {},
  })
  vm.runInContext(readFileSync(new URL('../public/haloflux/miya.js', import.meta.url), 'utf8'), context)
  return {
    scene: window.MiyaFlux,
    send: (data, origin = 'http://localhost') => listeners.message({ source: parent, origin, data: { type: 'miya:presence', ...data } }),
  }
}

test('the scene pulses for new events but not initial load or reconnection', () => {
  const { scene, send } = loadScene()
  send({ online: true, memoryCount: 100, messageCount: 8, memoryLayers: { pinned: 0 } })
  assert.equal(scene.state.echo, 0)
  assert.equal(scene.state.memoryLayers.pinned, 0)
  assert.equal(scene.state.memoryLayers.semantic, null)
  send({ online: true, memoryCount: 101, messageCount: 8 })
  assert.equal(scene.state.echo, 1)
  scene.state.echo = 0
  send({ online: false })
  send({ online: true, memoryCount: 120, messageCount: 12 })
  assert.equal(scene.state.echo, 0)
  send({ online: true, memoryCount: 120, messageCount: 13 })
  assert.ok(scene.state.echo > 0)
})

test('the scene rejects foreign messages and softens its rhythm during sleep', () => {
  const { scene, send } = loadScene()
  send({ online: true, memoryCount: 999 }, 'https://untrusted.example')
  assert.equal(scene.state.online, false)
  send({ online: true, phase: 'RUNNING', emotionIntensity: 80 })
  const config = {}
  for (let index = 0; index < 30; index++) scene.update(config, 0.1)
  const awakeTempo = config.tempo
  send({ online: true, phase: 'SLEEP', emotionIntensity: 80 })
  for (let index = 0; index < 30; index++) scene.update(config, 0.1)
  assert.ok(config.tempo < awakeTempo)
})

test('composition changes keep the complete ring visible and intentionally crop the closeup', () => {
  const { scene, send } = loadScene()
  for (const [width, height] of [[1280, 720], [310, 440], [740, 580]]) {
    send({ composition: 'complete', mode: 'quiet' })
    const full = scene.layout(width, height)
    assert.ok(full.x - full.outerRadius >= 0)
    assert.ok(full.x + full.outerRadius <= width)
    assert.ok(full.y - full.outerRadius >= 0)
    assert.ok(full.y + full.outerRadius <= height)
    send({ composition: 'closeup' })
    const closeup = scene.layout(width, height)
    assert.ok(closeup.x - closeup.outerRadius < 0)
    assert.ok(closeup.radius > full.radius)
    assert.equal(scene.state.mode, 'quiet')
    send({ composition: 'invalid' })
    assert.equal(scene.state.composition, 'closeup')
  }
})

test('per-layer changes pulse only known readings and micro panels render their actual sector', () => {
  const { scene, send } = loadScene()
  send({ online: true, memoryLayers: { dialogue: 100, pinned: 0 } })
  assert.equal(scene.state.layerEcho.dialogue, undefined)
  send({ online: true, memoryLayers: { dialogue: 101, pinned: 0, semantic: 10 } })
  assert.equal(scene.state.layerEcho.dialogue, 1)
  assert.equal(scene.state.layerEcho.semantic, undefined)
  const texts = []
  const ctx = {
    fillRect() {},
    fillText(value) {
      texts.push(value)
    },
    beginPath() {},
    moveTo() {},
    lineTo() {},
    stroke() {},
  }
  scene.renderTelemetry(ctx, { a: -Math.PI / 3 }, 64, 40, 0)
  assert.deepEqual(texts, ['对话', '101'])
  send({ online: false })
  assert.equal(scene.state.layerEcho.dialogue, 0)
  texts.length = 0
  scene.renderTelemetry(ctx, { a: -Math.PI / 3 }, 64, 40, 0)
  assert.deepEqual(texts, ['对话', '—'])
  send({ online: true, memoryLayers: { dialogue: 200 } })
  assert.equal(scene.state.layerEcho.dialogue, 0)
})

test('closeup camera pushes in, travels along the rim, and holds with a paused clock', () => {
  const { scene, send } = loadScene()
  send({ composition: 'closeup' })
  const start = scene.camera(1280, 720)
  for (let i = 0; i < 75; i++) scene.update({}, 0.1)
  const approach = scene.camera(1280, 720)
  assert.ok(approach.z > start.z)
  assert.notEqual(approach.y, start.y)
  for (let i = 0; i < 75; i++) scene.update({}, 0.1)
  const travel = scene.camera(1280, 720)
  assert.ok(travel.y > approach.y)
  for (let i = 0; i < 10; i++) scene.update({}, 0)
  assert.deepEqual(scene.camera(1280, 720), travel)
  scene.state.cameraTime = -0.001
  assert.ok(Number.isFinite(scene.camera(1280, 720).z))
})

test('observatory micro panels show actual runtime excerpts and omit memory card overlays', () => {
  const { scene, send } = loadScene()
  send({ composition: 'complete', online: true, runtimeLogs: [{ seq: 10, name: 'Tool.web_search', text: '检索完成' }] })
  const texts = []
  const context = {
    fillRect() {},
    fillText(value) {
      texts.push(value)
    },
  }
  scene.renderTelemetry(context, { index: 0, a: 0 }, 64, 40, 0)
  assert.deepEqual(texts, ['Tool.web_search', '检索完成'])
  texts.length = 0
  send({ composition: 'closeup', runtimeLogs: [] })
  scene.renderTelemetry(context, { index: 0, a: 0 }, 64, 40, 0)
  assert.deepEqual(texts, [])
})

test('composition transitions preserve the visible ring and support reversing mid-flight', () => {
  const { scene, send } = loadScene()
  const width = 1280
  const height = 720
  const screen = () => {
    const layout = scene.geometry
    const camera = scene.camera(width, height)
    scene.publishGeometry((layout.x - camera.x) * camera.z + width / 2, (layout.y - camera.y) * camera.z + height / 2, camera.z)
    return scene.screenGeometry
  }
  const matches = (a, b) => {
    for (const key of ['x', 'y', 'radius'])
      assert.ok(Math.abs(a[key] - b[key]) < 0.001, `${key} jumped on composition change`)
  }
  send({ composition: 'complete' })
  scene.layout(width, height)
  const full = screen()
  send({ composition: 'closeup' })
  scene.layout(width, height)
  matches(full, screen())
  scene.update({}, 0.8)
  const halfway = screen()
  assert.ok(halfway.radius > full.radius)
  send({ composition: 'complete' })
  scene.layout(width, height)
  matches(halfway, screen())
  scene.update({}, 1.7)
  matches(full, screen())
  assert.equal(scene.state.transition, null)
  send({ composition: 'closeup', paused: true })
  assert.equal(scene.state.transition, null)
})
