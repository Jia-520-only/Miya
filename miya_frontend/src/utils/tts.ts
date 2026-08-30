import { ref, watch } from 'vue'
import API from '@/api/core'
import { proxySetMouth, proxySetState } from '@/utils/live2dProxy'

const isLoggedIn = false

const audio = ref<HTMLAudioElement | null>(null)
export const isPlaying = ref(false)
let maxDurationTimer: number | null = null
let abortController: AbortController | null = null
let currentObjectUrl: string | null = null

const MAX_PLAYBACK_DURATION = 30000

// ── Live2D 口型同步 ──
let mouthSyncTimer: number | null = null
let mouthAudioCtx: AudioContext | null = null
let mouthAnalyser: AnalyserNode | null = null
let mouthSource: MediaElementAudioSourceNode | null = null

function startMouthSync(el: HTMLAudioElement): void {
  try {
    stopMouthSync()
    proxySetState('talking')

    mouthAudioCtx = new AudioContext()
    mouthSource = mouthAudioCtx.createMediaElementSource(el)
    mouthAnalyser = mouthAudioCtx.createAnalyser()
    mouthAnalyser.fftSize = 256
    mouthSource.connect(mouthAnalyser)
    mouthAnalyser.connect(mouthAudioCtx.destination)

    const dataArray = new Float32Array(mouthAnalyser.frequencyBinCount)

    function tick() {
      if (!mouthAnalyser) return
      mouthAnalyser.getFloatTimeDomainData(dataArray)
      let sum = 0
      for (let i = 0; i < dataArray.length; i++) sum += Math.abs(dataArray[i] ?? 0)
      const rms = sum / dataArray.length
      // ParamMouthOpenY: Cubism 口型张开参数
      const mouthOpen = Math.min(1, Math.max(0, rms * 5))
      proxySetMouth({ ParamMouthOpenY: mouthOpen })
      mouthSyncTimer = window.setTimeout(tick, 30)
    }
    tick()
  }
  catch {
    // 降级：使用定时器模拟口型
    let phase = 0
    function tick() {
      phase += 1
      const v = 0.3 + Math.abs(Math.sin(phase * 0.3)) * 0.7
      proxySetMouth({ ParamMouthOpenY: v })
      mouthSyncTimer = window.setTimeout(tick, 60)
    }
    tick()
  }
}

function stopMouthSync(): void {
  proxySetState('idle')
  proxySetMouth({ ParamMouthOpenY: 0 })
  if (mouthSyncTimer) {
    clearTimeout(mouthSyncTimer)
    mouthSyncTimer = null
  }
  try { mouthSource?.disconnect() } catch {}
  try { mouthAudioCtx?.close() } catch {}
  mouthSource = null
  mouthAnalyser = null
  mouthAudioCtx = null
}

// ── Progressive TTS Queue ──
const _queue: string[] = []
let _processingQueue = false

