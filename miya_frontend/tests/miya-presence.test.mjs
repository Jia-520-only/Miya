/* eslint-disable test/no-import-node-test -- This project uses Node's built-in test runner. */
import assert from 'node:assert/strict'
import test from 'node:test'
import { normalizeMiyaPresence } from '../src/utils/miyaPresence.ts'

test('reads the camelCase response produced by ApiClient', () => {
  assert.deepEqual(normalizeMiyaPresence({
    emotion: { emotionName: '温暖', intensity: 72 },
    memoryStats: { total: 2048 },
    platformInfo: { enabledCount: 3, totalCount: 12 },
  }, { persona: { name: '弥娅' } }), {
    persona: '弥娅',
    emotion: '温暖',
    activity: 72,
    memoryCount: 2048,
    platformCount: 3,
  })
})

test('also supports native backend fields and sums the two memory stores', () => {
  const result = normalizeMiyaPresence({
    emotion: { emotion_name: '平静', intensity: 40 },
    memory_stats: { tide_count: 12, longterm_count: 8 },
    platform_info: { enabled_count: 2 },
  }, { persona: { id: 'gentle' }, soul: { activity: 65 } })
  assert.deepEqual(result, { persona: 'gentle', emotion: '平静', activity: 65, memoryCount: 20, platformCount: 2 })
})

test('preserves actual zeroes and never counts all configured platforms as enabled', () => {
  assert.deepEqual(normalizeMiyaPresence({
    emotion: { intensity: 0 },
    memoryStats: { total: 0, nodeCount: 99 },
    platformInfo: { enabledCount: 0, totalCount: 12 },
  }, { soul: { activity: 0 } }), {
    persona: null,
    emotion: null,
    activity: 0,
    memoryCount: 0,
    platformCount: 0,
  })
  assert.equal(normalizeMiyaPresence({ platformInfo: { totalCount: 12 } }).platformCount, null)
})

test('missing and invalid values remain unknown rather than fabricated readings', () => {
  const empty = { persona: null, emotion: null, activity: null, memoryCount: null, platformCount: null }
  assert.deepEqual(normalizeMiyaPresence(null), empty)
  assert.deepEqual(normalizeMiyaPresence({
    emotion: { intensity: Number.NaN },
    memoryStats: { total: -5 },
    platformInfo: { enabledCount: '3' },
  }), empty)
})

test('finds the dominant emotion without mutating the response and bounds activity', () => {
  const emotions = [{ name: '平静', intensity: 20 }, { name: '喜悦', intensity: 90 }]
  const result = normalizeMiyaPresence({ emotion: { emotions }, memoryStats: { nodeCount: 42 } })
  assert.equal(result.emotion, '喜悦')
  assert.equal(result.activity, 90)
  assert.equal(result.memoryCount, 42)
  assert.equal(emotions[0].name, '平静')
  assert.equal(normalizeMiyaPresence({ emotion: { intensity: 130 } }).activity, 100)
})
