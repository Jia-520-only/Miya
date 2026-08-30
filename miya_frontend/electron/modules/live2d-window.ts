import { dirname, join, resolve } from 'node:path'
import fs from 'node:fs'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { app, BrowserWindow, screen } from 'electron'
import type { Live2DCallback } from './types'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let live2dWindow: BrowserWindow | null = null
let live2dCallback: Live2DCallback | null = null
let live2dClickThrough = false

const DEFAULT_SIZE = { width: 400, height: 600 }

export interface Live2dWindowConfig {
  bgColor: string
  bgAlpha: number
  windowScale: number
  modelScale: number
  alwaysOnTop: boolean
  visible: boolean
  clickThrough: boolean
  mouseTracking: boolean
  mouseIdleReturn: boolean
  bounds: { x: number, y: number, width: number, height: number } | null
}

const DEFAULT_CONFIG: Live2dWindowConfig = {
  bgColor: '#000000',
  bgAlpha: 0,
  windowScale: 100,
  modelScale: 100,
  alwaysOnTop: true,
  visible: true,
  clickThrough: false,
  mouseTracking: false,
  mouseIdleReturn: true,
  bounds: null,
}

function configPath(): string {
  return resolve(app.getPath('userData'), 'live2d-window.json')
}

export function getLive2dWindowConfig(): Live2dWindowConfig {
  try {
    const saved = JSON.parse(fs.readFileSync(configPath(), 'utf8')) as Partial<Live2dWindowConfig>
    return {
      bgColor: /^#[0-9a-f]{6}$/i.test(saved.bgColor ?? '') ? saved.bgColor! : DEFAULT_CONFIG.bgColor,
      bgAlpha: Number.isFinite(saved.bgAlpha) ? Math.max(0, Math.min(1, saved.bgAlpha!)) : DEFAULT_CONFIG.bgAlpha,
      windowScale: Number.isFinite(saved.windowScale) ? Math.max(40, Math.min(400, saved.windowScale!)) : DEFAULT_CONFIG.windowScale,
      modelScale: Number.isFinite(saved.modelScale) ? Math.max(40, Math.min(400, saved.modelScale!)) : DEFAULT_CONFIG.modelScale,
      alwaysOnTop: typeof saved.alwaysOnTop === 'boolean' ? saved.alwaysOnTop : DEFAULT_CONFIG.alwaysOnTop,
      visible: typeof saved.visible === 'boolean' ? saved.visible : DEFAULT_CONFIG.visible,
      clickThrough: typeof saved.clickThrough === 'boolean' ? saved.clickThrough : DEFAULT_CONFIG.clickThrough,
      mouseTracking: typeof saved.mouseTracking === 'boolean' ? saved.mouseTracking : DEFAULT_CONFIG.mouseTracking,
      mouseIdleReturn: typeof saved.mouseIdleReturn === 'boolean' ? saved.mouseIdleReturn : DEFAULT_CONFIG.mouseIdleReturn,
      bounds: isValidBounds(saved.bounds) ? saved.bounds : null,
    }
  }
  catch {
    return { ...DEFAULT_CONFIG }
  }
}

function isValidBounds(value: unknown): value is { x: number, y: number, width: number, height: number } {
  if (!value || typeof value !== 'object') return false
  const bounds = value as Record<string, unknown>
  return ['x', 'y', 'width', 'height'].every(key => Number.isFinite(bounds[key]))
    && Number(bounds.width) >= 200 && Number(bounds.height) >= 300
}

function restoreBounds(config: Live2dWindowConfig): { x: number, y: number, width: number, height: number } {
  const initialWidth = Math.round(DEFAULT_SIZE.width * config.windowScale / 100)
  const initialHeight = Math.round(DEFAULT_SIZE.height * config.windowScale / 100)
  if (!config.bounds) {
    const { workArea } = screen.getPrimaryDisplay()
    return { x: workArea.x + workArea.width - initialWidth - 20, y: workArea.y + workArea.height - initialHeight - 60, width: initialWidth, height: initialHeight }
  }
  const saved = config.bounds
  const display = screen.getDisplayMatching(saved)
  const area = display.workArea
  const width = Math.min(saved.width, DEFAULT_SIZE.width * 4)
  const height = Math.min(saved.height, DEFAULT_SIZE.height * 4)
  // Oversized transparent character windows are valid. Keep only an 80px
  // grab area visible instead of shrinking them to the display work area.
  const x = Math.max(area.x - width + 80, Math.min(saved.x, area.x + area.width - 80))
  const y = Math.max(area.y - height + 80, Math.min(saved.y, area.y + area.height - 80))
  return { x, y, width, height }
}

