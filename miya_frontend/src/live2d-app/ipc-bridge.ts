import type { EmotionCategory, Live2dState } from '../utils/live2dController'

// ─── 驱动独立 Live2D 窗口 ──────────────────────────────

export interface Live2dIPC {
  setEmotion: (emotion: string) => void
  setState: (state: string) => void
  triggerAction: (action: string) => void
  setTracking: (enabled: boolean) => void
  switchClothes: (clothes: string) => void
  toggleVisibility: () => void
  setAlwaysOnTop: (enabled: boolean) => void
  resetPosition: () => void
  onReady: (callback: () => void) => () => void
  onModelInfo: (callback: (info: { faceX: number, faceY: number }) => void) => () => void
}

type Live2dControl = {
  setEmotion: (emo: string) => void
  setState: (state: Live2dState) => void
  setMouth: (params: Record<string, number>) => void
  triggerAction: (action: string) => void
  setTracking: (enabled: boolean) => void
}

let _live2dIPCApi: Live2dIPC | null = null
let _control: Live2dControl | null = null

function getLive2dAPI(): Live2dIPC | null {
  if (_live2dIPCApi) return _live2dIPCApi

  const w = window as unknown as { live2dAPI?: Live2dIPC }
  if (w.live2dAPI) {
    _live2dIPCApi = w.live2dAPI
    return _live2dIPCApi
  }
  return null
}

function getLive2dControl(): Live2dControl | null {
  if (_control) return _control

  const w = window as unknown as { __live2dControl?: Live2dControl }
  if (w.__live2dControl) {
    _control = w.__live2dControl
    return _control
  }
  return null
}

// ─── 从主窗口驱动独立 Live2D ───────────────────────────

export function live2dSetEmotion(emotion: string): void {
  const api = getLive2dAPI()
  if (api) {
    api.setEmotion(emotion)
  }
  else {
    const ctrl = getLive2dControl()
    if (ctrl) ctrl.setEmotion(emotion)
  }
}

export function live2dSetState(state: Live2dState): void {
  const api = getLive2dAPI()
  if (api) {
    api.setState(state)
  }
  else {
    const ctrl = getLive2dControl()
    if (ctrl) ctrl.setState(state)
  }
}

export function live2dSetMouth(params: Record<string, number>): void {
  const ctrl = getLive2dControl()
  if (ctrl) ctrl.setMouth(params)
}

export function live2dTriggerAction(action: string): void {
  const api = getLive2dAPI()
  if (api) {
    api.triggerAction(action)
  }
  else {
    const ctrl = getLive2dControl()
    if (ctrl) ctrl.triggerAction(action)
  }
}

export function live2dSetTracking(enabled: boolean): void {
  const api = getLive2dAPI()
  if (api) {
    api.setTracking(enabled)
  }
  else {
    const ctrl = getLive2dControl()
    if (ctrl) ctrl.setTracking(enabled)
  }
}

export function live2dSwitchClothes(clothes: string): void {
  const api = getLive2dAPI()
  if (api) api.switchClothes(clothes)
}

export function live2dToggleWindow(): void {
  const api = getLive2dAPI()
  if (api) api.toggleVisibility()
}

export function live2dToggleAlwaysOnTop(enabled: boolean): void {
  const api = getLive2dAPI()
  if (api) api.setAlwaysOnTop(enabled)
}

export function live2dResetPosition(): void {
  const api = getLive2dAPI()
  if (api) api.resetPosition()
}

export function live2dOnReady(cb: () => void): () => void {
  const api = getLive2dAPI()
  if (api) return api.onReady(cb)
  return () => {}
}

export function live2dOnModelInfo(cb: (info: { faceX: number, faceY: number }) => void): () => void {
  const api = getLive2dAPI()
  if (api) return api.onModelInfo(cb)
  return () => {}
}