/** 移除 markdown 代码块（```...```）和行内代码（`...`），只保留自然语言文本 */
function stripCodeBlocks(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '') // 移除代码块
    .replace(/`[^`]+`/g, '') // 移除行内代码
    .replace(/\n{3,}/g, '\n\n') // 压缩多余空行
    .trim()
}

export function speak(text: string): Promise<void> {
  _stopCurrent()

  // 移除代码块，只朗读自然语言
  const cleanText = stripCodeBlocks(text)
  if (!cleanText)
    return Promise.resolve()

  // 走 API Server 代理（和 chatStream 同一个 endpoint），后端自动判断走 NagaBusiness 还是本地 edge-tts
  const url = `${API.endpoint}/tts/speech`

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  // 创建 AbortController 以便中途取消 fetch
  abortController = new AbortController()
  const { signal } = abortController

  return fetch(url, {
    method: 'POST',
    headers,
    signal,
    body: JSON.stringify({
      model: isLoggedIn ? 'default' : 'tts-1',
      input: cleanText,
      voice: isLoggedIn ? 'Cherry' : 'zh-CN-XiaoyiNeural',
      speed: 1.0,
      response_format: 'mp3',
    }),
  }).then(async (res) => {
    if (!res.ok)
      throw new Error(`TTS responded ${res.status}`)

    // 如果已被 stop() 中止，不再播放
    if (signal.aborted)
      return

    // ★ 流式播放：用 MediaSource 边收边播，大幅减少首音延迟
    if (typeof MediaSource !== 'undefined' && MediaSource.isTypeSupported('audio/mpeg')) {
      await _streamPlayback(res, signal)
    }
    else {
      // 降级：不支持 MediaSource 的浏览器走原始 blob 方式
      await _blobPlayback(res, signal)
    }
  }).catch((err) => {
    // AbortError 是正常取消，不需要报错
    if (err instanceof DOMException && err.name === 'AbortError')
      return
    cleanup()
    console.error('[TTS] speak failed:', err)
    throw err
  })
}

/** 等待 sourceBuffer 更新完成，同时监听 error 事件防止永远挂起 */
function waitForUpdateEnd(sb: SourceBuffer): Promise<void> {
  return new Promise((resolve, reject) => {
    function onEnd() {
      sb.removeEventListener('error', onErr)
      resolve()
    }
    function onErr() {
      sb.removeEventListener('updateend', onEnd)
      reject(new Error('SourceBuffer error'))
    }
    sb.addEventListener('updateend', onEnd, { once: true })
    sb.addEventListener('error', onErr, { once: true })
  })
}

/** 流式播放——边接收边播放，首音延迟降至 <500ms */
async function _streamPlayback(res: Response, signal: AbortSignal): Promise<void> {
  const mediaSource = new MediaSource()
  const objectUrl = URL.createObjectURL(mediaSource)
  currentObjectUrl = objectUrl
  const el = new Audio(objectUrl)
  audio.value = el

  el.onplay = () => {
    isPlaying.value = true
    startMouthSync(el)
  }
  el.onended = () => {
    cleanup()
  }
  el.onerror = () => {
    cleanup()
  }

  // 设置30秒最大播放时长定时器
  maxDurationTimer = window.setTimeout(() => {
    if (audio.value)
      stop()
  }, MAX_PLAYBACK_DURATION)

  return new Promise<void>((resolve, reject) => {
    mediaSource.addEventListener('sourceopen', async () => {
      const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg')
      const reader = res.body?.getReader()
      if (!reader) {
        cleanup()
        reject(new Error('No response body'))
        return
      }

      let firstChunk = true
      try {
        while (true) {
          if (signal.aborted) {
            await reader.cancel()
            break
          }
          const { done, value } = await reader.read()
          if (done)
            break
          if (!value || value.length === 0)
            continue

          // 等待 sourceBuffer 可写
          if (sourceBuffer.updating) {
            await waitForUpdateEnd(sourceBuffer)
          }
          sourceBuffer.appendBuffer(value)
          await waitForUpdateEnd(sourceBuffer)

          // 收到第一块数据后立即开始播放
          if (firstChunk) {
            firstChunk = false
            el.play().catch(() => {})
          }
        }
      }
      catch (e: any) {
        if (e?.name === 'AbortError' || signal.aborted) { /* 正常取消 */ }
        else { console.warn('[TTS] stream error:', e) }
      }

      // 流结束，关闭 MediaSource
      try {
        if (mediaSource.readyState === 'open') {
          if (sourceBuffer.updating) {
            await waitForUpdateEnd(sourceBuffer)
          }
          mediaSource.endOfStream()
        }
      }
      catch { /* ignore */ }
      resolve()
    }, { once: true })
  })
}

/** 降级播放——完整下载后播放（老浏览器兜底） */
async function _blobPlayback(res: Response, signal: AbortSignal): Promise<void> {
  const blob = await res.blob()
  if (blob.size === 0)
    throw new Error('TTS returned empty audio')
  if (signal.aborted)
    return

  const audioBlob = blob.type.startsWith('audio/') ? blob : new Blob([blob], { type: 'audio/mpeg' })
  const objectUrl = URL.createObjectURL(audioBlob)
  currentObjectUrl = objectUrl
  const el = new Audio(objectUrl)
  audio.value = el

  el.onplay = () => {
    isPlaying.value = true
    startMouthSync(el)
  }
  el.onended = () => {
    cleanup()
  }
  el.onerror = () => {
    cleanup()
  }

  maxDurationTimer = window.setTimeout(() => {
    if (audio.value)
      stop()
  }, MAX_PLAYBACK_DURATION)

  el.play().catch(() => {})
}

function cleanup() {
  stopMouthSync()
  if (maxDurationTimer) {
    clearTimeout(maxDurationTimer)
    maxDurationTimer = null
  }
  isPlaying.value = false
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl)
    currentObjectUrl = null
  }
  if (audio.value) {
    audio.value.onplay = null
    audio.value.onended = null
    audio.value.onerror = null
    audio.value.pause()
    audio.value.removeAttribute('src')
    audio.value.load()
  }
  audio.value = null
}

/** 停止当前播放（不清理队列，内部使用） */
function _stopCurrent() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }

  cleanup()
}

/** 停止所有 TTS（当前播放 + 清空队列） */
export function stop() {
  _queue.length = 0
  _processingQueue = false
  _stopCurrent()
}

/** 逐句入队，按顺序播放（流式 TTS 用） */
export function queueSpeak(text: string): void {
  const clean = stripCodeBlocks(text).trim()
  if (!clean)
    return
  _queue.push(clean)
  if (!_processingQueue)
    _drainQueue()
}

/** 清空待播放队列（不中断当前播放） */
export function clearSpeakQueue(): void {
  _queue.length = 0
}

async function _drainQueue(): Promise<void> {
  if (_queue.length === 0) {
    _processingQueue = false
    return
  }
  _processingQueue = true
  const text = _queue.shift()!
  try {
    await speak(text)
    // 等待当前音频播放完毕
    if (isPlaying.value) {
      await new Promise<void>((resolve) => {
        const unwatch = watch(isPlaying, (val) => {
          if (!val) {
            unwatch()
            resolve()
          }
        })
        setTimeout(() => {
          unwatch()
          resolve()
        }, 35000)
      })
    }
  }
  catch { /* 当前句失败，继续下一句 */ }
  _drainQueue()
}