export function updateLive2dWindowConfig(patch: Partial<Live2dWindowConfig>): Live2dWindowConfig {
  const next = { ...getLive2dWindowConfig(), ...patch }
  fs.writeFileSync(configPath(), JSON.stringify(next, null, 2), 'utf8')
  return next
}

function resolveLive2dUrl(): string {
  if (process.env.VITE_DEV_SERVER_URL) {
    const devBase = process.env.VITE_DEV_SERVER_URL.replace(/\/+$/, '')
    return `${devBase}/src/live2d-app/index.html`
  }

  // Production: Vite multi-page build outputs live2d-app under dist/src/live2d-app/
  const distPath = resolve(__dirname, '..', 'dist', 'src', 'live2d-app', 'index.html')
  if (fs.existsSync(distPath)) {
    return `file://${distPath}`
  }

  // Fallback: old path (for backwards compatibility)
  const legacyPath = resolve(__dirname, '..', 'dist', 'live2d-app', 'index.html')
  if (fs.existsSync(legacyPath)) {
    return `file://${legacyPath}`
  }

  // Development fallback: source path
  const srcPath = resolve(__dirname, '..', '..', 'src', 'live2d-app', 'index.html')
  if (fs.existsSync(srcPath)) {
    return `file://${srcPath}`
  }

  console.warn('[Live2D Window] live2d-app/index.html not found, window will not load')
  return ''
}

export function createLive2dWindow(
  callback?: Live2DCallback,
  alwaysOnTop = true,
): BrowserWindow | null {
  live2dCallback = callback ?? live2dCallback

  if (live2dWindow && !live2dWindow.isDestroyed()) {
    live2dWindow.setAlwaysOnTop(alwaysOnTop)
    live2dWindow.show()
    return live2dWindow
  }

  const url = resolveLive2dUrl()
  if (!url) return null

  const config = getLive2dWindowConfig()
  const initialBounds = restoreBounds(config)
  const savedBounds = config.bounds ? { ...initialBounds } : null

  live2dWindow = new BrowserWindow({
    ...initialBounds,
    minWidth: 200,
    minHeight: 300,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    thickFrame: false,
    roundedCorners: false,
    alwaysOnTop: config.alwaysOnTop ?? alwaysOnTop,
    skipTaskbar: true,
    // Scaling is controlled explicitly from settings. Native resize borders on
    // a transparent frameless window overlap model dragging and can make the
    // window slowly grow while it is being moved.
    resizable: false,
    hasShadow: false,
    show: config.visible,
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      webgl: true,
    },
  })

  live2dWindow.setResizable(false)
  live2dWindow.setBackgroundColor('#00000000')
  live2dWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })

  let saveBoundsTimer: ReturnType<typeof setTimeout> | null = null
  let restoringBounds = true
  const scheduleBoundsSave = () => {
    if (restoringBounds) return
    if (saveBoundsTimer) clearTimeout(saveBoundsTimer)
    saveBoundsTimer = setTimeout(() => {
      const win = getLive2dWindow()
      if (win) updateLive2dWindowConfig({ bounds: win.getBounds() })
    }, 150)
  }
  live2dWindow.on('move', scheduleBoundsSave)
  live2dWindow.on('resize', scheduleBoundsSave)
  live2dWindow.on('close', () => {
    const win = getLive2dWindow()
    if (win) updateLive2dWindowConfig({ bounds: win.getBounds() })
  })

  if (config.clickThrough) setLive2dClickThrough(true)
  if (config.mouseTracking) setLive2dMouseTracking(true)

  live2dWindow.loadURL(url).catch(err => {
    console.warn('[Live2D Window] loadURL failed:', err.message)
  })

  live2dWindow.webContents.on('did-finish-load', () => {
    injectApiPort()
    broadcastLive2dCommand('live2d:tracking', getLive2dWindowConfig().mouseTracking)
    // Windows may nudge a transparent frameless HWND while its renderer is
    // attaching. Reapply the persisted logical bounds once, then allow saves.
    if (savedBounds) live2dWindow?.setBounds(savedBounds, false)
    setTimeout(() => { restoringBounds = false }, 250)
    const portInterval = setInterval(injectApiPort, 3000)
    live2dWindow?.on('closed', () => clearInterval(portInterval))
  })

  function injectApiPort() {
    try {
      const portsFile = join(process.resourcesPath, 'backend', '_internal', 'config', 'runtime_ports.json')
      if (fs.existsSync(portsFile)) {
        const ports = JSON.parse(fs.readFileSync(portsFile, 'utf-8'))
        const apiPort = ports.web_api || ports.management_api || 9800
        live2dWindow?.webContents.executeJavaScript(
          `window.__MIYA_API_PORT__ = ${apiPort}`
        ).catch(() => {})
      }
    }
    catch { /* ignore */ }
  }

  live2dWindow.on('closed', () => {
    if (saveBoundsTimer) clearTimeout(saveBoundsTimer)
    live2dWindow = null
    live2dClickThrough = false
    dragStart = null
    if (mouseTrackingTimer) {
      clearInterval(mouseTrackingTimer)
      mouseTrackingTimer = null
    }
  })

  live2dWindow.webContents.on('did-fail-load', (_e, errorCode, errorDescription) => {
    console.warn(`[Live2D Window] load failed: ${errorCode} - ${errorDescription}`)
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    live2dWindow.webContents.openDevTools({ mode: 'detach' })
  }

  return live2dWindow
}

