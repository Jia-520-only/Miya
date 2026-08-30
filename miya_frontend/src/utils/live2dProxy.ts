/**
 * Live2D 统一代理层
 *
 * 自动检测独立窗口模式：
 *  - 如果有 window.live2dAPI → 通过 IPC 驱动独立窗口
 *  - 否则 → 降级到本地 live2dController
 */
import type { Live2dAPI } from '@/electron.d'
import type { Live2dState } from './live2dController'

let _api: Live2dAPI | null = null

function getAPI(): Live2dAPI | null {
  if (_api) return _api
  const w = window as unknown as { live2dAPI?: Live2dAPI }
  if (w.live2dAPI) {
    _api = w.live2dAPI
    return _api
  }
  return null
}

export function isIndependentMode(): boolean {
  return getAPI() !== null
}

// ── 表情 / 情绪 ──

export function proxySetEmotion(emotion: string): void {
  const api = getAPI()
  if (api) {
    api.setEmotion(emotion)
  }
  else {
    // @ts-expect-error dynamic require for runtime resolution
    const { setEmotion } = require('./live2dController')
    setEmotion?.(emotion)
  }
}

export function proxySetSoulEmotion(emotions: Array<{ name: string, intensity: number }>): void {
  const api = getAPI()
  if (api) {
    // 取 intensity 最高的情绪发给独立窗口
    const top = emotions.reduce((a, b) => (a.intensity > b.intensity ? a : b), emotions[0]!)
    if (top) {
      const emotionMap: Record<string, string> = {
        '高兴': 'happy', '开心': 'happy', '喜悦': 'happy', 'happy': 'happy',
        '悲伤': 'sad', '难过': 'sad', '伤心': 'sad', 'sad': 'sad',
        '愤怒': 'angry', '生气': 'angry', 'angry': 'angry',
        '惊讶': 'surprise', '吃惊': 'surprise', 'surprise': 'surprise',
      }
      const emo = emotionMap[top.name] || 'neutral'
      api.setEmotion(emo)
    }
  }
  else {
    // @ts-expect-error dynamic require for runtime resolution
    const { setSoulEmotion } = require('./live2dController')
    setSoulEmotion?.(emotions)
  }
}

// ── 状态 (idle / thinking / talking) ──

export function proxySetState(state: Live2dState): void {
  const api = getAPI()
  if (api) {
    api.setState(state)
  }
  else {
    // live2dState 是 Vue ref，在独立模式下不需要它
    // @ts-expect-error dynamic require for runtime resolution
    const { live2dState } = require('./live2dController')
    if (live2dState) live2dState.value = state
  }
}

// ── 口型 ──

export function proxySetMouth(params: Record<string, number>): void {
  const api = getAPI()
  if (api) {
    // 透传原始参数
    api.setMouth(params)
  }
  // 本地模式下口型由 live2dController 内部 tick 处理
}

// ── 动作 ──

export function proxyTriggerAction(action: string): void {
  const api = getAPI()
  if (api) {
    api.triggerAction(action)
  }
  else {
    // @ts-expect-error dynamic require for runtime resolution
    const { triggerAction } = require('./live2dController')
    triggerAction?.(action)
  }
}

// ── 眼球追踪 ──

export function proxySetTracking(enabled: boolean): void {
  const api = getAPI()
  if (api) {
    api.setTracking(enabled)
  }
  else {
    // @ts-expect-error dynamic require for runtime resolution
    const { startTracking, stopTracking } = require('./live2dController')
    enabled ? startTracking?.() : stopTracking?.()
  }
}

// ── 窗口控制 ──

export function proxyToggleWindow(): void {
  const api = getAPI()
  if (api) api.toggleVisibility()
}

export function proxySetAlwaysOnTop(enabled: boolean): void {
  const api = getAPI()
  if (api) api.setAlwaysOnTop(enabled)
}

export function proxyResetPosition(): void {
  const api = getAPI()
  if (api) api.resetPosition()
}
