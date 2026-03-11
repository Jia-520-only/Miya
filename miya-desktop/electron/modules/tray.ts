import { app, Tray, Menu, nativeImage } from 'electron'
import path from 'path'
import { fileURLToPath } from 'node:url'
import { getMainWindow, getFloatingState, exitFloatingMode } from './window'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

let tray: Tray | null = null

export function createTray(): void {
  // 创建托盘图标
  const iconPath = path.join(__dirname, '../../resources/icon.png')
  const icon = nativeImage.createFromPath(iconPath)
  tray = new Tray(icon.resize({ width: 16, height: 16 }))

  // 托盘右键菜单
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        const win = getMainWindow()
        if (win) {
          if (win.isMinimized()) win.restore()
          win.show()
          win.focus()
        }
      }
    },
    { type: 'separator' },
    {
      label: '悬浮球模式',
      type: 'checkbox',
      checked: () => getFloatingState() !== 'classic',
      click: () => {
        const state = getFloatingState()
        if (state === 'classic') {
          // 进入悬浮球模式 - 在前端实现
          getMainWindow()?.webContents.send('floating:enter')
        } else {
          exitFloatingMode()
        }
      }
    },
    { type: 'separator' },
    {
      label: '设置',
      click: () => {
        const win = getMainWindow()
        if (win) {
          win.show()
          win.webContents.send('navigate', '/settings')
        }
      }
    },
    {
      label: '关于弥娅',
      click: () => {
        const win = getMainWindow()
        if (win) {
          win.show()
          win.webContents.send('navigate', '/about')
        }
      }
    },
    { type: 'separator' },
    {
      label: '退出应用',
      click: () => {
        app.quit()
      }
    }
  ])

  tray.setToolTip('弥娅 - 数字生命伴侣')
  tray.setContextMenu(contextMenu)

  // 单击托盘显示/隐藏主窗口
  tray.on('click', () => {
    const win = getMainWindow()
    if (win?.isVisible()) {
      win.hide()
    } else {
      if (win) {
        win.show()
        win.focus()
      }
    }
  })
}

export function destroyTray(): void {
  tray?.destroy()
  tray = null
}