export function getLive2dWindow(): BrowserWindow | null {
  if (!live2dWindow) return null
  try {
    if (live2dWindow.isDestroyed()) {
      live2dWindow = null
      return null
    }
    return live2dWindow
  }
  catch {
    live2dWindow = null
    return null
  }
}

export function toggleLive2dVisibility(): void {
  const win = getLive2dWindow()
  if (!win) return
  setLive2dVisibility(!win.isVisible())
}

export function setLive2dVisibility(visible: boolean): boolean {
  const win = getLive2dWindow()
  if (!win) return false
  visible ? win.show() : win.hide()
  updateLive2dWindowConfig({ visible })
  broadcastLive2dCommand('live2d:visibilityChanged', visible)
  return true
}

export function setLive2dAlwaysOnTop(enabled: boolean): void {
  const win = getLive2dWindow()
  if (win) win.setAlwaysOnTop(enabled)
  updateLive2dWindowConfig({ alwaysOnTop: enabled })
}

export function setLive2dClickThrough(enabled: boolean): boolean {
  const win = getLive2dWindow()
  if (!win) return false
  if (enabled) {
    win.setFocusable(false)
    win.blur()
    // Do not use { forward: true } here: on some Windows/Electron builds it
    // keeps the transparent HWND participating in mouse hit testing.
    win.setIgnoreMouseEvents(true)
  }
  else {
    win.setIgnoreMouseEvents(false)
    win.setFocusable(true)
  }
  live2dClickThrough = enabled
  updateLive2dWindowConfig({ clickThrough: enabled })
  return live2dClickThrough
}

export function moveLive2dWindow(x: number, y: number): void {
  const win = getLive2dWindow()
  if (win && Number.isFinite(x) && Number.isFinite(y)) win.setPosition(Math.round(x), Math.round(y), false)
}

let dragStart: { cursorX: number, cursorY: number, windowX: number, windowY: number, width: number, height: number } | null = null
let mouseTrackingTimer: ReturnType<typeof setInterval> | null = null
let mouseIdleReturn = DEFAULT_CONFIG.mouseIdleReturn
let lastCursorPoint: { x: number, y: number } | null = null
let lastCursorMoveAt = Date.now()

export function setLive2dMouseIdleReturn(enabled: boolean): void {
  mouseIdleReturn = enabled
  lastCursorMoveAt = Date.now()
  updateLive2dWindowConfig({ mouseIdleReturn: enabled })
}

export function setLive2dMouseTracking(enabled: boolean): boolean {
  const config = updateLive2dWindowConfig({ mouseTracking: enabled })
  mouseIdleReturn = config.mouseIdleReturn
  lastCursorPoint = null
  lastCursorMoveAt = Date.now()
  if (mouseTrackingTimer) {
    clearInterval(mouseTrackingTimer)
    mouseTrackingTimer = null
  }
  broadcastLive2dCommand('live2d:tracking', enabled)
  if (!enabled) return false

  mouseTrackingTimer = setInterval(() => {
    const win = getLive2dWindow()
    if (!win || !win.isVisible()) return
    const bounds = win.getBounds()
    const cursor = screen.getCursorScreenPoint()
    if (!lastCursorPoint || cursor.x !== lastCursorPoint.x || cursor.y !== lastCursorPoint.y) {
      lastCursorPoint = cursor
      lastCursorMoveAt = Date.now()
    }
    const active = !mouseIdleReturn || Date.now() - lastCursorMoveAt < 10_000
    const x = Math.max(-1, Math.min(1, (cursor.x - (bounds.x + bounds.width / 2)) / Math.max(1, bounds.width / 2)))
    const y = Math.max(-1, Math.min(1, -((cursor.y - (bounds.y + bounds.height / 2)) / Math.max(1, bounds.height / 2))))
    broadcastLive2dCommand('live2d:cursor', { x, y, active })
  }, 33)
  return true
}

