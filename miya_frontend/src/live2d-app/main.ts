import * as PIXI from 'pixi.js'
import { install as installUnsafeEval } from '@pixi/unsafe-eval'
import type { Live2DModel } from 'pixi-live2d-display/cubism4'
import { ensureLive2dCoreLoaded } from '../utils/live2dCoreLoader'
import type { ActionsData, ExpressionDef } from './standalone-controller'
import { initStandaloneController, destroyStandaloneController } from './standalone-controller'

;(window as Window & typeof globalThis & { PIXI: typeof PIXI }).PIXI = PIXI
installUnsafeEval(PIXI)

const SSAA = 1.5

let app: PIXI.Application
let nativeWidth = 0
let nativeHeight = 0
let resizeObserver: ResizeObserver | null = null
let activeModel: Live2DModel | null = null
let modelScale = 1

interface WindowConfig {
  bgColor: string
  bgAlpha: number
  visible: boolean
  clickThrough: boolean
  modelScale: number
}

function layoutCanvas(canvas: HTMLCanvasElement) {
  const rw = canvas.clientWidth * SSAA
  const rh = canvas.clientHeight * SSAA
  canvas.width = rw
  canvas.height = rh
}

function relayoutModel(model: Live2DModel, canvas: HTMLCanvasElement) {
  if (nativeWidth === 0) return
  const cw = canvas.width
  const ch = canvas.height
  const s = Math.min(cw / nativeWidth, ch / nativeHeight) * 0.85 * modelScale
  model.scale.set(s)
  model.x = (cw - nativeWidth * s) / 2
  model.y = (ch - nativeHeight * s) / 2
}

