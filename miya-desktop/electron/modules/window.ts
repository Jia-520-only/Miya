import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'
import { app, BrowserWindow, screen, shell } from 'electron'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let mainWindow: BrowserWindow | null = null

// 悬浮球模式状态
export type FloatingState = 'classic' | 'ball' | 'compact' | 'full'
let floatingState: FloatingState = 'classic'
let classicBounds: Electron.Rectangle | null = null // 经典模式下记住窗口位置
let ballPosition: { x: number, y: number } | null = null // 球态位置

// 悬浮球默认尺寸配置
const BALL_SIZE = 100
const EXPANDED_WIDTH = 420
const MAX_FULL_HEIGHT = 640
const INITIAL_FULL_HEIGHT = 200
const MIN_FIT_HEIGHT = BALL_SIZE
const COMPACT_HEIGHT = BALL_SIZE

// 窗口渐变动画参数
const ANIM_DURATION_MS = 160
const ANIM_FPS = 60
const ANIM_FRAMES = Math.round(ANIM_DURATION_MS / (1000 / ANIM_FPS))

// 当前动画取消句柄,防止并发动画竞争
let cancelCurrentAnimation: (() => void) | null = null

/**
 * 分步动画过渡窗口尺寸和位置
 */
function animateBounds(
  win: BrowserWindow,
  from: Electron.Rectangle,
  to: Electron.Rectangle,
  onDone?: () => void,
): void {
  // 取消上一个动画
  cancelCurrentAnimation?.()

  let frame = 0
  const interval = setInterval(() => {
    frame++
    // easeOutCubic: 快起慢停
    const t = frame / ANIM_FRAMES
    const ease = 1 - (1 - t) ** 3

    const x = Math.round(from.x + (to.x - from.x) * ease)
    const y = Math.round(from.y + (to.y - from.y) * ease)
    const w = Math.round(from.width + (to.width - from.width) * ease)
    const h = Math.round(from.height + (to.height - from.height) * ease)

    win.setBounds({ x, y, width: w, height: h })

    if (frame >= ANIM_FRAMES) {
      clearInterval(interval)
      cancelCurrentAnimation = null
      win.setBounds(to)
      onDone?.()
    }
  }, 1000 / ANIM_FPS)

  cancelCurrentAnimation = () => {
    clearInterval(interval)
    cancelCurrentAnimation = null
  }
}

/**
 * 根据球的位置计算面板展开的位置
 */
function calcExpandPosition(ballX: number, ballY: number, targetHeight: number): { x: number, y: number } {
  const display = screen.getPrimaryDisplay()
  const { width: screenW, height: screenH } = display.workAreaSize

  // 水平方向:球在面板左边缘
  let expandX = ballX
  if (expandX + EXPANDED_WIDTH > screenW)
    expandX = screenW - EXPANDED_WIDTH
  if (expandX < 0)
    expandX = 0

  // 垂直方向:面板顶部与球顶部对齐,空间不足时上移
  let expandY = ballY
  if (expandY + targetHeight > screenH)
    expandY = screenH - targetHeight
  if (expandY < 0)
    expandY = 0

  return { x: expandX, y: expandY }
}

