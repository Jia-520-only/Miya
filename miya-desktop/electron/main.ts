import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { app, BrowserWindow, ipcMain, nativeTheme } from 'electron'
import { createWindow, getMainWindow, enterFloatingMode, exitFloatingMode } from './modules/window'
import { createTray, destroyTray } from './modules/tray'
import { createMenu } from './modules/menu'
import { registerHotkeys, unregisterHotkeys } from './modules/hotkeys'
import {
  createLive2DWindow,
  getLive2DWindow,
  getLive2DWindowInstance,
  closeLive2DWindow,
  toggleLive2DWindow,
  setLive2DWindowSize,
  getLive2DWindowSize,
  setLive2DWindowPosition,
  setLive2DWindowAlwaysOnTop
} from './modules/live2d-window'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let isQuitting = false

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
}
if (!gotTheLock) {
  app.quit()
}

app.on('second-instance', () => {
  const win = getMainWindow()
  if (win) {
    if (win.isMinimized()) win.restore()
    win.show()
    win.focus()
  }
})

// 设置用户数据目录到项目目录，避免权限问题
// 必须在 app.whenReady() 之前设置
import { existsSync, mkdirSync } from 'node:fs'
const userDataPath = join(__dirname, '../../userData')
if (!existsSync(userDataPath)) {
  mkdirSync(userDataPath, { recursive: true })
}
app.setPath('userData', userDataPath)
// 使用系统默认缓存路径，避免权限问题
// app.setPath('cache', join(userDataPath, 'cache'))
// app.setPath('userCache', join(userDataPath, 'cache'))

// 启用硬件加速以支持 WebGL（Live2D 需要）
// 必须在 app.whenReady() 之前设置
console.log('Enabling hardware acceleration for WebGL support...')
app.commandLine.appendSwitch('enable-gpu-rasterization')
app.commandLine.appendSwitch('enable-zero-copy')
// 注意：某些系统可能需要以下开关来修复 GPU 问题
// 如果遇到显示问题，可以临时添加：
// app.commandLine.appendSwitch('ignore-gpu-blacklist')
// app.commandLine.appendSwitch('use-angle', 'default')
console.log('GPU acceleration enabled successfully')

// 全局错误处理
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error)
})

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason)
})

