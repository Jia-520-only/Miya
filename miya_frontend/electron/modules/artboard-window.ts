import { dirname, join, resolve } from 'node:path'
import fs from 'node:fs'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { BrowserWindow, screen } from 'electron'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let artboardWindow: BrowserWindow | null = null

const DEFAULT_SIZE = { width: 1100, height: 750 }

function resolveArtboardUrl(): string {
  if (process.env.VITE_DEV_SERVER_URL) {
    const devBase = process.env.VITE_DEV_SERVER_URL.replace(/\/+$/, '')
    return `${devBase}/src/artboard-app/index.html`
  }

  const distPath = resolve(__dirname, '..', 'dist', 'artboard-app', 'index.html')
  if (fs.existsSync(distPath)) {
    return `file://${distPath}`
  }

  const srcPath = resolve(__dirname, '..', '..', 'src', 'artboard-app', 'index.html')
  if (fs.existsSync(srcPath)) {
    return `file://${srcPath}`
  }

  console.warn('[Artboard Window] No entry found')
  return ''
}

export function createArtboardWindow(): BrowserWindow {
  if (artboardWindow && !artboardWindow.isDestroyed()) {
    artboardWindow.show()
    artboardWindow.focus()
    return artboardWindow
  }

  const primaryDisplay = screen.getPrimaryDisplay()
  const { workArea } = primaryDisplay
  const x = workArea.x + Math.round((workArea.width - DEFAULT_SIZE.width) / 2)
  const y = workArea.y + Math.round((workArea.height - DEFAULT_SIZE.height) / 2)

  artboardWindow = new BrowserWindow({
    x,
    y,
    width: DEFAULT_SIZE.width,
    height: DEFAULT_SIZE.height,
    minWidth: 800,
    minHeight: 500,
    frame: true,
    transparent: false,
    alwaysOnTop: false,
    skipTaskbar: false,
    resizable: true,
    hasShadow: true,
    show: false,
    title: '弥娅 画板 · Artboard',
    backgroundColor: '#0f1117',
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      webgl: true,
    },
  })

  const url = resolveArtboardUrl()
  if (url) {
    artboardWindow.loadURL(url).catch(err => {
      console.warn('[Artboard Window] loadURL failed:', err.message)
    })
  }

  artboardWindow.once('ready-to-show', () => {
    artboardWindow?.show()
  })

  function injectArtboardPort() {
    try {
      const portsFile = join(process.resourcesPath, 'backend', '_internal', 'config', 'runtime_ports.json')
      if (fs.existsSync(portsFile)) {
        const ports = JSON.parse(fs.readFileSync(portsFile, 'utf-8'))
        const apiPort = ports.web_api || ports.management_api || 9800
        artboardWindow?.webContents.executeJavaScript(
          `window.__MIYA_API_PORT__ = ${apiPort}`
        ).catch(() => {})
      }
    }
    catch { /* ignore */ }
  }

  artboardWindow.webContents.on('did-finish-load', () => {
    injectArtboardPort()
    const portInterval = setInterval(injectArtboardPort, 3000)
    artboardWindow?.on('closed', () => clearInterval(portInterval))
    artboardWindow?.webContents.executeJavaScript(
      'window.__IS_ARTBOARD_WINDOW__ = true'
    ).catch(() => {})
  })

  artboardWindow.on('closed', () => {
    artboardWindow = null
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    artboardWindow.webContents.openDevTools({ mode: 'detach' })
  }

  return artboardWindow
}

export function getArtboardWindow(): BrowserWindow | null {
  if (!artboardWindow) return null
  try {
    if (artboardWindow.isDestroyed()) {
      artboardWindow = null
      return null
    }
    return artboardWindow
  }
  catch {
    artboardWindow = null
    return null
  }
}

export function toggleArtboardWindow(): BrowserWindow | null {
  const win = getArtboardWindow()
  if (win) {
    win.isVisible() ? win.hide() : (win.show(), win.focus())
    return win
  }
  return createArtboardWindow()
}

export function closeArtboardWindow(): void {
  if (artboardWindow && !artboardWindow.isDestroyed()) {
    artboardWindow.close()
    artboardWindow = null
  }
}
