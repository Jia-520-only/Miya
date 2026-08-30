import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { readdir } from 'node:fs/promises'
import { dirname, resolve, sep } from 'node:path'
import process from 'node:process'
import { domainToUnicode, fileURLToPath, pathToFileURL } from 'node:url'
import { app, BrowserWindow, desktopCapturer, ipcMain, Menu, nativeTheme, net, protocol, shell, systemPreferences } from 'electron'
import { getBackendLogs, startBackend, stopBackend, startPortPolling, stopPortPolling } from './modules/backend'
import { registerHotkeys, unregisterHotkeys } from './modules/hotkeys'
import { createMenu } from './modules/menu'
import { startTerminal, stopTerminal, writeToTerminal, resizeTerminal, isTerminalRunning, isTuiRunning, getTerminalUrl, getTerminalBuffer, setMiyaRoot, startDshHost, stopDshHost, isDshHostRunning, getDshHostUrl } from './modules/terminal'
import { createTray, destroyTray } from './modules/tray'
import { downloadUpdate, installUpdate, setupAutoUpdater } from './modules/updater'
import {
  collapseFloatingWindow,
  collapseFullToCompact,
  createWindow,
  enterFloatingMode,
  exitFloatingMode,
  expandCompactToFull,
  expandFloatingWindow,
  getFloatingState,
  getMainWindow,
  setFloatingHeight,
  setWindowPosition,
} from './modules/window'
import {
  createLive2dWindow,
  toggleLive2dVisibility,
  setLive2dAlwaysOnTop,
  setLive2dVisibility,
  resetLive2dPosition,
  setLive2dWindowScale,
  broadcastLive2dCommand,
  positionLive2dRelative,
  getLive2dWindow,
  getLive2dWindowConfig,
  setLive2dClickThrough,
  moveLive2dWindow,
  beginLive2dWindowDrag,
  dragLive2dWindow,
  endLive2dWindowDrag,
  setLive2dMouseTracking,
  setLive2dMouseIdleReturn,
  updateLive2dWindowConfig,
} from './modules/live2d-window'
import { activateLive2dPackage, deleteLive2dPackage, getActiveLive2dModelUrl, getLive2dPackagesDir, importLive2dPackage, listLive2dPackages } from './modules/live2d-packages'
import {
  createArtboardWindow,
  toggleArtboardWindow,
  closeArtboardWindow,
} from './modules/artboard-window'

// ES module __dirname polyfill
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let isQuitting = false

// 防止 EPIPE 导致 Electron 崩溃（后端进程 stdout 管道断开时会触发）
process.stdout?.on('error', () => {})
process.stderr?.on('error', () => {})

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
}

// ── 自定义协议：miya-char:// 用于加载用户安装的角色包 ──
const CHARACTERS_DIR = getLive2dPackagesDir()
const MIYA_ROOT = app.isPackaged
  ? resolve(process.resourcesPath, '..')
  : resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
// ── 自定义协议：miya-bg:// 用于加载 premium-assets/backgrounds 目录下的背景图片 ──
const BACKGROUNDS_DIR = app.isPackaged
  ? resolve(process.resourcesPath, 'premium-assets', 'backgrounds')
  : resolve(dirname(fileURLToPath(import.meta.url)), '..', 'premium-assets', 'backgrounds')
protocol.registerSchemesAsPrivileged([
  { scheme: 'miya-char', privileges: { secure: true, supportFetchAPI: true, corsEnabled: true, standard: true, stream: true } },
  { scheme: 'miya-bg', privileges: { secure: true, supportFetchAPI: true, corsEnabled: true, standard: true, stream: true } },
  { scheme: 'miya-app', privileges: { secure: true, supportFetchAPI: true, corsEnabled: true, standard: true, stream: true } },
])

app.on('second-instance', () => {
  try {
    const win = getMainWindow()
    if (win && !win.isDestroyed()) {
      if (win.isMinimized())
        win.restore()
      win.show()
      win.focus()
    }
  }
  catch { /* window destroyed between check and action */ }
})

