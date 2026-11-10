/* eslint-disable test/no-import-node-test -- Uses the project's Node test runner. */
import assert from 'node:assert/strict'
import test from 'node:test'
import { filterRuntimeLogs, normalizeRuntimeLog, reduceRuntimePayload, runtimeExcerpt, runtimeTelemetry } from '../src/utils/miyaRuntimeLogs.ts'

const entry = (seq, name = 'Miya.Spine', text = '运行事件', extra = {}) => ({ seq, ts: '2026-11-10T08:00:00.000', name, text, level: 'INFO', ...extra })

test('routes memory, tool execution and perception by emitting module', () => {
  for (const [name, expected] of [['Miya.MemoryBus', 'memory'], ['memory.historian.worker', 'memory'], ['Tool.memory_query', 'memory'], ['Tool.web_search', 'execution'], ['core.ai_client', 'execution'], ['Miya.Spine', 'execution'], ['Miya.Platform.OneBot', 'connection'], ['core.multi_vision_analyzer', 'connection']]) {
    assert.equal(normalizeRuntimeLog(entry(1, name), false, 1000).category, expected)
  }
  assert.equal(normalizeRuntimeLog(entry(1, 'core.ai_client', '[TTS] 播放中'), false, 1000).category, 'connection')
  assert.equal(normalizeRuntimeLog(entry(1, 'stdout', '[MemoryBus] 维护启动'), false, 1000).category, 'memory')
})

test('filters access noise, preserves warnings, strips ANSI and rejects malformed logs', () => {
  for (const name of ['uvicorn.access', 'httpx', 'Miya.DesktopFrontend'])
    assert.equal(normalizeRuntimeLog(entry(1, name), false, 0), null)
  assert.ok(normalizeRuntimeLog(entry(1, 'Miya.DesktopFrontend', '请求失败', { level: 'ERROR' }), false, 0))
  assert.equal(normalizeRuntimeLog(entry(1, 'stdout', 'GET /api/observatory/snapshot HTTP/1.1 200'), false, 0), null)
  assert.equal(normalizeRuntimeLog(entry(1, 'Miya.Spine', '\x1B[32mhello\x1B[0m\x00'), false, 0).text, 'hello')
  for (const bad of [null, {}, entry(-1), entry(1, 'Miya.Spine', '', { ts: 'bad' }), entry(1, 'Miya.Spine', 12)])
    assert.equal(normalizeRuntimeLog(bad, false, 0), null)
})

test('initial and resumed history never becomes new event activity', () => {
  const initial = reduceRuntimePayload([], 0, { type: 'init', entries: [entry(1)], latest_seq: 1 }, 100)
  assert.equal(initial.entries[0].historical, true)
  const resumed = reduceRuntimePayload(initial.entries, 1, { type: 'logs', historical: true, entries: [entry(2)] }, 200)
  assert.equal(resumed.entries[1].historical, true)
  const live = reduceRuntimePayload(resumed.entries, 2, { type: 'logs', entries: [entry(3)] }, 300)
  assert.equal(live.entries[2].historical, false)
  assert.equal(live.entries[2].receivedAt, 300)
})

test('deduplicates sequence numbers, sorts each batch and advances past filtered entries', () => {
  const result = reduceRuntimePayload([], 0, { type: 'logs', entries: [entry(3), entry(1), entry(3), entry(2), entry(9, 'uvicorn.access')] }, 100)
  assert.deepEqual(result.entries.map(item => item.seq), [1, 2, 3])
  assert.equal(result.cursor, 9)
  assert.equal(reduceRuntimePayload(result.entries, 9, { type: 'logs', entries: [entry(3), entry(10)] }, 200).entries.length, 4)
})

test('caps each category independently and resets after a backend buffer reset', () => {
  const logs = Array.from({ length: 900 }, (_, i) => entry(i + 1, ['Miya.MemoryBus', 'Tool.web_search', 'Miya.Platform.OneBot'][i % 3]))
  const result = reduceRuntimePayload([], 0, { type: 'logs', entries: logs }, 100)
  assert.equal(result.entries.length, 480)
  assert.equal(result.cursor, 900)
  const reset = reduceRuntimePayload(result.entries, 900, { type: 'reset', entries: [entry(1)], latest_seq: 1 }, 200)
  assert.equal(reset.cursor, 1)
  assert.equal(reset.entries.length, 1)
  assert.equal(reset.entries[0].historical, true)
})

test('excerpt collapses multiline log text without altering retained original', () => {
  const log = normalizeRuntimeLog(entry(1, 'Miya.MemoryBus', '[Miya.MemoryBus] INFO: 维护完成\n  12 条'), false, 0)
  assert.equal(runtimeExcerpt(log), '维护完成 12 条')
  assert.ok(log.text.includes('\n'))
  assert.equal(runtimeExcerpt(log, 4), '维护完成…')
})

test('search combines module and content terms while severity preserves error diagnostics', () => {
  const logs = [
    normalizeRuntimeLog(entry(1, 'Tool.web_search', '星图查询完成'), false, 0),
    normalizeRuntimeLog(entry(2, 'Tool.web_search', '星图查询超时', { level: 'WARNING' }), false, 0),
    normalizeRuntimeLog(entry(3, 'Miya.MemoryBus', '星图索引失败\n保留诊断', { level: 'ERROR' }), false, 0),
  ]
  assert.deepEqual(filterRuntimeLogs(logs, '  WEB_SEARCH 星图 ', 'all').map(log => log.seq), [1, 2])
  assert.deepEqual(filterRuntimeLogs(logs, '', 'warning').map(log => log.seq), [2, 3])
  assert.deepEqual(filterRuntimeLogs(logs, '诊断', 'error').map(log => log.seq), [3])
  assert.deepEqual(filterRuntimeLogs(logs, '不存在', 'all'), [])
  assert.equal(logs[2].text, '星图索引失败\n保留诊断')
})

test('main-ring excerpts retain quiet categories during a burst of execution logs', () => {
  const logs = [
    normalizeRuntimeLog(entry(1, 'Miya.MemoryBus'), false, 0),
    normalizeRuntimeLog(entry(2, 'Miya.Platform.OneBot'), false, 0),
    ...Array.from({ length: 100 }, (_, i) => normalizeRuntimeLog(entry(i + 3, 'Tool.web_search'), false, 0)),
  ]
  const telemetry = runtimeTelemetry(logs)
  assert.equal(telemetry.filter(log => log.category === 'execution').length, 8)
  assert.equal(telemetry.filter(log => log.category === 'memory').length, 1)
  assert.equal(telemetry.filter(log => log.category === 'connection').length, 1)
  assert.equal(telemetry.at(-1).seq, 102)
  assert.equal(logs.length, 102)
})