async function boot(): Promise<void> {
  const canvas = document.getElementById('live2d-canvas') as HTMLCanvasElement | null
  if (!canvas) {
    console.error('[Live2D App] canvas not found')
    return
  }

  layoutCanvas(canvas)
  console.log(`[Live2D App] canvas buffer: ${canvas.width}x${canvas.height}`)

  const ipc = (window as unknown as {
    live2dIPC?: {
      getActiveModel?: () => Promise<string | null>
      getConfig?: () => Promise<WindowConfig>
      send: (channel: string, ...args: unknown[]) => void
    }
  }).live2dIPC
  let startupConfig: WindowConfig = { bgColor: '#000000', bgAlpha: 0, visible: true, clickThrough: false, modelScale: 100 }
  try {
    startupConfig = { ...startupConfig, ...await ipc?.getConfig?.() }
  }
  catch { /* use safe defaults */ }
  const startupColor = parseInt(String(startupConfig.bgColor).replace('#', ''), 16)
  modelScale = Math.max(0.4, Math.min(4, Number(startupConfig.modelScale || 100) / 100))

  app = new PIXI.Application({
    view: canvas,
    width: canvas.width,
    height: canvas.height,
    antialias: true,
    backgroundColor: startupColor,
    backgroundAlpha: startupConfig.bgAlpha,
    clearBeforeRender: true,
    useContextAlpha: true,
  })

  await ensureLive2dCoreLoaded()
  console.log('[Live2D App] Cubism Core loaded, loading model...')

  try {
    const modelSource = await ipc?.getActiveModel?.() ?? null
    if (!modelSource) throw new Error('尚未安装 Live2D 角色包，请在设置中导入模型文件夹')
    // Cubism Core must exist before the cubism4 adapter module is evaluated.
    const { Live2DModel } = await import('pixi-live2d-display/cubism4')
    const rawModel = await Live2DModel.from(modelSource)
    activeModel = rawModel

    rawModel.autoInteract = false
    app.stage.addChild(rawModel)

    // 必须在 stage 上才能读到正确的像素尺寸
    nativeWidth = rawModel.width > 5000 ? rawModel.internalModel.width : rawModel.width
    nativeHeight = rawModel.height > 5000 ? rawModel.internalModel.height : rawModel.height

    relayoutModel(rawModel, canvas)

    // Keep the WebGL backing buffer in sync with the real window size. Without
    // this, Electron stretches the original 400x600 canvas and the model blurs.
    resizeObserver = new ResizeObserver(() => {
      const width = Math.max(1, Math.round(canvas.clientWidth * SSAA))
      const height = Math.max(1, Math.round(canvas.clientHeight * SSAA))
      if (app.renderer.width === width && app.renderer.height === height) return
      app.renderer.resize(width, height)
      relayoutModel(rawModel, canvas)
    })
    resizeObserver.observe(canvas)

    // Drag anywhere on the model when click-through is off. Pointer capture
    // keeps movement smooth even while the transparent window itself moves.
    let dragging = false
    canvas.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return
      dragging = true
      canvas.setPointerCapture(event.pointerId)
      const ipc = (window as unknown as { live2dIPC?: { send: (ch: string, ...args: unknown[]) => void } }).live2dIPC
      ipc?.send('live2d:dragStart', event.screenX, event.screenY)
    })
    canvas.addEventListener('pointermove', (event) => {
      if (!dragging) return
      const ipc = (window as unknown as { live2dIPC?: { send: (ch: string, ...args: unknown[]) => void } }).live2dIPC
      ipc?.send('live2d:dragMove', event.screenX, event.screenY)
    })
    const stopDragging = () => {
      if (!dragging) return
      dragging = false
      const ipc = (window as unknown as { live2dIPC?: { send: (ch: string, ...args: unknown[]) => void } }).live2dIPC
      ipc?.send('live2d:dragEnd')
    }
    canvas.addEventListener('pointerup', stopDragging)
    canvas.addEventListener('pointercancel', stopDragging)

    console.log('[Live2D App] Model loaded:', nativeWidth, 'x', nativeHeight, 'scale:', rawModel.scale.x, 'children:', app.stage.children.length)

    try {
      // Every asset is resolved relative to the selected model instead of a built-in character path.
      const expressions: ExpressionDef[] = []
      let actions: ActionsData | null = null
      try {
        const modelResponse = await fetch(modelSource)
        if (!modelResponse.ok) throw new Error(`model3.json returned ${modelResponse.status}`)
        const modelJson = await modelResponse.json()
        const expDefs: Array<{ Name?: string, File?: string }> = modelJson?.FileReferences?.Expressions || []
        for (const def of expDefs) {
          if (!def?.File) continue
          try {
            const r = await fetch(new URL(def.File, modelSource).toString())
            if (r.ok) {
              const json = await r.json()
              expressions.push({
                name: (def.Name || def.File.replace(/\.exp3\.json$/i, '')).toLowerCase(),
                fadeInTime: Number(json.FadeInTime ?? 0.3),
                params: (json.Parameters ?? []).map((item: any) => ({
                  Id: String(item.Id),
                  Value: Number(item.Value),
                  Blend: item.Blend === 'Multiply' || item.Blend === 'Overwrite' ? item.Blend : 'Add',
                })),
              })
            }
          }
          catch { /* skip unavailable expression file */ }
        }
        // Miya actions are an optional extension, not part of the Cubism
        // model format. Only request them when the model explicitly opts in;
        // ordinary third-party packages should not emit a harmless 404.
        const actionsFile = modelJson?.FileReferences?.MiyaActions ?? modelJson?.MiyaActions
        if (typeof actionsFile === 'string' && actionsFile.trim()) {
          const actionsResponse = await fetch(new URL(actionsFile, modelSource).toString())
          if (!actionsResponse.ok) throw new Error(`MiyaActions returned ${actionsResponse.status}`)
          actions = await actionsResponse.json() as ActionsData
        }
      }
      catch (error) { console.warn('[Live2D App] Optional controller assets unavailable:', error) }
      await initStandaloneController(rawModel, actions, expressions)
    }
    catch {
      console.warn('[Live2D App] actions/expressions not available')
      await initStandaloneController(rawModel, null, [])
    }

    startIPCListener()
    if (startupConfig.visible) startYinmeiPolling()
    notifyLive2dReady()
    console.log('[Live2D App] Ready!')
  }
  catch (err) {
    console.error('[Live2D App] Model load failed:', err)
  }
}

function getControl() {
  const w = window as unknown as {
    __live2dControl?: {
      setEmotion(e: string): void
      setState(s: string): void
      setMouth(p: Record<string, number>): void
      triggerAction(a: string): void
      setTracking(e: boolean): void
      setTrackingTarget(x: number, y: number, active?: boolean): void
    }
  }
  return w.__live2dControl ?? null
}