export async function createWindow(): Promise<BrowserWindow> {
  console.log('Creating BrowserWindow...')

  // 检查 preload.js 是否存在
  const preloadPath = join(__dirname, 'preload.js')
  const preloadExists = existsSync(preloadPath)
  console.log('Preload file exists:', preloadExists, 'at:', preloadPath)

  if (!preloadExists) {
    console.error('❌ preload.js not found! Electron APIs will not work.')
    console.error('   Please ensure Vite has compiled the Electron files.')
  }

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    resizable: true,
    hasShadow: true,
    transparent: true,
    show: false,
    webPreferences: {
      preload: preloadExists ? preloadPath : undefined,
      contextIsolation: true,
      nodeIntegration: false,
      webgl: true,
      webSecurity: false,
    },
  })
  console.log('BrowserWindow created:', mainWindow.id)

  // 窗口事件监听
  mainWindow.on('closed', () => {
    console.log('Window closed')
    mainWindow = null
  })
  mainWindow.on('minimize', () => {
    console.log('Window minimized')
  })
  mainWindow.on('maximize', () => {
    console.log('Window maximized')
    // 通知渲染进程最大化状态变化
    mainWindow.webContents.send('maximized')
  })
  mainWindow.on('unmaximize', () => {
    console.log('Window unmaximized')
    // 通知渲染进程最大化状态变化
    mainWindow.webContents.send('unmaximized')
  })

  // 错误处理 - 不要在加载失败时关闭窗口，让重试逻辑处理
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error('Failed to load:', errorCode, errorDescription, validatedURL)
    // 不要关闭窗口，让 loadWithRetry 重试逻辑处理
    event.preventDefault()
  })
  mainWindow.webContents.on('did-start-loading', () => {
    console.log('Page started loading')
  })
  mainWindow.webContents.on('did-stop-loading', () => {
    console.log('Page stopped loading')
  })
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('Page finished loading')
  })

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    console.log('Window ready to show')
    mainWindow?.show()
  })

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // 加载开发URL（优先）或生产URL
  // 默认使用本地开发服务器
  const devUrl = 'http://127.0.0.1:5173'
  const prodUrl = join(__dirname, '../dist/index.html')

  // 优先使用开发服务器,带重试机制
  console.log('Loading app from:', devUrl)

  const loadWithRetry = async (url: string, retries = 5, delay = 2000) => {
    for (let i = 0; i < retries; i++) {
      try {
        console.log(`Attempt ${i + 1}/${retries}: Loading ${url}`)
        await mainWindow.loadURL(url)
        console.log('Successfully loaded URL:', url)
        return true
      } catch (error) {
        console.error(`Attempt ${i + 1}/${retries} failed:`, error)
        if (i < retries - 1) {
          console.log(`Retrying in ${delay}ms...`)
          await new Promise(resolve => setTimeout(resolve, delay))
        }
      }
    }
    return false
  }

  // 尝试加载开发服务器
  const devLoaded = await loadWithRetry(devUrl, 10, 3000)

  if (!devLoaded) {
    console.error('Failed to load dev URL after retries, trying prod URL')
    try {
      await mainWindow.loadFile(prodUrl)
      console.log('Loaded prod URL successfully')
    } catch (prodError) {
      console.error('Failed to load prod URL:', prodError)
      // 显示错误页面
      mainWindow.loadFile(join(__dirname, '../error.html'))
    }
  }

  // 仅在开发模式下打开开发者工具
  if (process.env.NODE_ENV === 'development' || process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools()
  }

  // 添加 F12 快捷键打开/关闭开发者工具
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F12' && input.type === 'keyDown') {
      if (mainWindow.webContents.isDevToolsOpened()) {
        mainWindow.webContents.closeDevTools()
      } else {
        mainWindow.webContents.openDevTools()
      }
    }
  })

  return mainWindow
}

export function getMainWindow(): BrowserWindow | null {
  return mainWindow
}

export function getFloatingState(): FloatingState {
  return floatingState
}

/**
 * 进入悬浮球模式:将窗口缩小为球态
 */
export function enterFloatingMode(): void {
  const win = getMainWindow()
  if (!win || floatingState !== 'classic') return

  // 保存当前窗口位置
  classicBounds = win.getBounds()

  // 计算球位置(默认屏幕右下角)
  const display = screen.getPrimaryDisplay()
  const { width: screenW, height: screenH } = display.workAreaSize
  ballPosition = {
    x: screenW - BALL_SIZE - 50,
    y: screenH - BALL_SIZE - 50
  }

  // 动画过渡到球态
  animateBounds(
    win,
    classicBounds,
    { x: ballPosition.x, y: ballPosition.y, width: BALL_SIZE, height: BALL_SIZE },
    () => {
      floatingState = 'ball'
      win.setAlwaysOnTop(true, 'screen-saver')
      win.setSkipTaskbar(true)
      win.webContents.send('floating:stateChanged', floatingState)
    }
  )
}

/**
 * 退出悬浮球模式:恢复到经典窗口模式
 */
export function exitFloatingMode(): void {
  const win = getMainWindow()
  if (!win) {
    console.warn('[Window] 主窗口不存在，无法退出悬浮模式')
    return
  }

  console.log('[Window] 当前状态:', floatingState)
  if (floatingState === 'classic') {
    console.log('[Window] 已经是经典模式，无需切换')
    return
  }

  const currentBounds = win.getBounds()
  const targetBounds = classicBounds || { x: 100, y: 100, width: 1280, height: 800 }

  console.log('[Window] 退出悬浮模式，目标窗口:', targetBounds)

  // 动画过渡到经典模式
  animateBounds(
    win,
    currentBounds,
    targetBounds,
    () => {
      floatingState = 'classic'
      win.setAlwaysOnTop(false)
      win.setSkipTaskbar(false)
      win.webContents.send('floating:stateChanged', floatingState)
      console.log('[Window] 已退出悬浮模式，状态:', floatingState)
    }
  )
}
