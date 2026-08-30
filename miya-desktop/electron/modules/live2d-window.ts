import { BrowserWindow } from 'electron'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'
import { getMainWindow } from './window'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let live2dWindow: BrowserWindow | null = null

// Live2D 窗口配置
const LIVE2D_WINDOW_CONFIG = {
  width: 600,  // 较小窗口
  height: 800,
  x: 100,
  y: 100,
  frame: false,        // 无边框
  transparent: true,   // 透明背景
  resizable: true,     // 允许调整大小
  alwaysOnTop: true,    // 始终置顶
  skipTaskbar: true,    // 不显示在任务栏
  minimizable: false,   // 不能最小化
  maximizable: false,   // 不能最大化
  closable: true,       // 允许关闭
  titleBarStyle: 'hidden',
  show: false,          // 初始不显示，等页面加载完再显示
  autoHideMenuBar: true,
  backgroundColor: '#00000000',  // 完全透明的背景色
  webPreferences: {
    preload: join(__dirname, '../preload.js'),
    contextIsolation: true,
    nodeIntegration: false,
    webSecurity: false, // 允许加载本地资源
    experimentalFeatures: true,  // 启用实验性功能
    offscreen: false,
    backgroundThrottling: false,  // 禁用后台节流
    enableRemoteModule: false,
    safeDialogs: false
  }
}

// 创建 Live2D 独立窗口
export function createLive2DWindow(): void {
  // 检查窗口是否存在且未被销毁
  if (live2dWindow && !live2dWindow.isDestroyed()) {
    console.log('Live2D window already exists')
    live2dWindow.show()  // 如果已存在，显示窗口
    return
  }

  // 窗口已被销毁或不存在，重置状态
  live2dWindow = null

  console.log('Creating Live2D window...')

  // 检查 preload.js 是否存在
  const preloadPath = join(__dirname, '../preload.js')
  const preloadExists = existsSync(preloadPath)
  console.log('Live2D window: Preload file exists:', preloadExists, 'at:', preloadPath)

  if (!preloadExists) {
    console.warn('⚠️ preload.js not found! Electron APIs may not work.')
  }

  // 更新配置以使用 preload（如果存在）
  const config = {
    ...LIVE2D_WINDOW_CONFIG,
    webPreferences: {
      ...LIVE2D_WINDOW_CONFIG.webPreferences,
      preload: preloadExists ? preloadPath : undefined
    }
  }

  live2dWindow = new BrowserWindow(config)

  // 设置窗口背景透明
  live2dWindow.setBackgroundColor('#00000000')

  // 加载 Live2D 页面
  let url: string
  if (process.env.VITE_DEV_SERVER_URL) {
    // 开发环境
    url = `${process.env.VITE_DEV_SERVER_URL}#/live2d`
    console.log('Live2D window: Loading URL (dev):', url)
    live2dWindow.loadURL(url)
  } else {
    // 生产环境
    const htmlPath = join(__dirname, '../../dist-electron/index.html')
    console.log('Live2D window: Loading file (prod):', htmlPath, 'hash: live2d')
    live2dWindow.loadFile(htmlPath, {
      hash: 'live2d'
    })
  }

  // 页面加载完成后显示窗口
  live2dWindow.webContents.once('did-finish-load', () => {
    console.log('Live2D window page loaded')

    // 延迟显示，确保渲染完成
    setTimeout(() => {
      if (live2dWindow) {
        // 修改页面标题为空
        live2dWindow.webContents.executeJavaScript(`
          document.title = '';
        `)

        // 验证当前路由
        live2dWindow.webContents.executeJavaScript(`
          console.log('Live2D window: Current URL:', window.location.href);
          console.log('Live2D window: Current hash:', window.location.hash);
          if (window.location.hash !== '#/live2d') {
            console.log('Live2D window: Wrong route, redirecting to #/live2d');
            window.location.hash = '#/live2d';
          }
        `)

        // 不设置默认鼠标穿透，让用户可以自由交互
        console.log('Live2D window: Default mouse passthrough disabled for interaction')

        // 监听来自渲染进程的鼠标事件控制
        live2dWindow.webContents.on('set-ignore-mouse-events', (event, ignore, options) => {
          console.log('Live2D window: Set ignore mouse events:', ignore, options)
          live2dWindow.setIgnoreMouseEvents(ignore, options)
        })

        // 监听窗口拖动开始
        live2dWindow.webContents.on('live2d:startDrag', () => {
          console.log('Live2D window: Start drag requested')
          // 暂时让窗口可移动
          live2dWindow.setMovable(true)
        })

        // 只显示窗口，不获取焦点，避免抢走主窗口焦点
        live2dWindow.show()
        // 移除 focus() 调用，保持主窗口焦点
        console.log('Live2D window shown (no focus steal)')
      }
    }, 100)
  })

  // 窗口关闭事件 - 通知主窗口更新状态
  live2dWindow.on('closed', () => {
    console.log('Live2D window closed')
    // 通知主窗口桌宠已关闭
    const mainWindow = getMainWindow()
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('live2d:closed')
      // 恢复主窗口焦点
      mainWindow.focus()
    }
    live2dWindow = null
  })

  // 窗口移动时保存位置
  live2dWindow.on('moved', () => {
    if (live2dWindow) {
      const [x, y] = live2dWindow.getPosition()
      console.log('Live2D window moved to:', x, y)
    }
  })

  console.log('Live2D window created successfully')
}

// 获取 Live2D 窗口是否存在（用于 IPC）
export function getLive2DWindow(): boolean {
  return live2dWindow !== null && !live2dWindow.isDestroyed()
}

// 获取 Live2D 窗口实例（内部使用）
export function getLive2DWindowInstance(): BrowserWindow | null {
  return live2dWindow
}

// 关闭 Live2D 窗口
export function closeLive2DWindow(): void {
  console.log('[Live2D Window] ========== closeLive2DWindow 被调用 ==========')
  console.log('[Live2D Window] 窗口状态:', live2dWindow ? '存在' : '不存在')
  if (live2dWindow) {
    console.log('[Live2D Window] 窗口是否已销毁:', live2dWindow.isDestroyed())
    console.log('[Live2D Window] 窗口是否可见:', live2dWindow.isVisible())
    console.log('[Live2D Window] 开始关闭窗口...')
    live2dWindow.close()
    live2dWindow = null
    console.log('[Live2D Window] 窗口已关闭并置为 null')
  } else {
    console.log('[Live2D Window] 窗口不存在，无需关闭')
  }
}

// 显示/隐藏 Live2D 窗口
export function toggleLive2DWindow(): void {
  if (live2dWindow) {
    if (live2dWindow.isVisible()) {
      live2dWindow.hide()
    } else {
      live2dWindow.show()
    }
  }
}

// 设置 Live2D 窗口大小
export function setLive2DWindowSize(width: number, height: number): void {
  if (live2dWindow) {
    live2dWindow.setSize(width, height)
  }
}

// 获取 Live2D 窗口大小
export function getLive2DWindowSize(): { width: number; height: number } | null {
  if (live2dWindow && !live2dWindow.isDestroyed()) {
    const [width, height] = live2dWindow.getSize()
    return { width, height }
  }
  return null
}

// 设置 Live2D 窗口位置
export function setLive2DWindowPosition(x: number, y: number): void {
  if (live2dWindow) {
    live2dWindow.setPosition(x, y)
  }
}

// 设置 Live2D 窗口置顶状态
export function setLive2DWindowAlwaysOnTop(alwaysOnTop: boolean): void {
  if (live2dWindow) {
    live2dWindow.setAlwaysOnTop(alwaysOnTop)
  }
}