function startIPCListener(): void {
  const ctrl = getControl()
  if (!ctrl) return
  const ipc = (window as unknown as {
    live2dIPC?: { on: (ch: string, h: (...args: unknown[]) => void) => void }
  }).live2dIPC
  if (!ipc) return

  ipc.on('live2d:emotion', (emotion: unknown) => ctrl.setEmotion(emotion as string))
  ipc.on('live2d:state', (state: unknown) => ctrl.setState(state as string))
  ipc.on('live2d:mouth', (params: unknown) => ctrl.setMouth(params as Record<string, number>))
  ipc.on('live2d:action', (action: unknown) => ctrl.triggerAction(action as string))
  ipc.on('live2d:tracking', (enabled: unknown) => ctrl.setTracking(enabled as boolean))
  ipc.on('live2d:cursor', (point: unknown) => {
    const value = point as { x?: unknown, y?: unknown, active?: unknown }
    ctrl.setTrackingTarget(Number(value?.x), Number(value?.y), value?.active !== false)
  })
  ipc.on('live2d:background', (data: unknown) => {
    const d = data as { color: string; alpha: number }
    if (app && app.renderer) {
      app.renderer.backgroundColor = parseInt(String(d.color), 16)
      app.renderer.backgroundAlpha = d.alpha
    }
  })
  ipc.on('live2d:modelScale', (scale: unknown) => {
    modelScale = Math.max(0.4, Math.min(4, Number(scale) / 100 || 1))
    const canvas = document.getElementById('live2d-canvas') as HTMLCanvasElement | null
    if (activeModel && canvas) relayoutModel(activeModel, canvas)
  })
  ipc.on('live2d:visibilityChanged', (visible: unknown) => {
    if (visible) {
      startYinmeiPolling()
    } else {
      stopYinmeiPolling()
    }
  })
  console.log('[Live2D App] IPC listener started')
}

function notifyLive2dReady(): void {
  try {
    const ipc = (window as unknown as {
      live2dIPC?: { send: (ch: string, ...args: unknown[]) => void }
    }).live2dIPC
    if (ipc) ipc.send('live2d:ready')
  }
  catch { /* ignore */ }
}

let _yinmeiPollTimer: ReturnType<typeof setInterval> | null = null
function stopYinmeiPolling(): void {
  if (_yinmeiPollTimer) {
    clearInterval(_yinmeiPollTimer)
    _yinmeiPollTimer = null
    console.log('[Live2D App] Yinmei polling stopped')
  }
}

function startYinmeiPolling(): void {
  stopYinmeiPolling()
  const apiPort = (window as any).__MIYA_API_PORT__ || Number(import.meta.env.VITE_API_PORT) || 9800
  const pollUrl = `http://127.0.0.1:${apiPort}/api/yinmei/live2d/commands`

  _yinmeiPollTimer = setInterval(async () => {
    try {
      const resp = await fetch(pollUrl)
      if (!resp.ok) return
      const data = await resp.json()

      const cmds = data.commands || []
      if (cmds.length === 0) return

      const ctrl = getControl()
      if (!ctrl) return

      for (const cmd of cmds) {
        switch (cmd.type) {
          case 'emotion':
            ctrl.setEmotion(cmd.value)
            break
          case 'state':
            ctrl.setState(cmd.value)
            break
          case 'mouth':
            ctrl.setMouth(cmd.value)
            break
          case 'action':
            ctrl.triggerAction(cmd.value)
            break
        }
      }
    }
    catch { /* API not ready yet */ }
  }, 500)

  console.log('[Live2D App] Yinmei polling started:', pollUrl)
}

window.addEventListener('beforeunload', () => {
  resizeObserver?.disconnect()
  if (_yinmeiPollTimer) {
    clearInterval(_yinmeiPollTimer)
    _yinmeiPollTimer = null
  }
  destroyStandaloneController()
  activeModel = null
  if (app) app.destroy(true, { children: true })
})

boot().catch(err => console.error('[Live2D App] Boot failed:', err))