app.whenReady().then(async () => {
  try {
  // Set Miya project root for terminal module
  setMiyaRoot(MIYA_ROOT)

  // MIME 映射（音频/视频等二进制媒体文件需要通过 fs.readFile 读取以兼容 asar）
  const MEDIA_MIME: Record<string, string> = {
    mp3: 'audio/mpeg',
    wav: 'audio/wav',
    ogg: 'audio/ogg',
    m4a: 'audio/mp4',
    flac: 'audio/flac',
    aac: 'audio/aac',
    webm: 'audio/webm',
    mp4: 'video/mp4',
    mkv: 'video/x-matroska',
  }
  const FILE_MIME: Record<string, string> = {
    ...MEDIA_MIME,
    json: 'application/json; charset=utf-8',
    txt: 'text/plain; charset=utf-8',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    webp: 'image/webp',
    svg: 'image/svg+xml',
    moc3: 'application/octet-stream',
  }

  function resolveCustomProtocolPath(requestUrl: string, baseDir: string): string | null {
    try {
      const url = new URL(requestUrl)
      const host = domainToUnicode(url.hostname || '')
      const pathname = decodeURIComponent(url.pathname).replace(/^\/+/, '')
      const relativePath = [host, pathname].filter(Boolean).join('/')
      const filePath = resolve(baseDir, relativePath)
      if (!filePath.startsWith(baseDir)) {
        return null
      }
      return filePath
    }
    catch {
      return null
    }
  }

  function serveLocalFile(filePath: string, notFoundMessage = 'Not Found'): Response {
    try {
      const data = readFileSync(filePath)
      const ext = filePath.split('.').pop()?.toLowerCase() ?? ''
      const mime = FILE_MIME[ext] || 'application/octet-stream'
      return new Response(data, {
        headers: {
          'Content-Type': mime,
          'Content-Length': data.length.toString(),
          'Cache-Control': 'no-cache',
        },
      })
    }
    catch {
      return new Response(notFoundMessage, { status: 404 })
    }
  }

  // miya-app://路径 → 加载 dist/ 目录文件
  // 仅打包模式生效，开发模式走 Vite dev server
  const appDistDir = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'dist')
  protocol.handle('miya-app', (request) => {
    const rawPath = decodeURIComponent(new URL(request.url).pathname).replace(/^\/+/, '')
    const relativePath = rawPath.startsWith('dist/') ? rawPath.slice(5) : rawPath

    const basePath = resolve(appDistDir, relativePath)
    if (!basePath.startsWith(appDistDir)) {
      return new Response('Forbidden', { status: 403 })
    }

    // 音频/视频文件通过 fs.readFileSync 读取（Node fs 天然兼容 asar），
    // 避免 net.fetch(file://) 在 asar 内对媒体文件不兼容的问题。
    // 注意：此处使用 readFileSync 而非 async readFile，因为构建工具（Rollup/Rolldown）
    // 的 tree-shaking 会将 async handler 中的 await readFile 分支整体移除，
    // 导致打包后音频无 Content-Type/Content-Length 头，播放约 6 秒后卡死。
    const ext = basePath.split('.').pop()?.toLowerCase() ?? ''
    const mime = MEDIA_MIME[ext]
    if (mime) {
      try {
        const data = readFileSync(basePath)
        return new Response(data, {
          headers: { 'Content-Type': mime, 'Content-Length': data.length.toString() },
        })
      }
      catch {
        return new Response('Not Found', { status: 404 })
      }
    }

    return net.fetch(pathToFileURL(basePath).toString())
  })

  // miya-char://包ID/文件名 → 用户数据目录中的已安装角色包
  protocol.handle('miya-char', (request) => {
    try {
      const url = new URL(request.url)
      const host = domainToUnicode(url.hostname || '')
      const pathname = decodeURIComponent(url.pathname).replace(/^\/+/, '')
      if (!host) return new Response('Invalid Character Package', { status: 400 })
      const relativePath = [host, pathname].filter(Boolean).join('/')
      const filePath = resolve(CHARACTERS_DIR, relativePath)
      if (!filePath.startsWith(`${CHARACTERS_DIR}${sep}`)) {
        return new Response('Forbidden', { status: 403 })
      }
      return serveLocalFile(filePath, 'Character Asset Not Found')
    }
    catch {
      return new Response('Forbidden', { status: 403 })
    }
  })

  // miya-bg://文件名 → premium-assets/backgrounds/文件名
  protocol.handle('miya-bg', (request) => {
    const filePath = resolveCustomProtocolPath(request.url, BACKGROUNDS_DIR)
    if (!filePath) {
      return new Response('Forbidden', { status: 403 })
    }
    return serveLocalFile(filePath, 'Background Asset Not Found')
  })

  // 强制暗色主题（确保原生菜单等 UI 为深色）
  nativeTheme.themeSource = 'dark'

  // Create menu
  createMenu()

  // Create main window
  const win = createWindow()

  // Register boot-critical handlers before loading the standalone renderer.
  // Its first script immediately asks for the selected model and saved config.
  ipcMain.handle('live2dPackages:getActiveModel', () => getActiveLive2dModelUrl())
  ipcMain.handle('live2d:getConfig', () => getLive2dWindowConfig())
  ipcMain.on('live2d:ready', () => {
    // did-finish-load fires before the renderer installs its controller IPC
    // listeners. Recreate the saved tracker only after the model says ready.
    const config = getLive2dWindowConfig()
    setLive2dMouseIdleReturn(config.mouseIdleReturn)
    setLive2dMouseTracking(config.mouseTracking)
  })

  // Create standalone Live2D window (透明无边框独立窗口)
  createLive2dWindow()

  // 透明无边框窗口在 Windows 上 unmaximize 后系统不可靠地还原尺寸，手动保存/还原
  let preMaximizeBounds: Electron.Rectangle | null = null

  // Create system tray
  createTray()

  // Register global hotkeys
  registerHotkeys()

  // Setup auto-updater (checks GitHub Releases for new versions)
  void setupAutoUpdater(win)

  // --- IPC Handlers ---

  // Window controls
  ipcMain.on('window:minimize', () => getMainWindow()?.minimize())
  ipcMain.on('window:maximize', () => {
    const w = getMainWindow()
    if (w) {
      if (w.isMaximized()) {
        w.unmaximize()
      }
      else {
        preMaximizeBounds = w.getBounds()
        w.maximize()
      }
    }
  })
  ipcMain.on('window:close', () => {
    const state = getFloatingState()
    if (state === 'compact' || state === 'full') {
      // 悬浮球展开态：收起为球态
      collapseFloatingWindow()
    }
    else if (state === 'classic') {
      // 经典模式：关闭窗口 → 自动进入悬浮球
      enterFloatingMode()
    }
    else {
      // 已经是球态，隐藏到托盘
      getMainWindow()?.hide()
    }
  })

  ipcMain.handle('window:isMaximized', () => getMainWindow()?.isMaximized() ?? false)
  ipcMain.handle('window:getBounds', () => getMainWindow()?.getBounds() ?? { x: 0, y: 0, width: 1280, height: 800 })
  ipcMain.on('window:setBounds', (_event, bounds: { x?: number, y?: number, width?: number, height?: number }) => {
    const win = getMainWindow()
    if (!win || win.isMaximized())
      return
    const current = win.getBounds()
    const next = {
      x: bounds.x ?? current.x,
      y: bounds.y ?? current.y,
      width: Math.max(800, bounds.width ?? current.width),
      height: Math.max(600, bounds.height ?? current.height),
    }
    win.setBounds(next)
  })

  // 悬浮球模式控制
  ipcMain.handle('floating:enter', () => {
    enterFloatingMode()
  })
  ipcMain.handle('floating:exit', () => {
    exitFloatingMode()
  })
  ipcMain.handle('floating:expand', (_event, toFull?: boolean) => {
    expandFloatingWindow(toFull ?? false)
  })
  ipcMain.handle('floating:expandToFull', () => {
    expandCompactToFull()
  })
  ipcMain.handle('floating:collapse', () => {
    collapseFloatingWindow()
  })
  ipcMain.handle('floating:collapseToCompact', () => {
    collapseFullToCompact()
  })
  ipcMain.handle('floating:getState', () => getFloatingState())
  ipcMain.on('floating:pin', (_event, pinned: boolean) => {
    const w = getMainWindow()
    if (w) {
      // 固定时显示任务栏图标，取消固定时隐藏（悬浮球模式下 alwaysOnTop 始终为 true）
      w.setSkipTaskbar(!pinned)
    }
  })
  ipcMain.on('floating:setPosition', (_event, x: number, y: number) => {
    setWindowPosition(x, y)
  })
  ipcMain.on('floating:fitHeight', (_event, height: number) => {
    setFloatingHeight(height)
  })

  // Update controls
  ipcMain.on('updater:download', () => downloadUpdate())
  ipcMain.on('updater:install', () => installUpdate())

  // App quit
  ipcMain.on('app:quit', () => {
    isQuitting = true
    app.quit()
  })

  // 悬浮球右键菜单
  ipcMain.on('context-menu:show', () => {
    const menu = Menu.buildFromTemplate([
      {
        label: '打开主界面',
        click: () => exitFloatingMode(),
      },
      {
        label: '隐藏到托盘',
        click: () => getMainWindow()?.hide(),
      },
      { type: 'separator' },
      {
        label: '退出应用',
        click: () => {
          isQuitting = true
          app.quit()
        },
      },
    ])
    menu.popup()
  })

  // 窗口截屏功能
  ipcMain.handle('capture:getSources', async () => {
    // macOS 需要屏幕录制权限
    if (process.platform === 'darwin') {
      const status = systemPreferences.getMediaAccessStatus('screen')
      if (status !== 'granted') {
        return { permission: status }
      }
    }

    try {
      const sources = await desktopCapturer.getSources({
        types: ['window', 'screen'],
        thumbnailSize: { width: 320, height: 180 },
        fetchWindowIcons: true,
      })
      return sources.map(s => ({
        id: s.id,
        name: s.name,
        thumbnail: s.thumbnail.toDataURL(),
        appIcon: s.appIcon?.toDataURL() || null,
      }))
    }
    catch {
      // desktopCapturer 可能因权限问题抛出异常
      return { permission: 'denied' }
    }
  })

  ipcMain.handle('capture:captureWindow', async (_event, sourceId: string) => {
    const sources = await desktopCapturer.getSources({
      types: ['window', 'screen'],
      thumbnailSize: { width: 1920, height: 1080 },
    })
    const target = sources.find(s => s.id === sourceId)
    if (!target)
      return null
    return target.thumbnail.toDataURL()
  })

  // 打开 macOS 屏幕录制权限设置
  ipcMain.handle('capture:openScreenSettings', async () => {
    if (process.platform === 'darwin') {
      await shell.openExternal('x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture')
    }
  })

  // 扫描背景图片文件夹
  ipcMain.handle('backgrounds:scan', async () => {
    try {
      const files = await readdir(BACKGROUNDS_DIR)
      const imageExts = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif']
      return files.filter(f => imageExts.some(ext => f.toLowerCase().endsWith(ext)))
    }
    catch {
      return []
    }
  })

  ipcMain.handle('fs:writeFile', (_event, relPath: string, base64: string) => {
    const base = app.isPackaged
      ? resolve(process.resourcesPath)
      : resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
    const filePath = resolve(base, relPath)
    mkdirSync(dirname(filePath), { recursive: true })
    writeFileSync(filePath, Buffer.from(base64, 'base64'))
  })

  // 开机自启动
  ipcMain.handle('autoLaunch:get', () => {
    return app.getLoginItemSettings().openAtLogin
  })
  ipcMain.handle('autoLaunch:set', (_event, enabled: boolean) => {
    app.setLoginItemSettings({ openAtLogin: enabled })
  })
  ipcMain.handle('backend:getLogs', () => getBackendLogs())

  // ── Artboard 独立窗口 ──
  ipcMain.handle('artboard:open', () => {
    createArtboardWindow()
  })
  ipcMain.handle('artboard:close', () => {
    closeArtboardWindow()
  })
  ipcMain.handle('artboard:toggle', () => {
    toggleArtboardWindow()
  })

  // ── Live2D 独立窗口 ──
  ipcMain.handle('live2dPackages:list', () => listLive2dPackages())
  ipcMain.handle('live2dPackages:import', () => {
    const imported = importLive2dPackage()
    if (imported?.active) getLive2dWindow()?.reload()
    return imported
  })
  ipcMain.handle('live2dPackages:activate', (_event, id: string) => {
    activateLive2dPackage(id)
    getLive2dWindow()?.reload()
  })
  ipcMain.handle('live2dPackages:delete', (_event, id: string) => {
    const deletedActive = deleteLive2dPackage(id)
    if (deletedActive) getLive2dWindow()?.reload()
  })

  ipcMain.on('live2d:emotion', (_event, emotion: string) => {
    broadcastLive2dCommand('live2d:emotion', emotion)
  })
  ipcMain.on('live2d:state', (_event, state: string) => {
    broadcastLive2dCommand('live2d:state', state)
  })
  ipcMain.on('live2d:mouth', (_event, params: Record<string, number>) => {
    broadcastLive2dCommand('live2d:mouth', params)
  })
  ipcMain.on('live2d:action', (_event, action: string) => {
    broadcastLive2dCommand('live2d:action', action)
  })
  ipcMain.on('live2d:tracking', (_event, enabled: boolean) => {
    setLive2dMouseTracking(enabled)
  })
  ipcMain.on('live2d:mouseIdleReturn', (_event, enabled: boolean) => {
    setLive2dMouseIdleReturn(enabled)
  })
  ipcMain.on('live2d:clothes', (_event, clothes: string) => {
    broadcastLive2dCommand('live2d:clothes', clothes)
  })
  ipcMain.on('live2d:toggleVisibility', () => {
    toggleLive2dVisibility()
  })
  ipcMain.handle('live2d:setVisibility', (_event, visible: boolean) => setLive2dVisibility(visible))
  ipcMain.on('live2d:alwaysOnTop', (_event, enabled: boolean) => {
    setLive2dAlwaysOnTop(enabled)
  })
  ipcMain.on('live2d:clickThrough', (_event, enabled: boolean) => {
    setLive2dClickThrough(enabled)
  })
  ipcMain.handle('live2d:setClickThrough', (_event, enabled: boolean) => {
    return setLive2dClickThrough(enabled)
  })
  ipcMain.on('live2d:moveWindow', (_event, x: number, y: number) => {
    moveLive2dWindow(x, y)
  })
  ipcMain.on('live2d:dragStart', (_event, x: number, y: number) => beginLive2dWindowDrag(x, y))
  ipcMain.on('live2d:dragMove', (_event, x: number, y: number) => dragLive2dWindow(x, y))
  ipcMain.on('live2d:dragEnd', () => endLive2dWindowDrag())
  ipcMain.on('live2d:resetPosition', () => {
    resetLive2dPosition()
  })
  ipcMain.on('live2d:positionRelative', (_event, bounds?: { x: number, y: number, width: number, height: number }) => {
    if (bounds) {
      positionLive2dRelative(bounds)
    } else {
      const mainWin = getMainWindow()
      if (mainWin) {
        setTimeout(() => {
          const b = mainWin.getBounds()
          positionLive2dRelative({ x: b.x, y: b.y, width: b.width, height: b.height })
        }, 300)
      }
    }
  })
  ipcMain.on('live2d:readyToggle', () => {
    // 启动时检查 localStorage 中的 visible 配置，如果关闭则隐藏窗口
    toggleLive2dVisibility()
  })
  ipcMain.on('live2d:background', (_event, data: { color: string, alpha: number }) => {
    const normalizedColor = String(data?.color ?? '').replace(/^0x/i, '#')
    updateLive2dWindowConfig({ bgColor: normalizedColor, bgAlpha: Number(data?.alpha) })
    broadcastLive2dCommand('live2d:background', data)
  })
  ipcMain.handle('live2d:setWindowScale', (_event, scale: number) => setLive2dWindowScale(scale))
  ipcMain.on('live2d:modelScale', (_event, scale: number) => {
    const safeScale = Math.max(40, Math.min(400, Number.isFinite(scale) ? scale : 100))
    updateLive2dWindowConfig({ modelScale: safeScale })
    broadcastLive2dCommand('live2d:modelScale', safeScale)
  })

  // ── Terminal (DeepSeek Harness: TUI + Web) ──
  ipcMain.handle('terminal:start', (_event, options: { model?: string, mode?: 'tui' | 'web' }) => {
    return startTerminal(
      options,
      (data: string) => {
        getMainWindow()?.webContents.send('terminal:data', data)
      },
      (code: number) => {
        getMainWindow()?.webContents.send('terminal:exit', code)
      },
    )
  })

  ipcMain.handle('terminal:write', (_event, data: string) => {
    writeToTerminal(data)
  })

  ipcMain.handle('terminal:resize', (_event, cols: number, rows: number) => {
    resizeTerminal(cols, rows)
  })

  ipcMain.handle('terminal:stop', () => {
    stopTerminal()
  })

  ipcMain.handle('terminal:isRunning', () => isTerminalRunning())
  ipcMain.handle('terminal:isTuiRunning', () => isTuiRunning())
  ipcMain.handle('terminal:getUrl', () => getTerminalUrl())
  ipcMain.handle('terminal:getBuffer', () => getTerminalBuffer())

  // ── DSH Web 板块（独立 host 管理，与 TUI 共存） ──
  ipcMain.handle('dshWeb:ensure', (_event, options: { model?: string }) => {
    return startDshHost(options)
  })

  ipcMain.handle('dshWeb:stop', () => {
    stopDshHost()
  })

  ipcMain.handle('dshWeb:isRunning', () => isDshHostRunning())
  ipcMain.handle('dshWeb:getUrl', () => getDshHostUrl())
  ipcMain.handle('dshWeb:openBrowser', () => {
    const url = getDshHostUrl()
    if (url) {
      shell.openExternal(url)
      return true
    }
    return false
  })

  // Minimize to tray on close instead of quitting
  win.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      win.hide()
    }
  })

  win.on('maximize', () => win.webContents.send('window:maximized', true))
  win.on('unmaximize', () => {
    win.webContents.send('window:maximized', false)
    // 透明无边框窗口在 Windows 上还原尺寸不可靠，手动恢复最大化前的 bounds
    if (preMaximizeBounds) {
      win.setBounds(preMaximizeBounds)
      preMaximizeBounds = null
    }
  })

  // 悬浮球展开态失焦时自动收起（由渲染进程控制是否启用）
  win.on('blur', () => {
    win.webContents.send('floating:windowBlur')
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
    else {
      getMainWindow()?.show()
    }
  })

  // Start backend services (skip if MIYA_NO_BACKEND is set)
  if (!process.env.MIYA_NO_BACKEND) {
    startBackend()
    startPortPolling()
  }
  else {
    console.log('[Main] MIYA_NO_BACKEND=1, skipping backend auto-start')
  }
  }
  catch (error) {
    console.error('[Main] Startup failed. Showing a fallback error window instead of silently exiting.', error)

    const fallbackWindow = new BrowserWindow({
      width: 900,
      height: 600,
      show: true,
      frame: true,
      backgroundColor: '#0f1117',
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
      },
    })

    fallbackWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`
      <html><body style="margin:0;background:#0f1117;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;">
        <h2 style="margin:0">Miya 启动失败</h2>
        <pre style="max-width:820px;white-space:pre-wrap;word-break:break-word;padding:16px;background:#1a1f2a;border-radius:8px;">${String(error instanceof Error ? error.stack ?? error.message : error)}</pre>
      </body></html>
    `)}`)

    fallbackWindow.on('closed', () => {
      if (process.platform !== 'darwin') {
        app.quit()
      }
    })
  }
})

app.on('before-quit', () => {
  isQuitting = true
})

app.on('will-quit', () => {
  unregisterHotkeys()
  destroyTray()
  stopTerminal()
  stopBackend()
  stopPortPolling()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