export function beginLive2dWindowDrag(cursorX: number, cursorY: number): void {
  const win = getLive2dWindow()
  if (!win || !Number.isFinite(cursorX) || !Number.isFinite(cursorY)) return
  const bounds = win.getBounds()
  dragStart = { cursorX, cursorY, windowX: bounds.x, windowY: bounds.y, width: bounds.width, height: bounds.height }
}

export function dragLive2dWindow(cursorX: number, cursorY: number): void {
  const win = getLive2dWindow()
  if (!win || !dragStart || !Number.isFinite(cursorX) || !Number.isFinite(cursorY)) return
  const x = Math.round(dragStart.windowX + cursorX - dragStart.cursorX)
  const y = Math.round(dragStart.windowY + cursorY - dragStart.cursorY)
  win.setBounds({ x, y, width: dragStart.width, height: dragStart.height }, false)
}

export function endLive2dWindowDrag(): void {
  const win = getLive2dWindow()
  if (win) updateLive2dWindowConfig({ bounds: win.getBounds() })
  dragStart = null
}

export function resetLive2dPosition(): void {
  const win = getLive2dWindow()
  if (!win) return
  const primaryDisplay = screen.getPrimaryDisplay()
  const { workArea } = primaryDisplay
  const bounds = win.getBounds()
  const x = workArea.x + workArea.width - bounds.width - 20
  const y = workArea.y + workArea.height - bounds.height - 60
  win.setPosition(x, y, false)
  updateLive2dWindowConfig({ bounds: win.getBounds() })
}

export function positionLive2dRelative(mainBounds: { x: number, y: number, width: number, height: number }): void {
  const win = getLive2dWindow()
  if (!win) return

  const topBarH = 68   // titleBar 32 + statusBar 36
  const bottomBarH = 40
  const sideNavW = 64
  const gap = 28

  const contentX = mainBounds.x + sideNavW + gap
  const contentY = mainBounds.y + topBarH + gap
  const contentW = mainBounds.width - sideNavW - gap * 2
  const contentH = mainBounds.height - topBarH - bottomBarH - gap * 2

  const l2dH = Math.max(300, Math.round(contentH * 0.85))
  const l2dW = Math.max(200, Math.round(l2dH * 2 / 3))

  const x = contentX + Math.round((contentW - l2dW) / 2)
  const y = contentY + Math.round((contentH - l2dH) / 2)

  win.setBounds({ x, y, width: l2dW, height: l2dH })
  updateLive2dWindowConfig({ bounds: win.getBounds(), windowScale: Math.round(l2dW / DEFAULT_SIZE.width * 100) })
  console.log('[Live2D] positioned:', { x, y, width: l2dW, height: l2dH, mainBounds })
}

export function setLive2dWindowScale(scale: number): number {
  const win = getLive2dWindow()
  if (!win) return getLive2dWindowConfig().windowScale
  const current = win.getBounds()
  const display = screen.getDisplayMatching(current)
  const area = display.workArea
  const safeScale = Math.max(40, Math.min(400, Number.isFinite(scale) ? scale : 100))
  const newWidth = Math.round(DEFAULT_SIZE.width * safeScale / 100)
  const newHeight = Math.round(DEFAULT_SIZE.height * safeScale / 100)
  const centerX = current.x + current.width / 2
  const centerY = current.y + current.height / 2
  const x = Math.round(Math.max(area.x - newWidth + 80, Math.min(centerX - newWidth / 2, area.x + area.width - 80)))
  const y = Math.round(Math.max(area.y - newHeight + 80, Math.min(centerY - newHeight / 2, area.y + area.height - 80)))
  win.setBounds({ x, y, width: newWidth, height: newHeight }, false)
  const appliedBounds = win.getBounds()
  const appliedScale = Math.round(appliedBounds.width / DEFAULT_SIZE.width * 100)
  updateLive2dWindowConfig({ windowScale: appliedScale, bounds: appliedBounds })
  return appliedScale
}

export function broadcastLive2dCommand(channel: string, ...args: unknown[]): void {
  const win = getLive2dWindow()
  if (!win) return
  try {
    win.webContents.send(channel, ...args)
  }
  catch {
    // Window destroyed between check and send — ignore
  }
}
