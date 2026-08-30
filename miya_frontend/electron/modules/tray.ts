import { join } from 'node:path'
import process from 'node:process'
import { app, Menu, nativeImage, Tray } from 'electron'
import { getMainWindow } from './window'

let tray: Tray | null = null

export function createTray(): Tray {
  const isWin = process.platform === 'win32'
  const baseDir = app.getAppPath()

  let icon: Electron.NativeImage
  try {
    const pngPath = app.isPackaged
      ? join(baseDir, 'dist', 'my.png')
      : join(baseDir, 'public', 'my.png')
    icon = nativeImage.createFromPath(pngPath)
    if (isWin) {
      icon = icon.resize({ width: 32, height: 32 })
    } else {
      icon = icon.resize({ width: 64, height: 64 }).resize({ width: 22, height: 22 })
    }
  }
  catch {
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon)
  tray.setToolTip('弥娅 AI')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示窗口',
      click: () => {
        const win = getMainWindow()
        if (win) {
          win.show()
          win.focus()
        }
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)

  // Click tray icon to show window
  tray.on('click', () => {
    const win = getMainWindow()
    if (win) {
      if (win.isVisible()) {
        win.focus()
      }
      else {
        win.show()
      }
    }
  })

  return tray
}

export function destroyTray(): void {
  if (tray) {
    tray.destroy()
    tray = null
  }
}