app.whenReady().then(async () => {
  console.log('App.whenReady() called')
  try {
    // 强制暗色主题
    nativeTheme.themeSource = 'dark'
    console.log('Dark theme set')

    // 创建菜单
    createMenu()
    console.log('Menu created')

    // 创建主窗口
    const win = await createWindow()
    console.log('Window created:', win ? 'success' : 'failed')

    // 强制显示窗口（确保窗口一定显示）
    if (win) {
      win.show()
      win.focus()
      console.log('Window shown and focused')
    }

    // 创建系统托盘
    createTray()
    console.log('Tray created')

    // 注册全局快捷键
    registerHotkeys()
    console.log('Hotkeys registered')

    // --- IPC Handlers ---

    // 窗口控制
    ipcMain.on('window:minimize', () => getMainWindow()?.minimize())
    ipcMain.on('window:maximize', () => {
      const w = getMainWindow()
      if (w) {
        w.isMaximized() ? w.unmaximize() : w.maximize()
      }
    })
    ipcMain.on('window:close', () => {
      console.log('Window close IPC received')
      const win = getMainWindow()
      console.log('Main window exists:', !!win)
      if (win) {
        console.log('Window is maximized:', win.isMaximized())
        console.log('Window is full screen:', win.isFullScreen())
        console.log('Window is visible:', win.isVisible())
        // 如果窗口在全屏或最大化状态,先退出这些状态
        if (win.isFullScreen()) {
          console.log('Exiting full screen')
          win.setFullScreen(false)
        }
        if (win.isMaximized()) {
          console.log('Unmaximizing window')
          win.unmaximize()
        }
        // 设置退出标志并退出应用
        isQuitting = true
        console.log('Calling app.quit()')
        app.quit()
      } else {
        console.log('No main window, quitting directly')
        app.quit()
      }
    })

    ipcMain.handle('window:isMaximized', () => getMainWindow()?.isMaximized() ?? false)

    // 悬浮球模式控制
    ipcMain.handle('floating:enter', () => enterFloatingMode())
    ipcMain.handle('floating:exit', () => exitFloatingMode())

    // Live2D 窗口控制
    ipcMain.handle('live2d:create', () => createLive2DWindow())
    ipcMain.handle('live2d:get', () => getLive2DWindow())
    ipcMain.handle('live2d:close', () => {
      console.log('[IPC Main] ========== live2d:close 收到请求 ==========')
      return closeLive2DWindow()
    })
    ipcMain.handle('live2d:toggle', () => toggleLive2DWindow())
    ipcMain.handle('live2d:setSize', (_, width: number, height: number) => setLive2DWindowSize(width, height))
    ipcMain.handle('live2d:getSize', () => getLive2DWindowSize())
    ipcMain.handle('live2d:setPosition', (_, x: number, y: number) => setLive2DWindowPosition(x, y))
    ipcMain.handle('live2d:setAlwaysOnTop', (_, alwaysOnTop: boolean) => setLive2DWindowAlwaysOnTop(alwaysOnTop))


    // Live2D 表情控制（从主窗口发送到 Live2D 窗口）
    ipcMain.on('live2d:setExpression', (_, expressionIndex: number) => {
      const win = getLive2DWindowInstance()
      if (win && !win.isDestroyed()) {
        win.webContents.send('live2d:setExpression', expressionIndex)
      }
    })

    // Live2D 动作控制（从主窗口发送到 Live2D 窗口）
    ipcMain.on('live2d:setMotion', (_, motionIndex: number) => {
      const win = getLive2DWindowInstance()
      if (win && !win.isDestroyed()) {
        win.webContents.send('live2d:setMotion', motionIndex)
      }
    })

    // Live2D 模型切换（从主窗口发送到 Live2D 窗口）
    ipcMain.on('live2d:setModelChange', (_, modelId: string) => {
      const win = getLive2DWindowInstance()
      if (win && !win.isDestroyed()) {
        win.webContents.send('live2d:setModelChange', modelId)
      }
    })

    // 控制鼠标穿透（用于桌宠）
    ipcMain.on('set-ignore-mouse-events', (event, ignore: boolean, options: { forward?: boolean }) => {
      console.log('IPC: Set ignore mouse events:', ignore, options)
      const live2dWindow = getLive2DWindowInstance()
      if (live2dWindow && !live2dWindow.isDestroyed()) {
        live2dWindow.setIgnoreMouseEvents(ignore, options)
      }
    })

    // 控制主窗口 Live2D 显示/隐藏（避免与桌宠窗口 WebGL 冲突）
    ipcMain.on('main-live2d:hide', () => {
      console.log('[IPC] 收到隐藏主窗口 Live2D 请求')
      const mainWindow = getMainWindow()
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('main-live2d:hide')
      }
    })

    ipcMain.on('main-live2d:show', () => {
      console.log('[IPC] 收到显示主窗口 Live2D 请求')
      const mainWindow = getMainWindow()
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('main-live2d:show')
      }
    })

    // 应用退出
    ipcMain.on('app:quit', () => {
      isQuitting = true
      app.quit()
    })

    // 添加全局快捷键: Alt+F4 强制退出
    app.on('browser-window-focus', () => {
      console.log('Window focused')
    })

    // 注册全局快捷键: Ctrl+Q 或 Cmd+Q 退出应用
    app.on('ready', () => {
      const { globalShortcut } = require('electron')
      try {
        globalShortcut.register('CommandOrControl+Q', () => {
          console.log('Ctrl+Q pressed, quitting app')
          isQuitting = true
          app.quit()
        })
        globalShortcut.register('Alt+F4', () => {
          console.log('Alt+F4 pressed, quitting app')
          isQuitting = true
          app.quit()
        })
        console.log('Global shortcuts registered: Ctrl+Q, Alt+F4')
      } catch (error) {
        console.error('Failed to register global shortcuts:', error)
      }
    })

    app.on('will-quit', () => {
      const { globalShortcut } = require('electron')
      globalShortcut.unregisterAll()
    })

    // 窗口关闭事件处理
    win.on('close', () => {
      console.log('Window close event triggered, isQuitting:', isQuitting)
      console.log('Window close call stack:', new Error().stack)

      // 如果不是正在退出,尝试阻止默认行为并隐藏窗口
      if (!isQuitting) {
        console.log('Preventing default close, hiding window instead')
        // event.preventDefault()
        // win.hide()
        // 如果要退出,点击关闭按钮应该直接退出
        isQuitting = true
        console.log('Set isQuitting to true, proceeding with quit')
      } else {
        console.log('Already quitting, allowing window to close')
      }
    })

    app.on('activate', async () => {
      // 移除未使用的 event 参数
      if (BrowserWindow.getAllWindows().length === 0) {
        await createWindow()
      } else {
        getMainWindow()?.show()
      }
    })
    console.log('App initialization complete')
  } catch (error) {
    console.error('Failed to initialize app:', error)
    // 不要立即退出，给用户时间查看错误
    setTimeout(() => {
      if (!isQuitting) {
        app.quit()
      }
    }, 5000)
  }
})

app.on('before-quit', () => {
  console.log('before-quit event triggered')
  isQuitting = true
})

app.on('will-quit', () => {
  console.log('will-quit event triggered')
  unregisterHotkeys()
  destroyTray()
})

app.on('window-all-closed', () => {
  // 移除未使用的 event 参数
  console.log('All windows closed, isQuitting:', isQuitting)
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
